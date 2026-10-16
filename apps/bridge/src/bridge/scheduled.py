"""Time-triggered SMS: absent-student alerts and the daily admin summary.

Ported from legacy `_scheduled_sms_check` / `_send_absent_notifications` /
`_send_daily_summary`. Unlike the legacy in-memory "sent today" flags, "already
sent" is read back from `smsLog`, so a restart never re-sends.
"""

import logging
from datetime import datetime, time, timedelta

from bridge.models import TS_FORMAT, BridgeSettings, Person, Schedule, SmsLogEntry, SmsSettings
from bridge.sms import SmsGateway
from bridge.store import ServiceStore

log = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d"
DISPLAY_DATE_FORMAT = "%d/%m/%Y"

_ABSENT_SAMPLE = {"name": "", "id": "", "date": ""}
_SUMMARY_SAMPLE = {"date": "", "present": 0, "absent": 0, "late": 0, "total": 0}


def _parse_hhmm(value: str | None) -> time | None:
    try:
        return datetime.strptime(value, "%H:%M").time()  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _renders(template: str, sample: dict, kind: str) -> bool:
    """Check a template once per pass so a bad one logs one error, not one per student."""
    try:
        template.format_map(sample)
        return True
    except Exception as exc:
        log.error("%s sms template is invalid (%s); nothing sent", kind, exc)
        return False


def _send_and_log(
    store: ServiceStore,
    gateway: SmsGateway,
    person_id: str,
    phone: str,
    body: str,
    kind: str,
    now: datetime,
) -> bool:
    """Send one SMS (gateway errors are caught) and record it. True if sent."""
    try:
        sent = bool(gateway.send(phone, body))
    except Exception as exc:
        log.warning("%s sms to %s raised: %s", kind, phone, exc)
        sent = False
    try:
        store.log_sms(
            SmsLogEntry(
                person_id=person_id,
                phone=phone,
                body=body,
                kind=kind,
                status="sent" if sent else "failed",
                punch_id=None,
                ts=now.strftime(TS_FORMAT),
            )
        )
    except Exception:
        log.exception("could not log %s sms to %s", kind, phone)
    return sent


def _absent_phone(student: Person) -> str:
    return student.father_phone or student.mother_phone or student.phone


def _in_absent_window(schedule: Schedule | None, now: datetime, stale_window_min: int) -> bool:
    """now is in (end + grace, dismissal if set else end + grace + stale window]."""
    if schedule is None:
        return False
    end = _parse_hhmm(schedule.end)
    if end is None:
        return False
    cutoff = datetime.combine(now.date(), end) + timedelta(minutes=schedule.grace_min)
    dismissal = _parse_hhmm(schedule.dismissal)
    if dismissal is not None:
        upper = datetime.combine(now.date(), dismissal)
    else:
        upper = cutoff + timedelta(minutes=stale_window_min)
    return cutoff < now <= upper


def _send_absent(
    store: ServiceStore,
    gateway: SmsGateway,
    sms: SmsSettings,
    now: datetime,
    stale_window_min: int,
) -> int:
    if not _renders(sms.absent_template, _ABSENT_SAMPLE, "absent"):
        return 0
    date = now.strftime(DATE_FORMAT)
    display_date = now.strftime(DISPLAY_DATE_FORMAT)

    # Cheapest checks first: enrolment, phone, then the schedule window (one
    # schedule lookup per class/department per pass).
    schedules: dict[str, tuple[str, Schedule] | None] = {}
    due: list[tuple[Person, str]] = []
    for student in store.list_active_students():
        phone = _absent_phone(student)
        if not student.device_enrolled or not phone:
            continue
        try:
            key = student.class_name or student.department_id
            if key is None:
                found = store.get_schedule_for(student)
            else:
                if key not in schedules:
                    schedules[key] = store.get_schedule_for(student)
                found = schedules[key]
            if _in_absent_window(found[1] if found else None, now, stale_window_min):
                due.append((student, phone))
        except Exception:
            log.exception("absent sms schedule lookup for %s failed", student.id)
    if not due:
        return 0

    punched = store.punched_person_ids(date)  # one query for the whole pass
    sent_count = 0
    for student, phone in due:
        if student.id in punched:
            continue
        try:
            if store.sms_logged(student.id, "absent", date):
                continue
            body = sms.absent_template.format_map(
                {"name": student.name, "id": student.id, "date": display_date}
            )
            if _send_and_log(store, gateway, student.id, phone, body, "absent", now):
                sent_count += 1
        except Exception:
            log.exception("absent sms for %s failed", student.id)
    return sent_count


def _send_summary(
    store: ServiceStore, gateway: SmsGateway, sms: SmsSettings, now: datetime
) -> int:
    summary_at = _parse_hhmm(sms.summary_time)
    admin_phones = [p for p in sms.admin_phones if p]
    if summary_at is None or not admin_phones or now.time() < summary_at:
        return 0
    if not _renders(sms.summary_template, _SUMMARY_SAMPLE, "summary"):
        return 0
    date = now.strftime(DATE_FORMAT)
    if store.sms_logged(None, "summary", date):
        return 0
    present, late = store.punch_counts_for(date)
    total = store.count_active_people()
    body = sms.summary_template.format_map(
        {
            "date": now.strftime(DISPLAY_DATE_FORMAT),
            "present": present,
            "absent": max(total - present, 0),
            "late": late,
            "total": total,
        }
    )
    # Person-less entries use an empty personId (the smsLog schema requires one).
    return sum(
        _send_and_log(store, gateway, "", phone, body, "summary", now)
        for phone in admin_phones
    )


def run_scheduled_sms(
    store: ServiceStore,
    gateway: SmsGateway,
    sms: SmsSettings,
    now: datetime,
    stale_sms_window_min: int = BridgeSettings().stale_sms_window_min,
    *,
    allow_absent: bool = True,
) -> dict[str, int]:
    """Send whatever absent/summary SMS are due at `now` (naive local time).

    Absent SMS go only to enrolled active students with no punch today, and only
    while `now` is inside (end + grace, dismissal or end + grace + stale window];
    `allow_absent=False` skips them (the caller could not trust today's punches).
    Returns how many were sent per kind. Safe to call repeatedly: each kind is
    sent at most once per person per local date.
    """
    counts = {"absent": 0, "summary": 0}
    if not sms.sms_enabled:
        return counts
    date = now.strftime(DATE_FORMAT)
    try:
        if store.is_holiday(date):
            return counts
        if sms.absent_enabled and allow_absent:
            counts["absent"] = _send_absent(store, gateway, sms, now, stale_sms_window_min)
    except Exception:
        log.exception("absent sms check failed")
    try:
        if sms.summary_enabled:
            counts["summary"] = _send_summary(store, gateway, sms, now)
    except Exception:
        log.exception("summary sms failed")
    return counts
