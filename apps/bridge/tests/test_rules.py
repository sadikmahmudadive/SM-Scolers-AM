import pytest

from bridge.models import PunchFlags
from bridge.rules import direction_from_status, evaluate_punch
from conftest import load_cases, schedule_from_json

_CASES = load_cases()


@pytest.mark.parametrize("case", _CASES["evaluate"], ids=lambda c: c["name"])
def test_evaluate_punch(case):
    inp = case["input"]
    got = evaluate_punch(
        inp["time"],
        schedule_from_json(inp["schedule"]),
        inp["previousPunchMinutesAgo"],
        inp["isHoliday"],
    )
    exp = case["expected"]
    assert got == PunchFlags(
        late=exp["late"], early_leave=exp["earlyLeave"], duplicate=exp["duplicate"]
    )


@pytest.mark.parametrize("case", _CASES["direction"], ids=lambda c: f"status-{c['status']!r}")
def test_direction_from_status(case):
    assert direction_from_status(case["status"]) == case["expected"]
