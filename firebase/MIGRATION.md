# Migrating legacy data (Realtime Database to Firestore)

`firebase/migrate.py` copies the legacy RTDB `users` and `attendance_logs`
into the Firestore `people` and `attendance` collections. It only reads the
RTDB; the legacy data is never modified or deleted.

Writes are create-only: a document whose id already exists in Firestore is
never touched.

## Prerequisites

- A service account JSON key with access to both the legacy RTDB and the target Firestore project (keep it out of git; the script never prints it).
- The bridge virtualenv (it has `firebase-admin`, `google-cloud-firestore`, `tzdata` and the `bridge` package):
  `apps/bridge/.venv/Scripts/python` on Windows.

## 1. Dry run first

```
python firebase/migrate.py --service-account KEY.json --database-url https://<legacy>.firebaseio.com --dry-run
```

Reads the RTDB, lists the existing Firestore document ids (read-only), and
prints source counts, how many documents would be created and how many already
exist, the first 3 documents that would be created per collection, and any
skipped records. It writes nothing.

Options: `--project-id ID` (Firestore project if not in the key), `--tz Asia/Dhaka`
(time zone of the legacy `YYYY-MM-DD HH:MM:SS` timestamps; default `Asia/Dhaka`).

## 2. Real run

Same command without `--dry-run`. It creates the missing documents in batches
of 500 and prints created counts, already-existing counts and the final
destination counts.

## 3. Verify

- `people` destination count equals the source `users` count, and `attendance` equals the source `attendance_logs` count minus the skipped records (listed, first 10 shown). Skipped records are logs with a missing `user_id` or an unparsable timestamp, or non-object entries.
- Destination counts can be higher than the source if Firestore already held other documents (for example punches the bridge saved).
- The final line must read: `The Realtime Database data was NOT modified.`

Exit code is 0 even if some records were skipped (a warning is printed). It is
non-zero (2) if Firebase cannot be initialised, the legacy database cannot be
read, the Firestore client cannot be created or `--tz` is unknown, and 1 if the
migration fails part-way.

## Re-running

Safe. A re-run only adds documents that are missing. Existing documents are
never modified, including attendance written by the bridge (for example a
catch-up backfill using the same `{user_id}_{digits}` id, with real
`late`/`earlyLeave`/`deviceId`) and people edited in the web app
(`guardianUids`, `deviceEnrolled`, `active`, contact details, `createdAt`).
Once everything exists, a re-run creates nothing and the counts match.

The flip side: RTDB edits made after a document was first migrated (a changed
phone number, say) are not copied. To re-migrate a document, delete it in
Firestore first.

If a run is interrupted, just run it again; only the missing documents are
written.

## Mapping

- `role` (case-insensitive): `Student` to `student`, `Teacher` to `teacher`, anything else to `staff`.
- `phone`, `father_phone`, `mother_phone`, `class_name`, `section` to `phone`, `fatherPhone`, `motherPhone`, `className`, `section` (omitted when empty).
- `card_id`, `student_type`, `father_name`, `mother_name` are kept in a `legacy` map.
- Logs: `ts` (tz-aware, org time zone), `date`, `status`, `direction` (device status 1/2/5 is out, else in), `deviceId: "migrated"`, `late` and `earlyLeave` false. Legacy `name` and `role` are dropped.
