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
    assert store.existing_punch_ids_since("2026-10-16") == set()
    store.save_punch(punch())
    store.save_punch(punch(ts="2026-10-16 09:00:00"))
    assert store.existing_punch_ids_since("2026-10-16") == {
        "12_20261016082121",
        "12_20261016090000",
    }


def test_existing_punch_ids_loaded_once_then_kept_in_memory(store, client):
    store.save_punch(punch())
    assert store.existing_punch_ids_since("2026-10-16") == {"12_20261016082121"}
    # a write by someone else is not seen until an explicit refresh
    client.collection("attendance").document("77_20261016090000").set(
        {"personId": "77", "date": "2026-10-16"}
    )
    assert store.existing_punch_ids_since("2026-10-16") == {"12_20261016082121"}
    # but this store's own saves are added without re-reading the collection
    store.save_punch(punch(ts="2026-10-16 09:30:00"))
    assert "12_20261016093000" in store.existing_punch_ids_since("2026-10-16")
    store.refresh_existing_punch_ids()
    assert store.existing_punch_ids_since("2026-10-16") == {
        "12_20261016082121",
        "77_20261016090000",
        "12_20261016093000",
    }


def test_existing_punch_ids_since_loads_only_the_requested_range(store, client):
    store.save_punch(punch(ts="2026-09-01 08:00:00"))
    store.save_punch(punch(ts="2026-10-10 08:00:00"))
    store.save_punch(punch(ts="2026-10-16 08:00:00"))
    store.refresh_existing_punch_ids()  # start from an empty cache
    assert store.existing_punch_ids_since("2026-10-15") == {"12_20261016080000"}
    # a later date is inside the loaded range: no new query, same set
    assert store.existing_punch_ids_since("2026-10-16") == {"12_20261016080000"}
    # an earlier date loads only the older range [2026-10-01, 2026-10-15)
    client.collection("attendance").document("77_20261016090000").set(
        {"personId": "77", "date": "2026-10-16"}
    )
    ids = store.existing_punch_ids_since("2026-10-01")
    assert ids == {"12_20261010080000", "12_20261016080000"}  # 77 (newer range) not re-read
    assert store._ids_from == "2026-10-01"


def test_existing_punch_ids_since_queries_firestore_once_per_new_range(store, monkeypatch):
    calls = []
    real = store._punch_ids_between
    monkeypatch.setattr(
        store, "_punch_ids_between", lambda lo, hi: calls.append((lo, hi)) or real(lo, hi)
    )
    store.existing_punch_ids_since("2026-10-16")
    store.existing_punch_ids_since("2026-10-16")
    store.existing_punch_ids_since("2026-10-20")
    store.existing_punch_ids_since("2026-10-05")
    store.existing_punch_ids_since("2026-10-05")
    assert calls == [("2026-10-16", None), ("2026-10-05", "2026-10-16")]
    store.refresh_existing_punch_ids()
    store.existing_punch_ids_since("2026-10-12")
    assert calls[-1] == ("2026-10-12", None)


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


# -- ServiceStore -----------------------------------------------------------


def test_get_settings_defaults_when_docs_missing(store):
    from bridge.models import BridgeSettings, SmsSettings

    assert store.get_bridge_settings() == BridgeSettings()
    assert store.get_sms_settings() == SmsSettings()


def test_get_bridge_settings_maps_camel_case_and_fills_missing(store, client):
    client.collection("settings").document("bridge").set(
        {"pollIntervalSec": 3, "gsmPort": "COM7", "gsmBaud": 115200, "ussdCode": "*222#"}
    )
    s = store.get_bridge_settings()
    assert (s.poll_interval_sec, s.gsm_port, s.gsm_baud, s.ussd_code) == (3, "COM7", 115200, "*222#")
    assert s.zk_timeout_sec == 5 and s.stale_sms_window_min == 30  # defaults


def test_get_sms_settings_maps_camel_case_and_fills_missing(store, client):
    client.collection("settings").document("sms").set(
        {
            "smsEnabled": False,
            "absentEnabled": True,
            "summaryEnabled": True,
            "summaryTime": "17:30",
            "absentTemplate": "{name} absent",
            "adminPhones": ["017", "018"],
            "lateTemplate": None,
        }
    )
    s = store.get_sms_settings()
    assert s.sms_enabled is False and s.absent_enabled is True and s.summary_enabled is True
    assert s.summary_time == "17:30"
    assert s.absent_template == "{name} absent"
    assert s.admin_phones == ["017", "018"]
    assert s.early_leave_enabled is False
    assert "LATE" in s.late_template  # null falls back to the default
    assert "Summary" in s.summary_template


