"""Deterministic attendance document id."""

import re


def punch_id(person_id: str, timestamp: str) -> str:
    """`<person_id>_<timestamp digits only>`."""
    return f"{person_id}_{re.sub(r'\D', '', timestamp)}"
