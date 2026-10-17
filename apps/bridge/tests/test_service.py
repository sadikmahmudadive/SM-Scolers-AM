import threading
from datetime import datetime, timedelta, timezone

from bridge import __version__
from bridge.heartbeat import beat
from bridge.models import (
    BridgeSettings,
    DeviceInfo,
    Person,
    RawPunch,
    Schedule,
    SmsSettings,
)
from bridge.service import ServiceRunner, org_now
from fakes import FakeGsm, FakeZk, InMemoryStore

NOW = datetime(2026, 10, 16, 8, 30, 0)
DEV1 = DeviceInfo(id="dev1", name="Gate", ip="10.0.0.1", port=4370)
DEV2 = DeviceInfo(id="dev2", name="Back", ip="10.0.0.2", port=4370)
SCHED = ("sch1", Schedule("08:00", "09:00", 10))


class ScriptedEvent(threading.Event):
    """A stop event whose wait() never blocks: it records the timeout and sets
    itself once `stop_after` waits have happened (or `stop_on_timeout` is seen)."""

    def __init__(self, stop_after: int | None = None, stop_on_timeout: float | None = None):
        super().__init__()
        self.waits: list[float | None] = []
        self.stop_after = stop_after
        self.stop_on_timeout = stop_on_timeout

    def wait(self, timeout=None):
        self.waits.append(timeout)
        if (self.stop_after is not None and len(self.waits) >= self.stop_after) or (
            self.stop_on_timeout is not None and timeout == self.stop_on_timeout
        ):
            self.set()
        return self.is_set()


class Mono:
    """Fake monotonic clock: advances by `step` on every read."""

    def __init__(self, t: float = 0.0, step: float = 0.0):
        self.t = t
        self.step = step

    def __call__(self) -> float:
        value = self.t
        self.t += self.step
        return value


def punch(uid="1", ts="2026-10-16 08:20:00"):
    return RawPunch(user_id=uid, timestamp=ts, status="0")


def make_runner(store, zks, gateway=None, clock=lambda tz: NOW, mono=None, **kw):
    """`zks` maps device id -> ZkSource. By default every monotonic read jumps
    far ahead, so no throttle (scheduled SMS, heartbeat) ever holds back a run."""
    gateway = gateway or FakeGsm()
    runner = ServiceRunner(
        store,
        gateway_factory=lambda port, baud: gateway,
        zk_factory=lambda device, settings: zks[device.id],
        clock=clock,
        monotonic=mono or Mono(step=1000),
        **kw,
    )
    return runner, gateway


def people_store(**kw):
    p = Person(
        id="1",
        name="Rahim",
        kind="student",
        class_name="Six",
        father_phone="0171",
        device_enrolled=True,
    )
    return InMemoryStore(people=[p], schedules={"1": SCHED}, **kw)


# -- run_once ---------------------------------------------------------------


def test_run_once_syncs_punches_commands_and_heartbeat():
    store = people_store(
        devices=[DEV1],
        commands=[
            {"id": "c1", "type": "test_sms", "payload": {"phone": "0199", "message": "hi"},
             "status": "pending"}
        ],
    )
    runner, gw = make_runner(store, {"dev1": FakeZk([punch()])})

    result = runner.run_once(NOW)

    assert result.new_punches == 1
    assert result.devices_ok == 1 and result.devices_failed == 0
    assert result.commands_processed == 1
    assert store.finished["c1"] == ("done", {"sent": True})
    assert ("0171", "Attendance: Rahim (1) at 08:20 AM") in gw.sent
    (hb,) = store.heartbeats
    assert hb["device_online"] is True
    assert hb["version"] == __version__
    assert (hb["carrier"], hb["gsm_signal"]) == ("Grameenphone", 21)
    assert hb["now"] == NOW


