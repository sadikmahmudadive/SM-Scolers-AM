"""FirestoreStore against the Firestore emulator (skipped when it is not running)."""

import os
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

EMULATOR = os.environ.get("FIRESTORE_EMULATOR_HOST")
pytestmark = pytest.mark.skipif(not EMULATOR, reason="FIRESTORE_EMULATOR_HOST not set")

PROJECT = "demo-hrm"
DHAKA = ZoneInfo("Asia/Dhaka")


@pytest.fixture
def client():
    from google.auth.credentials import AnonymousCredentials
    from google.cloud import firestore

    c = firestore.Client(project=PROJECT, credentials=AnonymousCredentials())
    req = urllib.request.Request(
        f"http://{EMULATOR}/emulator/v1/projects/{PROJECT}/databases/(default)/documents",
        method="DELETE",
    )
    urllib.request.urlopen(req).read()
    yield c
    c.close()


@pytest.fixture
def store(client):
    from bridge.firestore_store import FirestoreStore

    return FirestoreStore(client, "Asia/Dhaka")


def punch(pid="12", ts="2026-10-16 08:21:21", **kw):
    from bridge.models import StoredPunch
    from bridge.punch_id import punch_id as make_id

    base = dict(
        id=make_id(pid, ts),
        person_id=pid,
        ts=ts,
        date=ts[:10],
        status="0",
        direction="in",
        device_id="dev1",
        late=False,
        early_leave=False,
    )
    base.update(kw)
    return StoredPunch(**base)


def test_save_punch_writes_document_per_spec(store, client):
    store.save_punch(punch(late=True, schedule_id="sch1"))
    doc = client.collection("attendance").document("12_20261016082121").get()
    assert doc.exists
    d = doc.to_dict()
    assert d["personId"] == "12"
    assert d["date"] == "2026-10-16"
    assert d["status"] == "0"
    assert d["direction"] == "in"
    assert d["deviceId"] == "dev1"
    assert d["late"] is True
    assert d["earlyLeave"] is False
    assert d["scheduleId"] == "sch1"
    assert d["ts"].tzinfo is not None
    assert d["ts"] == datetime(2026, 10, 16, 8, 21, 21, tzinfo=DHAKA)
    assert d["ts"].astimezone(DHAKA).hour == 8


def test_save_punch_omits_schedule_id_when_none(store, client):
    store.save_punch(punch())
    d = client.collection("attendance").document("12_20261016082121").get().to_dict()
    assert "scheduleId" not in d


def test_save_punch_is_idempotent(store, client):
    store.save_punch(punch())
    store.save_punch(punch())
    assert len(list(client.collection("attendance").stream())) == 1


def test_existing_punch_ids(store):
    assert store.existing_punch_ids() == set()
    store.save_punch(punch())
    store.save_punch(punch(ts="2026-10-16 09:00:00"))
    assert store.existing_punch_ids() == {"12_20261016082121", "12_20261016090000"}


def test_previous_punch_minutes_ago_same_day(store):
    store.save_punch(punch(ts="2026-10-16 08:00:00"))
    store.save_punch(punch(ts="2026-10-16 08:20:00"))
    # latest earlier is 08:20 -> 10 minutes (and 59s rounds down)
    assert store.previous_punch_minutes_ago("12", "2026-10-16 08:30:59") == 10


def test_previous_punch_minutes_ago_first_punch_is_none(store):
    assert store.previous_punch_minutes_ago("12", "2026-10-16 08:00:00") is None


def test_previous_punch_minutes_ago_ignores_other_people_and_later_punches(store):
    store.save_punch(punch(pid="13", ts="2026-10-16 08:25:00"))
    store.save_punch(punch(pid="12", ts="2026-10-16 09:00:00"))
    assert store.previous_punch_minutes_ago("12", "2026-10-16 08:30:00") is None


def test_previous_punch_minutes_ago_none_when_only_previous_date(store):
    store.save_punch(punch(ts="2026-10-15 23:58:00"))
    assert store.previous_punch_minutes_ago("12", "2026-10-16 00:02:00") is None


