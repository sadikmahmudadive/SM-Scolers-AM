"""One-off migration: legacy Realtime Database -> Firestore (spec section 8).

Reads `users` and `attendance_logs` from the legacy RTDB and creates `people`
and `attendance` documents in Firestore under the same IDs. Writes are
CREATE-ONLY: a document that already exists is never touched (the bridge may
have written attendance with the same id, and admins edit people), so
re-running only adds what is missing. The RTDB is only ever read.

Usage:
    python firebase/migrate.py --service-account KEY.json --database-url URL \
        [--project-id ID] [--tz Asia/Dhaka] [--dry-run]

No network code runs at import time; firebase_admin is imported lazily.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from bridge.rules import direction_from_status

PEOPLE = "people"
ATTENDANCE = "attendance"
TS_FORMAT = "%Y-%m-%d %H:%M:%S"
FIRESTORE_BATCH_LIMIT = 500
SAMPLE_COUNT = 3


# -- converters --------------------------------------------------------------


def _s(value: Any) -> str:
    """Stringify a legacy value; None becomes an empty string."""
    return "" if value is None else str(value).strip()


def _kind(role: Any) -> str:
    role = _s(role).lower()
    if role == "student":
        return "student"
    if role == "teacher":
        return "teacher"
    return "staff"


def convert_user(uid: str, data: dict, now: datetime) -> dict:
    """Legacy `users/{uid}` -> Firestore `people/{uid}` (shape of PersonSchema).

    PersonSchema's contact/class fields are optional strings, so empty values
    are omitted rather than stored as "".
    """
    doc: dict[str, Any] = {"name": _s(data.get("name")), "kind": _kind(data.get("role"))}
    for target, source in (
        ("phone", "phone"),
        ("fatherPhone", "father_phone"),
        ("motherPhone", "mother_phone"),
        ("className", "class_name"),
        ("section", "section"),
    ):
        value = _s(data.get(source))
        if value:
            doc[target] = value
    doc.update(guardianUids=[], deviceEnrolled=False, active=True, createdAt=now)

    legacy = {
        key: value
        for key, value in (
            ("cardId", _s(data.get("card_id"))),
            ("studentType", _s(data.get("student_type"))),
            ("fatherName", _s(data.get("father_name"))),
            ("motherName", _s(data.get("mother_name"))),
        )
        if value
    }
    if legacy:
        doc["legacy"] = legacy
    return doc


def convert_log(key: str, data: dict, tz: ZoneInfo) -> tuple[str, dict]:
    """Legacy `attendance_logs/{key}` -> (doc id, Firestore `attendance` doc).

    Raises ValueError for a missing user_id or an unparsable/missing timestamp.
    """
    person_id = _s(data.get("user_id"))
    if not person_id:
        raise ValueError("missing user_id")
    raw_ts = data.get("timestamp")
    if not isinstance(raw_ts, str) or not raw_ts.strip():
        raise ValueError(f"missing timestamp: {raw_ts!r}")
    try:
        ts = datetime.strptime(raw_ts.strip(), TS_FORMAT).replace(tzinfo=tz)
    except ValueError:
        raise ValueError(f"unparsable timestamp: {raw_ts!r}") from None
    status = _s(data.get("status"))
    return key, {
        "personId": person_id,
        "ts": ts,
        "date": ts.strftime("%Y-%m-%d"),
        "status": status,
        "direction": direction_from_status(status),
        "deviceId": "migrated",
        "late": False,
        "earlyLeave": False,
    }


# -- source / destination ----------------------------------------------------


def normalise_rtdb(value: Any) -> dict[str, dict]:
    """RTDB returns a list when keys are small integers; normalise to a dict.

    List indexes become string keys; None (gap) entries are skipped.
    """
    if value is None:
        return {}
    if isinstance(value, list):
        return {str(i): v for i, v in enumerate(value) if v is not None}
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items() if v is not None}
    raise ValueError(f"unexpected RTDB payload type: {type(value).__name__}")


class LegacySource(Protocol):
    def read_users(self) -> dict[str, dict]: ...
    def read_logs(self) -> dict[str, dict]: ...


class FirestoreDest(Protocol):
    def write_batch(self, collection: str, docs: list[tuple[str, dict]]) -> None:
        """Create the given documents (they are known not to exist)."""

    def count(self, collection: str) -> int: ...

    def existing_ids(self, collection: str) -> set[str]:
        """Read-only: ids of all documents currently in the collection."""


class StaticSource:
    """LegacySource over data that has already been read (and normalised)."""

    def __init__(self, users: dict[str, dict], logs: dict[str, dict]) -> None:
        self._users, self._logs = users, logs

    def read_users(self) -> dict[str, dict]:
        return self._users

    def read_logs(self) -> dict[str, dict]:
        return self._logs


# -- runner ------------------------------------------------------------------


@dataclass
class MigrationReport:
    users_source: int = 0
    logs_source: int = 0
    # Created this run (always 0 in a dry run).
    users_written: int = 0
    logs_written: int = 0
    # Converted documents that do not exist yet (would be / were created).
    users_to_create: int = 0
    logs_to_create: int = 0
    # Converted documents skipped because the id already exists in Firestore.
    users_skipped_existing: int = 0
    logs_skipped_existing: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)
    users_dest_count: int | None = None
    logs_dest_count: int | None = None
    # First converted (id, doc) pairs per collection (documents that would be created).
    samples: dict[str, list[tuple[str, dict]]] = field(
        default_factory=lambda: {PEOPLE: [], ATTENDANCE: []}
    )


def _write_all(
    dest: FirestoreDest, collection: str, docs: list[tuple[str, dict]], batch_size: int
) -> int:
    for start in range(0, len(docs), batch_size):
        dest.write_batch(collection, docs[start : start + batch_size])
    return len(docs)


def run_migration(
    source: LegacySource,
    dest: FirestoreDest,
    tz_name: str,
    dry_run: bool,
    now: datetime,
    batch_size: int = FIRESTORE_BATCH_LIMIT,
) -> MigrationReport:
    tz = ZoneInfo(tz_name)
    report = MigrationReport()

    users = source.read_users()
    logs = source.read_logs()
    report.users_source = len(users)
    report.logs_source = len(logs)

    people: list[tuple[str, dict]] = []
    for uid, data in users.items():
        if not isinstance(data, dict):
            report.skipped.append((f"users/{uid}", "record is not an object"))
            continue
        people.append((uid, convert_user(uid, data, now)))

    attendance: list[tuple[str, dict]] = []
    for key, data in logs.items():
        try:
            if not isinstance(data, dict):
                raise ValueError("record is not an object")
            attendance.append(convert_log(key, data, tz))
        except ValueError as exc:
            report.skipped.append((f"attendance_logs/{key}", str(exc)))

    # Create-only: never touch a document that already exists. existing_ids is
    # read-only, so it is safe in a dry run too.
    existing_people = dest.existing_ids(PEOPLE)
    existing_logs = dest.existing_ids(ATTENDANCE)
    new_people = [(i, d) for i, d in people if i not in existing_people]
    new_logs = [(i, d) for i, d in attendance if i not in existing_logs]
    report.users_to_create = len(new_people)
    report.logs_to_create = len(new_logs)
    report.users_skipped_existing = len(people) - len(new_people)
    report.logs_skipped_existing = len(attendance) - len(new_logs)

    report.samples[PEOPLE] = new_people[:SAMPLE_COUNT]
    report.samples[ATTENDANCE] = new_logs[:SAMPLE_COUNT]

    if dry_run:
        return report

    report.users_written = _write_all(dest, PEOPLE, new_people, batch_size)
    report.logs_written = _write_all(dest, ATTENDANCE, new_logs, batch_size)
    report.users_dest_count = dest.count(PEOPLE)
    report.logs_dest_count = dest.count(ATTENDANCE)
    return report


# -- real Firebase adapter (only built by the CLI) ----------------------------


class _FirestoreDest:
    def __init__(self, client: Any) -> None:
        self._db = client

    def write_batch(self, collection: str, docs: list[tuple[str, dict]]) -> None:
        # create() (not set) so a document that appears concurrently is never overwritten.
        for start in range(0, len(docs), FIRESTORE_BATCH_LIMIT):
            batch = self._db.batch()
            for doc_id, doc in docs[start : start + FIRESTORE_BATCH_LIMIT]:
                batch.create(self._db.collection(collection).document(doc_id), doc)
            batch.commit()

    def count(self, collection: str) -> int:
        result = self._db.collection(collection).count().get()
        return int(result[0][0].value)

    def existing_ids(self, collection: str) -> set[str]:
        return {doc.id for doc in self._db.collection(collection).select([]).stream()}


def print_report(report: MigrationReport, dry_run: bool, out=print) -> None:
    out("")
    out("DRY RUN: nothing was written." if dry_run else "Migration complete.")
    out(f"people     source: {report.users_source}")
    out(f"attendance source: {report.logs_source}")
    verb = "would create" if dry_run else "created"
    out(
        f"people     {verb}: {report.users_to_create}, "
        f"already existing (untouched): {report.users_skipped_existing}"
    )
    out(
        f"attendance {verb}: {report.logs_to_create}, "
        f"already existing (untouched): {report.logs_skipped_existing}"
    )
    if dry_run:
        for collection in (PEOPLE, ATTENDANCE):
            out(f"first {SAMPLE_COUNT} {collection} docs that would be created:")
            for doc_id, doc in report.samples[collection]:
                out(f"  {doc_id}: {doc}")
    else:
        out(f"people     destination count: {report.users_dest_count}")
        out(f"attendance destination count: {report.logs_dest_count}")
    out(f"skipped records: {len(report.skipped)}")
    if report.skipped:
        out("WARNING: some records were skipped (first 10):")
        for key, reason in report.skipped[:10]:
            out(f"  {key}: {reason}")
    out("The Realtime Database data was NOT modified.")


def _fail(message: str, code: int) -> int:
    print(f"error: {message}", file=sys.stderr)
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy RTDB data to Firestore.")
    parser.add_argument("--service-account", required=True, help="path to service account JSON")
    parser.add_argument("--database-url", required=True, help="legacy RTDB URL")
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--tz", default="Asia/Dhaka", help="org time zone of legacy timestamps")
    parser.add_argument("--dry-run", action="store_true", help="read and convert, write nothing")
    args = parser.parse_args(argv)

    try:
        ZoneInfo(args.tz)
    except Exception:
        return _fail(f"unknown time zone {args.tz!r} (use an IANA name such as Asia/Dhaka)", 2)

    import firebase_admin
    from firebase_admin import credentials, db, firestore

    options: dict[str, str] = {"databaseURL": args.database_url}
    if args.project_id:
        options["projectId"] = args.project_id
    try:
        firebase_admin.initialize_app(credentials.Certificate(args.service_account), options)
    except Exception as exc:
        # Only the exception type: never echo anything derived from the key file.
        return _fail(f"could not initialise Firebase from the service account ({type(exc).__name__})", 2)

    # Read once, up front, so a failed read exits non-zero before anything is written.
    try:
        source = StaticSource(
            normalise_rtdb(db.reference("users").get()),
            normalise_rtdb(db.reference("attendance_logs").get()),
        )
    except Exception as exc:
        return _fail(f"could not read the legacy database: {type(exc).__name__}: {exc}", 2)

    # Needed even for --dry-run: existing_ids is a read-only listing.
    try:
        dest = _FirestoreDest(firestore.client())
    except Exception as exc:
        return _fail(f"could not create the Firestore client ({type(exc).__name__})", 2)

    try:
        report = run_migration(source, dest, args.tz, args.dry_run, datetime.now(timezone.utc))
    except Exception as exc:
        return _fail(f"migration failed: {type(exc).__name__}: {exc}", 1)
    print_report(report, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
