"""ZkDevice against a fake pyzk (no hardware)."""

from datetime import datetime
from types import SimpleNamespace

import pytest

from bridge.models import DeviceUser, RawPunch
from bridge.zk_device import ZkDevice


class FakeConn:
    def __init__(self, events, attendance=(), users=(), fail_in=None, device_time=None):
        self.events = events
        self.device_time = device_time or datetime(2026, 10, 16, 9, 0, 0)
        self._attendance = list(attendance)
        self._users = list(users)
        self.fail_in = fail_in

    def _maybe_fail(self, name):
        if self.fail_in == name:
            raise OSError(f"{name} failed")

    def disable_device(self):
        self.events.append("disable")
        self._maybe_fail("disable")

    def get_attendance(self):
        self.events.append("read")
        self._maybe_fail("read")
        return self._attendance

    def get_time(self):
        self.events.append("time")
        self._maybe_fail("time")
        return self.device_time

    def get_users(self):
        self.events.append("read_users")
        self._maybe_fail("read_users")
        return self._users

    def enable_device(self):
        self.events.append("enable")

    def disconnect(self):
        self.events.append("disconnect")


class FakeZKClass:
    """Stands in for pyzk's `ZK`; records constructor args and the call order."""

    def __init__(self, events, conn, connect_error=None):
        self.events = events
        self.conn = conn
        self.connect_error = connect_error
        self.args = None

    def __call__(self, ip, port=4370, timeout=60):
        self.args = (ip, port, timeout)
        return self

    def connect(self):
        self.events.append("connect")
        if self.connect_error:
            raise self.connect_error
        return self.conn


@pytest.fixture
def events():
    return []


def install(monkeypatch, events, **conn_kwargs):
    conn = FakeConn(events, **conn_kwargs)
    fake = FakeZKClass(events, conn)
    monkeypatch.setattr("bridge.zk_device.ZK", fake)
    return fake


def test_get_attendance_maps_records_and_follows_connection_discipline(monkeypatch, events):
    records = [
        SimpleNamespace(user_id="12", timestamp=datetime(2026, 10, 16, 8, 21, 21), status=0),
        SimpleNamespace(user_id=7, timestamp=datetime(2026, 10, 16, 15, 0, 0), status=1),
    ]
    fake = install(monkeypatch, events, attendance=records)

    punches = ZkDevice("192.168.1.201", 4370, 5).get_attendance()

    assert punches == [
        RawPunch("12", "2026-10-16 08:21:21", "0"),
        RawPunch("7", "2026-10-16 15:00:00", "1"),
    ]
    assert fake.args == ("192.168.1.201", 4370, 5)
    assert events == ["connect", "disable", "read", "time", "enable", "disconnect"]


def test_get_attendance_reenables_and_disconnects_when_read_fails(monkeypatch, events):
    install(monkeypatch, events, fail_in="read")
    with pytest.raises(OSError, match="read failed"):
        ZkDevice("1.2.3.4", 4370, 5).get_attendance()
    assert events == ["connect", "disable", "read", "enable", "disconnect"]


def test_get_attendance_cleans_up_when_disable_fails(monkeypatch, events):
    install(monkeypatch, events, fail_in="disable")
    with pytest.raises(OSError):
        ZkDevice("1.2.3.4", 4370, 5).get_attendance()
    assert events[-2:] == ["enable", "disconnect"]


def test_get_attendance_disconnects_even_if_enable_fails(monkeypatch, events):
    fake = install(monkeypatch, events, attendance=[])

    def bad_enable():
        events.append("enable")
        raise OSError("enable failed")

    fake.conn.enable_device = bad_enable
    # cleanup errors are swallowed: the read itself succeeded
    assert ZkDevice("1.2.3.4", 4370, 5).get_attendance() == []
    assert events[-1] == "disconnect"


def test_connect_failure_propagates_without_cleanup(monkeypatch, events):
    fake = install(monkeypatch, events)
    fake.connect_error = TimeoutError("no route")
    with pytest.raises(TimeoutError):
        ZkDevice("1.2.3.4", 4370, 5).get_attendance()
    assert events == ["connect"]


def test_get_users_maps_and_cleans_up(monkeypatch, events):
    users = [
        SimpleNamespace(user_id="12", name="Rahim"),
        SimpleNamespace(user_id=13, name="Karim"),
    ]
    install(monkeypatch, events, users=users)
    assert ZkDevice("1.2.3.4", 4370, 5).get_users() == [
        DeviceUser("12", "Rahim"),
        DeviceUser("13", "Karim"),
    ]
    assert events == ["connect", "disable", "read_users", "enable", "disconnect"]


def test_get_users_disconnects_on_error(monkeypatch, events):
    install(monkeypatch, events, fail_in="read_users")
    with pytest.raises(OSError):
        ZkDevice("1.2.3.4", 4370, 5).get_users()
    assert events[-2:] == ["enable", "disconnect"]


def test_get_attendance_records_the_device_clock(monkeypatch, events):
    install(monkeypatch, events, device_time=datetime(2026, 10, 16, 9, 7, 0))
    dev = ZkDevice("1.2.3.4", 4370, 5)
    assert dev.device_time is None
    dev.get_attendance()
    assert dev.device_time == datetime(2026, 10, 16, 9, 7, 0)


def test_a_failing_clock_read_never_breaks_the_attendance_read(monkeypatch, events):
    records = [SimpleNamespace(user_id="12", timestamp=datetime(2026, 10, 16, 8, 0, 0), status=0)]
    install(monkeypatch, events, attendance=records, fail_in="time")
    dev = ZkDevice("1.2.3.4", 4370, 5)
    assert dev.get_attendance() == [RawPunch("12", "2026-10-16 08:00:00", "0")]
    assert dev.device_time is None
    assert events[-2:] == ["enable", "disconnect"]
