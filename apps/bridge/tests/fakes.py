"""In-memory fakes for the sync-cycle boundaries."""

from datetime import datetime

from bridge.models import TS_FORMAT, Person, RawPunch, Schedule, SmsLogEntry, StoredPunch


class InMemoryStore:
    """Implements PunchStore. Saved punches are immediately visible to queries."""

    def __init__(
        self,
        people: list[Person] | None = None,
        schedules: dict[str, tuple[str, Schedule]] | None = None,
        holidays: set[str] | None = None,
        punches: list[StoredPunch] | None = None,
        fail_save_ids: set[str] | None = None,
        fail_log: bool = False,
    ) -> None:
        self.people = {p.id: p for p in people or []}
        self.schedules = schedules or {}
        self.holidays = holidays or set()
        self.punches: dict[str, StoredPunch] = {p.id: p for p in punches or []}
        self.fail_save_ids = fail_save_ids or set()
        self.fail_log = fail_log
        self.sms_log: list[SmsLogEntry] = []

    def existing_punch_ids(self) -> set[str]:
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


class FakeZk:
    def __init__(self, punches: list[RawPunch], error: Exception | None = None) -> None:
        self.punches = punches
        self.error = error

    def get_attendance(self) -> list[RawPunch]:
        if self.error is not None:
            raise self.error
        return list(self.punches)


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
