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
