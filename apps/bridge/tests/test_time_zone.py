"""An unknown zone name must never stop the bridge (it would crash-loop the service)."""

import logging

import pytest

from bridge.firestore_store import DEFAULT_TIME_ZONE, FirestoreStore, resolve_zone
from bridge.service import _load_time_zone


class _Doc:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return self._data


class _Client:
    """Just enough of firestore.Client for settings/app reads."""

    def __init__(self, app):
        self.app = app

    def collection(self, name):
        assert name == "settings"
        return self

    def document(self, name):
        assert name == "app"
        return self

    def get(self):
        return _Doc(self.app)


BAD = ["+06:00", "GMT+6", "Not/AZone", "../etc/passwd", ""]


def test_default_zone_is_asia_dhaka():
    assert DEFAULT_TIME_ZONE == "Asia/Dhaka"


@pytest.mark.parametrize("name", BAD)
def test_resolve_zone_falls_back_to_the_default(name, caplog):
    with caplog.at_level(logging.ERROR):
        assert resolve_zone(name).key == "Asia/Dhaka"
    if name:
        assert any("time zone" in r.getMessage() for r in caplog.records)


def test_resolve_zone_keeps_a_valid_name():
    assert resolve_zone("America/New_York").key == "America/New_York"
    assert resolve_zone("UTC").key == "UTC"


@pytest.mark.parametrize("name", BAD)
def test_store_constructor_never_raises_on_a_bad_zone(name):
    store = FirestoreStore(_Client(None), name)
    assert store._tz.key == "Asia/Dhaka"


@pytest.mark.parametrize("name", ["+06:00", "GMT+6", "Not/AZone"])
def test_load_time_zone_falls_back_on_an_unknown_zone(name):
    assert _load_time_zone(_Client({"timeZone": name})) == "Asia/Dhaka"


def test_load_time_zone_reads_a_valid_zone_and_defaults_when_missing():
    assert _load_time_zone(_Client({"timeZone": "Europe/London"})) == "Europe/London"
    assert _load_time_zone(_Client(None)) == "Asia/Dhaka"
    assert _load_time_zone(_Client({})) == "Asia/Dhaka"


def test_get_time_zone_keeps_the_current_zone_on_a_bad_name():
    client = _Client({"timeZone": "Europe/London"})
    store = FirestoreStore(client, "Asia/Dhaka")
    assert store.get_time_zone() == "Europe/London"
    client.app = {"timeZone": "+06:00"}
    assert store.get_time_zone() == "Europe/London"