def test_list_devices(store, client):
    from bridge.models import DeviceInfo

    client.collection("devices").document("b").set({"name": "Back", "ip": "10.0.0.2", "port": 4371})
    client.collection("devices").document("a").set({"name": "Gate", "ip": "10.0.0.1", "port": 4370})
    client.collection("devices").document("x").set({"name": "No IP"})
    assert store.list_devices() == [
        DeviceInfo("a", "Gate", "10.0.0.1", 4370),
        DeviceInfo("b", "Back", "10.0.0.2", 4371),
    ]


def _commands(client):
    col = client.collection("commands")
    col.document("new").set(
        {"type": "ussd", "payload": {"code": "*1#"}, "status": "pending",
         "createdAt": datetime(2026, 10, 16, 9, 5, tzinfo=DHAKA)}
    )
    col.document("old").set(
        {"type": "test_sms", "payload": {"phone": "1", "message": "m"}, "status": "pending",
         "createdAt": datetime(2026, 10, 16, 9, 0, tzinfo=DHAKA)}
    )
    col.document("nodate").set({"type": "read_inbox", "payload": {}, "status": "pending"})
    col.document("done").set({"type": "ussd", "payload": {}, "status": "done"})
    col.document("running").set({"type": "ussd", "payload": {}, "status": "running"})
    return col


def test_pending_command_ids_oldest_first_without_claiming(store, client):
    col = _commands(client)
    assert store.pending_command_ids() == ["nodate", "old", "new"]
    assert col.document("old").get().to_dict()["status"] == "pending"


def test_claim_command_marks_running_and_returns_the_command(store, client):
    col = _commands(client)
    claimed = store.claim_command("old")
    assert claimed["id"] == "old" and claimed["type"] == "test_sms"
    assert claimed["payload"] == {"phone": "1", "message": "m"} and claimed["status"] == "running"
    assert col.document("old").get().to_dict()["status"] == "running"
    assert store.claim_command("old") is None  # already running
    assert store.claim_command("done") is None
    assert store.claim_command("missing") is None
    assert col.document("new").get().to_dict()["status"] == "pending"  # untouched


def test_claim_command_loses_when_the_document_changed_since_it_was_read(
    store, client, monkeypatch
):
    col = _commands(client)
    real = client.write_option

    def racing(**kwargs):
        # another bridge process claims the command between our read and write
        col.document("old").update({"touched": True})
        return real(**kwargs)

    monkeypatch.setattr(client, "write_option", racing)
    assert store.claim_command("old") is None
    assert col.document("old").get().to_dict()["status"] == "pending"


def test_recover_stranded_commands_marks_running_as_error(store, client):
    col = _commands(client)
    assert store.recover_stranded_commands() == 1
    d = col.document("running").get().to_dict()
    assert d["status"] == "error" and d["result"] == {"error": "bridge restarted"}
    assert col.document("new").get().to_dict()["status"] == "pending"
    assert store.recover_stranded_commands() == 0


def test_finish_command_stores_status_and_result(store, client):
    col = client.collection("commands")
    col.document("c1").set({"type": "ussd", "payload": {}, "status": "running"})
    col.document("c2").set({"type": "ussd", "payload": {}, "status": "running"})
    store.finish_command("c1", "done", {"text": "ok", "sessionActive": False})
    store.finish_command("c2", "error", {"error": "boom"})
    d1, d2 = (col.document(i).get().to_dict() for i in ("c1", "c2"))
    assert d1["status"] == "done" and d1["result"] == {"text": "ok", "sessionActive": False}
    assert d2["status"] == "error" and d2["result"] == {"error": "boom"}
    assert d1["type"] == "ussd"  # merged, not replaced


