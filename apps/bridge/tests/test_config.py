import json

import pytest

from bridge.config import LocalConfig, load_local_config


def test_load_local_config(tmp_path):
    p = tmp_path / "local.json"
    p.write_text(json.dumps({"serviceAccountPath": "C:/k.json", "projectId": "hrm-1"}))
    assert load_local_config(p) == LocalConfig("C:/k.json", "hrm-1")


def test_load_local_config_requires_fields(tmp_path):
    p = tmp_path / "local.json"
    p.write_text(json.dumps({"projectId": "hrm-1"}))
    with pytest.raises(ValueError):
        load_local_config(p)


def test_make_firestore_client_initialises_once(monkeypatch):
    import firebase_admin
    from firebase_admin import credentials, firestore

    from bridge.config import make_firestore_client

    state = {"initialised": False, "init_calls": 0}

    def fake_get_app():
        if not state["initialised"]:
            raise ValueError("no app")
        return object()

    def fake_init(cred, options):
        state["initialised"] = True
        state["init_calls"] += 1
        state["options"] = options

    monkeypatch.setattr(firebase_admin, "get_app", fake_get_app)
    monkeypatch.setattr(firebase_admin, "initialize_app", fake_init)
    monkeypatch.setattr(credentials, "Certificate", lambda path: ("cert", path))
    monkeypatch.setattr(firestore, "client", lambda: "client")

    cfg = LocalConfig("C:/k.json", "hrm-1")
    assert make_firestore_client(cfg) == "client"
    assert make_firestore_client(cfg) == "client"
    assert state["init_calls"] == 1
    assert state["options"] == {"projectId": "hrm-1"}
