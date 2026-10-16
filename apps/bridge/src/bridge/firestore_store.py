"""Firestore implementation of `PunchStore` (documents per spec section 5)."""

from datetime import datetime
from zoneinfo import ZoneInfo

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from bridge.models import TS_FORMAT, Person, Schedule, SmsLogEntry, StoredPunch


class FirestoreStore:
    def __init__(self, client: firestore.Client, time_zone: str) -> None:
        self._db = client
        self._tz = ZoneInfo(time_zone)

    def _to_dt(self, ts: str) -> datetime:
        """Naive local device time -> tz-aware datetime in the org time zone."""
        return datetime.strptime(ts, TS_FORMAT).replace(tzinfo=self._tz)

    # -- attendance --------------------------------------------------------

    def existing_punch_ids(self) -> set[str]:
        return {doc.id for doc in self._db.collection("attendance").select([]).stream()}

    def previous_punch_minutes_ago(self, person_id: str, ts: str) -> int | None:
        ts_dt = self._to_dt(ts)
        query = (
            self._db.collection("attendance")
            .where(filter=FieldFilter("personId", "==", person_id))
            .where(filter=FieldFilter("ts", "<", ts_dt))
            .order_by("ts", direction=firestore.Query.DESCENDING)
            .limit(1)
        )
        for doc in query.stream():
            data = doc.to_dict() or {}
            if data.get("date") != ts[:10]:
                return None
            return int((ts_dt - data["ts"]).total_seconds() // 60)
        return None

    def save_punch(self, punch: StoredPunch) -> None:
        data: dict = {
            "personId": punch.person_id,
            "ts": self._to_dt(punch.ts),
            "date": punch.date,
            "status": punch.status,
            "direction": punch.direction,
            "deviceId": punch.device_id,
            "late": punch.late,
            "earlyLeave": punch.early_leave,
        }
        if punch.schedule_id is not None:
            data["scheduleId"] = punch.schedule_id
        self._db.collection("attendance").document(punch.id).set(data)

    # -- people / schedules / holidays ------------------------------------

    def get_person(self, person_id: str) -> Person | None:
        doc = self._db.collection("people").document(person_id).get()
        if not doc.exists:
            return None
        d = doc.to_dict() or {}
        return Person(
            id=doc.id,
            name=d.get("name", ""),
            kind=d.get("kind", "staff"),
            phone=d.get("phone") or "",
            father_phone=d.get("fatherPhone") or "",
            mother_phone=d.get("motherPhone") or "",
            class_name=d.get("className") or "",
            section=d.get("section") or "",
            department_id=d.get("departmentId"),
            manager_id=d.get("managerId"),
            guardian_uids=list(d.get("guardianUids") or []),
            device_enrolled=bool(d.get("deviceEnrolled", False)),
            active=bool(d.get("active", True)),
        )

    def get_schedule_for(self, person: Person) -> tuple[str, Schedule] | None:
        key = person.class_name or person.department_id
        if not key:
            return None
        docs = (
            self._db.collection("schedules")
            .where(filter=FieldFilter("appliesTo", "array_contains", key))
            .stream()
        )
        for doc in sorted(docs, key=lambda d: d.id):
            d = doc.to_dict() or {}
            if "start" not in d or "end" not in d:
                continue
            return (
                doc.id,
                Schedule(
                    start=d["start"],
                    end=d["end"],
                    grace_min=int(d.get("graceMin") or 0),
                    dismissal=d.get("dismissal"),
                ),
            )
        return None

    def is_holiday(self, date: str) -> bool:
        return self._db.collection("holidays").document(date).get().exists

    # -- smsLog ------------------------------------------------------------

    def log_sms(self, entry: SmsLogEntry) -> None:
        data: dict = {
            "personId": entry.person_id,
            "phone": entry.phone,
            "body": entry.body,
            "kind": entry.kind,
            "status": entry.status,
            "ts": self._to_dt(entry.ts),
        }
        if entry.punch_id is not None:
            data["punchId"] = entry.punch_id
        self._db.collection("smsLog").add(data)
