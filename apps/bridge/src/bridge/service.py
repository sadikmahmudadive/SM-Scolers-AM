"""The long-running bridge service: poll devices, run commands, send scheduled SMS."""

import argparse
import logging
import os
import signal
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from bridge import __version__
from bridge.commands import process_commands
from bridge.config import load_local_config, make_firestore_client
from bridge.firestore_store import DEFAULT_TIME_ZONE, FirestoreStore, resolve_zone
from bridge.gsm import GsmGateway
from bridge.heartbeat import beat
from bridge.logsetup import configure_logging
from bridge.models import BridgeSettings, DeviceInfo, RawPunch
from bridge.scheduled import run_scheduled_sms
from bridge.store import ServiceStore
from bridge.sync import ZkSource, run_cycle
from bridge.zk_device import ZkDevice

log = logging.getLogger(__name__)

STARTUP_ATTEMPTS = 3
STARTUP_ATTEMPT_GAP_SEC = 3
STARTUP_RETRY_SEC = 60
# Absent/summary SMS are minute-level features; checking them every poll would
# re-read every active student each cycle, so they run at most this often.
SCHEDULED_SMS_INTERVAL_SEC = 300
# The website only needs a "bridge is alive" signal; faster polls do not need a
# faster heartbeat. A device-state change always writes one immediately.
HEARTBEAT_INTERVAL_SEC = 30
# people.deviceEnrolled (which gates absent SMS) is mirrored from the devices'
# user tables this often, and on the first clean iteration after startup.
ENROLLMENT_REFRESH_SEC = 1800
# After a failed refresh (a user-table read or the store write failed).
ENROLLMENT_RETRY_SEC = 300


def org_now(tz_name: str, utc_now: datetime | None = None) -> datetime:
    """Naive local wall-clock time in the ORGANISATION's zone (not the PC's):
    device punches, smsLog `ts` and schedules are all in that zone."""
    instant = utc_now or datetime.now(timezone.utc)
    return instant.astimezone(ZoneInfo(tz_name)).replace(tzinfo=None)


@dataclass
class RunResult:
    new_punches: int = 0
    sms_sent: int = 0
    devices_ok: int = 0
    devices_failed: int = 0
    commands_processed: int = 0
    absent_sms: int = 0
    summary_sms: int = 0
    # False if any device could not be read or a punch could not be saved: the
    # day's punches are then incomplete and absent SMS would be false alarms.
    synced_cleanly: bool = True
    errors: list[str] = field(default_factory=list)


class _TrackedZk:
    """Remembers whether the device read itself failed (vs a later store error),
    and runs `on_first_read` once a read succeeds (before the cycle uses the
    stored-id set)."""

    def __init__(
        self, inner: ZkSource, on_read: Callable[[], None] | None = None
    ) -> None:
        self._inner = inner
        self._on_read = on_read
        self.read_ok = False

    def get_attendance(self) -> list[RawPunch]:
        punches = self._inner.get_attendance()
        self.read_ok = True
        if self._on_read is not None:
            self._on_read()
        return punches


