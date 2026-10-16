"""Persistence boundary for the sync cycle (the real adapter arrives later)."""

from typing import Protocol

from bridge.models import Person, Schedule, SmsLogEntry, StoredPunch


class PunchStore(Protocol):
    def existing_punch_ids(self) -> set[str]: ...

    def get_person(self, person_id: str) -> Person | None: ...

    def get_schedule_for(self, person: Person) -> tuple[str, Schedule] | None:
        """The (schedule id, schedule) that applies to this person, if any."""
        ...

    def is_holiday(self, date: str) -> bool: ...

    def previous_punch_minutes_ago(self, person_id: str, ts: str) -> int | None:
        """Whole minutes between the latest EARLIER punch of this person on the
        same date and `ts`; None if there is none. Must see punches saved
        earlier in the same cycle."""
        ...

    def save_punch(self, punch: StoredPunch) -> None: ...

    def log_sms(self, entry: SmsLogEntry) -> None: ...
