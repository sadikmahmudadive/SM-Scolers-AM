"""Plain data types shared across the bridge."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Schedule:
    """Arrival window and optional dismissal, all "HH:mm"."""

    start: str
    end: str
    grace_min: int
    dismissal: str | None = None


@dataclass(frozen=True)
class PunchFlags:
    late: bool
    early_leave: bool
    duplicate: bool


@dataclass(frozen=True)
class RawPunch:
    """A punch as read from the device (timestamp is local, device-formatted)."""

    user_id: str
    timestamp: str
    status: str


@dataclass
class Person:
    """Mirrors the shared PersonSchema (snake_case)."""

    id: str
    name: str
    kind: str  # "staff" | "teacher" | "student"
    phone: str = ""
    father_phone: str = ""
    mother_phone: str = ""
    class_name: str = ""
    section: str = ""
    department_id: str | None = None
    manager_id: str | None = None
    guardian_uids: list[str] = field(default_factory=list)
    device_enrolled: bool = False
    active: bool = True
