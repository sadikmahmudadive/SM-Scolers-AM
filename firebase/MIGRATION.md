# Migrating legacy data (Realtime Database to Firestore)

`firebase/migrate.py` copies the legacy RTDB `users` and `attendance_logs`
into the Firestore `people` and `attendance` collections. It only reads the
RTDB; the legacy data is never modified or deleted.

## Prerequisites

- A service account JSON key with access to both the legacy RTDB and the target Firestore project (keep it out of git; the script never prints it).
- The bridge virtualenv (it has `firebase-admin`, `google-cloud-firestore`, `tzdata` and the `bridge` package):
  `apps/bridge/.venv/Scripts/python` on Windows.

## 1. Dry run first

```
python firebase/migrate.py --service-account KEY.json --database-url https://<legacy>.firebaseio.com --dry-run
```

Reads and converts everything, prints source counts, the first 3 converted
documents per collection and any skipped records, and writes nothing.

Options: `--project-id ID` (Firestore project if not in the key), `--tz Asia/Dhaka`
(time zone of the legacy `YYYY-MM-DD HH:MM:SS` timestamps; default `Asia/Dhaka`).

## 2. Real run

Same command without `--dry-run`. It writes in batches of 500 with
`set(..., merge=True)` and prints source and destination counts.

## 3. Verify

- `people` destination count equals the source `users` count.
- `attendance` destination count equals the source `attendance_logs` count minus the skipped records (listed, first 10 shown). Skipped records are logs with a missing `user_id` or an unparsable timestamp; fix them in the source and re-run if they matter.
- The destination counts can be higher than the migrated counts if Firestore already held other documents (for example punches the bridge saved).
- The final line must read: `The Realtime Database data was NOT modified.`

Exit code is 0 even if some records were skipped (a warning is printed); it is
non-zero if the source read or the migration fails.

## Re-running

Safe: documents keep their IDs (`people/{user_id}`, `attendance/{user_id}_{digits}`)
and are written with merge, so a second run changes nothing in the data
fields. Note that a re-run rewrites the fields the migration sets, so values
changed in Firestore since the first run (`deviceEnrolled`, `guardianUids`,
`active`, `createdAt`, edited contact details) on migrated people are reset to
the migrated defaults. Do not re-run after editing people in the web app
unless that is intended.

## Mapping

- `role`: `Student` to `student`, `Teacher` to `teacher`, anything else to `staff`.
- `phone`, `father_phone`, `mother_phone`, `class_name`, `section` to `phone`, `fatherPhone`, `motherPhone`, `className`, `section` (omitted when empty).
- `card_id`, `student_type`, `father_name`, `mother_name` are kept in a `legacy` map.
- Logs: `ts` (tz-aware, org time zone), `date`, `status`, `direction` (device status 1/2/5 is out, else in), `deviceId: "migrated"`, `late` and `earlyLeave` false. Legacy `name` and `role` are dropped.
