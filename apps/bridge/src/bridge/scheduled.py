"""Time-triggered SMS: absent-student alerts and the daily admin summary.

Ported from legacy `_scheduled_sms_check` / `_send_absent_notifications` /
`_send_daily_summary`. Unlike the legacy in-memory "sent today" flags, "already
sent" is read back from `smsLog`, so a restart never re-sends.
"""

import logging
from datetime import datetime, time, timedelta

from bridge.models import TS_FORMAT, Person, SmsLogEntry, SmsSettings
from bridge.sms import SmsGateway
from bridge.store import ServiceStore

log = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d"
DISPLAY_DATE_FORMAT = "%d/%m/%Y"


def _parse_hhmm(value: str) -> time | None:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        return None


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


def _is_due_absent(store: ServiceStore, student: Person, now: datetime) -> bool:
    found = store.get_schedule_for(student)
    if found is None:
        return False
    schedule = found[1]
    end = _parse_hhmm(schedule.end)
    if end is None:
        return False
    cutoff = datetime.combine(now.date(), end) + timedelta(minutes=schedule.grace_min)
    return now > cutoff


def _send_absent(
    store: ServiceStore, gateway: SmsGateway, sms: SmsSettings, now: datetime
) -> int:
    date = now.strftime(DATE_FORMAT)
    display_date = now.strftime(DISPLAY_DATE_FORMAT)
    sent_count = 0
    for student in store.list_active_students():
        try:
            phone = _absent_phone(student)
            if not phone:
                continue
            if store.has_punch_on(student.id, date):
                continue
            if store.sms_logged(student.id, "absent", date):
                continue
            if not _is_due_absent(store, student, now):
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
    store: ServiceStore, gateway: SmsGateway, sms: SmsSettings, now: datetime
) -> dict[str, int]:
    """Send whatever absent/summary SMS are due at `now` (naive local time).

    Returns how many were sent per kind. Safe to call every few minutes: each
    kind is sent at most once per person per local date.
    """
    counts = {"absent": 0, "summary": 0}
    if not sms.sms_enabled:
        return counts
    date = now.strftime(DATE_FORMAT)
    try:
        if store.is_holiday(date):
            return counts
        if sms.absent_enabled:
            counts["absent"] = _send_absent(store, gateway, sms, now)
    except Exception:
        log.exception("absent sms check failed")
    try:
        if sms.summary_enabled:
            counts["summary"] = _send_summary(store, gateway, sms, now)
    except Exception:
        log.exception("summary sms failed")
    return counts
