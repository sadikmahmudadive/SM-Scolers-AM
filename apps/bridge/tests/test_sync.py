from datetime import datetime

import pytest

from bridge.models import (
    TS_FORMAT,
    BridgeSettings,
    Person,
    RawPunch,
    Schedule,
    SmsSettings,
    StoredPunch,
)
from bridge.punch_id import punch_id
from bridge.sync import run_cycle
from fakes import FakeGateway, FakeZk, InMemoryStore

SCHEDULE = Schedule("07:45", "08:15", 5, "13:00")
DAY = "2026-10-12"
SETTINGS = BridgeSettings(stale_sms_window_min=30)
SMS = SmsSettings()


def ts(hms: str, day: str = DAY) -> str:
    return f"{day} {hms}"


def raw(user: str, hms: str, status: str = "0", day: str = DAY) -> RawPunch:
    return RawPunch(user_id=user, timestamp=ts(hms, day), status=status)


def at(hms: str, day: str = DAY) -> datetime:
    return datetime.strptime(ts(hms, day), TS_FORMAT)


def student(pid="S1", phone="111", father="222", mother="333") -> Person:
    return Person(
        id=pid, name="Rafi", kind="student",
        phone=phone, father_phone=father, mother_phone=mother,
    )


def store_with(*people: Person, **kwargs) -> InMemoryStore:
    schedules = {p.id: ("sch1", SCHEDULE) for p in people}
    return InMemoryStore(people=list(people), schedules=schedules, **kwargs)


def morning_punch(pid="S1") -> StoredPunch:
    return StoredPunch(
        id=punch_id(pid, ts("08:00:00")), person_id=pid, ts=ts("08:00:00"),
        date=DAY, status="0", direction="in", device_id="dev1",
        late=False, early_leave=False,
    )


def cycle(store, punches, now, gateway=None, sms=SMS, settings=SETTINGS, zk=None):
    gateway = gateway if gateway is not None else FakeGateway()
    zk = zk if zk is not None else FakeZk(punches)
    return run_cycle(zk, "dev1", store, gateway, settings, sms, now), gateway


def test_new_punch_is_stored_and_sms_sent():
    store = store_with(student())
    result, gw = cycle(store, [raw("S1", "08:00:00")], at("08:02:00"))
    assert result.new_punches == 1
    assert result.sms_sent == 3
    assert [p for p, _ in gw.sent] == ["111", "222", "333"]
    saved = store.punches[punch_id("S1", ts("08:00:00"))]
    assert saved.late is False and saved.early_leave is False
    assert saved.direction == "in" and saved.device_id == "dev1"
    assert saved.date == DAY and saved.schedule_id == "sch1"
    assert [e.status for e in store.sms_log] == ["sent"] * 3
    assert all(e.kind == "normal" for e in store.sms_log)


def test_replay_is_idempotent():
    store = store_with(student())
    punches = [raw("S1", "08:00:00")]
    first, gw = cycle(store, punches, at("08:02:00"))
    second, _ = cycle(store, punches, at("08:03:00"), gateway=gw)
    assert first.new_punches == 1
    assert second.new_punches == 0 and second.sms_sent == 0
    assert len(store.punches) == 1
    assert len(gw.sent) == 3


def test_catch_up_stores_all_but_skips_stale_sms():
    store = store_with(student("S1"), student("S2"))
    punches = [raw("S1", "08:00:00"), raw("S2", "08:05:00")]
    result, gw = cycle(store, punches, at("10:10:00"))  # >2h old, window 30 min
    assert result.new_punches == 2
    assert result.sms_sent == 0
    assert result.sms_skipped_stale == 6
    assert gw.sent == []
    assert len(store.sms_log) == 6
    assert all(e.status == "skipped-stale" for e in store.sms_log)


def test_stale_boundary_exactly_at_window_is_not_stale():
    result, _ = cycle(
        store_with(student(father="", mother="")), [raw("S1", "08:00:00")], at("08:30:00")
    )
    assert result.sms_sent == 1 and result.sms_skipped_stale == 0
    result2, _ = cycle(
        store_with(student(father="", mother="")), [raw("S1", "08:00:00")], at("08:30:01")
    )
    assert result2.sms_sent == 0 and result2.sms_skipped_stale == 1


