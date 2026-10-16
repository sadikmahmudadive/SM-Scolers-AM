"""In-memory fakes for the sync-cycle boundaries."""

from datetime import datetime

from bridge.models import (
    TS_FORMAT,
    BridgeSettings,
    DeviceInfo,
    DeviceUser,
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
        self.existing_ids_calls = 0

    def existing_punch_ids(self) -> set[str]:
        self.existing_ids_calls += 1
        if self.existing_ids_calls <= self.existing_ids_failures:
            raise ConnectionError("store unreachable")
        return set(self.punches)

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

    def claim_pending_commands(self) -> list[dict]:
        claimed = []
        for cmd in self.commands:
            if cmd.get("status") == "pending":
                cmd["status"] = "running"
                claimed.append(dict(cmd))
        return claimed

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

    def has_punch_on(self, person_id: str, date: str) -> bool:
        return any(p.person_id == person_id and p.date == date for p in self.punches.values())

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
