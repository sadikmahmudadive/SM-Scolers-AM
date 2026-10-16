"""SMS gateway boundary and message body construction."""

from datetime import datetime
from typing import Protocol

from bridge.models import Person, Schedule, StoredPunch

# Ported from legacy/app.py.
PUNCH_STATUS_MAP = {
    "0": "Check-In",
    "1": "Check-Out",
    "2": "Break-Out",
    "3": "Break-In",
    "4": "OT-In",
    "5": "OT-Out",
}


class SmsGateway(Protocol):
    def send(self, phone: str, body: str) -> bool: ...


def build_sms_body(
    template: str,
    punch: StoredPunch,
    person: Person,
    schedule: Schedule | None,
) -> str:
    """Fill `{id} {name} {time} {date} {status} {role} {start} {end}`.

    Every key is always supplied so a template using any subset never raises.
    """
    try:
        dt = datetime.strptime(punch.ts, "%Y-%m-%d %H:%M:%S")
        time_only = dt.strftime("%I:%M %p")
        date_only = dt.strftime("%d-%b-%Y")
    except ValueError:
        time_only = punch.ts
        date_only = ""
    values = {
        "id": person.id,
        "name": person.name,
        "time": time_only,
        "date": date_only,
        "status": PUNCH_STATUS_MAP.get(punch.status, punch.status),
        "role": person.kind,
        "start": schedule.start if schedule else "",
        "end": schedule.end if schedule else "",
    }
    return template.format_map(values)
