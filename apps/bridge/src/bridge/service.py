"""The long-running bridge service: poll devices, run commands, send scheduled SMS."""

import argparse
import logging
import os
import signal
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from bridge import __version__
from bridge.commands import process_commands
from bridge.config import load_local_config, make_firestore_client
from bridge.firestore_store import FirestoreStore
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
DEFAULT_TIME_ZONE = "Asia/Dhaka"


@dataclass
class RunResult:
    new_punches: int = 0
    sms_sent: int = 0
    devices_ok: int = 0
    devices_failed: int = 0
    commands_processed: int = 0
    absent_sms: int = 0
    summary_sms: int = 0
    errors: list[str] = field(default_factory=list)


class _TrackedZk:
    """Remembers whether the device read itself failed (vs a later store error)."""

    def __init__(self, inner: ZkSource) -> None:
        self._inner = inner
        self.read_ok = False

    def get_attendance(self) -> list[RawPunch]:
        punches = self._inner.get_attendance()
        self.read_ok = True
        return punches


class ServiceRunner:
    def __init__(
        self,
        store: ServiceStore,
        gateway_factory: Callable[[str, int], object],
        zk_factory: Callable[[DeviceInfo, BridgeSettings], ZkSource],
        *,
        version: str = __version__,
        clock: Callable[[], datetime] = datetime.now,
        scheduled_interval_sec: int = SCHEDULED_SMS_INTERVAL_SEC,
    ) -> None:
        self._store = store
        self._gateway_factory = gateway_factory
        self._zk_factory = zk_factory
        self._version = version
        self._clock = clock
        self.scheduled_interval_sec = scheduled_interval_sec
        self._gateway_key: tuple[str, int] | None = None
        self._gateway = None
        self._device_online: dict[str, bool] = {}
        self._last_scheduled: datetime | None = None
        self._poll_interval_sec = BridgeSettings().poll_interval_sec

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
        zk: _TrackedZk | None = None
        try:
            zk = _TrackedZk(self._zk_factory(device, bridge))
            cycle = run_cycle(zk, device.id, self._store, gateway, bridge, sms, now)
        except Exception as exc:
            if zk is not None and zk.read_ok:  # the terminal answered; the failure was on our side
                self._note_device(device, True)
                result.devices_ok += 1
                result.errors.append(f"{device.id}: {exc}")
                log.exception("cycle for device %s failed after reading it", device.id)
            else:
                self._note_device(device, False, str(exc))
                result.devices_failed += 1
                result.errors.append(f"{device.id}: {exc}")
            return
        self._note_device(device, True)
        result.devices_ok += 1
        result.new_punches += cycle.new_punches
        result.sms_sent += cycle.sms_sent
        result.errors.extend(cycle.errors)

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

        if (
            self._last_scheduled is None
            or (now - self._last_scheduled).total_seconds() >= self.scheduled_interval_sec
        ):
            self._last_scheduled = now
            try:
                counts = run_scheduled_sms(store, gateway, sms, now)
                result.absent_sms = counts["absent"]
                result.summary_sms = counts["summary"]
            except Exception as exc:
                log.exception("scheduled sms failed")
                result.errors.append(f"scheduled sms: {exc}")

        try:
            beat(store, gateway, self._version, result.devices_ok > 0, now)
        except Exception as exc:
            log.exception("heartbeat failed")
            result.errors.append(f"heartbeat: {exc}")
        return result

    # -- the loop ----------------------------------------------------------

    def _startup(self, stop: threading.Event) -> bool:
        """Prove the store is reachable before the first cycle. No SMS is sent
        until this succeeds; on failure retry the whole thing after a minute."""
        while not stop.is_set():
            for attempt in range(1, STARTUP_ATTEMPTS + 1):
                try:
                    count = len(self._store.existing_punch_ids())
                    log.info("startup: %d punches already stored", count)
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

    def run_forever(self, stop: threading.Event) -> None:
        if not self._startup(stop):
            return
        log.info("bridge %s running", self._version)
        while not stop.is_set():
            try:
                result = self.run_once(self._clock())
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
    try:
        doc = client.collection("settings").document("app").get()
        return (doc.to_dict() or {}).get("timeZone") or DEFAULT_TIME_ZONE
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
