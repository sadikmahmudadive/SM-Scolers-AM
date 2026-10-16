"""Shared helpers: load the language-neutral punch-rule cases."""

import json
from pathlib import Path

import pytest

from bridge.models import Schedule

CASES_PATH = Path(__file__).resolve().parents[3] / "packages/shared/cases/punch-rules.json"


def load_cases() -> dict:
    assert CASES_PATH.exists(), f"shared punch-rule cases not found at {CASES_PATH}"
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def schedule_from_json(raw: dict | None) -> Schedule | None:
    """Map the camelCase JSON schedule to the snake_case dataclass."""
    if raw is None:
        return None
    return Schedule(
        start=raw["start"],
        end=raw["end"],
        grace_min=raw["graceMin"],
        dismissal=raw.get("dismissal"),
    )


@pytest.fixture(scope="session")
def cases() -> dict:
    return load_cases()