def test_run_once_runs_scheduled_sms_after_devices():
    store = people_store(
        devices=[DEV1],
        sms_settings=SmsSettings(sms_enabled=True, absent_enabled=True),
    )
    runner, gw = make_runner(store, {"dev1": FakeZk([])})
    result = runner.run_once(datetime(2026, 10, 16, 9, 30, 0))
    assert result.absent_sms == 1
    assert gw.sent == [("0171", "Absent: Rahim (1) was not present on 16/10/2026.")]


def test_scheduled_sms_checks_are_throttled():
    store = people_store(
        devices=[DEV1], sms_settings=SmsSettings(sms_enabled=True, absent_enabled=True)
    )
    calls = []
    real = store.list_active_students
    store.list_active_students = lambda: calls.append(1) or real()
    t0 = datetime(2026, 10, 16, 9, 30, 0)
    mono = Mono()
    runner, _ = make_runner(store, {"dev1": FakeZk([])}, mono=mono)
    runner.run_once(t0)
    mono.t += 10
    runner.run_once(t0 + timedelta(seconds=10))
    assert len(calls) == 1
    mono.t += runner.scheduled_interval_sec
    runner.run_once(t0 + timedelta(seconds=runner.scheduled_interval_sec))
    assert len(calls) == 2


def test_device_offline_sets_heartbeat_device_online_false():
    store = people_store(devices=[DEV1])
    zk = FakeZk([punch()], error=TimeoutError("device unreachable"))
    runner, gw = make_runner(store, {"dev1": zk})

    first = runner.run_once(NOW)
    assert first.devices_failed == 1 and first.devices_ok == 0
    assert store.heartbeats[-1]["device_online"] is False
    assert store.punches == {}

    # the device comes back: missed punches are back-filled
    zk.error = None
    second = runner.run_once(NOW + timedelta(seconds=10))
    assert second.new_punches == 1
    (stored,) = store.punches.values()
    assert stored.id == "1_20261016082000"
    assert stored.device_id == "dev1"
    assert store.heartbeats[-1]["device_online"] is True
    assert len(gw.sent) == 1


def test_one_device_failing_does_not_stop_other_devices():
    store = people_store(devices=[DEV1, DEV2])
    bad = FakeZk([], error=ConnectionError("down"))
    good = FakeZk([punch()])
    runner, _ = make_runner(store, {"dev1": bad, "dev2": good})

    result = runner.run_once(NOW)

    assert (result.devices_ok, result.devices_failed) == (1, 1)
    assert result.new_punches == 1
    (stored,) = store.punches.values()
    assert stored.device_id == "dev2"
    # at least one device read OK -> online
    assert store.heartbeats[-1]["device_online"] is True


def test_no_devices_is_offline_but_still_beats_and_runs_commands():
    store = people_store(
        commands=[{"id": "c1", "type": "read_inbox", "payload": {}, "status": "pending"}]
    )
    runner, _ = make_runner(store, {})
    result = runner.run_once(NOW)
    assert result.devices_ok == 0
    assert store.heartbeats[-1]["device_online"] is False
    assert store.finished["c1"][0] == "done"


def test_sync_command_without_a_device_records_an_error():
    store = people_store(
        commands=[{"id": "c1", "type": "sync_device_users", "payload": {}, "status": "pending"}]
    )
    runner, _ = make_runner(store, {})
    runner.run_once(NOW)
    assert store.finished["c1"][0] == "error"


def test_sync_command_uses_first_device():
    from bridge.models import DeviceUser

    store = people_store(
        devices=[DEV1, DEV2],
        commands=[{"id": "c1", "type": "sync_device_users", "payload": {}, "status": "pending"}],
    )
    first = FakeZk([], users=[DeviceUser("50", "New")])
    runner, _ = make_runner(store, {"dev1": first, "dev2": FakeZk([])})
    runner.run_once(NOW)
    assert store.finished["c1"] == ("done", {"created": 1, "total": 1})


def test_heartbeat_tolerates_gsm_failure():
    store = InMemoryStore()
    gw = FakeGsm()
    gw.signal_error = OSError("port busy")
    beat(store, gw, "9.9.9", True, NOW)
    hb = store.heartbeats[0]
    assert (hb["carrier"], hb["gsm_signal"], hb["device_online"], hb["version"]) == (
        "",
        0,
        True,
        "9.9.9",
    )


