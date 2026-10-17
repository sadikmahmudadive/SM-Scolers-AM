"""In-memory fakes for the sync-cycle boundaries."""

from datetime import datetime

from bridge.models import (
    TS_FORMAT,
    BridgeSettings,
    DeviceInfo,
    DeviceUser,
    EnrollmentChange,
    Person,
    RawPunch,
    Schedule,
    SmsLogEntry,
    SmsSettings,
    StoredPunch,
)


class InMemoryStore:
    """Implements PunchStore and ServiceStore. Saved punches are immediately visible."""

    def __init__(
        self,
        people: list[Person] | None = None,
        schedules: dict[str, tuple[str, Schedule]] | None = None,
        holidays: set[str] | None = None,
        punches: list[StoredPunch] | None = None,
        fail_save_ids: set[str] | None = None,
        fail_log: bool = False,
        *,
        bridge_settings: BridgeSettings | None = None,
        sms_settings: SmsSettings | None = None,
        devices: list[DeviceInfo] | None = None,
        commands: list[dict] | None = None,
        existing_ids_failures: int = 0,
        fail_claim_ids: set[str] | None = None,
        time_zone: str = "Asia/Dhaka",
    ) -> None:
        self.people = {p.id: p for p in people or []}
        self.schedules = schedules or {}
        self.holidays = holidays or set()
        self.punches: dict[str, StoredPunch] = {p.id: p for p in punches or []}
        self.fail_save_ids = fail_save_ids or set()
        self.fail_log = fail_log
        self.sms_log: list[SmsLogEntry] = []
        self.bridge_settings = bridge_settings or BridgeSettings()
        self.sms_settings = sms_settings or SmsSettings()
        self.devices = list(devices or [])
        self.commands = [dict(c) for c in commands or []]
        self.finished: dict[str, tuple[str, dict | None]] = {}
        self.heartbeats: list[dict] = []
        self.existing_ids_failures = existing_ids_failures
        self.existing_ids_calls = 0  # loads attempted (mirrors FirestoreStore's cache)
        self._ids_loaded = False
        self.fail_claim_ids = fail_claim_ids or set()
        self.time_zone = time_zone

    def existing_punch_ids(self) -> set[str]:
        # Like FirestoreStore: only a (re)load counts, later calls hit the cache.
        if not self._ids_loaded:
            self.existing_ids_calls += 1
            if self.existing_ids_calls <= self.existing_ids_failures:
                raise ConnectionError("store unreachable")
            self._ids_loaded = True
        return set(self.punches)

    def refresh_existing_punch_ids(self) -> None:
        self._ids_loaded = False

    def get_person(self, person_id: str) -> Person | None:
        return self.people.get(person_id)

    def get_schedule_for(self, person: Person) -> tuple[str, Schedule] | None:
        return self.schedules.get(person.id)

    def is_holiday(self, date: str) -> bool:
        return date in self.holidays

    def previous_punch_minutes_ago(self, person_id: str, ts: str) -> int | None:
        earlier = [
            p.ts
            for p in self.punches.values()
            if p.person_id == person_id and p.date == ts[:10] and p.ts < ts
        ]
        if not earlier:
            return None
        delta = datetime.strptime(ts, TS_FORMAT) - datetime.strptime(
            max(earlier), TS_FORMAT
        )
        return int(delta.total_seconds() // 60)

    def save_punch(self, punch: StoredPunch) -> None:
        if punch.id in self.fail_save_ids:
            raise RuntimeError("simulated write failure")
        self.punches[punch.id] = punch

    def log_sms(self, entry: SmsLogEntry) -> None:
        if self.fail_log:
            raise RuntimeError("simulated log failure")
        self.sms_log.append(entry)

    # -- ServiceStore ------------------------------------------------------

    def get_bridge_settings(self) -> BridgeSettings:
        return self.bridge_settings

    def get_sms_settings(self) -> SmsSettings:
        return self.sms_settings

    def list_devices(self) -> list[DeviceInfo]:
        return list(self.devices)

    def pending_command_ids(self) -> list[str]:
        return [c["id"] for c in self.commands if c.get("status") == "pending"]

    def claim_command(self, command_id: str) -> dict | None:
        if command_id in self.fail_claim_ids:
            raise ConnectionError("claim failed")
        for cmd in self.commands:
            if cmd["id"] == command_id and cmd.get("status") == "pending":
                cmd["status"] = "running"
                return dict(cmd)
        return None

    def recover_stranded_commands(self) -> int:
        recovered = 0
        for cmd in self.commands:
            if cmd.get("status") == "running":
                cmd["status"] = "error"
                cmd["result"] = {"error": "bridge restarted"}
                self.finished[cmd["id"]] = ("error", cmd["result"])
                recovered += 1
        return recovered

    def get_time_zone(self) -> str:
        return self.time_zone

    def finish_command(self, command_id: str, status: str, result: dict | None) -> None:
        self.finished[command_id] = (status, result)
        for cmd in self.commands:
            if cmd["id"] == command_id:
                cmd["status"] = status
                cmd["result"] = result

    def write_heartbeat(
        self,
        version: str,
        carrier: str,
        gsm_signal: int,
        device_online: bool,
        now: datetime,
    ) -> None:
        self.heartbeats.append(
            {
                "version": version,
                "carrier": carrier,
                "gsm_signal": gsm_signal,
                "device_online": device_online,
                "now": now,
            }
        )

    def list_active_students(self) -> list[Person]:
        return sorted(
            (p for p in self.people.values() if p.kind == "student" and p.active),
            key=lambda p: p.id,
        )

    def punched_person_ids(self, date: str) -> set[str]:
        return {p.person_id for p in self.punches.values() if p.date == date}

    def punch_counts_for(self, date: str) -> tuple[int, int]:
        todays = [p for p in self.punches.values() if p.date == date]
        return len({p.person_id for p in todays}), sum(1 for p in todays if p.late)

    def count_active_people(self) -> int:
        return sum(1 for p in self.people.values() if p.active)

    def sms_logged(self, person_id: str | None, kind: str, date: str) -> bool:
        return any(
            e.kind == kind
            and e.ts[:10] == date
            and (person_id is None or e.person_id == person_id)
            for e in self.sms_log
        )

    def upsert_device_users(self, users: list[DeviceUser]) -> int:
        created = 0
        for user in users:
            existing = self.people.get(user.user_id)
            if existing is None:
                self.people[user.user_id] = Person(
                    id=user.user_id,
                    name=user.name,
                    kind="student",
                    device_enrolled=True,
                    active=True,
                )
                created += 1
            else:
                existing.device_enrolled = True
        return created


    def refresh_enrollment(self, device_user_ids: set[str]) -> EnrollmentChange:
        enrolled, unenrolled = [], []
        for pid, person in sorted(self.people.items()):
            on_device = pid in device_user_ids
            if on_device and not person.device_enrolled:
                person.device_enrolled = True
                enrolled.append(pid)
            elif not on_device and person.device_enrolled:
                person.device_enrolled = False
                unenrolled.append(pid)
        return EnrollmentChange(tuple(enrolled), tuple(unenrolled))


class FakeZk:
    def __init__(
        self,
        punches: list[RawPunch],
        error: Exception | None = None,
        users: list[DeviceUser] | None = None,
    ) -> None:
        self.punches = punches
        self.error = error
        self.users = users or []

    def get_attendance(self) -> list[RawPunch]:
        if self.error is not None:
            raise self.error
        return list(self.punches)

    def get_users(self) -> list[DeviceUser]:
        if self.error is not None:
            raise self.error
        return list(self.users)


class FakeGateway:
    """Records every attempted (phone, body); returns False (or raises) per phone."""

    def __init__(
        self, fail_phones: set[str] | None = None, raise_phones: set[str] | None = None
    ) -> None:
        self.fail_phones = fail_phones or set()
        self.raise_phones = raise_phones or set()
        self.sent: list[tuple[str, str]] = []

    def send(self, phone: str, body: str) -> bool:
        self.sent.append((phone, body))
        if phone in self.raise_phones:
            raise TimeoutError("modem timeout")
        return phone not in self.fail_phones


class FakeGsm(FakeGateway):
    """FakeGateway plus the modem methods the website commands use."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.calls: list[tuple] = []
        self.signal = ("Grameenphone", 21)
        self.signal_error: Exception | None = None

    def signal_info(self) -> tuple[str, int]:
        if self.signal_error is not None:
            raise self.signal_error
        return self.signal

    def run_ussd_session(self, code: str) -> tuple[str, bool]:
        self.calls.append(("ussd", code))
        return (f"balance for {code}", True)

    def ussd_reply_session(self, text: str) -> tuple[str, bool]:
        self.calls.append(("ussd_reply", text))
        return (f"reply {text}", False)

    def read_inbox(self, max_messages: int = 20) -> list[dict]:
        self.calls.append(("inbox", max_messages))
        return [{"index": 1, "sender": "+880", "timestamp": "t", "body": "hi"}]

    def run_at(self, command: str, read_seconds: float = 1.0) -> str:
        self.calls.append(("at", command, read_seconds))
        return "OK"
