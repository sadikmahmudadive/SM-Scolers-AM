"""Persistence boundaries: `PunchStore` (sync cycle) and `ServiceStore` (service loop)."""

from datetime import datetime
from typing import Protocol

from bridge.models import (
    BridgeSettings,
    DeviceInfo,
    DeviceUser,
    EnrollmentChange,
    Person,
    Schedule,
    SmsLogEntry,
    SmsSettings,
    StoredPunch,
)


class PunchStore(Protocol):
    def existing_punch_ids_since(self, min_date: str) -> set[str]:
        """Ids of the stored punches whose `date` (yyyy-MM-dd) is >= `min_date`
        (the set may also hold older ids loaded earlier). Kept in memory: the
        first call loads `date >= min_date`; a later call with an EARLIER date
        loads only the missing older range; new saves are added. Treat the
        returned set as read-only."""
        ...

    def refresh_existing_punch_ids(self) -> None:
        """Drop the in-memory id set so the next `existing_punch_ids_since`
        reloads it (called after a device reconnects)."""
        ...

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

    def pending_command_ids(self) -> list[str]:
        """Ids of commands with status "pending", oldest first (nothing claimed)."""
        ...

    def claim_command(self, command_id: str) -> dict | None:
        """Atomically mark one pending command "running" and return it (with its
        "id"). Returns None if it is no longer pending or another process won it."""
        ...

    def recover_stranded_commands(self) -> int:
        """Mark every command still "running" as "error" ("bridge restarted").
        Called once at startup; returns how many were recovered."""
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

    def punched_person_ids(self, date: str) -> set[str]:
        """Ids of everyone with at least one punch on `date` (one query)."""
        ...

    def get_time_zone(self) -> str:
        """The organisation's IANA time zone (`settings/app.timeZone`)."""
        ...

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

    def refresh_enrollment(self, device_user_ids: set[str]) -> EnrollmentChange:
        """Mirror the devices' user lists onto EXISTING people only: set
        deviceEnrolled=true where the id is in `device_user_ids` and the flag is
        not yet true, and false where it is true but the id is on no device.
        Never creates people and touches no other field; unknown ids are ignored."""
        ...
