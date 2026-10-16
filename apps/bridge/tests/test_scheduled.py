from dataclasses import replace
from datetime import datetime

from bridge.models import Person, Schedule, SmsSettings, StoredPunch
from bridge.scheduled import run_scheduled_sms
from fakes import FakeGateway, InMemoryStore

DATE = "2026-10-16"
SCHEDULE = ("sch1", Schedule(start="08:00", end="09:00", grace_min=10))
AFTER_CUTOFF = datetime(2026, 10, 16, 9, 30, 0)  # cutoff 09:10, window ends 09:40

ABSENT_ON = SmsSettings(sms_enabled=True, absent_enabled=True)


def student(pid="1", name="Rahim", **kw):
    base = dict(
        id=pid,
        name=name,
        kind="student",
        class_name="Six",
        father_phone="0171" + pid,
        device_enrolled=True,
    )
    base.update(kw)
    return Person(**base)


def punch(pid, ts=f"{DATE} 08:30:00", late=False):
    return StoredPunch(
        id=f"{pid}_{ts}",
        person_id=pid,
        ts=ts,
        date=ts[:10],
        status="0",
        direction="in",
        device_id="d",
        late=late,
        early_leave=False,
    )


def make_store(people=None, **kw):
    people = people if people is not None else [student("1")]
    schedules = {p.id: SCHEDULE for p in people}
    return InMemoryStore(people=people, schedules=schedules, **kw)


# -- absent -----------------------------------------------------------------


def test_absent_sms_sent_once_per_day():
    store, gw = make_store(), FakeGateway()
    first = run_scheduled_sms(store, gw, ABSENT_ON, AFTER_CUTOFF)
    second = run_scheduled_sms(store, gw, ABSENT_ON, AFTER_CUTOFF)
    assert first["absent"] == 1 and second["absent"] == 0
    assert gw.sent == [("01711", "Absent: Rahim (1) was not present on 16/10/2026.")]
    (entry,) = store.sms_log
    assert (entry.kind, entry.status, entry.person_id, entry.phone) == (
        "absent",
        "sent",
        "1",
        "01711",
    )
    assert entry.ts == "2026-10-16 09:30:00"


def test_no_absent_sms_on_holiday():
    store, gw = make_store(holidays={DATE}), FakeGateway()
    assert run_scheduled_sms(store, gw, ABSENT_ON, AFTER_CUTOFF) == {"absent": 0, "summary": 0}
    assert gw.sent == []


def test_absent_sms_skipped_for_student_with_punch():
    store = make_store(
        [student("1"), student("2", "Karim")], punches=[punch("1")]
    )
    gw = FakeGateway()
    run_scheduled_sms(store, gw, ABSENT_ON, AFTER_CUTOFF)
    assert [phone for phone, _ in gw.sent] == ["01712"]


def test_absent_sms_not_sent_before_end_plus_grace():
    store, gw = make_store(), FakeGateway()
    run_scheduled_sms(store, gw, ABSENT_ON, datetime(2026, 10, 16, 9, 10, 0))  # == cutoff
    run_scheduled_sms(store, gw, ABSENT_ON, datetime(2026, 10, 16, 8, 0, 0))
    assert gw.sent == []
    run_scheduled_sms(store, gw, ABSENT_ON, datetime(2026, 10, 16, 9, 10, 1))
    assert len(gw.sent) == 1


def test_absent_sms_not_sent_after_the_stale_window():
    store, gw = make_store(), FakeGateway()
    run_scheduled_sms(store, gw, ABSENT_ON, datetime(2026, 10, 16, 9, 40, 1))
    assert gw.sent == []
    # a larger configured window reaches further
    run_scheduled_sms(store, gw, ABSENT_ON, datetime(2026, 10, 16, 9, 40, 1), 60)
    assert len(gw.sent) == 1


def test_absent_window_extends_to_dismissal_when_set():
    sched = ("sch1", Schedule(start="08:00", end="09:00", grace_min=10, dismissal="15:00"))
    store = InMemoryStore(people=[student("1")], schedules={"1": sched})
    gw = FakeGateway()
    run_scheduled_sms(store, gw, ABSENT_ON, datetime(2026, 10, 16, 15, 0, 1))
    assert gw.sent == []
    run_scheduled_sms(store, gw, ABSENT_ON, datetime(2026, 10, 16, 14, 0, 0))
    assert len(gw.sent) == 1


def test_absent_sms_skipped_for_students_not_enrolled_on_the_device():
    people = [student("1", device_enrolled=False), student("2", "Karim")]
    store, gw = make_store(people), FakeGateway()
    run_scheduled_sms(store, gw, ABSENT_ON, AFTER_CUTOFF)
    assert [p for p, _ in gw.sent] == ["01712"]