def test_double_scan_sends_no_late_or_early_sms():
    store = store_with(student(father="", mother=""))
    punches = [raw("S1", "08:21:00"), raw("S1", "08:23:00")]
    result, gw = cycle(store, punches, at("08:24:00"))
    assert result.new_punches == 2
    # Only the first (late) punch was texted; the second is a duplicate scan.
    assert len(gw.sent) == 1 and gw.sent[0][1].startswith("LATE")
    second = store.punches[punch_id("S1", ts("08:23:00"))]
    assert second.late is False and second.early_leave is False
    assert [e.punch_id for e in store.sms_log] == [punch_id("S1", ts("08:21:00"))]


def test_duplicate_stored_with_flags_but_no_gateway_call():
    store = store_with(
        student(),
        punches=[
            StoredPunch(
                id=punch_id("S1", ts("08:00:00")), person_id="S1", ts=ts("08:00:00"),
                date=DAY, status="0", direction="in", device_id="dev1",
                late=False, early_leave=False,
            )
        ],
    )
    result, gw = cycle(store, [raw("S1", "08:03:00")], at("08:04:00"))
    assert result.new_punches == 1
    assert gw.sent == [] and store.sms_log == []
    assert punch_id("S1", ts("08:03:00")) in store.punches


def test_unknown_user_stored_without_sms():
    store = InMemoryStore()  # get_person returns None
    result, gw = cycle(store, [raw("99", "08:00:00")], at("08:01:00"))
    assert result.new_punches == 1 and result.errors == []
    assert punch_id("99", ts("08:00:00")) in store.punches
    assert gw.sent == [] and store.sms_log == []


def test_person_without_phone_sends_nothing():
    store = store_with(Person(id="T1", name="Sir", kind="teacher"))
    result, gw = cycle(store, [raw("T1", "08:00:00")], at("08:01:00"))
    assert result.new_punches == 1 and result.errors == []
    assert gw.sent == [] and store.sms_log == []


def test_student_without_guardians_only_self_phone():
    store = store_with(student(father="", mother=""))
    result, gw = cycle(store, [raw("S1", "08:00:00")], at("08:01:00"))
    assert [p for p, _ in gw.sent] == ["111"]
    assert result.sms_sent == 1


def test_non_student_does_not_text_guardian_phones():
    teacher = Person(
        id="T1", name="Sir", kind="teacher",
        phone="111", father_phone="222", mother_phone="333",
    )
    _, gw = cycle(store_with(teacher), [raw("T1", "08:00:00")], at("08:01:00"))
    assert [p for p, _ in gw.sent] == ["111"]


def test_recipients_are_deduplicated_in_stable_order():
    store = store_with(student(phone="222", father="222", mother="333"))
    _, gw = cycle(store, [raw("S1", "08:00:00")], at("08:01:00"))
    assert [p for p, _ in gw.sent] == ["222", "333"]


def test_save_failure_skips_sms_and_continues():
    first_id = punch_id("S1", ts("08:00:00"))
    store = store_with(
        student("S1", father="", mother=""),
        student("S2", phone="444", father="", mother=""),
        fail_save_ids={first_id},
    )
    punches = [raw("S1", "08:00:00"), raw("S2", "08:01:00")]
    result, gw = cycle(store, punches, at("08:02:00"))
    assert result.new_punches == 1
    assert len(result.errors) == 1 and result.errors[0].startswith(f"{first_id}: ")
    assert result.save_failures == 1
    assert first_id not in store.punches
    assert [p for p, _ in gw.sent] == ["444"]
    assert all(e.punch_id != first_id for e in store.sms_log)
    # The failed punch is retried on the next cycle (still not stored).
    store.fail_save_ids.clear()
    retry, _ = cycle(store, punches, at("08:03:00"))
    assert retry.new_punches == 1 and first_id in store.punches


def test_holiday_sends_normal_template_only():
    store = store_with(student(father="", mother=""), holidays={DAY})
    result, gw = cycle(store, [raw("S1", "09:30:00")], at("09:31:00"))
    assert len(gw.sent) == 1
    assert gw.sent[0][1].startswith("Attendance:")
    saved = store.punches[punch_id("S1", ts("09:30:00"))]
    assert saved.late is False and saved.early_leave is False
    assert store.sms_log[0].kind == "normal"


