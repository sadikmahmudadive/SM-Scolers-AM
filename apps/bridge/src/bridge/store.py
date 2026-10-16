"""Persistence boundaries: `PunchStore` (sync cycle) and `ServiceStore` (service loop)."""

from datetime import datetime
from typing import Protocol

from bridge.models import (
    BridgeSettings,
    DeviceInfo,
    DeviceUser,
    Person,
    Schedule,
    SmsLogEntry,
    SmsSettings,
    StoredPunch,
)


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


class ServiceStore(Protocol):
    """What the long-running service needs on top of `PunchStore`."""

    def get_bridge_settings(self) -> BridgeSettings:
        """`settings/bridge`; a missing doc or field falls back to the defaults."""
        ...

    def get_sms_settings(self) -> SmsSettings:
        """`settings/sms`; a missing doc or field falls back to the defaults."""
        ...

    def list_devices(self) -> list[DeviceInfo]: ...

    def claim_pending_commands(self) -> list[dict]:
        """Commands with status "pending", oldest first, each including its "id".
        Every returned command is marked "running" before it is returned."""
        ...

    def finish_command(
        self, command_id: str, status: str, result: dict | None
    ) -> None:
        """Set status ("done" | "error") and store `result` under `result`."""
        ...

    def write_heartbeat(
        self,
        version: str,
        carrier: str,
        gsm_signal: int,
        device_online: bool,
        now: datetime,
    ) -> None:
        """Write `bridgeStatus/main` (`now` is naive local time)."""
        ...

    def list_active_students(self) -> list[Person]: ...

    def has_punch_on(self, person_id: str, date: str) -> bool: ...

    def punch_counts_for(self, date: str) -> tuple[int, int]:
        """(distinct people with a punch on `date`, number of late punches)."""
        ...

    def count_active_people(self) -> int: ...

    def sms_logged(self, person_id: str | None, kind: str, date: str) -> bool:
        """True if an smsLog entry of `kind` (for `person_id`; None for the
        person-less "summary") exists whose local `ts` date is `date`."""
        ...

    def upsert_device_users(self, users: list[DeviceUser]) -> int:
        """Create missing people (kind "student", active, deviceEnrolled) and set
        deviceEnrolled on existing ones, touching nothing else. Returns the
        number of newly created people."""
        ...