def test_allow_absent_false_skips_absent_but_not_summary():
    settings = replace(ABSENT_ON, summary_enabled=True, summary_time="09:00", admin_phones=["0199"])
    store, gw = make_store(), FakeGateway()
    result = run_scheduled_sms(store, gw, settings, AFTER_CUTOFF, allow_absent=False)
    assert result == {"absent": 0, "summary": 1}
    assert [p for p, _ in gw.sent] == ["0199"]


def test_pass_reads_punches_once_and_schedules_once_per_class():
    people = [student(str(i), f"S{i}") for i in range(1, 6)]
    store, gw = make_store(people), FakeGateway()
    punched_calls, schedule_calls = [], []
    real_punched, real_sched = store.punched_person_ids, store.get_schedule_for
    store.punched_person_ids = lambda d: punched_calls.append(d) or real_punched(d)
    store.get_schedule_for = lambda p: schedule_calls.append(p.id) or real_sched(p)
    run_scheduled_sms(store, gw, ABSENT_ON, AFTER_CUTOFF)
    assert len(gw.sent) == 5
    assert punched_calls == [DATE]
    assert len(schedule_calls) == 1  # all five are class "Six"


def test_punch_query_skipped_when_nobody_is_due():
    store, gw = make_store(), FakeGateway()
    calls = []
    store.punched_person_ids = lambda d: calls.append(d) or set()
    run_scheduled_sms(store, gw, ABSENT_ON, datetime(2026, 10, 16, 8, 0, 0))
    assert calls == []


def test_invalid_absent_template_logs_one_error_not_one_per_student(caplog):
    settings = replace(ABSENT_ON, absent_template="{bogus}")
    store, gw = make_store([student("1"), student("2"), student("3")]), FakeGateway()
    with caplog.at_level("ERROR"):
        result = run_scheduled_sms(store, gw, settings, AFTER_CUTOFF)
    assert result["absent"] == 0 and gw.sent == []
    assert len([r for r in caplog.records if r.levelname == "ERROR"]) == 1


def test_absent_sms_skips_students_without_schedule():
    store = InMemoryStore(people=[student("1")])
    gw = FakeGateway()
    run_scheduled_sms(store, gw, ABSENT_ON, AFTER_CUTOFF)
    assert gw.sent == []


def test_absent_sms_recipient_falls_back_father_mother_phone():
    people = [
        student("1", father_phone="", mother_phone="0182", phone="0193"),
        student("2", father_phone="", mother_phone="", phone="0194"),
        student("3", father_phone="0175", mother_phone="0185"),
    ]
    store, gw = make_store(people), FakeGateway()
    run_scheduled_sms(store, gw, ABSENT_ON, AFTER_CUTOFF)
    assert sorted(p for p, _ in gw.sent) == ["0175", "0182", "0194"]


def test_absent_sms_without_any_phone_is_skipped_without_crash():
    people = [student("1", father_phone=""), student("2", "Karim")]
    store, gw = make_store(people), FakeGateway()
    result = run_scheduled_sms(store, gw, ABSENT_ON, AFTER_CUTOFF)
    assert result["absent"] == 1
    assert [e.person_id for e in store.sms_log] == ["2"]


def test_absent_ignores_inactive_and_non_students():
    people = [
        student("1", active=False),
        Person(id="2", name="Teacher", kind="teacher", phone="0188", department_id="d"),
    ]
    store, gw = make_store(people), FakeGateway()
    run_scheduled_sms(store, gw, ABSENT_ON, AFTER_CUTOFF)
    assert gw.sent == []


def test_failed_send_is_logged_failed_and_not_retried():
    store, gw = make_store(), FakeGateway(fail_phones={"01711"})
    first = run_scheduled_sms(store, gw, ABSENT_ON, AFTER_CUTOFF)
    run_scheduled_sms(store, gw, ABSENT_ON, AFTER_CUTOFF)
    assert first["absent"] == 0
    assert store.sms_log[0].status == "failed"
    assert len(gw.sent) == 1


def test_gateway_exception_does_not_stop_other_students():
    people = [student("1"), student("2", "Karim")]
    store, gw = make_store(people), FakeGateway(raise_phones={"01711"})
    result = run_scheduled_sms(store, gw, ABSENT_ON, AFTER_CUTOFF)
    assert result["absent"] == 1
    statuses = {e.person_id: e.status for e in store.sms_log}
    assert statuses == {"1": "failed", "2": "sent"}


