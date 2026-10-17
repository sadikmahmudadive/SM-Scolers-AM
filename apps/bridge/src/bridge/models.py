"""Plain data types shared across the bridge."""

from dataclasses import dataclass, field


# Device / smsLog timestamp format (naive local time).
TS_FORMAT = "%Y-%m-%d %H:%M:%S"


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


@dataclass(frozen=True)
class BridgeSettings:
    """Mirrors the shared BridgeSettingsSchema (snake_case)."""

    poll_interval_sec: int = 10
    zk_timeout_sec: int = 5
    gsm_port: str = ""
    gsm_baud: int = 9600
    stale_sms_window_min: int = 30
    ussd_code: str = ""


DEFAULT_NORMAL_TEMPLATE = "Attendance: {name} ({id}) at {time}"
DEFAULT_LATE_TEMPLATE = (
    "LATE: {name} ({id}) punched at {time}. Expected in-time: {start} - {end}"
)
DEFAULT_EARLY_LEAVE_TEMPLATE = (
    "EARLY LEAVE: {name} ({id}) left at {time}. Expected dismissal: {end}"
)
DEFAULT_ABSENT_TEMPLATE = "Absent: {name} ({id}) was not present on {date}."
DEFAULT_SUMMARY_TEMPLATE = (
    "Summary {date}: Present {present}, Absent {absent}, Late {late}, Total {total}"
)


@dataclass(frozen=True)
class SmsSettings:
    """Mirrors the shared SmsSettingsSchema (snake_case)."""

    normal_template: str = DEFAULT_NORMAL_TEMPLATE
    late_template: str = DEFAULT_LATE_TEMPLATE
    early_leave_template: str = DEFAULT_EARLY_LEAVE_TEMPLATE
    sms_enabled: bool = True
    early_leave_enabled: bool = False
    absent_enabled: bool = False
    summary_enabled: bool = False
    summary_time: str = ""
    absent_template: str = DEFAULT_ABSENT_TEMPLATE
    summary_template: str = DEFAULT_SUMMARY_TEMPLATE
    admin_phones: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DeviceInfo:
    """A `devices` document: where to reach one attendance terminal."""

    id: str
    name: str
    ip: str
    port: int


@dataclass(frozen=True)
class DeviceUser:
    """A user enrolled on the terminal."""

    user_id: str
    name: str


@dataclass(frozen=True)
class StoredPunch:
    """An attendance document. `ts`/`date` are local, device-formatted strings."""

    id: str
    person_id: str
    ts: str  # "YYYY-MM-DD HH:MM:SS"
    date: str  # "YYYY-MM-DD"
    status: str
    direction: str  # "in" | "out"
    device_id: str
    late: bool
    early_leave: bool
    schedule_id: str | None = None


@dataclass(frozen=True)
class SmsLogEntry:
    person_id: str
    phone: str
    body: str
    kind: str  # normal | late | early | absent | summary | test
    status: str  # sent | failed | skipped-stale
    punch_id: str | None
    ts: str


@dataclass(frozen=True)
class EnrollmentChange:
    """What `refresh_enrollment` changed: ids set to deviceEnrolled=true / false."""

    enrolled: tuple[str, ...] = ()
    unenrolled: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.enrolled or self.unenrolled)


@dataclass
class CycleResult:
    new_punches: int = 0
    sms_sent: int = 0
    sms_skipped_stale: int = 0
    save_failures: int = 0
    errors: list[str] = field(default_factory=list)