class ServiceRunner:
    def __init__(
        self,
        store: ServiceStore,
        gateway_factory: Callable[[str, int], object],
        zk_factory: Callable[[DeviceInfo, BridgeSettings], ZkSource],
        *,
        version: str = __version__,
        clock: Callable[[str], datetime] = org_now,
        monotonic: Callable[[], float] = time.monotonic,
        scheduled_interval_sec: int = SCHEDULED_SMS_INTERVAL_SEC,
        heartbeat_interval_sec: int = HEARTBEAT_INTERVAL_SEC,
        enrollment_refresh_sec: int = ENROLLMENT_REFRESH_SEC,
    ) -> None:
        self._store = store
        self._gateway_factory = gateway_factory
        self._zk_factory = zk_factory
        self._version = version
        self._clock = clock
        self._monotonic = monotonic
        self.scheduled_interval_sec = scheduled_interval_sec
        self.heartbeat_interval_sec = heartbeat_interval_sec
        self.enrollment_refresh_sec = enrollment_refresh_sec
        # Monotonic time the next enrollment refresh is due; None = at the first
        # clean iteration.
        self._next_enrollment: float | None = None
        self._gateway_key: tuple[str, int] | None = None
        self._gateway = None
        self._device_online: dict[str, bool] = {}
        self._state_changed = False
        self._last_scheduled: float | None = None
        self._last_beat: float | None = None
        self._poll_interval_sec = BridgeSettings().poll_interval_sec
        self._time_zone = DEFAULT_TIME_ZONE

    # -- helpers -----------------------------------------------------------

    def _gateway_for(self, settings: BridgeSettings):
        key = (settings.gsm_port, settings.gsm_baud)
        if self._gateway is None or key != self._gateway_key:
            self._gateway = self._gateway_factory(*key)
            self._gateway_key = key
        return self._gateway

    def _note_device(self, device: DeviceInfo, online: bool, detail: str = "") -> None:
        if self._device_online.get(device.id) is online:
            return
        self._device_online[device.id] = online
        self._state_changed = True
        if online:
            log.info("device %s (%s:%s) is online", device.id, device.ip, device.port)
        else:
            log.warning(
                "device %s (%s:%s) is offline: %s", device.id, device.ip, device.port, detail
            )

    def _sync_device(
        self,
        device: DeviceInfo,
        bridge: BridgeSettings,
        sms,
        gateway,
        now: datetime,
        result: RunResult,
    ) -> None:
        # After an offline period the stored-id set is reloaded (spec section 7),
        # but only once the device actually answers, not on every failed attempt.
        was_offline = self._device_online.get(device.id) is False
        zk: _TrackedZk | None = None
        try:
            zk = _TrackedZk(
                self._zk_factory(device, bridge),
                self._store.refresh_existing_punch_ids if was_offline else None,
            )
            cycle = run_cycle(zk, device.id, self._store, gateway, bridge, sms, now)
        except Exception as exc:
            result.synced_cleanly = False
            result.errors.append(f"{device.id}: {exc}")
            if zk is not None and zk.read_ok:  # the terminal answered; our side failed
                self._note_device(device, True)
                result.devices_ok += 1
                log.exception("cycle for device %s failed after reading it", device.id)
            else:
                self._note_device(device, False, str(exc))
                result.devices_failed += 1
            return
        self._note_device(device, True)
        result.devices_ok += 1
        result.new_punches += cycle.new_punches
        result.sms_sent += cycle.sms_sent
        result.errors.extend(cycle.errors)
        if cycle.save_failures:
            result.synced_cleanly = False

    def _refresh_enrollment(
        self, devices: list[DeviceInfo], bridge: BridgeSettings, result: RunResult
    ) -> None:
        """Mirror the union of every device's user ids onto people.deviceEnrolled
        (existing people only). Called only when every device was read cleanly
        this iteration, so a device that is down cannot un-enroll its users."""
        mono = self._monotonic()
        if self._next_enrollment is not None and mono < self._next_enrollment:
            return
        ids: set[str] = set()
        try:
            for device in devices:
                # One connection per call, like get_attendance.
                for user in self._zk_factory(device, bridge).get_users():
                    if user.user_id:
                        ids.add(user.user_id)
            if not ids:
                # A reset terminal or a glitch must not un-enroll everyone.
                log.warning("enrollment refresh: no users on any device; nothing changed")
                self._next_enrollment = mono + self.enrollment_refresh_sec
                return
            change = self._store.refresh_enrollment(ids)
        except Exception as exc:
            self._next_enrollment = mono + ENROLLMENT_RETRY_SEC
            log.warning(
                "enrollment refresh failed (%s); retrying in %ds", exc, ENROLLMENT_RETRY_SEC
            )
            result.errors.append(f"enrollment refresh: {exc}")
            return
        self._next_enrollment = mono + self.enrollment_refresh_sec
        if change.changed:
            log.info(
                "enrollment refresh: %d person(s) now enrolled, %d no longer on any device",
                len(change.enrolled),
                len(change.unenrolled),
            )

    # -- one iteration -----------------------------------------------------

    def run_once(self, now: datetime) -> RunResult:
        """One poll iteration. Store-level failures reading settings propagate
        (`run_forever` logs them and carries on); everything after that is
        isolated per stage so one failure cannot skip the heartbeat."""
        store = self._store
        bridge = store.get_bridge_settings()
        sms = store.get_sms_settings()
        devices = store.list_devices()
        self._poll_interval_sec = bridge.poll_interval_sec
        gateway = self._gateway_for(bridge)
        result = RunResult()

        for device in devices:
            self._sync_device(device, bridge, sms, gateway, now, result)

        def main_device_zk():
            if not devices:
                raise RuntimeError("No device configured")
            return self._zk_factory(devices[0], bridge)

        try:
            result.commands_processed = process_commands(
                store, gateway, main_device_zk, now
            )
        except Exception as exc:
            log.exception("command processing failed")
            result.errors.append(f"commands: {exc}")

        if devices and result.devices_failed == 0 and result.devices_ok == len(devices):
            self._refresh_enrollment(devices, bridge, result)

        mono = self._monotonic()
        if self._last_scheduled is None or mono - self._last_scheduled >= self.scheduled_interval_sec:
            # Absent SMS need a complete picture of today's punches: only when
            # every device was read and every punch saved this iteration. A dirty
            # iteration does not consume the throttle slot, so it retries next cycle.
            clean = bool(devices) and result.synced_cleanly
            if clean:
                self._last_scheduled = mono
            try:
                counts = run_scheduled_sms(
                    store,
                    gateway,
                    sms,
                    now,
                    bridge.stale_sms_window_min,
                    allow_absent=clean,
                )
                result.absent_sms = counts["absent"]
                result.summary_sms = counts["summary"]
            except Exception as exc:
                log.exception("scheduled sms failed")
                result.errors.append(f"scheduled sms: {exc}")

        mono = self._monotonic()
        if (
            self._state_changed
            or self._last_beat is None
            or mono - self._last_beat >= self.heartbeat_interval_sec
        ):
            try:
                beat(store, gateway, self._version, result.devices_ok > 0, now)
                self._last_beat = mono
                self._state_changed = False
            except Exception as exc:
                log.exception("heartbeat failed")
                result.errors.append(f"heartbeat: {exc}")
        return result

    # -- the loop ----------------------------------------------------------

    def _now(self) -> datetime:
        """Organisation-local now; the zone is re-read from settings each call."""
        try:
            self._time_zone = self._store.get_time_zone()
        except Exception as exc:
            log.warning("could not read time zone (%s); using %s", exc, self._time_zone)
        return self._clock(self._time_zone)

    def _startup(self, stop: threading.Event) -> bool:
        """Prove the store is reachable (and load the stored-punch ids) before the
        first cycle. No SMS is sent until this succeeds; on failure retry the
        whole thing after a minute."""
        while not stop.is_set():
            for attempt in range(1, STARTUP_ATTEMPTS + 1):
                try:
                    count = len(self._store.existing_punch_ids())
                    log.info("startup: %d punches already stored", count)
                    self._recover_commands()
                    return True
                except Exception as exc:
                    log.warning(
                        "startup: loading stored punches failed (%d/%d): %s",
                        attempt,
                        STARTUP_ATTEMPTS,
                        exc,
                    )
                    if attempt < STARTUP_ATTEMPTS and stop.wait(STARTUP_ATTEMPT_GAP_SEC):
                        return False
            log.error(
                "startup: store unreachable; no SMS will be sent. Retrying in %ds",
                STARTUP_RETRY_SEC,
            )
            if stop.wait(STARTUP_RETRY_SEC):
                return False
        return False

    def _recover_commands(self) -> None:
        """Commands left "running" by a previous process will never finish."""
        try:
            recovered = self._store.recover_stranded_commands()
            if recovered:
                log.warning("startup: marked %d stranded command(s) as error", recovered)
        except Exception:
            log.exception("startup: could not recover stranded commands")

    def run_forever(self, stop: threading.Event) -> None:
        if not self._startup(stop):
            return
        log.info("bridge %s running", self._version)
        while not stop.is_set():
            try:
                result = self.run_once(self._now())
                if result.new_punches or result.commands_processed or result.errors:
                    log.info(
                        "cycle: %d new punches, %d sms, %d commands, %d errors",
                        result.new_punches,
                        result.sms_sent,
                        result.commands_processed,
                        len(result.errors),
                    )
            except Exception:
                log.exception("iteration failed; continuing")
            if stop.wait(self._poll_interval_sec):
                break
        log.info("bridge stopped")