def test_get_person_maps_camel_case(store, client):
    client.collection("people").document("12").set(
        {
            "name": "Rahim",
            "kind": "student",
            "phone": "017",
            "fatherPhone": "018",
            "motherPhone": "019",
            "className": "Six",
            "section": "A",
            "departmentId": "dep1",
            "managerId": "m1",
            "guardianUids": ["g1", "g2"],
            "deviceEnrolled": True,
            "active": False,
        }
    )
    p = store.get_person("12")
    assert p is not None
    assert (p.id, p.name, p.kind, p.phone) == ("12", "Rahim", "student", "017")
    assert (p.father_phone, p.mother_phone) == ("018", "019")
    assert (p.class_name, p.section) == ("Six", "A")
    assert (p.department_id, p.manager_id) == ("dep1", "m1")
    assert p.guardian_uids == ["g1", "g2"]
    assert p.device_enrolled is True
    assert p.active is False


def test_get_person_defaults_for_missing_optional_fields(store, client):
    client.collection("people").document("7").set({"name": "Karim", "kind": "staff"})
    p = store.get_person("7")
    assert p is not None
    assert p.phone == "" and p.father_phone == "" and p.mother_phone == ""
    assert p.class_name == "" and p.section == ""
    assert p.department_id is None and p.manager_id is None
    assert p.guardian_uids == []
    assert p.device_enrolled is False
    assert p.active is True


def test_get_person_missing_returns_none(store):
    assert store.get_person("nope") is None


def test_get_schedule_for_class(store, client):
    from bridge.models import Schedule

    client.collection("schedules").document("b").set(
        {"name": "B", "start": "09:00", "end": "09:30", "graceMin": 5, "appliesTo": ["Six"]}
    )
    client.collection("schedules").document("a").set(
        {
            "name": "A",
            "start": "08:00",
            "end": "08:30",
            "graceMin": 10,
            "dismissal": "15:00",
            "appliesTo": ["Six", "Seven"],
        }
    )
    client.collection("schedules").document("c").set(
        {"name": "C", "start": "10:00", "end": "10:30", "graceMin": 0, "appliesTo": ["Eight"]}
    )
    from bridge.models import Person

    person = Person(id="12", name="Rahim", kind="student", class_name="Six")
    # lowest doc id wins
    assert store.get_schedule_for(person) == ("a", Schedule("08:00", "08:30", 10, "15:00"))


def test_get_schedule_for_department_when_no_class(store, client):
    from bridge.models import Person, Schedule

    client.collection("schedules").document("s1").set(
        {"name": "S", "start": "08:00", "end": "08:30", "graceMin": 5, "appliesTo": ["dep1"]}
    )
    person = Person(id="9", name="T", kind="teacher", department_id="dep1")
    assert store.get_schedule_for(person) == ("s1", Schedule("08:00", "08:30", 5, None))


def test_get_schedule_for_none_when_nothing_applies(store, client):
    from bridge.models import Person

    client.collection("schedules").document("s1").set(
        {"name": "S", "start": "08:00", "end": "08:30", "graceMin": 5, "appliesTo": ["Eight"]}
    )
    assert store.get_schedule_for(Person(id="1", name="x", kind="student", class_name="Six")) is None
    assert store.get_schedule_for(Person(id="2", name="y", kind="staff")) is None


def test_is_holiday(store, client):
    client.collection("holidays").document("2026-10-20").set({"name": "Holiday"})
    assert store.is_holiday("2026-10-20") is True
    assert store.is_holiday("2026-10-21") is False


def test_log_sms_writes_expected_fields(store, client):
    from bridge.models import SmsLogEntry

    store.log_sms(
        SmsLogEntry(
            person_id="12",
            phone="017",
            body="hi",
            kind="late",
            status="sent",
            punch_id="12_20261016082121",
            ts="2026-10-16 08:21:30",
        )
    )
    store.log_sms(
        SmsLogEntry("12", "017", "hi2", "normal", "failed", None, "2026-10-16 08:22:00")
    )
    docs = {d.to_dict()["body"]: d.to_dict() for d in client.collection("smsLog").stream()}
    first = docs["hi"]
    assert first["personId"] == "12" and first["phone"] == "017"
    assert first["kind"] == "late" and first["status"] == "sent"
    assert first["punchId"] == "12_20261016082121"
    assert first["ts"] == datetime(2026, 10, 16, 8, 21, 30, tzinfo=DHAKA)
    assert "punchId" not in docs["hi2"]


def test_get_schedule_for_null_grace_min_defaults_to_zero(store, client):
    from bridge.models import Person, Schedule

    client.collection("schedules").document("s1").set(
        {"name": "S", "start": "08:00", "end": "08:30", "graceMin": None, "appliesTo": ["Six"]}
    )
    person = Person(id="1", name="x", kind="student", class_name="Six")
    assert store.get_schedule_for(person) == ("s1", Schedule("08:00", "08:30", 0, None))
