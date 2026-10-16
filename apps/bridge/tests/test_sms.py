import dataclasses

from bridge.models import Person, Schedule, StoredPunch
from bridge.sms import build_sms_body

PERSON = Person(id="S1", name="Rafi", kind="student")
PUNCH = StoredPunch(
    id="S1_x", person_id="S1", ts="2026-10-12 14:05:09", date="2026-10-12",
    status="1", direction="out", device_id="d", late=False, early_leave=False,
)
SCHED = Schedule("07:45", "08:15", 5, "13:00")


def test_all_placeholders():
    body = build_sms_body(
        "{id}|{name}|{time}|{date}|{status}|{role}|{start}|{end}", PUNCH, PERSON, SCHED
    )
    assert body == "S1|Rafi|02:05 PM|12-Oct-2026|Check-Out|student|07:45|08:15"


def test_no_schedule_gives_empty_start_end():
    assert build_sms_body("[{start}][{end}]", PUNCH, PERSON, None) == "[][]"


def test_template_missing_keys_does_not_raise():
    assert build_sms_body("hi {name}", PUNCH, PERSON, None) == "hi Rafi"


def test_unknown_status_falls_back_to_raw_value():
    p = dataclasses.replace(PUNCH, status="15")
    assert build_sms_body("{status}", p, PERSON, None) == "15"