def test_write_heartbeat(store, client):
    store.write_heartbeat("0.1.0", "Grameenphone", 21, True, datetime(2026, 10, 16, 9, 0, 5))
    d = client.collection("bridgeStatus").document("main").get().to_dict()
    assert d["version"] == "0.1.0" and d["carrier"] == "Grameenphone"
    assert d["gsmSignal"] == 21 and d["deviceOnline"] is True
    assert d["heartbeat"] == datetime(2026, 10, 16, 9, 0, 5, tzinfo=DHAKA)
    store.write_heartbeat("0.1.0", "", 0, False, datetime(2026, 10, 16, 9, 0, 15))
    d = client.collection("bridgeStatus").document("main").get().to_dict()
    assert d["deviceOnline"] is False and d["gsmSignal"] == 0


def _add_person(client, pid, **fields):
    base = {"name": f"P{pid}", "kind": "student", "active": True, "deviceEnrolled": False}
    base.update(fields)
    client.collection("people").document(pid).set(base)


def test_list_active_students_and_count_active_people(store, client):
    _add_person(client, "1")
    _add_person(client, "2", active=False)
    _add_person(client, "3", kind="teacher")
    _add_person(client, "4")
    assert [p.id for p in store.list_active_students()] == ["1", "4"]
    assert store.count_active_people() == 3


def test_punched_person_ids_and_counts(store):
    store.save_punch(punch(pid="1", ts="2026-10-16 08:00:00", late=True))
    store.save_punch(punch(pid="1", ts="2026-10-16 15:00:00"))
    store.save_punch(punch(pid="2", ts="2026-10-16 08:10:00"))
    store.save_punch(punch(pid="3", ts="2026-10-15 08:10:00", late=True))
    assert store.punched_person_ids("2026-10-16") == {"1", "2"}
    assert store.punched_person_ids("2026-10-17") == set()
    assert store.punch_counts_for("2026-10-16") == (2, 1)
    assert store.punch_counts_for("2026-10-17") == (0, 0)


def test_get_time_zone_reads_settings_and_applies_it(store, client):
    assert store.get_time_zone() == "Asia/Dhaka"  # no settings doc: keep current
    client.collection("settings").document("app").set({"timeZone": "America/New_York"})
    assert store.get_time_zone() == "America/New_York"
    store.write_heartbeat("v", "", 0, True, datetime(2026, 10, 16, 9, 0, 0))
    d = client.collection("bridgeStatus").document("main").get().to_dict()
    assert d["heartbeat"].astimezone(ZoneInfo("UTC")).hour == 13  # 09:00 EDT
    client.collection("settings").document("app").set({"timeZone": "Not/AZone"})
    assert store.get_time_zone() == "America/New_York"  # invalid zone ignored


def test_sms_logged_per_person_kind_and_local_date(store):
    from bridge.models import SmsLogEntry

    store.log_sms(SmsLogEntry("1", "017", "b", "absent", "sent", None, "2026-10-16 09:30:00"))
    store.log_sms(SmsLogEntry("2", "018", "b", "absent", "failed", None, "2026-10-16 00:00:30"))
    store.log_sms(SmsLogEntry("3", "019", "b", "late", "sent", "p", "2026-10-16 09:31:00"))
    assert store.sms_logged("1", "absent", "2026-10-16") is True
    assert store.sms_logged("1", "absent", "2026-10-17") is False
    assert store.sms_logged("1", "late", "2026-10-16") is False
    assert store.sms_logged("3", "absent", "2026-10-16") is False
    # 00:00:30 Dhaka is still the 16th locally (it is the 15th in UTC)
    assert store.sms_logged("2", "absent", "2026-10-16") is True
    assert store.sms_logged("2", "absent", "2026-10-15") is False


def test_log_sms_writes_org_local_date_field(store, client):
    from bridge.models import SmsLogEntry

    store.log_sms(SmsLogEntry("2", "018", "b", "absent", "sent", None, "2026-10-16 00:00:30"))
    (doc,) = client.collection("smsLog").stream()
    assert doc.to_dict()["date"] == "2026-10-16"  # UTC would say the 15th


def test_sms_logged_summary_has_no_person(store):
    from bridge.models import SmsLogEntry

    assert store.sms_logged(None, "summary", "2026-10-16") is False
    store.log_sms(SmsLogEntry("", "0199", "b", "summary", "sent", None, "2026-10-16 17:00:00"))
    assert store.sms_logged(None, "summary", "2026-10-16") is True
    assert store.sms_logged(None, "summary", "2026-10-17") is False