def test_late_uses_late_template():
    store = store_with(student(father="", mother=""))
    _, gw = cycle(store, [raw("S1", "08:21:00")], at("08:22:00"))
    assert gw.sent[0][1] == (
        "LATE: Rafi (S1) punched at 08:21 AM. Expected in-time: 07:45 - 08:15"
    )
    assert store.punches[punch_id("S1", ts("08:21:00"))].late is True
    assert store.sms_log[0].kind == "late"


def test_early_leave_uses_early_template():
    store = store_with(student(father="", mother=""), punches=[morning_punch()])
    sms = SmsSettings(early_leave_enabled=True)
    punches = [raw("S1", "08:00:00"), raw("S1", "12:00:00", status="1")]
    result, gw = cycle(store, punches, at("12:01:00"), sms=sms)
    assert result.new_punches == 1 and result.sms_sent == 1
    assert gw.sent[0][1] == (
        "EARLY LEAVE: Rafi (S1) left at 12:00 PM. Expected dismissal: 13:00"
    )
    out = store.punches[punch_id("S1", ts("12:00:00"))]
    assert out.early_leave is True and out.direction == "out"
    assert store.sms_log[0].kind == "early"


def test_early_leave_disabled_falls_back_to_normal():
    store = store_with(student(father="", mother=""), punches=[morning_punch()])
    punches = [raw("S1", "08:00:00"), raw("S1", "12:00:00", status="1")]
    _, gw = cycle(store, punches, at("12:01:00"))  # early_leave_enabled False
    assert gw.sent[0][1].startswith("Attendance:")
    assert store.sms_log[0].kind == "normal"
    # The flag is still recorded on the stored punch.
    assert store.punches[punch_id("S1", ts("12:00:00"))].early_leave is True


def test_sms_disabled_logs_nothing_sent():
    store = store_with(student())
    result, gw = cycle(
        store, [raw("S1", "08:21:00")], at("08:22:00"), sms=SmsSettings(sms_enabled=False)
    )
    assert result.new_punches == 1
    assert gw.sent == [] and store.sms_log == []
    assert result.sms_sent == 0 and result.sms_skipped_stale == 0


def test_failed_gateway_send_is_logged_failed_and_not_counted():
    store = store_with(student(father="", mother=""))
    gw = FakeGateway(fail_phones={"111"})
    result, _ = cycle(store, [raw("S1", "08:00:00")], at("08:01:00"), gateway=gw)
    assert result.sms_sent == 0
    assert [e.status for e in store.sms_log] == ["failed"]


def test_zk_exception_propagates():
    store = store_with(student())
    with pytest.raises(ConnectionError):
        cycle(store, [], at("08:00:00"), zk=FakeZk([], error=ConnectionError("down")))


def test_out_of_order_punches_are_processed_ascending():
    store = store_with(student(father="", mother=""))
    # Given latest-first; the 08:23 scan must still see 08:21 as its predecessor.
    punches = [raw("S1", "08:23:00"), raw("S1", "08:21:00")]
    _, gw = cycle(store, punches, at("08:24:00"))
    assert store.punches[punch_id("S1", ts("08:21:00"))].late is True
    assert store.punches[punch_id("S1", ts("08:23:00"))].late is False
    assert len(gw.sent) == 1


def test_duplicate_raw_entries_in_one_read_are_stored_once():
    store = store_with(student(father="", mother=""))
    result, gw = cycle(store, [raw("S1", "08:00:00")] * 2, at("08:01:00"))
    assert result.new_punches == 1 and len(gw.sent) == 1


def test_gateway_raising_is_failed_log_and_cycle_continues():
    store = store_with(
        student("S1"),  # phones 111 / 222 (father) / 333 (mother)
        student("S2", phone="444", father="", mother=""),
    )
    gw = FakeGateway(raise_phones={"222"})
    punches = [raw("S1", "08:00:00"), raw("S2", "08:01:00")]
    result, _ = cycle(store, punches, at("08:02:00"), gateway=gw)
    assert result.new_punches == 2
    assert [p for p, _ in gw.sent] == ["111", "222", "333", "444"]
    assert result.sms_sent == 3
    by_phone = {e.phone: e.status for e in store.sms_log}
    assert by_phone == {"111": "sent", "222": "failed", "333": "sent", "444": "sent"}
    assert len(result.errors) == 1
    assert result.errors[0].startswith(f"{punch_id('S1', ts('08:00:00'))} sms 222: ")