def test_command_stage_failure_does_not_prevent_heartbeat():
    store = people_store(devices=[DEV1])
    store.pending_command_ids = lambda: (_ for _ in ()).throw(ConnectionError("x"))
    runner, _ = make_runner(store, {"dev1": FakeZk([])})
    result = runner.run_once(NOW)
    assert result.errors
    assert len(store.heartbeats) == 1


def test_gateway_rebuilt_only_when_port_or_baud_changes():
    store = people_store(devices=[DEV1])
    built = []
    gw = FakeGsm()
    mono = Mono()
    runner = ServiceRunner(
        store,
        gateway_factory=lambda port, baud: built.append((port, baud)) or gw,
        zk_factory=lambda d, s: FakeZk([]),
        clock=lambda: NOW,
        monotonic=mono,
    )
    runner.run_once(NOW)
    runner.run_once(NOW)
    store.bridge_settings = BridgeSettings(gsm_port="COM7", gsm_baud=115200)
    mono.t += runner.settings_cache_sec  # settings are cached for one TTL window
    runner.run_once(NOW)
    assert built == [("", 9600), ("COM7", 115200)]


# -- run_forever ------------------------------------------------------------


def test_startup_aborts_without_sms_when_store_unreachable():
    store = people_store(devices=[DEV1], existing_ids_failures=3)
    runner, gw = make_runner(store, {"dev1": FakeZk([punch()])})
    stop = ScriptedEvent(stop_on_timeout=60)

    runner.run_forever(stop)

    assert store.existing_ids_calls == 3
    assert gw.sent == []
    assert store.punches == {} and store.heartbeats == []
    # 3 s between attempts, then the 60 s startup retry (waited on the stop event)
    assert stop.waits == [3, 3, 60]


def test_startup_retries_whole_startup_then_proceeds():
    store = people_store(devices=[DEV1], existing_ids_failures=3)
    runner, gw = make_runner(store, {"dev1": FakeZk([punch()])})
    stop = ScriptedEvent(stop_after=5)  # 3,3,60 (startup), then 10 (poll)... stop after 5th wait

    runner.run_forever(stop)

    assert stop.waits[:3] == [3, 3, 60]
    assert len(store.punches) == 1  # the cycle ran after the retry succeeded
    assert store.heartbeats


def test_startup_recovers_within_attempts_without_waiting_a_minute():
    store = people_store(devices=[DEV1], existing_ids_failures=2)
    runner, _ = make_runner(store, {"dev1": FakeZk([punch()])})
    stop = ScriptedEvent(stop_after=3)

    runner.run_forever(stop)

    assert stop.waits[:2] == [3, 3]
    assert 60 not in stop.waits
    assert len(store.punches) == 1


def test_run_forever_waits_poll_interval_between_cycles():
    store = people_store(
        devices=[DEV1], bridge_settings=BridgeSettings(poll_interval_sec=7)
    )
    runner, _ = make_runner(store, {"dev1": FakeZk([])})
    stop = ScriptedEvent(stop_after=3)
    runner.run_forever(stop)
    assert stop.waits == [7, 7, 7]
    assert len(store.heartbeats) == 3


def test_unexpected_exception_in_iteration_does_not_kill_loop():
    store = people_store(devices=[DEV1])
    real = store.get_bridge_settings
    state = {"n": 0}

    def flaky():
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("firestore hiccup")
        return real()

    store.get_bridge_settings = flaky
    runner, _ = make_runner(store, {"dev1": FakeZk([punch()])})
    stop = ScriptedEvent(stop_after=2)

    runner.run_forever(stop)

    assert state["n"] == 2
    assert len(store.punches) == 1  # iteration 2 worked after iteration 1 blew up
    assert len(store.heartbeats) == 1