def test_sms_logged_reads_through_for_entries_written_elsewhere(store, client):
    assert store.sms_logged("1", "absent", "2026-10-16") is False
    client.collection("smsLog").add(
        {"personId": "1", "phone": "1", "body": "b", "kind": "absent", "status": "sent",
         "ts": datetime(2026, 10, 16, 9, 30, tzinfo=DHAKA), "date": "2026-10-16"}
    )
    assert store.sms_logged("1", "absent", "2026-10-16") is True


def test_upsert_device_users_creates_and_marks(store, client):
    from bridge.models import DeviceUser

    _add_person(client, "12", name="Old", kind="staff", phone="017", active=False)
    created = store.upsert_device_users(
        [DeviceUser("12", "Device Name"), DeviceUser("13", "Karim"), DeviceUser("13", "Dup")]
    )
    assert created == 1
    existing = client.collection("people").document("12").get().to_dict()
    assert existing["deviceEnrolled"] is True
    assert (existing["name"], existing["kind"], existing["phone"], existing["active"]) == (
        "Old", "staff", "017", False,
    )
    new = client.collection("people").document("13").get().to_dict()
    assert (new["name"], new["kind"], new["deviceEnrolled"], new["active"]) == (
        "Karim", "student", True, True,
    )
    assert new["guardianUids"] == [] and new["createdAt"] is not None
    # idempotent
    assert store.upsert_device_users([DeviceUser("13", "Karim")]) == 0


def test_upsert_device_users_handles_more_than_one_batch(store, client):
    from bridge.models import DeviceUser

    users = [DeviceUser(str(i), f"U{i}") for i in range(1, 801)]
    assert store.upsert_device_users(users) == 800
    assert len(list(client.collection("people").select([]).stream())) == 800


def test_sms_logged_cache_is_dropped_when_the_date_moves_on(store):
    from bridge.models import SmsLogEntry

    store.log_sms(SmsLogEntry("1", "017", "b", "absent", "sent", None, "2026-10-16 09:30:00"))
    assert store._sms_days
    store.log_sms(SmsLogEntry("1", "017", "b", "absent", "sent", None, "2026-10-17 09:30:00"))
    assert {k[2] for k in store._sms_days} == {"2026-10-17"}


def test_refresh_enrollment_mirrors_device_ids_onto_existing_people_only(store, client):
    _add_person(client, "1")  # on a device, not yet enrolled -> true
    _add_person(client, "2", deviceEnrolled=True)  # on a device, already true -> untouched
    _add_person(client, "3", deviceEnrolled=True, phone="017")  # on no device -> false
    _add_person(client, "4")  # on no device, already false -> untouched
    client.collection("people").document("5").set({"name": "No flag", "kind": "student"})
    change = store.refresh_enrollment({"1", "2", "5", "99", ""})
    assert change.enrolled == ("1", "5")
    assert change.unenrolled == ("3",)
    people = {d.id: d.to_dict() for d in client.collection("people").stream()}
    assert set(people) == {"1", "2", "3", "4", "5"}  # "99" was not created
    assert {k: v.get("deviceEnrolled") for k, v in people.items()} == {
        "1": True, "2": True, "3": False, "4": False, "5": True,
    }
    assert people["3"]["phone"] == "017" and people["3"]["name"] == "P3"  # other fields kept
    assert store.refresh_enrollment({"1", "2", "5"}).changed is False


def test_refresh_enrollment_handles_more_than_one_batch(store, client):
    batch = client.batch()
    for i in range(1, 851):
        batch.set(
            client.collection("people").document(str(i)),
            {"name": f"P{i}", "kind": "student", "active": True, "deviceEnrolled": i > 425},
        )
        if i % 400 == 0:
            batch.commit()
            batch = client.batch()
    batch.commit()
    change = store.refresh_enrollment({str(i) for i in range(1, 426)})
    assert len(change.enrolled) == 425 and len(change.unenrolled) == 425
    from google.cloud.firestore_v1.base_query import FieldFilter

    enrolled = {
        d.id
        for d in client.collection("people")
        .where(filter=FieldFilter("deviceEnrolled", "==", True))
        .select([])
        .stream()
    }
    assert enrolled == {str(i) for i in range(1, 426)}
