from datetime import datetime

import pytest

from bridge.commands import execute_command, process_commands
from bridge.models import DeviceUser, Person
from fakes import FakeGsm, FakeZk, InMemoryStore

NOW = datetime(2026, 10, 16, 9, 0, 0)


def run(cmd, gateway=None, store=None, zk=None):
    gateway = gateway or FakeGsm()
    store = store or InMemoryStore()
    zk = zk or FakeZk([])
    return execute_command(cmd, gateway, lambda: zk, store, NOW), gateway, store


def cmd(type_, payload=None, id_="c1"):
    return {"id": id_, "type": type_, "payload": payload or {}, "status": "pending"}


def test_test_sms_sends_and_logs_kind_test():
    result, gw, store = run(cmd("test_sms", {"phone": "0171", "message": "hello"}))
    assert result == {"sent": True}
    assert gw.sent == [("0171", "hello")]
    (entry,) = store.sms_log
    assert (entry.kind, entry.status, entry.phone, entry.body) == ("test", "sent", "0171", "hello")
    assert entry.ts == "2026-10-16 09:00:00"
    assert entry.punch_id is None


def test_test_sms_failure_returns_sent_false_and_logs_failed():
    result, gw, store = run(
        cmd("test_sms", {"phone": "0171", "message": "x"}), gateway=FakeGsm(fail_phones={"0171"})
    )
    assert result == {"sent": False}
    assert store.sms_log[0].status == "failed"


def test_test_sms_gateway_exception_is_a_failed_send():
    result, _, store = run(
        cmd("test_sms", {"phone": "0171", "message": "x"}), gateway=FakeGsm(raise_phones={"0171"})
    )
    assert result == {"sent": False}
    assert store.sms_log[0].status == "failed"


def test_test_sms_requires_phone_and_message():
    with pytest.raises(ValueError):
        run(cmd("test_sms", {"phone": "0171"}))
    with pytest.raises(ValueError):
        run(cmd("test_sms", {}))


def test_ussd_code_uses_session_variant():
    result, gw, _ = run(cmd("ussd", {"code": "*222#"}))
    assert result == {"text": "balance for *222#", "sessionActive": True}
    assert gw.calls == [("ussd", "*222#")]


def test_ussd_reply_continues_the_session():
    result, gw, _ = run(cmd("ussd", {"code": "*222#", "reply": "1"}))
    assert result == {"text": "reply 1", "sessionActive": False}
    assert gw.calls == [("ussd_reply", "1")]


def test_ussd_requires_code_or_reply():
    with pytest.raises(ValueError):
        run(cmd("ussd", {}))


def test_read_inbox_default_and_max():
    result, gw, _ = run(cmd("read_inbox"))
    assert result["messages"][0]["body"] == "hi"
    assert gw.calls == [("inbox", 20)]
    _, gw2, _ = run(cmd("read_inbox", {"max": 5}))
    assert gw2.calls == [("inbox", 5)]


def test_at_command():
    result, gw, _ = run(cmd("at_command", {"command": "AT+CSQ", "readSeconds": 2}))
    assert result == {"output": "OK"}
    assert gw.calls == [("at", "AT+CSQ", 2.0)]
    _, gw2, _ = run(cmd("at_command", {"command": "AT"}))
    assert gw2.calls == [("at", "AT", 1.0)]


def test_at_command_requires_command():
    with pytest.raises(ValueError):
        run(cmd("at_command", {}))


def test_sync_device_users_creates_missing_and_marks_existing():
    store = InMemoryStore(
        people=[Person(id="12", name="Old Name", kind="staff", phone="017", active=False)]
    )
    zk = FakeZk([], users=[DeviceUser("12", "Rahim"), DeviceUser("13", "Karim")])
    result, _, store = run(cmd("sync_device_users"), store=store, zk=zk)

    assert result == {"created": 1, "total": 2}
    existing = store.people["12"]
    assert existing.device_enrolled is True
    # nothing else on the existing person is touched
    assert (existing.name, existing.kind, existing.phone, existing.active) == (
        "Old Name",
        "staff",
        "017",
        False,
    )
    new = store.people["13"]
    assert (new.name, new.kind, new.device_enrolled, new.active) == ("Karim", "student", True, True)