def test_stop_set_before_start_exits_immediately():
    store = people_store(devices=[DEV1])
    runner, gw = make_runner(store, {"dev1": FakeZk([punch()])})
    stop = threading.Event()
    stop.set()
    runner.run_forever(stop)
    assert store.punches == {} and gw.sent == []


# -- stored-id cache, absent safety, clock, heartbeat, recovery ----------------


def test_stored_punch_ids_are_loaded_once_and_again_after_reconnect():
    store = people_store(devices=[DEV1])
    zk = FakeZk([punch()])
    runner, _ = make_runner(store, {"dev1": zk})

    for _ in range(3):
        runner.run_once(NOW)
    assert store.existing_ids_calls == 1  # one load, however many cycles

    zk.error = TimeoutError("unplugged")
    runner.run_once(NOW)
    runner.run_once(NOW)  # still offline: no reload on failed attempts
    assert store.existing_ids_calls == 1

    zk.error = None
    zk.punches = [punch(), punch(ts="2026-10-16 08:25:00")]
    result = runner.run_once(NOW)
    assert store.existing_ids_calls == 2  # reloaded once after offline -> online
    assert result.new_punches == 1  # the punch missed while offline is back-filled
    assert "1_20261016082500" in store.punches
    runner.run_once(NOW)
    assert store.existing_ids_calls == 2


def test_no_absent_sms_when_a_device_could_not_be_read_then_none_for_punchers():
    people = [
        Person(id=str(i), name=f"S{i}", kind="student", class_name="Six",
               father_phone=f"017{i}", device_enrolled=True)
        for i in (1, 2)
    ]
    store = InMemoryStore(
        people=people,
        schedules={p.id: SCHED for p in people},
        devices=[DEV1, DEV2],
        sms_settings=SmsSettings(sms_enabled=True, absent_enabled=True),
    )
    down = FakeZk([punch("1")], error=ConnectionError("down"))
    up = FakeZk([])
    runner, gw = make_runner(store, {"dev1": down, "dev2": up}, mono=Mono())
    late_morning = datetime(2026, 10, 16, 9, 30, 0)

    dirty = runner.run_once(late_morning)
    assert dirty.absent_sms == 0
    assert [p for p, _ in gw.sent] == []

    down.error = None  # device 1 is back and its punch for student 1 is back-filled
    clean = runner.run_once(late_morning)
    assert clean.new_punches == 1
    assert [p for p, _ in gw.sent] == ["0172"]  # only the student who never punched


def test_no_absent_sms_when_a_punch_could_not_be_saved():
    store = people_store(
        devices=[DEV1],
        sms_settings=SmsSettings(sms_enabled=True, absent_enabled=True),
        fail_save_ids={"1_20261016082000"},
    )
    runner, gw = make_runner(store, {"dev1": FakeZk([punch()])}, mono=Mono())
    result = runner.run_once(datetime(2026, 10, 16, 9, 30, 0))
    assert result.synced_cleanly is False
    assert gw.sent == []


def test_no_absent_sms_without_any_device():
    store = people_store(sms_settings=SmsSettings(sms_enabled=True, absent_enabled=True))
    runner, gw = make_runner(store, {}, mono=Mono())
    runner.run_once(datetime(2026, 10, 16, 9, 30, 0))
    assert gw.sent == []


def test_org_now_uses_the_organisation_zone_not_the_pc_zone():
    instant = datetime(2026, 10, 16, 20, 30, 0, tzinfo=timezone.utc)
    assert org_now("Asia/Dhaka", instant) == datetime(2026, 10, 17, 2, 30, 0)
    assert org_now("America/New_York", instant) == datetime(2026, 10, 16, 16, 30, 0)
    assert org_now("Asia/Dhaka", instant).tzinfo is None


