"""One sync cycle: device punches -> stored punches -> SMS policy."""

import dataclasses
from datetime import datetime, timedelta
from typing import Protocol

from bridge.models import (
    BridgeSettings,
    CycleResult,
    Person,
    PunchFlags,
    RawPunch,
    Schedule,
    SmsLogEntry,
    SmsSettings,
    StoredPunch,
)
from bridge.punch_id import punch_id
from bridge.rules import direction_from_status, evaluate_punch
from bridge.sms import SmsGateway, build_sms_body
from bridge.store import PunchStore

TS_FORMAT = "%Y-%m-%d %H:%M:%S"


class ZkSource(Protocol):
    def get_attendance(self) -> list[RawPunch]: ...


def _recipients(person: Person) -> list[str]:
    phones = [person.phone]
    if person.kind == "student":
        phones += [person.father_phone, person.mother_phone]
    unique: list[str] = []
    for phone in phones:
        if phone and phone not in unique:
            unique.append(phone)
    return unique


def _notify(
    store: PunchStore,
    gateway: SmsGateway,
    sms: SmsSettings,
    result: CycleResult,
    punch: StoredPunch,
    person: Person,
    schedule: Schedule | None,
    flags: PunchFlags,
    stale: bool,
) -> None:
    if not sms.sms_enabled or flags.duplicate:
        return
    recipients = _recipients(person)
    if not recipients:
        return

    body_schedule = schedule
    if flags.late:
        kind, template = "late", sms.late_template
    elif flags.early_leave and sms.early_leave_enabled:
        kind, template = "early", sms.early_leave_template
        # The early-leave template's {end} is the dismissal time.
        if schedule is not None and schedule.dismissal is not None:
            body_schedule = dataclasses.replace(schedule, end=schedule.dismissal)
    else:
        kind, template = "normal", sms.normal_template

    body = build_sms_body(template, punch, person, body_schedule)
    for phone in recipients:
        if stale:
            status = "skipped-stale"
            result.sms_skipped_stale += 1
        elif gateway.send(phone, body):
            status = "sent"
            result.sms_sent += 1
        else:
            status = "failed"
        store.log_sms(
            SmsLogEntry(
                person_id=person.id,
                phone=phone,
                body=body,
                kind=kind,
                status=status,
                punch_id=punch.id,
                ts=punch.ts,
            )
        )


def run_cycle(
    zk: ZkSource,
    device_id: str,
    store: PunchStore,
    gateway: SmsGateway,
    settings: BridgeSettings,
    sms: SmsSettings,
    now: datetime,
) -> CycleResult:
    """Store every punch not yet stored (catch-up) and text only fresh ones.

    `now` is naive local time. Device errors propagate to the caller.
    """
    result = CycleResult()
    raw_punches = zk.get_attendance()
    seen = set(store.existing_punch_ids())
    stale_after = timedelta(minutes=settings.stale_sms_window_min)

    pending: list[tuple[str, RawPunch]] = []
    for raw in raw_punches:
        pid = punch_id(raw.user_id, raw.timestamp)
        if pid in seen:
            continue
        seen.add(pid)
        pending.append((pid, raw))
    pending.sort(key=lambda item: item[1].timestamp)

    for pid, raw in pending:
        try:
            punch_dt = datetime.strptime(raw.timestamp, TS_FORMAT)
        except ValueError as exc:
            result.errors.append(f"{pid}: {exc}")
            continue

        person = store.get_person(raw.user_id)
        found = store.get_schedule_for(person) if person is not None else None
        schedule_id, schedule = found if found is not None else (None, None)
        date = raw.timestamp[:10]
        flags = evaluate_punch(
            raw.timestamp[11:],
            schedule,
            store.previous_punch_minutes_ago(raw.user_id, raw.timestamp),
            store.is_holiday(date),
        )
        punch = StoredPunch(
            id=pid,
            person_id=raw.user_id,
            ts=raw.timestamp,
            date=date,
            status=raw.status,
            direction=direction_from_status(raw.status),
            device_id=device_id,
            late=flags.late,
            early_leave=flags.early_leave,
            schedule_id=schedule_id,
        )
        try:
            store.save_punch(punch)
        except Exception as exc:  # one bad write must not stop the cycle
            result.errors.append(f"{pid}: {exc}")
            continue
        result.new_punches += 1

        if person is None:
            continue
        _notify(
            store,
            gateway,
            sms,
            result,
            punch,
            person,
            schedule,
            flags,
            stale=now - punch_dt > stale_after,
        )
    return result