def test_unknown_type_raises_value_error():
    with pytest.raises(ValueError, match="format_disk"):
        run(cmd("format_disk"))


def test_process_commands_marks_done_with_result():
    store = InMemoryStore(commands=[cmd("test_sms", {"phone": "0171", "message": "hi"})])
    n = process_commands(store, FakeGsm(), lambda: FakeZk([]), NOW)
    assert n == 1
    assert store.finished["c1"] == ("done", {"sent": True})
    assert store.commands[0]["status"] == "done"


def test_unknown_command_type_marks_error():
    store = InMemoryStore(commands=[cmd("format_disk")])
    assert process_commands(store, FakeGsm(), lambda: FakeZk([]), NOW) == 1
    status, result = store.finished["c1"]
    assert status == "error"
    assert "format_disk" in result["error"]


def test_command_failure_records_error_text_and_next_command_still_runs():
    store = InMemoryStore(
        commands=[
            cmd("at_command", {}, id_="bad"),  # missing command -> ValueError
            cmd("test_sms", {"phone": "0171", "message": "ok"}, id_="good"),
        ]
    )
    gw = FakeGsm()
    assert process_commands(store, gw, lambda: FakeZk([]), NOW) == 2
    assert store.finished["bad"][0] == "error"
    assert store.finished["bad"][1]["error"]
    assert store.finished["good"] == ("done", {"sent": True})


def test_zk_failure_in_sync_command_is_recorded_not_raised():
    store = InMemoryStore(commands=[cmd("sync_device_users")])
    zk = FakeZk([], error=TimeoutError("device down"))
    process_commands(store, FakeGsm(), lambda: zk, NOW)
    assert store.finished["c1"] == ("error", {"error": "device down"})


def test_only_pending_commands_are_processed():
    store = InMemoryStore(
        commands=[{**cmd("test_sms", {"phone": "1", "message": "m"}), "status": "done"}]
    )
    assert process_commands(store, FakeGsm(), lambda: FakeZk([]), NOW) == 0
    assert store.finished == {}


def test_failure_to_record_a_result_does_not_stop_the_rest():
    store = InMemoryStore(
        commands=[
            cmd("test_sms", {"phone": "1", "message": "a"}, id_="a"),
            cmd("test_sms", {"phone": "2", "message": "b"}, id_="b"),
        ]
    )
    real_finish = store.finish_command

    def flaky(command_id, status, result):
        if command_id == "a":
            raise ConnectionError("firestore down")
        real_finish(command_id, status, result)

    store.finish_command = flaky
    assert process_commands(store, FakeGsm(), lambda: FakeZk([]), NOW) == 2
    assert "b" in store.finished


def test_claim_failure_does_not_strand_or_stop_other_commands():
    store = InMemoryStore(
        commands=[
            cmd("test_sms", {"phone": "1", "message": "a"}, id_="a"),
            cmd("test_sms", {"phone": "2", "message": "b"}, id_="b"),
        ],
        fail_claim_ids={"a"},
    )
    assert process_commands(store, FakeGsm(), lambda: FakeZk([]), NOW) == 1
    assert store.finished["b"] == ("done", {"sent": True})
    # "a" was never claimed, so it is still pending (not stuck in running)
    assert [c["status"] for c in store.commands if c["id"] == "a"] == ["pending"]


def test_command_lost_to_another_bridge_is_skipped():
    store = InMemoryStore(commands=[cmd("test_sms", {"phone": "1", "message": "a"}, id_="a")])
    real = store.claim_command
    store.claim_command = lambda cid: None  # another process claimed it first
    assert process_commands(store, FakeGsm(), lambda: FakeZk([]), NOW) == 0
    assert store.finished == {}
    store.claim_command = real


def test_read_inbox_max_is_clamped():
    _, gw, _ = run(cmd("read_inbox", {"max": 5000}))
    assert gw.calls == [("inbox", 50)]
    _, gw, _ = run(cmd("read_inbox", {"max": -3}))
    assert gw.calls == [("inbox", 1)]