def test_log_sms_raising_does_not_stop_the_cycle():
    store = store_with(
        student("S1", father="", mother=""),
        student("S2", phone="444", father="", mother=""),
        fail_log=True,
    )
    punches = [raw("S1", "08:00:00"), raw("S2", "08:01:00")]
    result, gw = cycle(store, punches, at("08:02:00"), settings=SETTINGS)
    assert result.new_punches == 2
    assert [p for p, _ in gw.sent] == ["111", "444"]
    assert result.sms_sent == 2
    assert len(result.errors) == 2
    assert all(" log " in e for e in result.errors)


def test_sms_log_ts_is_cycle_now_not_punch_time():
    store = store_with(student(father="", mother=""))
    cycle(store, [raw("S1", "08:00:00")], at("08:02:07"))
    assert [e.ts for e in store.sms_log] == [ts("08:02:07")]


def test_aware_now_is_rejected():
    from datetime import timezone

    store = store_with(student())
    aware = at("08:00:00").replace(tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        cycle(store, [], aware)


def test_stale_duplicate_gets_no_skipped_stale_log():
    store = store_with(student(), punches=[morning_punch()])
    # 08:00 already stored; 08:03 is a duplicate AND stale at 10:00.
    result, gw = cycle(store, [raw("S1", "08:03:00")], at("10:00:00"))
    assert result.new_punches == 1
    assert result.sms_skipped_stale == 0
    assert store.sms_log == [] and gw.sent == []


def test_seconds_apart_scan_is_duplicate():
    store = store_with(student(father="", mother=""))
    punches = [raw("S1", "08:21:00"), raw("S1", "08:21:30")]
    result, gw = cycle(store, punches, at("08:22:00"))
    assert result.new_punches == 2
    assert len(gw.sent) == 1 and gw.sent[0][1].startswith("LATE")
    assert store.punches[punch_id("S1", ts("08:21:30"))].late is False


@pytest.mark.parametrize(
    "bad",
    ["Dear {name, your child", "Bye :-}", "Hi {}", "{bogus} arrived"],
)
def test_unrenderable_template_logs_failed_and_never_aborts_the_cycle(bad):
    from dataclasses import replace

    store = store_with(student("S1"), student("S2", phone="444", father="", mother=""))
    sms = replace(SMS, normal_template=bad)
    punches = [raw("S1", "08:00:00"), raw("S2", "08:01:00"), raw("S1", "12:00:00")]
    result, gw = cycle(store, punches, at("12:01:00"), sms=sms)
    # Every punch is saved; no SMS was attempted with a broken body.
    assert result.new_punches == 3
    assert len(store.punches) == 3
    assert gw.sent == []
    assert result.sms_sent == 0
    # One failed log row per recipient per fresh punch (the 08:xx ones are stale at 12:01).
    fresh = [e for e in store.sms_log if e.punch_id == punch_id("S1", ts("12:00:00"))]
    assert [e.status for e in fresh] == ["failed"] * 3
    assert all("template" in e.body for e in fresh)
    stale = [e for e in store.sms_log if e.punch_id != punch_id("S1", ts("12:00:00"))]
    assert stale and all(e.status == "skipped-stale" for e in stale)
    # The error is reported once per punch, not swallowed.
    assert len([e for e in result.errors if "template" in e]) == 3


def test_later_punches_are_processed_after_a_template_error():
    from dataclasses import replace

    store = store_with(student("S1"))
    broken = replace(SMS, normal_template="Bye :-}")
    first, _ = cycle(store, [raw("S1", "08:00:00")], at("08:01:00"), sms=broken)
    assert first.new_punches == 1
    second, gw = cycle(
        store,
        [raw("S1", "08:00:00"), raw("S1", "09:00:00")],
        at("09:01:00"),
    )
    assert second.new_punches == 1
    assert second.sms_sent == 3
    assert len(gw.sent) == 3