def test_run_forever_asks_the_clock_for_the_stores_time_zone():
    store = people_store(devices=[DEV1], time_zone="America/New_York")
    seen = []
    runner, _ = make_runner(
        store, {"dev1": FakeZk([])}, clock=lambda tz: seen.append(tz) or NOW
    )
    runner.run_forever(ScriptedEvent(stop_after=2))
    # the startup gate (bounded id load) and the two iterations
    assert seen == ["America/New_York"] * 3
    store.time_zone = "Asia/Dhaka"  # a settings change is picked up on the next call
    assert runner._now() == NOW and seen[-1] == "Asia/Dhaka"


def test_heartbeat_is_throttled_but_written_on_device_state_change():
    store = people_store(devices=[DEV1])
    zk = FakeZk([])
    mono = Mono()
    runner, _ = make_runner(store, {"dev1": zk}, mono=mono)

    runner.run_once(NOW)
    mono.t += 5
    runner.run_once(NOW)
    mono.t += 5
    runner.run_once(NOW)
    assert len(store.heartbeats) == 1  # polls faster than the 30 s cadence

    zk.error = TimeoutError("x")  # state change: written immediately
    runner.run_once(NOW)
    assert len(store.heartbeats) == 2
    assert store.heartbeats[-1]["device_online"] is False

    mono.t += runner.heartbeat_interval_sec
    runner.run_once(NOW)
    assert len(store.heartbeats) == 3


def test_startup_marks_stranded_running_commands_as_error():
    store = people_store(
        devices=[DEV1],
        commands=[
            {"id": "stuck", "type": "ussd", "payload": {}, "status": "running"},
            {"id": "waiting", "type": "read_inbox", "payload": {}, "status": "pending"},
        ],
    )
    runner, _ = make_runner(store, {"dev1": FakeZk([])})
    runner.run_forever(ScriptedEvent(stop_after=1))
    assert store.finished["stuck"] == ("error", {"error": "bridge restarted"})
    assert store.finished["waiting"][0] == "done"  # pending ones still run


def test_no_recovery_while_the_store_is_unreachable():
    store = people_store(
        devices=[DEV1],
        existing_ids_failures=3,
        commands=[{"id": "stuck", "type": "ussd", "payload": {}, "status": "running"}],
    )
    runner, _ = make_runner(store, {"dev1": FakeZk([])})
    runner.run_forever(ScriptedEvent(stop_on_timeout=60))
    assert "stuck" not in store.finished


# -- automatic device-enrollment refresh --------------------------------------


def _enroll_store(**kw):
    people = [
        Person(id="1", name="A", kind="student", device_enrolled=False),
        Person(id="2", name="B", kind="student", device_enrolled=False),
        Person(id="3", name="C", kind="staff", device_enrolled=True),  # removed from devices
        Person(id="4", name="D", kind="student", device_enrolled=True),  # still on a device
    ]
    return InMemoryStore(people=people, devices=[DEV1, DEV2], **kw)


def _users(*ids):
    from bridge.models import DeviceUser

    return [DeviceUser(i, f"U{i}") for i in ids]


def _count_refreshes(store):
    calls = []
    real = store.refresh_enrollment
    store.refresh_enrollment = lambda ids: calls.append(set(ids)) or real(ids)
    return calls


def test_enrollment_refresh_uses_the_union_of_all_devices_and_never_creates_people():
    store = _enroll_store()
    zks = {"dev1": FakeZk([], users=_users("1", "99")), "dev2": FakeZk([], users=_users("2", "4"))}
    runner, _ = make_runner(store, zks)
    runner.run_once(NOW)  # the first clean iteration after startup refreshes
    enrolled = {pid: p.device_enrolled for pid, p in store.people.items()}
    assert enrolled == {"1": True, "2": True, "3": False, "4": True}
    assert "99" not in store.people  # unknown device ids are ignored
    # other fields untouched
    assert (store.people["3"].name, store.people["3"].kind) == ("C", "staff")


