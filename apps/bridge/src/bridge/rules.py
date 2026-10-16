"""Pure punch rules. Must behave identically to packages/shared/src/rules.ts."""

from bridge.models import PunchFlags, Schedule

# A punch within this many minutes of the previous one is a duplicate scan.
DUPLICATE_WINDOW_MIN = 5


def _to_seconds(hhmm: str) -> int:
    """Seconds since midnight for "HH:mm" or "HH:mm:ss"."""
    parts = hhmm.split(":")
    h, m, s = (int(parts[i]) if i < len(parts) else 0 for i in range(3))
    return h * 3600 + m * 60 + s


def evaluate_punch(
    time: str,
    schedule: Schedule | None,
    previous_punch_minutes_ago: int | None,
    is_holiday: bool,
) -> PunchFlags:
    # Duplicate is computed first and independently of holiday/schedule.
    duplicate = (
        previous_punch_minutes_ago is not None
        and previous_punch_minutes_ago < DUPLICATE_WINDOW_MIN
    )

    if duplicate or is_holiday or schedule is None:
        return PunchFlags(late=False, early_leave=False, duplicate=duplicate)

    t = _to_seconds(time)
    is_first_punch = previous_punch_minutes_ago is None

    late = is_first_punch and t > _to_seconds(schedule.end) + schedule.grace_min * 60
    early_leave = (
        not is_first_punch
        and schedule.dismissal is not None
        and t < _to_seconds(schedule.dismissal)
    )
    return PunchFlags(late=late, early_leave=early_leave, duplicate=duplicate)


def direction_from_status(raw: str) -> str:
    """Device status: 1/2/5 are check-out; 0/3/4 and anything else are "in"."""
    return "out" if raw in ("1", "2", "5") else "in"