def test_disabled_flags_send_nothing():
    for settings in (
        SmsSettings(sms_enabled=False, absent_enabled=True, summary_enabled=True,
                    summary_time="00:00", admin_phones=["0199"]),
        SmsSettings(sms_enabled=True, absent_enabled=False, summary_enabled=False,
                    summary_time="00:00", admin_phones=["0199"]),
    ):
        store, gw = make_store(), FakeGateway()
        assert run_scheduled_sms(store, gw, settings, AFTER_CUTOFF) == {"absent": 0, "summary": 0}
        assert gw.sent == [] and store.sms_log == []


def test_custom_absent_template():
    settings = replace(ABSENT_ON, absent_template="{name}/{id}/{date}")
    store, gw = make_store(), FakeGateway()
    run_scheduled_sms(store, gw, settings, AFTER_CUTOFF)
    assert gw.sent[0][1] == "Rahim/1/16/10/2026"


def test_bad_absent_template_does_not_block_summary():
    settings = replace(
        ABSENT_ON,
        absent_template="{bogus}",
        summary_enabled=True,
        summary_time="09:00",
        admin_phones=["0199"],
    )
    store, gw = make_store(), FakeGateway()
    result = run_scheduled_sms(store, gw, settings, AFTER_CUTOFF)
    assert result["absent"] == 0
    assert result["summary"] == 1


# -- summary ----------------------------------------------------------------

SUMMARY_ON = SmsSettings(
    sms_enabled=True,
    summary_enabled=True,
    summary_time="17:00",
    admin_phones=["0199", "0188"],
)
EVENING = datetime(2026, 10, 16, 17, 0, 0)


def summary_store():
    people = [student("1"), student("2", "Karim"), student("3", "Salim"),
              Person(id="9", name="Gone", kind="staff", active=False)]
    return make_store(
        people,
        punches=[punch("1", late=True), punch("1", f"{DATE} 15:00:00"), punch("2")],
    )


def test_summary_sent_at_time_to_both_admins_with_counts():
    store, gw = summary_store(), FakeGateway()
    result = run_scheduled_sms(store, gw, SUMMARY_ON, EVENING)
    assert result == {"absent": 0, "summary": 2}
    body = "Summary 16/10/2026: Present 2, Absent 1, Late 1, Total 3"
    assert gw.sent == [("0199", body), ("0188", body)]
    assert [(e.kind, e.phone, e.status) for e in store.sms_log] == [
        ("summary", "0199", "sent"),
        ("summary", "0188", "sent"),
    ]


def test_summary_sent_once_per_day():
    store, gw = summary_store(), FakeGateway()
    run_scheduled_sms(store, gw, SUMMARY_ON, EVENING)
    again = run_scheduled_sms(store, gw, SUMMARY_ON, datetime(2026, 10, 16, 18, 30, 0))
    assert again["summary"] == 0
    assert len(gw.sent) == 2


def test_summary_not_before_time():
    store, gw = summary_store(), FakeGateway()
    run_scheduled_sms(store, gw, SUMMARY_ON, datetime(2026, 10, 16, 16, 59, 59))
    assert gw.sent == []


def test_summary_needs_admin_phones():
    store, gw = summary_store(), FakeGateway()
    result = run_scheduled_sms(store, gw, replace(SUMMARY_ON, admin_phones=[]), EVENING)
    assert result["summary"] == 0
    assert gw.sent == [] and store.sms_log == []


def test_summary_needs_summary_time():
    store, gw = summary_store(), FakeGateway()
    run_scheduled_sms(store, gw, replace(SUMMARY_ON, summary_time=""), EVENING)
    assert gw.sent == []


def test_summary_absent_never_negative():
    people = [student("1")]
    store = make_store(people, punches=[punch("1"), punch("77")])  # 2 present, 1 total
    gw = FakeGateway()
    run_scheduled_sms(store, gw, SUMMARY_ON, EVENING)
    assert "Absent 0" in gw.sent[0][1]


def test_no_summary_on_holiday():
    store, gw = summary_store(), FakeGateway()
    store.holidays.add(DATE)
    assert run_scheduled_sms(store, gw, SUMMARY_ON, EVENING) == {"absent": 0, "summary": 0}


def test_summary_next_day_sends_again():
    store, gw = summary_store(), FakeGateway()
    run_scheduled_sms(store, gw, SUMMARY_ON, EVENING)
    run_scheduled_sms(store, gw, SUMMARY_ON, datetime(2026, 10, 17, 17, 0, 0))
    assert len(gw.sent) == 4


def test_summary_failed_phone_does_not_stop_other_phone():
    store, gw = summary_store(), FakeGateway(raise_phones={"0199"})
    result = run_scheduled_sms(store, gw, SUMMARY_ON, EVENING)
    assert result["summary"] == 1
    assert [e.status for e in store.sms_log] == ["failed", "sent"]