# -- process entry point ---------------------------------------------------


def default_config_path() -> Path:
    base = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
    return Path(base) / "SMScolersBridge" / "config.json"


def _load_time_zone(client) -> str:
    """The org zone from settings/app; an unknown name (e.g. "+06:00") is logged and
    replaced by the default instead of stopping the service."""
    try:
        doc = client.collection("settings").document("app").get()
        name = ((doc.to_dict() or {}) if doc.exists else {}).get("timeZone")
        return resolve_zone(name).key
    except Exception as exc:
        log.warning("could not read settings/app time zone (%s); using %s", exc, DEFAULT_TIME_ZONE)
        return DEFAULT_TIME_ZONE


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="SM Scolers attendance bridge")
    parser.add_argument(
        "--config",
        type=Path,
        default=default_config_path(),
        help="path to config.json (default: %%ProgramData%%\\SMScolersBridge\\config.json)",
    )
    args = parser.parse_args(argv)

    log_path = configure_logging(args.config)
    log.info("starting bridge %s (config %s, log %s)", __version__, args.config, log_path)

    config = load_local_config(args.config)
    client = make_firestore_client(config)
    store = FirestoreStore(client, _load_time_zone(client))
    runner = ServiceRunner(
        store,
        gateway_factory=lambda port, baud: GsmGateway(port, baud),
        zk_factory=lambda device, settings: ZkDevice(
            device.ip, device.port, settings.zk_timeout_sec
        ),
    )

    stop = threading.Event()

    def request_stop(signum, _frame) -> None:
        log.info("signal %s received; stopping", signum)
        stop.set()

    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), request_stop)

    runner.run_forever(stop)


if __name__ == "__main__":
    main()
