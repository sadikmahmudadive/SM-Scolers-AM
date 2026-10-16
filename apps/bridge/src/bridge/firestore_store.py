"""Firestore implementation of `PunchStore` and `ServiceStore` (spec section 5)."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from bridge.models import (
    TS_FORMAT,
    BridgeSettings,
    DeviceInfo,
    DeviceUser,
    Person,
    Schedule,
    SmsLogEntry,
    SmsSettings,
    StoredPunch,
)

# Firestore allows 500 writes per batch.
BATCH_LIMIT = 400
DEFAULT_ZK_PORT = 4370


class FirestoreStore:
    def __init__(self, client: firestore.Client, time_zone: str) -> None:
        self._db = client
        self._tz = ZoneInfo(time_zone)
        # Positive answers never change within a day, so remember them: the
        # scheduled-SMS pass asks these once per student per run.
        self._punch_days: set[tuple[str, str]] = set()
        self._sms_days: set[tuple[str, str, str]] = set()

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
        self._punch_days.add((punch.person_id, punch.date))

    # -- people / schedules / holidays ------------------------------------

    @staticmethod
    def _person_from(doc) -> Person:
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

    def get_person(self, person_id: str) -> Person | None:
        doc = self._db.collection("people").document(person_id).get()
        return self._person_from(doc) if doc.exists else None

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
        self._sms_days.add((entry.person_id, entry.kind, entry.ts[:10]))

    # -- ServiceStore: settings / devices ----------------------------------

    def _settings_doc(self, name: str) -> dict:
        doc = self._db.collection("settings").document(name).get()
        return (doc.to_dict() or {}) if doc.exists else {}

    @staticmethod
    def _pick(data: dict, mapping: dict[str, str]) -> dict:
        """Map camelCase document fields to snake_case kwargs, skipping
        missing/null ones so the dataclass defaults apply."""
        return {
            attr: data[key] for key, attr in mapping.items() if data.get(key) is not None
        }

    def get_bridge_settings(self) -> BridgeSettings:
        data = self._settings_doc("bridge")
        return BridgeSettings(
            **self._pick(
                data,
                {
                    "pollIntervalSec": "poll_interval_sec",
                    "zkTimeoutSec": "zk_timeout_sec",
                    "gsmPort": "gsm_port",
                    "gsmBaud": "gsm_baud",
                    "staleSmsWindowMin": "stale_sms_window_min",
                    "ussdCode": "ussd_code",
                },
            )
        )

    def get_sms_settings(self) -> SmsSettings:
        data = self._settings_doc("sms")
        kwargs = self._pick(
            data,
            {
                "normalTemplate": "normal_template",
                "lateTemplate": "late_template",
                "earlyLeaveTemplate": "early_leave_template",
                "smsEnabled": "sms_enabled",
                "earlyLeaveEnabled": "early_leave_enabled",
                "absentEnabled": "absent_enabled",
                "summaryEnabled": "summary_enabled",
                "summaryTime": "summary_time",
                "absentTemplate": "absent_template",
                "summaryTemplate": "summary_template",
            },
        )
        if data.get("adminPhones") is not None:
            kwargs["admin_phones"] = [str(p) for p in data["adminPhones"] if p]
        return SmsSettings(**kwargs)

    def list_devices(self) -> list[DeviceInfo]:
        devices = []
        for doc in sorted(self._db.collection("devices").stream(), key=lambda d: d.id):
            d = doc.to_dict() or {}
            if not d.get("ip"):
                continue
            devices.append(
                DeviceInfo(
                    id=doc.id,
                    name=d.get("name") or doc.id,
                    ip=d["ip"],
                    port=int(d.get("port") or DEFAULT_ZK_PORT),
                )
            )
        return devices

    # -- ServiceStore: commands / heartbeat --------------------------------

    def claim_pending_commands(self) -> list[dict]:
        # Equality-only query (no composite index); ordering is done here
        # because `createdAt` is optional and order_by would drop such docs.
        docs = list(
            self._db.collection("commands")
            .where(filter=FieldFilter("status", "==", "pending"))
            .stream()
        )
        epoch = datetime.min.replace(tzinfo=timezone.utc)
        docs.sort(key=lambda d: ((d.to_dict() or {}).get("createdAt") or epoch, d.id))
        claimed = []
        for doc in docs:
            doc.reference.update({"status": "running"})
            data = doc.to_dict() or {}
            data.update(id=doc.id, status="running")
            claimed.append(data)
        return claimed

    def finish_command(
        self, command_id: str, status: str, result: dict | None
    ) -> None:
        data: dict = {"status": status}
        if result is not None:
            data["result"] = result
        self._db.collection("commands").document(command_id).update(data)

    def write_heartbeat(
        self,
        version: str,
        carrier: str,
        gsm_signal: int,
        device_online: bool,
        now: datetime,
    ) -> None:
        self._db.collection("bridgeStatus").document("main").set(
            {
                "heartbeat": now.replace(tzinfo=self._tz),
                "version": version,
                "gsmSignal": gsm_signal,
                "carrier": carrier,
                "deviceOnline": device_online,
            }
        )

    # -- ServiceStore: attendance / people queries -------------------------

    def list_active_students(self) -> list[Person]:
        docs = (
            self._db.collection("people")
            .where(filter=FieldFilter("kind", "==", "student"))
            .where(filter=FieldFilter("active", "==", True))
            .stream()
        )
        return sorted((self._person_from(d) for d in docs), key=lambda p: p.id)

    def has_punch_on(self, person_id: str, date: str) -> bool:
        key = (person_id, date)
        if key in self._punch_days:
            return True
        found = any(
            True
            for _ in self._db.collection("attendance")
            .where(filter=FieldFilter("personId", "==", person_id))
            .where(filter=FieldFilter("date", "==", date))
            .select([])
            .limit(1)
            .stream()
        )
        if found:
            self._punch_days.add(key)
        return found

    def punch_counts_for(self, date: str) -> tuple[int, int]:
        people: set[str] = set()
        late = 0
        for doc in (
            self._db.collection("attendance")
            .where(filter=FieldFilter("date", "==", date))
            .select(["personId", "late"])
            .stream()
        ):
            d = doc.to_dict() or {}
            people.add(d.get("personId", ""))
            late += 1 if d.get("late") else 0
        return len(people), late

    def count_active_people(self) -> int:
        return sum(
            1
            for _ in self._db.collection("people")
            .where(filter=FieldFilter("active", "==", True))
            .select([])
            .stream()
        )

    def sms_logged(self, person_id: str | None, kind: str, date: str) -> bool:
        # Person-less entries (summary) are stored with personId "".
        pid = person_id or ""
        key = (pid, kind, date)
        if key in self._sms_days:
            return True
        # Equality-only (kind, personId): no composite index. The local-date
        # check is done here since `ts` is stored as an instant.
        docs = (
            self._db.collection("smsLog")
            .where(filter=FieldFilter("kind", "==", kind))
            .where(filter=FieldFilter("personId", "==", pid))
            .select(["ts"])
            .stream()
        )
        for doc in docs:
            ts = (doc.to_dict() or {}).get("ts")
            if ts is not None and ts.astimezone(self._tz).strftime("%Y-%m-%d") == date:
                self._sms_days.add(key)
                return True
        return False

    def upsert_device_users(self, users: list[DeviceUser]) -> int:
        wanted: dict[str, DeviceUser] = {}
        for user in users:
            if user.user_id and user.user_id not in wanted:
                wanted[user.user_id] = user
        refs = [self._db.collection("people").document(uid) for uid in wanted]
        existing = {
            snap.id: snap
            for start in range(0, len(refs), BATCH_LIMIT)
            for snap in self._db.get_all(refs[start : start + BATCH_LIMIT])
        }
        created = 0
        batch = self._db.batch()
        pending = 0
        for ref in refs:
            snap = existing.get(ref.id)
            if snap is not None and snap.exists:
                if (snap.to_dict() or {}).get("deviceEnrolled") is True:
                    continue
                batch.update(ref, {"deviceEnrolled": True})
            else:
                user = wanted[ref.id]
                batch.set(
                    ref,
                    {
                        "name": user.name or user.user_id,
                        "kind": "student",
                        "guardianUids": [],
                        "deviceEnrolled": True,
                        "active": True,
                        "createdAt": firestore.SERVER_TIMESTAMP,
                    },
                )
                created += 1
            pending += 1
            if pending >= BATCH_LIMIT:
                batch.commit()
                batch = self._db.batch()
                pending = 0
        if pending:
            batch.commit()
        return created