def test_enrollment_refresh_is_throttled():
    store = _enroll_store()
    calls = _count_refreshes(store)
    zks = {"dev1": FakeZk([], users=_users("1")), "dev2": FakeZk([], users=_users("2"))}
    mono = Mono()
    runner, _ = make_runner(store, zks, mono=mono)
    runner.run_once(NOW)
    mono.t += 600
    runner.run_once(NOW)
    assert len(calls) == 1
    mono.t += runner.enrollment_refresh_sec
    runner.run_once(NOW)
    assert len(calls) == 2
    assert calls[-1] == {"1", "2"}


def test_default_enrollment_interval_is_thirty_minutes():
    from bridge.service import ENROLLMENT_REFRESH_SEC

    assert ENROLLMENT_REFRESH_SEC == 1800
    runner, _ = make_runner(InMemoryStore(), {})
    assert runner.enrollment_refresh_sec == 1800


def test_enrollment_refresh_skipped_when_a_device_was_not_read_cleanly():
    store = _enroll_store()
    calls = _count_refreshes(store)
    down = FakeZk([], error=ConnectionError("down"), users=_users("2"))
    zks = {"dev1": FakeZk([], users=_users("1")), "dev2": down}
    mono = Mono()
    runner, _ = make_runner(store, zks, mono=mono)
    runner.run_once(NOW)
    assert calls == []
    assert store.people["4"].device_enrolled is True  # nobody flipped on partial data
    down.error = None
    mono.t += 10
    runner.run_once(NOW)  # the next clean iteration does it (the slot was not consumed)
    assert calls == [{"1", "2"}]


def test_enrollment_refresh_skipped_without_devices():
    store = InMemoryStore(people=[Person(id="1", name="A", kind="student", device_enrolled=True)])
    calls = _count_refreshes(store)
    runner, _ = make_runner(store, {})
    runner.run_once(NOW)
    assert calls == []
    assert store.people["1"].device_enrolled is True


def test_enrollment_refresh_skipped_when_reading_users_fails_and_retried_later():
    from bridge.service import ENROLLMENT_RETRY_SEC

    store = _enroll_store()
    calls = _count_refreshes(store)

    class UsersFail(FakeZk):
        fail = True

        def get_users(self):
            if UsersFail.fail:
                raise TimeoutError("user table read timed out")
            return super().get_users()

    zks = {"dev1": FakeZk([], users=_users("1")), "dev2": UsersFail([], users=_users("2"))}
    mono = Mono()
    runner, _ = make_runner(store, zks, mono=mono)
    result = runner.run_once(NOW)
    assert calls == []
    assert any("enrollment" in e for e in result.errors)
    UsersFail.fail = False
    mono.t += 10
    runner.run_once(NOW)
    assert calls == []  # waits for the retry gap, not every poll
    mono.t += ENROLLMENT_RETRY_SEC
    runner.run_once(NOW)
    assert calls == [{"1", "2"}]


def test_enrollment_refresh_skipped_when_every_device_lists_no_users():
    # An empty user table (reset terminal, glitch) must not un-enroll everyone.
    store = _enroll_store()
    calls = _count_refreshes(store)
    runner, _ = make_runner(store, {"dev1": FakeZk([]), "dev2": FakeZk([])})
    runner.run_once(NOW)
    assert calls == []
    assert store.people["4"].device_enrolled is True


def test_in_memory_refresh_enrollment_reports_the_change():
    store = _enroll_store()
    change = store.refresh_enrollment({"1", "4", "77"})
    assert change.enrolled == ("1",)
    assert change.unenrolled == ("3",)
    assert change.changed is True
    assert store.refresh_enrollment({"1", "4"}).changed is False


# -- summary only on a clean pass ----------------------------------------------


