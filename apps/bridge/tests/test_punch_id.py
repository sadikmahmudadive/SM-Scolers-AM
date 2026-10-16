import pytest

from bridge.punch_id import punch_id
from conftest import load_cases

_CASES = load_cases()


@pytest.mark.parametrize(
    "case", _CASES["punchId"], ids=lambda c: f"{c['personId']}-{c['timestamp']}"
)
def test_punch_id(case):
    assert punch_id(case["personId"], case["timestamp"]) == case["expected"]
