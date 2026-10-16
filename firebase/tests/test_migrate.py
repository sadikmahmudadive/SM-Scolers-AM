"""Tests for the RTDB -> Firestore migration (spec section 8)."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

import migrate
from migrate import convert_log, convert_user, run_migration

TZ = ZoneInfo("Asia/Dhaka")
NOW = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)

LEGACY_STUDENT = {
    "name": "Rahim Uddin",
    "role": "Student",
    "phone": "01711111111",
    "card_id": "0012345",
    "student_type": "Day",
    "class_name": "Six",
    "section": "A",
    "father_name": "Karim Uddin",
    "father_phone": "01822222222",
    "mother_name": "Amina Begum",
    "mother_phone": "01933333333",
}


# -- convert_user ------------------------------------------------------------


def test_convert_user_student_maps_every_field():
    assert convert_user("12", LEGACY_STUDENT, NOW) == {
        "name": "Rahim Uddin",
        "kind": "student",
        "phone": "01711111111",
        "fatherPhone": "01822222222",
        "motherPhone": "01933333333",
        "className": "Six",
        "section": "A",
        "guardianUids": [],
        "deviceEnrolled": False,
        "active": True,
        "createdAt": NOW,
        "legacy": {
            "cardId": "0012345",
            "studentType": "Day",
            "fatherName": "Karim Uddin",
            "motherName": "Amina Begum",
        },
    }


@pytest.mark.parametrize(
    "role,kind",
    [
        ("Teacher", "teacher"),
        ("Student", "student"),
        ("Admin", "staff"),
        ("Staff", "staff"),
        ("", "staff"),
        (None, "staff"),
    ],
)
def test_convert_user_role_mapping(role, kind):
    assert convert_user("1", {"name": "X", "role": role}, NOW)["kind"] == kind


def test_convert_user_missing_role_is_staff():
    assert convert_user("1", {"name": "X"}, NOW)["kind"] == "staff"


def test_convert_user_omits_empty_optionals_and_legacy_map():
    # PersonSchema: phone/fatherPhone/motherPhone/className/section are optional
    # strings, so empty values are omitted rather than stored as "".
    doc = convert_user(
        "1", {"name": "Teacher T", "role": "Teacher", "phone": "", "class_name": None}, NOW
    )
    assert doc == {
        "name": "Teacher T",
        "kind": "teacher",
        "guardianUids": [],
        "deviceEnrolled": False,
        "active": True,
        "createdAt": NOW,
    }


def test_convert_user_stringifies_and_strips_values():
    doc = convert_user("1", {"name": " A ", "role": "Student", "phone": 1711, "card_id": 99}, NOW)
    assert doc["name"] == "A"
    assert doc["phone"] == "1711"
    assert doc["legacy"] == {"cardId": "99"}


# -- convert_log -------------------------------------------------------------


def test_convert_log_keeps_id_and_derives_fields():
    doc_id, doc = convert_log(
        "12_20261016082121",
        {
            "user_id": "12",
            "timestamp": "2026-10-16 08:21:21",
            "status": "0",
            "role": "Student",
            "name": "Rahim",
        },
        TZ,
    )
    assert doc_id == "12_20261016082121"
    assert doc == {
        "personId": "12",
        "ts": datetime(2026, 10, 16, 8, 21, 21, tzinfo=ZoneInfo("Asia/Dhaka")),
        "date": "2026-10-16",
        "status": "0",
        "direction": "in",
        "deviceId": "migrated",
        "late": False,
        "earlyLeave": False,
    }
    assert doc["ts"].utcoffset().total_seconds() == 6 * 3600
    assert "name" not in doc and "role" not in doc


def test_convert_log_direction_and_int_status():
    _, out = convert_log(
        "1_20261016150000",
        {"user_id": 1, "timestamp": "2026-10-16 15:00:00", "status": 1},
        TZ,
    )
    assert out["direction"] == "out"
    assert out["status"] == "1"
    assert out["personId"] == "1"


@pytest.mark.parametrize(
    "data",
    [
        {"user_id": "1", "timestamp": "garbage", "status": "0"},
        {"user_id": "1", "status": "0"},
        {"user_id": "1", "timestamp": None, "status": "0"},
        {"timestamp": "2026-10-16 08:00:00", "status": "0"},
        {"user_id": "", "timestamp": "2026-10-16 08:00:00", "status": "0"},
    ],
)
def test_convert_log_invalid_raises_value_error(data):
    with pytest.raises(ValueError):
        convert_log("1_x", data, TZ)


# -- runner ------------------------------------------------------------------


class FakeSource:
    def __init__(self, users, logs):
        self._users, self._logs = users, logs

    def read_users(self):
        return self._users

    def read_logs(self):
        return self._logs


class FakeDest:
    def __init__(self):
        self.data: dict[str, dict[str, dict]] = {}
        self.batches: list[tuple[str, int]] = []

    def write_batch(self, collection, docs):
        self.batches.append((collection, len(docs)))
        col = self.data.setdefault(collection, {})
        for doc_id, doc in docs:
            col.setdefault(doc_id, {}).update(doc)  # merge semantics

    def count(self, collection):
        return len(self.data.get(collection, {}))


class ExplodingDest:
    def write_batch(self, collection, docs):
        raise AssertionError("dry run must not write")

    def count(self, collection):
        raise AssertionError("dry run must not count")


def _log(uid, ts, status="0"):
    return {"user_id": uid, "timestamp": ts, "status": status, "role": "Student", "name": "n"}


def _source(n_logs=5):
    users = {
        "1": dict(LEGACY_STUDENT),
        "2": {"name": "T", "role": "Teacher"},
        "3": {"name": "Adm", "role": "Admin"},
    }
    logs = {
        f"1_2026101608{i:02d}00": _log("1", f"2026-10-16 08:{i:02d}:00") for i in range(n_logs)
    }
    return FakeSource(users, logs)


def test_dry_run_writes_nothing_and_reports_samples():
    report = run_migration(_source(), ExplodingDest(), "Asia/Dhaka", True, NOW)
    assert report.users_source == 3 and report.logs_source == 5
    assert report.users_written == 0 and report.logs_written == 0
    assert report.users_dest_count is None and report.logs_dest_count is None
    assert len(report.samples["people"]) == 3
    assert len(report.samples["attendance"]) == 3
    assert report.skipped == []


def test_real_run_writes_in_batches_of_two():
    dest = FakeDest()
    report = run_migration(_source(), dest, "Asia/Dhaka", False, NOW, batch_size=2)
    assert dest.batches == [
        ("people", 2),
        ("people", 1),
        ("attendance", 2),
        ("attendance", 2),
        ("attendance", 1),
    ]
    assert report.users_written == 3 and report.logs_written == 5
    assert report.users_dest_count == 3 and report.logs_dest_count == 5
    assert dest.data["people"]["1"]["kind"] == "student"
    assert "1_20261016080000" in dest.data["attendance"]


def test_rerun_is_idempotent():
    dest = FakeDest()
    run_migration(_source(), dest, "Asia/Dhaka", False, NOW)
    snapshot = {c: {k: dict(v) for k, v in d.items()} for c, d in dest.data.items()}
    report = run_migration(_source(), dest, "Asia/Dhaka", False, NOW)
    assert dest.data == snapshot
    assert report.users_dest_count == 3 and report.logs_dest_count == 5


def test_list_shaped_rtdb_data_is_normalised_skipping_none():
    assert migrate.normalise_rtdb([None, {"name": "A"}, None, {"name": "B"}]) == {
        "1": {"name": "A"},
        "3": {"name": "B"},
    }
    assert migrate.normalise_rtdb({"7": {"name": "A"}}) == {"7": {"name": "A"}}
    assert migrate.normalise_rtdb(None) == {}


def test_normalising_source_adapter():
    src = migrate.NormalisingSource(
        lambda: [None, {"name": "A", "role": "Student"}], lambda: {}
    )
    assert src.read_users() == {"1": {"name": "A", "role": "Student"}}
    assert src.read_logs() == {}


def test_bad_logs_are_skipped_and_rest_written():
    source = _source(2)
    source._logs["bad_1"] = {"user_id": "1", "timestamp": "nope", "status": "0"}
    source._logs["bad_2"] = {"timestamp": "2026-10-16 08:00:00"}
    dest = FakeDest()
    report = run_migration(source, dest, "Asia/Dhaka", False, NOW)
    assert report.logs_source == 4
    assert report.logs_written == 2
    assert dest.count("attendance") == 2
    assert [k for k, _ in report.skipped] == ["attendance_logs/bad_1", "attendance_logs/bad_2"]
    assert all(reason for _, reason in report.skipped)


def test_print_report_states_rtdb_untouched_and_limits_skipped_reasons():
    source = _source(1)
    for i in range(12):
        source._logs[f"bad_{i}"] = {"user_id": "1", "timestamp": "nope"}
    report = run_migration(source, FakeDest(), "Asia/Dhaka", False, NOW)
    lines: list[str] = []
    migrate.print_report(report, False, out=lines.append)
    text = "\n".join(lines)
    assert "skipped records: 12" in text
    assert text.count("attendance_logs/bad_") == 10
    assert "NOT modified" in text