def test_summary_waits_for_a_clean_pass_then_is_sent_once():
    store = people_store(
        devices=[DEV1],
        sms_settings=SmsSettings(
            sms_enabled=True, summary_enabled=True, summary_time="17:00", admin_phones=["0199"]
        ),
    )
    zk = FakeZk([punch()], error=ConnectionError("down"))
    mono = Mono()
    runner, gw = make_runner(store, {"dev1": zk}, mono=mono)
    evening = datetime(2026, 10, 16, 17, 5, 0)

    dirty = runner.run_once(evening)
    assert dirty.summary_sms == 0
    assert gw.sent == [] and store.sms_log == []

    zk.error = None  # next iteration is clean and still the same day, after 17:00
    mono.t += 10
    clean = runner.run_once(evening.replace(minute=6))
    assert clean.summary_sms == 1
    summaries = [e for e in store.sms_log if e.kind == "summary"]
    assert [(e.phone, e.status) for e in summaries] == [("0199", "sent")]
    assert "Present 1" in summaries[0].body  # the back-filled punch is counted

    mono.t += runner.scheduled_interval_sec
    again = runner.run_once(evening.replace(minute=30))
    assert again.summary_sms == 0
    assert len([e for e in store.sms_log if e.kind == "summary"]) == 1


# -- settings cache (Firestore read volume) ------------------------------------


def _count_calls(store, *names):
    counts = {n: 0 for n in names}
    for n in names:
        real = getattr(store, n)

        def wrapped(*a, _real=real, _n=n, **k):
            counts[_n] += 1
            return _real(*a, **k)

        setattr(store, n, wrapped)
    return counts


def test_settings_and_devices_are_read_once_per_ttl_window_but_commands_every_poll():
    from bridge.service import SETTINGS_CACHE_SEC

    assert SETTINGS_CACHE_SEC == 60
    store = people_store(devices=[DEV1])
    counts = _count_calls(
        store, "get_bridge_settings", "get_sms_settings", "list_devices",
        "get_time_zone", "pending_command_ids",
    )
    mono = Mono()
    runner, _ = make_runner(store, {"dev1": FakeZk([])}, mono=mono)
    for _ in range(4):
        runner.run_once(runner._now())
        mono.t += 10
    assert counts == {
        "get_bridge_settings": 1, "get_sms_settings": 1, "list_devices": 1,
        "get_time_zone": 1, "pending_command_ids": 4,
    }
    mono.t += SETTINGS_CACHE_SEC  # the window has passed: re-read once
    runner.run_once(runner._now())
    runner.run_once(runner._now())
    assert counts["get_bridge_settings"] == 2 and counts["get_sms_settings"] == 2
    assert counts["list_devices"] == 2 and counts["get_time_zone"] == 2
    assert counts["pending_command_ids"] == 6


def test_a_settings_change_is_applied_after_the_ttl():
    store = people_store(devices=[DEV1], bridge_settings=BridgeSettings(poll_interval_sec=7))
    mono = Mono()
    runner, _ = make_runner(store, {"dev1": FakeZk([])}, mono=mono)
    runner.run_once(NOW)
    store.bridge_settings = BridgeSettings(poll_interval_sec=20)
    mono.t += 30
    runner.run_once(NOW)
    assert runner._poll_interval_sec == 7  # still cached
    mono.t += 60
    runner.run_once(NOW)
    assert runner._poll_interval_sec == 20


def test_a_failed_settings_read_is_not_cached():
    store = people_store(devices=[DEV1])
    real = store.get_sms_settings
    state = {"n": 0}

    def flaky():
        state["n"] += 1
        if state["n"] == 1:
            raise ConnectionError("hiccup")
        return real()

    store.get_sms_settings = flaky
    mono = Mono()
    runner, _ = make_runner(store, {"dev1": FakeZk([])}, mono=mono)
    try:
        runner.run_once(NOW)
    except ConnectionError:
        pass
    mono.t += 1
    runner.run_once(NOW)  # retried at once, not after the TTL
    assert state["n"] == 2


def test_startup_proves_the_store_is_reachable_with_a_bounded_load():
    store = people_store(devices=[DEV1])
    runner, _ = make_runner(store, {"dev1": FakeZk([])})
    runner.run_forever(ScriptedEvent(stop_after=1))
    # NOW is 2026-10-16: the startup load covers the last 7 days only.
    assert store.id_queries[0] == ("2026-10-09", None)
