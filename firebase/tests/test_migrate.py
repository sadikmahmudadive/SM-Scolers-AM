"""Tests for the RTDB -> Firestore migration (spec section 8)."""

import sys
import types
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

import migrate
from migrate import convert_log, convert_user, run_migration

TZ = ZoneInfo("Asia/Dhaka")
NOW = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)
NOW2 = datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

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
        ("student", "student"),
        (" TEACHER ", "teacher"),
        ("sTuDeNt", "student"),
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


def test_convert_log_status_none_is_empty_string_and_in():
    _, out = convert_log(
        "1_20261016150000", {"user_id": "1", "timestamp": "2026-10-16 15:00:00", "status": None}, TZ
    )
    assert out["status"] == ""
    assert out["direction"] == "in"


@pytest.mark.parametrize(
    "data",
    [
        {"user_id": "1", "timestamp": "garbage", "status": "0"},
        {"user_id": "1", "status": "0"},
        {"user_id": "1", "timestamp": None, "status": "0"},
        {"user_id": "1", "timestamp": 1760600000, "status": "0"},
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
    """In-memory Firestore stand-in. write_batch is create-only (fails on an existing id)."""

    def __init__(self, initial=None):
        self.data: dict[str, dict[str, dict]] = {
            c: {k: dict(v) for k, v in d.items()} for c, d in (initial or {}).items()
        }
        self.batches: list[tuple[str, int]] = []
        self.written_ids: list[tuple[str, str]] = []

    def write_batch(self, collection, docs):
        self.batches.append((collection, len(docs)))
        col = self.data.setdefault(collection, {})
        for doc_id, doc in docs:
            assert doc_id not in col, f"overwrite attempted: {collection}/{doc_id}"
            col[doc_id] = dict(doc)
            self.written_ids.append((collection, doc_id))

    def count(self, collection):
        return len(self.data.get(collection, {}))

    def existing_ids(self, collection):
        return set(self.data.get(collection, {}))


class WriteForbiddenDest(FakeDest):
    """Allows the read-only calls, raises on any write."""

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


def test_dry_run_writes_nothing_and_reports_would_create_counts():
    dest = WriteForbiddenDest(
        {"people": {"2": {"name": "kept"}}, "attendance": {"1_20261016080000": {"late": True}}}
    )
    report = run_migration(_source(), dest, "Asia/Dhaka", True, NOW)
    assert report.users_source == 3 and report.logs_source == 5
    assert report.users_written == 0 and report.logs_written == 0
    assert report.users_to_create == 2 and report.users_skipped_existing == 1
    assert report.logs_to_create == 4 and report.logs_skipped_existing == 1
    assert report.users_dest_count is None and report.logs_dest_count is None
    assert [i for i, _ in report.samples["people"]] == ["1", "3"]
    assert len(report.samples["attendance"]) == 3
    assert report.skipped == []
    assert dest.batches == []


def test_dry_run_samples_first_three():
    report = run_migration(_source(), WriteForbiddenDest(), "Asia/Dhaka", True, NOW)
    assert len(report.samples["people"]) == 3
    assert len(report.samples["attendance"]) == 3


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
    assert report.users_to_create == 3 and report.logs_to_create == 5
    assert report.users_skipped_existing == 0 and report.logs_skipped_existing == 0
    assert report.users_dest_count == 3 and report.logs_dest_count == 5
    assert dest.data["people"]["1"]["kind"] == "student"
    assert "1_20261016080000" in dest.data["attendance"]


def test_rerun_with_different_now_is_idempotent_and_creates_nothing():
    dest = FakeDest()
    run_migration(_source(), dest, "Asia/Dhaka", False, NOW)
    snapshot = {c: {k: dict(v) for k, v in d.items()} for c, d in dest.data.items()}
    dest.batches.clear()
    report = run_migration(_source(), dest, "Asia/Dhaka", False, NOW2)
    assert dest.data == snapshot  # including createdAt: still NOW, not NOW2
    assert dest.batches == []
    assert report.users_written == 0 and report.logs_written == 0
    assert report.users_skipped_existing == 3 and report.logs_skipped_existing == 5
    assert report.users_dest_count == 3 and report.logs_dest_count == 5


def test_existing_documents_are_never_modified():
    live_person = {
        "name": "Rahim Edited",
        "kind": "student",
        "phone": "01999999999",
        "guardianUids": ["g"],
        "deviceEnrolled": True,
        "active": True,
        "createdAt": NOW,
    }
    live_log = {
        "personId": "1",
        "late": True,
        "earlyLeave": False,
        "deviceId": "gate",
        "scheduleId": "s1",
    }
    dest = FakeDest(
        {"people": {"1": dict(live_person)}, "attendance": {"1_20261016080000": dict(live_log)}}
    )
    report = run_migration(_source(), dest, "Asia/Dhaka", False, NOW2)
    assert dest.data["people"]["1"] == live_person
    assert dest.data["attendance"]["1_20261016080000"] == live_log
    assert report.users_written == 2 and report.logs_written == 4
    assert report.users_skipped_existing == 1 and report.logs_skipped_existing == 1


def test_partially_populated_dest_only_receives_missing_ids_in_batches():
    dest = FakeDest(
        {
            "people": {"1": {"name": "x"}},
            "attendance": {"1_20261016080000": {"x": 1}, "1_20261016080100": {"x": 1}},
        }
    )
    run_migration(_source(), dest, "Asia/Dhaka", False, NOW, batch_size=2)
    assert sorted(i for c, i in dest.written_ids if c == "people") == ["2", "3"]
    assert sorted(i for c, i in dest.written_ids if c == "attendance") == [
        "1_20261016080200",
        "1_20261016080300",
        "1_20261016080400",
    ]
    assert dest.batches == [("people", 2), ("attendance", 2), ("attendance", 1)]


def test_list_shaped_rtdb_data_is_normalised_skipping_none():
    assert migrate.normalise_rtdb([None, {"name": "A"}, None, {"name": "B"}]) == {
        "1": {"name": "A"},
        "3": {"name": "B"},
    }
    assert migrate.normalise_rtdb({"7": {"name": "A"}}) == {"7": {"name": "A"}}
    assert migrate.normalise_rtdb({"7": None, "8": {"name": "B"}}) == {"8": {"name": "B"}}
    assert migrate.normalise_rtdb(None) == {}
    with pytest.raises(ValueError):
        migrate.normalise_rtdb("garbage")


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


def test_non_object_records_are_skipped_not_crashed():
    source = FakeSource(
        {"1": "oops", "2": {"name": "ok", "role": "Teacher"}},
        {"a": 5, "1_20261016080000": _log("1", "2026-10-16 08:00:00")},
    )
    dest = FakeDest()
    report = run_migration(source, dest, "Asia/Dhaka", False, NOW)
    assert dest.count("people") == 1 and dest.count("attendance") == 1
    assert report.skipped == [
        ("users/1", "record is not an object"),
        ("attendance_logs/a", "record is not an object"),
    ]


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


# -- real Firestore adapter + CLI (with fake firebase_admin) -------------------


class _Doc:
    def __init__(self, doc_id):
        self.id = doc_id


class _AggResult:
    def __init__(self, value):
        self.value = value


class _CountQuery:
    def __init__(self, n):
        self._n = n

    def get(self):
        # real shape: list of lists of AggregationResult
        return [[_AggResult(self._n)]]


class _Collection:
    def __init__(self, client, name):
        self._client, self._name = client, name

    def document(self, doc_id):
        return (self._name, doc_id)

    def select(self, fields):
        assert fields == []  # ids only
        return self

    def stream(self):
        return [_Doc(i) for i in self._client.store.get(self._name, {})]

    def count(self):
        return _CountQuery(len(self._client.store.get(self._name, {})))


class _Batch:
    """Only supports create(): calling set() would raise AttributeError."""

    def __init__(self, client):
        self._client, self._ops = client, []

    def create(self, ref, doc):
        self._ops.append((ref, doc))

    def commit(self):
        assert len(self._ops) <= 500
        self._client.commits.append(len(self._ops))
        for (collection, doc_id), doc in self._ops:
            col = self._client.store.setdefault(collection, {})
            assert doc_id not in col, "create() on an existing doc"
            col[doc_id] = doc


class FakeFirestoreClient:
    def __init__(self, store=None):
        self.store = store if store is not None else {}
        self.commits: list[int] = []

    def collection(self, name):
        return _Collection(self, name)

    def batch(self):
        return _Batch(self)


CANARY = "CANARY-PRIVATE-KEY-DO-NOT-PRINT"


@pytest.fixture
def key_file(tmp_path):
    path = tmp_path / "key.json"
    path.write_text('{"private_key": "%s"}' % CANARY)
    return str(path)


def install_fake_firebase(
    monkeypatch, rtdb, client=None, cert_error=False, client_error=False
):
    """Install fake firebase_admin modules; `rtdb` maps path -> value or Exception."""
    state = types.SimpleNamespace(init_calls=[], client=client or FakeFirestoreClient())

    credentials = types.ModuleType("firebase_admin.credentials")

    def certificate(path):
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        if cert_error:
            raise ValueError(f"bad key file: {content}")
        return object()

    credentials.Certificate = certificate

    db = types.ModuleType("firebase_admin.db")

    class _Ref:
        def __init__(self, path):
            self._path = path

        def get(self):
            value = rtdb.get(self._path)
            if isinstance(value, Exception):
                raise value
            return value

    db.reference = _Ref

    firestore = types.ModuleType("firebase_admin.firestore")

    def make_client():
        if client_error:
            raise RuntimeError(f"no credentials ({CANARY})")
        return state.client

    firestore.client = make_client

    admin = types.ModuleType("firebase_admin")
    admin.credentials, admin.db, admin.firestore = credentials, db, firestore
    admin.initialize_app = lambda cred, options=None: state.init_calls.append(options)
    for name, mod in (
        ("firebase_admin", admin),
        ("firebase_admin.credentials", credentials),
        ("firebase_admin.db", db),
        ("firebase_admin.firestore", firestore),
    ):
        monkeypatch.setitem(sys.modules, name, mod)
    return state


def _argv(key_file, *extra):
    return ["--service-account", key_file, "--database-url", "https://x.firebaseio.com", *extra]


GOOD_RTDB = {
    "users": {"1": dict(LEGACY_STUDENT), "2": {"name": "T", "role": "Teacher"}},
    "attendance_logs": {"1_20261016082121": _log("1", "2026-10-16 08:21:21")},
}


def test_main_success_creates_docs_and_reports(monkeypatch, key_file, capsys):
    state = install_fake_firebase(monkeypatch, GOOD_RTDB)
    assert migrate.main(_argv(key_file, "--project-id", "p1")) == 0
    out = capsys.readouterr().out
    assert set(state.client.store["people"]) == {"1", "2"}
    assert set(state.client.store["attendance"]) == {"1_20261016082121"}
    assert state.init_calls == [{"databaseURL": "https://x.firebaseio.com", "projectId": "p1"}]
    assert "destination count: 2" in out and "NOT modified" in out
    assert CANARY not in out


def test_main_list_shaped_rtdb_with_none(monkeypatch, key_file):
    rtdb = {"users": [None, {"name": "A", "role": "Student"}, None], "attendance_logs": None}
    state = install_fake_firebase(monkeypatch, rtdb)
    assert migrate.main(_argv(key_file)) == 0
    assert set(state.client.store["people"]) == {"1"}


def test_main_source_read_failure_exits_2_and_writes_nothing(monkeypatch, key_file, capsys):
    state = install_fake_firebase(monkeypatch, {"users": RuntimeError("rtdb down")})
    assert migrate.main(_argv(key_file)) == 2
    captured = capsys.readouterr()
    assert "could not read the legacy database" in captured.err
    assert state.client.commits == [] and state.client.store == {}


def test_main_skipped_records_exit_0_with_warning(monkeypatch, key_file, capsys):
    rtdb = {
        "users": {"1": {"name": "A"}},
        "attendance_logs": {"bad": {"user_id": "1", "timestamp": "nope"}},
    }
    state = install_fake_firebase(monkeypatch, rtdb)
    assert migrate.main(_argv(key_file)) == 0
    out = capsys.readouterr().out
    assert "WARNING: some records were skipped" in out
    assert "attendance_logs/bad" in out
    assert set(state.client.store["people"]) == {"1"}


def test_main_unknown_tz_exits_2(monkeypatch, key_file, capsys):
    state = install_fake_firebase(monkeypatch, GOOD_RTDB)
    assert migrate.main(_argv(key_file, "--tz", "Mars/Olympus")) == 2
    assert "unknown time zone 'Mars/Olympus'" in capsys.readouterr().err
    assert state.init_calls == [] and state.client.store == {}


def test_main_dry_run_writes_nothing(monkeypatch, key_file, capsys):
    state = install_fake_firebase(monkeypatch, GOOD_RTDB)
    assert migrate.main(_argv(key_file, "--dry-run")) == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "would create: 2" in out
    assert state.client.store == {} and state.client.commits == []


def test_main_second_run_creates_nothing(monkeypatch, key_file, capsys):
    state = install_fake_firebase(monkeypatch, GOOD_RTDB)
    assert migrate.main(_argv(key_file)) == 0
    state.client.commits.clear()
    assert migrate.main(_argv(key_file)) == 0
    assert state.client.commits == []  # create-only: nothing new, nothing touched


def test_main_credential_init_failure_is_clean_and_never_echoes_key(monkeypatch, key_file, capsys):
    install_fake_firebase(monkeypatch, GOOD_RTDB, cert_error=True)
    assert migrate.main(_argv(key_file)) == 2
    captured = capsys.readouterr()
    assert "could not initialise Firebase" in captured.err
    assert CANARY not in captured.out + captured.err
    assert "Traceback" not in captured.err


def test_main_firestore_client_failure_is_clean_exit_2(monkeypatch, key_file, capsys):
    install_fake_firebase(monkeypatch, GOOD_RTDB, client_error=True)
    assert migrate.main(_argv(key_file)) == 2
    captured = capsys.readouterr()
    assert "could not create the Firestore client" in captured.err
    assert CANARY not in captured.out + captured.err


def test_adapter_chunks_at_500_uses_create_only_and_unpacks_count():
    client = FakeFirestoreClient({"people": {"existing": {"x": 1}}})
    dest = migrate._FirestoreDest(client)
    assert dest.existing_ids("people") == {"existing"}
    assert dest.existing_ids("attendance") == set()
    docs = [(f"id{i}", {"n": i}) for i in range(1203)]
    dest.write_batch("attendance", docs)
    assert client.commits == [500, 500, 203]
    assert dest.count("attendance") == 1203
    assert dest.count("people") == 1
    assert isinstance(dest.count("people"), int)


def test_run_migration_through_adapter_is_create_only():
    client = FakeFirestoreClient({"people": {"1": {"name": "live", "deviceEnrolled": True}}})
    report = run_migration(_source(), migrate._FirestoreDest(client), "Asia/Dhaka", False, NOW)
    assert client.store["people"]["1"] == {"name": "live", "deviceEnrolled": True}
    assert report.users_written == 2 and report.users_skipped_existing == 1
    assert report.users_dest_count == 3
