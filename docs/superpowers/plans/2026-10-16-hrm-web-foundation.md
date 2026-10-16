# HRM Web Platform — Foundation + Attendance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the SM Scolers desktop attendance app as a Next.js web app plus a headless Python bridge, on Firestore, with role-based access.

**Architecture:** pnpm/Turborepo monorepo. `apps/web` (Next.js server actions with the Admin SDK for trusted logic, client SDK for realtime reads), `apps/bridge` (Python service: ZKTeco polling, SMS, catch-up), `packages/shared` (Zod schemas, role map, punch-rule test cases). The website controls the bridge through Firestore documents.

**Tech Stack:** Next.js 15 (App Router), TypeScript, Tailwind, shadcn/ui, TanStack Table/Query, Recharts, react-three-fiber/drei, React Hook Form, Zod, `@react-pdf/renderer`, Firebase Auth + Firestore, Vitest, Playwright; Python 3.12, pyzk, pyserial, firebase-admin, pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-hrm-web-foundation-design.md`

## Global Constraints

- Monorepo layout: `apps/web`, `apps/bridge`, `packages/shared`, `firebase/`, `docs/`, `legacy/`; pnpm workspaces + Turborepo.
- Next.js 15 App Router, TypeScript, server components by default; Tailwind + shadcn/ui, light and dark themes.
- Firestore collections and fields exactly as spec section 5; roles are `admin`, `manager`, `staff`, `guardian` (custom claims).
- Punch document ID: `{personId}_{yyyyMMddHHmmss}`; `date` is `yyyy-MM-dd` in `settings/app.timeZone` (default `Asia/Dhaka`).
- Clients never write `attendance`, `smsLog`, `bridgeStatus`; client writes to `people`, `settings`, `commands` are denied; rules are deny-by-default.
- Punch-rule semantics are the spec's "Late and early-leave semantics" section (5-minute duplicate window).
- Stale-SMS window default 30 minutes; heartbeat about every 30 seconds.
- Device status map: `0` Check-In, `1` Check-Out, `2` Break-Out, `3` Break-In, `4` OT-In, `5` OT-Out; directions `in` = 0, 3, 4 and `out` = 1, 2, 5.
- No credentials in git (`serviceAccountKey.json`, `.env*`, real phone numbers); `config.example.json` replaces `config.json`.
- Three.js loads lazily only on dashboard and login, with a `prefers-reduced-motion` fallback.

## Review Focus

1. A double scan seconds after the first punch must not produce an early-leave or late SMS (tasks 2, 5, 6).
2. A device user missing from `people` must still be stored, with name `Unknown`, and send no SMS and not crash the cycle (task 6).
3. A person with no phone numbers, or a student with no guardians, sends no SMS and raises no error (task 6).
4. A Firestore write failure on one punch must skip that punch's SMS and let the rest of the cycle continue (task 6).
5. A malformed or duplicate-ID CSV row on people import is reported per row; valid rows still import (task 12).

---

## File Structure

```
package.json, pnpm-workspace.yaml, turbo.json, .gitignore, config.example.json
packages/shared/src/{roles.ts,schemas.ts,paths.ts,punch-id.ts,rules.ts,index.ts}
packages/shared/cases/punch-rules.json            # shared test cases for TS + Python
apps/bridge/pyproject.toml
apps/bridge/src/bridge/{models.py,rules.py,punch_id.py,store.py,firestore_store.py,sms.py,gsm.py,sync.py,commands.py,heartbeat.py,config.py,service.py}
apps/bridge/tests/{test_rules.py,test_punch_id.py,test_sync.py,test_commands.py,fakes.py}
apps/bridge/installer/{install-service.ps1,uninstall-service.ps1}
firebase/{firestore.rules,firestore.indexes.json,firebase.json,migrate.py}
firebase/tests/rules.test.ts
apps/web/src/{app,components,lib,actions}/...    # detailed per task
legacy/                                           # old app.py, installer, android_app, etc.
```

---

### Task 1: Monorepo scaffold, legacy archive, repo hygiene

**Files:**
- Create: `package.json`, `pnpm-workspace.yaml`, `turbo.json`, `config.example.json`, `.github/workflows/ci.yml` (lint/typecheck/test jobs, filled out in task 20)
- Modify: `.gitignore`
- Move to `legacy/`: `app.py`, `gsm_diagnostic.py`, `app.spec`, `build_installer.ps1`, `installer/`, `android_app/`, `SNIPPETS.md`, `requirements.txt`, `SM_Scolers.wixobj`, `Icon.ico`, `Logo.png`, `photos/`
- Remove from git index: `build/`, `dist/`, `config.json`

**Interfaces:**
- Produces: workspace names `@hrm/web`, `@hrm/shared`; root scripts `dev`, `build`, `lint`, `typecheck`, `test` (all via `turbo run`).

- [ ] **Step 1:** `git mv` the listed files into `legacy/`; `git rm -r --cached build dist config.json`. Keep `README.md` at the root.
- [ ] **Step 2:** Create `config.example.json` from `config.json` with all values replaced by placeholders (`USER_PHONE_MAP` emptied, Firebase URL `https://<project>-default-rtdb.firebaseio.com/`).
- [ ] **Step 3:** Add root `package.json` (private, `packageManager` pnpm), `pnpm-workspace.yaml` (`apps/*`, `packages/*`), `turbo.json` with `build`, `lint`, `typecheck`, `test` pipelines. Extend `.gitignore` with `.env*`, `serviceAccountKey.json`, `node_modules/`, `.next/`, `.turbo/`, `.firebase/`.
- [ ] **Step 4:** Run `git ls-files | grep -E '^(build|dist)/|config\.json$'`. Expected: no output.
- [ ] **Step 5:** Commit: `chore: archive legacy desktop app and scaffold monorepo`.

---

### Task 2: Shared punch rules (TypeScript) with the shared case file

**Files:**
- Create: `packages/shared/package.json` (name `@hrm/shared`), `packages/shared/src/{rules.ts,punch-id.ts,roles.ts,paths.ts,index.ts}`, `packages/shared/cases/punch-rules.json`
- Test: `packages/shared/src/rules.test.ts`, `packages/shared/src/punch-id.test.ts`

**Interfaces:**
- Produces (TS): `type Schedule = { start: string; end: string; graceMin: number; dismissal?: string }`; `type PunchEvalInput = { time: string /* "HH:mm:ss" local */; schedule: Schedule | null; previousPunchMinutesAgo: number | null; isHoliday: boolean }`; `type PunchFlags = { late: boolean; earlyLeave: boolean; duplicate: boolean }`; `evaluatePunch(input: PunchEvalInput): PunchFlags`; `directionFromStatus(raw: string): "in" | "out"`; `punchId(personId: string, timestamp: string): string` (digits-only suffix); `ROLES`, `type Role`.
- Case file shape: `{ "evaluate": [ { "name": string, "input": PunchEvalInput, "expected": PunchFlags } ], "direction": [ { "status": string, "expected": "in"|"out" } ], "punchId": [ { "personId": string, "timestamp": string, "expected": string } ] }`.

- [ ] **Step 1: Write `punch-rules.json`** with at least these evaluate cases (schedule `{start:"07:45", end:"08:15", graceMin:5, dismissal:"13:00"}` unless noted): first punch 07:30 → no flags; 08:20 → no flags (inside grace); 08:21 → `late`; second punch (previous 120 min) at 12:00 → `earlyLeave`; second punch at 13:00 → no flags; punch 2 minutes after previous → `duplicate: true`, no `late`/`earlyLeave` even at 08:21 / 12:00; `isHoliday: true` → no flags; `schedule: null` → no flags; schedule without `dismissal`, second punch at 09:00 → no `earlyLeave`; previous exactly 5 minutes ago → not duplicate. Direction cases for statuses `0..5` and unknown `"9"` → `"in"`. PunchId case: `("12", "2026-10-16 08:21:05")` → `"12_20261016082105"`.
- [ ] **Step 2: Write failing Vitest tests** that load the JSON and assert each case against `evaluatePunch`, `directionFromStatus`, `punchId`.
- [ ] **Step 3:** Run `pnpm --filter @hrm/shared test`. Expected: FAIL (modules missing).
- [ ] **Step 4:** Implement the functions in `rules.ts` / `punch-id.ts` per the spec semantics: late only on the first punch (`previousPunchMinutesAgo === null`), `time > end + graceMin`; early-leave only on a non-duplicate later punch with `dismissal` set; duplicate is `previousPunchMinutesAgo !== null && < 5`.
- [ ] **Step 5:** Run `pnpm --filter @hrm/shared test`. Expected: PASS.
- [ ] **Step 6:** Commit: `feat(shared): punch rules and shared test cases`.

---

### Task 3: Shared schemas, roles and Firestore paths

**Files:**
- Create: `packages/shared/src/schemas.ts`; extend `roles.ts`, `paths.ts`
- Test: `packages/shared/src/schemas.test.ts`

**Interfaces:**
- Produces: Zod schemas `PersonSchema`, `AttendanceSchema`, `ScheduleSchema`, `HolidaySchema`, `SmsLogSchema`, `DeviceSchema`, `CommandSchema`, `BridgeSettingsSchema`, `SmsSettingsSchema`, `AppSettingsSchema` (fields exactly as spec section 5) and their inferred types; `COLLECTIONS` constant (`people`, `attendance`, `schedules`, `holidays`, `smsLog`, `devices`, `commands`, `settings`, `bridgeStatus`, `users`); `can(role: Role, action: "manage" | "read:all" | "read:team" | "read:self" | "read:children"): boolean`.

- [ ] **Step 1: Write failing tests:** `PersonSchema` accepts a valid student and rejects an unknown `kind`; `ScheduleSchema` rejects `start: "8am"`; `CommandSchema` accepts types `test_sms`, `ussd`, `sync_device_users`, `read_inbox`, `at_command` and rejects others; `can("guardian","manage")` is false, `can("admin","manage")` is true.
- [ ] **Step 2:** Run tests; expected FAIL. **Step 3:** Implement. **Step 4:** Run; expected PASS.
- [ ] **Step 5:** Commit: `feat(shared): schemas, roles, collection paths`.

---

### Task 4: Firestore security rules and emulator tests

**Files:**
- Create: `firebase/firestore.rules`, `firebase/firestore.indexes.json`, `firebase/firebase.json`, `firebase/tests/rules.test.ts`
- Indexes: `attendance` on (`personId` asc, `ts` desc), (`date` asc, `ts` desc), (`date` asc, `personId` asc)

**Interfaces:**
- Consumes: `COLLECTIONS`, `Role` from `@hrm/shared`.

- [ ] **Step 1: Write failing `@firebase/rules-unit-testing` tests** (Firestore emulator), one `describe` per collection:
  - admin reads `people` and `attendance`; admin client write to `people`, `settings`, `commands` is denied.
  - manager reads a person with `managerId == uid` and that person's attendance, is denied another person's; staff reads only own person/attendance (via `users/{uid}.personId` claim `personId`); guardian reads a student whose `guardianUids` contains the uid and is denied others.
  - nobody (including admin) can write `attendance`, `smsLog`, `bridgeStatus`.
  - unauthenticated reads are denied on every collection.
- [ ] **Step 2:** Run `pnpm --filter firebase-tests test` (emulator via `firebase emulators:exec --only firestore`). Expected: FAIL.
- [ ] **Step 3:** Write the rules: deny by default, role from `request.auth.token.role`, own-person from `request.auth.token.personId`.
- [ ] **Step 4:** Run; expected PASS. **Step 5:** Commit: `feat(firebase): firestore rules and rule tests`.

---

### Task 5: Bridge package, punch rules in Python

**Files:**
- Create: `apps/bridge/pyproject.toml`, `apps/bridge/src/bridge/{__init__.py,models.py,rules.py,punch_id.py}`
- Test: `apps/bridge/tests/test_rules.py`, `apps/bridge/tests/test_punch_id.py`

**Interfaces:**
- Produces: `@dataclass Schedule(start: str, end: str, grace_min: int, dismissal: str | None)`; `@dataclass PunchFlags(late: bool, early_leave: bool, duplicate: bool)`; `evaluate_punch(time: str, schedule: Schedule | None, previous_punch_minutes_ago: int | None, is_holiday: bool) -> PunchFlags`; `direction_from_status(raw: str) -> str`; `punch_id(person_id: str, timestamp: str) -> str`. Also `@dataclass RawPunch(user_id: str, timestamp: str, status: str)`, `@dataclass Person(...)` mirroring `PersonSchema`.

- [ ] **Step 1:** Write pytest tests that load `packages/shared/cases/punch-rules.json` and assert every case (parametrized by `name`), mapping JSON keys camelCase → snake_case.
- [ ] **Step 2:** `pytest apps/bridge/tests -q`. Expected: FAIL. **Step 3:** Implement. **Step 4:** Expected PASS.
- [ ] **Step 5:** Commit: `feat(bridge): python punch rules passing shared cases`.

---

### Task 6: Bridge sync cycle with catch-up and SMS policy

**Files:**
- Create: `apps/bridge/src/bridge/{store.py,sms.py,sync.py}`, `apps/bridge/tests/fakes.py`
- Test: `apps/bridge/tests/test_sync.py`

**Interfaces:**
- Produces: `Protocol PunchStore` with `existing_punch_ids() -> set[str]`, `get_person(person_id: str) -> Person | None`, `get_schedule_for(person: Person) -> Schedule | None`, `is_holiday(date: str) -> bool`, `previous_punch_minutes_ago(person_id: str, ts: str) -> int | None`, `save_punch(punch: StoredPunch) -> None`, `log_sms(entry: SmsLogEntry) -> None`; `Protocol SmsGateway` with `send(phone: str, body: str) -> bool`; `Protocol ZkSource` with `get_attendance() -> list[RawPunch]`; `run_cycle(zk: ZkSource, device_id: str, store: PunchStore, gateway: SmsGateway, settings: BridgeSettings, now: datetime) -> CycleResult`; `@dataclass CycleResult(new_punches: int, sms_sent: int, sms_skipped_stale: int, errors: list[str])`; `build_sms_body(template: str, punch: StoredPunch, person: Person) -> str`; recipients: person phone, plus `father_phone`/`mother_phone` for `kind == "student"`.
- `fakes.py` provides `InMemoryStore` (optionally raising on `save_punch` for given IDs), `FakeZk`, `FakeGateway` (records sends).

- [ ] **Step 1: Write failing tests** with fakes:
  - `test_new_punch_is_stored_and_sms_sent`: one punch, student with a phone and both parents → 3 SMS recorded, 1 saved punch with `late=False`.
  - `test_replay_is_idempotent`: running the same cycle twice saves once, sends once.
  - `test_catch_up_stores_all_but_skips_stale_sms`: punches 2 h old with a 30-minute window → all stored, `smsLog` entries have `status="skipped-stale"`, gateway not called.
  - `test_double_scan_sends_no_late_or_early_sms` (Review Focus 1): second punch 2 min after the first at 08:21 → stored with `duplicate`, gateway not called for it.
  - `test_unknown_user_stored_without_sms` (Focus 2): `get_person` returns `None` → punch saved with name `"Unknown"`, no SMS, no exception.
  - `test_person_without_phone_sends_nothing` (Focus 3), `test_student_without_guardians_only_self_phone`.
  - `test_save_failure_skips_sms_and_continues` (Focus 4): store raises for the first ID → that punch has no SMS and appears in `errors`; the second punch is stored and texted.
  - `test_holiday_sends_normal_template_only`, `test_late_uses_late_template`, `test_early_leave_uses_early_template`.
  - `test_sms_disabled_logs_nothing_sent`.
- [ ] **Step 2:** Run `pytest apps/bridge/tests/test_sync.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement `run_cycle`: diff `zk.get_attendance()` against `existing_punch_ids()` by `punch_id`; for each new punch resolve person, schedule, holiday, previous-punch minutes, call `evaluate_punch`, save, then decide SMS (skip when stale, duplicate, disabled, or save failed). Port template placeholders from the legacy code: `{id} {name} {time} {date} {status} {role} {start} {end}`, time `%I:%M %p`, date `%d-%b-%Y`.
- [ ] **Step 4:** Run; expected PASS. **Step 5:** Commit: `feat(bridge): sync cycle with catch-up and stale-SMS policy`.

---

### Task 7: Firestore store and GSM gateway adapters

**Files:**
- Create: `apps/bridge/src/bridge/{firestore_store.py,gsm.py,config.py}`
- Test: `apps/bridge/tests/test_firestore_store.py` (Firestore emulator, skipped when `FIRESTORE_EMULATOR_HOST` is unset)

**Interfaces:**
- Consumes: `PunchStore`, `SmsGateway` (task 6).
- Produces: `FirestoreStore(client: google.cloud.firestore.Client, time_zone: str)` implementing `PunchStore`, writing documents exactly as spec section 5 (ID, `ts` Timestamp, `date` in org time zone); `GsmGateway(port: str, baud: int)` implementing `SmsGateway`, plus `signal_info() -> tuple[str, int]`, `run_ussd(code: str) -> str`, `ussd_reply(text: str) -> str`, `cancel_ussd() -> None`, `read_inbox(max_messages: int) -> list[dict]`, `run_at(command: str, read_seconds: float) -> str`, ported from legacy `send_sms_gsm`, `get_gsm_signal_info`, `run_ussd_command`, `run_ussd_reply`, `cancel_ussd_session`, `read_sms_inbox`, `run_at_command` with the shared serial lock; `load_local_config(path) -> LocalConfig(service_account_path: str, project_id: str)`.

- [ ] **Step 1:** Write emulator tests: `save_punch` creates `attendance/12_20261016082121` with `date == "2026-10-16"`; `existing_punch_ids` returns it; `previous_punch_minutes_ago` returns the gap to the latest earlier punch the same date, `None` for the first.
- [ ] **Step 2:** Run with the emulator; expected FAIL. **Step 3:** Implement `FirestoreStore`; port the GSM code without behaviour changes (move, do not rewrite). **Step 4:** Expected PASS. **Step 5:** Commit: `feat(bridge): firestore store and gsm adapters`.

---

### Task 8: Bridge service runtime — loop, heartbeat, commands, ZK adapter

**Files:**
- Create: `apps/bridge/src/bridge/{commands.py,heartbeat.py,service.py}`
- Test: `apps/bridge/tests/test_commands.py`, `apps/bridge/tests/test_service.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `ZkDevice(ip: str, port: int, timeout: int)` implementing `ZkSource` (wraps pyzk: connect, `disable_device`, `get_attendance`, `enable_device`, always disconnect); `execute_command(cmd: dict, gateway: GsmGateway, zk_factory, store) -> dict` handling the five command types and returning the result; `write_heartbeat(store, version: str, gsm: tuple[str,int], device_online: bool) -> None` (writes `bridgeStatus/main`); `main() -> None` loop: read `settings/bridge`, per cycle `run_cycle` for the main and each extra device, heartbeat, process `commands` where `status == "pending"` (set `running` → `done`/`error`), wait `poll_interval_sec` on a stop event.
- Startup rule: load existing punch IDs with 3 attempts (3 s apart); if all fail, log an error and retry the whole startup after 60 s without sending any SMS.
- Scheduled SMS (ported from legacy `_scheduled_sms_check`, `_send_absent_notifications`, `_send_daily_summary`, `app.py:1837-1950`): `run_scheduled_sms(store: PunchStore, gateway: SmsGateway, settings: SmsSettings, now: datetime) -> dict[str, int]` sends `absent` SMS to guardians of students with no punch after their schedule's `end + graceMin`, and a `summary` SMS at the configured time. Each kind is sent at most once per person per date (checked through `smsLog`), never on holidays.

- [ ] **Step 1: Write failing tests:** `test_absent_sms_sent_once_per_day` (call twice → one SMS), `test_no_absent_sms_on_holiday`, `test_absent_sms_skipped_for_student_with_punch`; `test_test_sms_command_sends_and_marks_done`; `test_unknown_command_type_marks_error`; `test_command_failure_records_error_text`; `test_startup_aborts_without_sms_when_store_unreachable`; `test_device_offline_sets_heartbeat_device_online_false` and the next successful cycle back-fills missed punches (use `FakeZk` that fails then succeeds).
- [ ] **Step 2:** Run; expected FAIL. **Step 3:** Implement. **Step 4:** Expected PASS. **Step 5:** Commit: `feat(bridge): service loop, heartbeat and website commands`.

---

### Task 9: Windows service installer

**Files:**
- Create: `apps/bridge/installer/install-service.ps1`, `apps/bridge/installer/uninstall-service.ps1`, `apps/bridge/README.md`

- [ ] **Step 1:** Write `install-service.ps1` taking `-ServiceAccountPath` and `-ProjectId`: creates a venv, installs the package, writes `%ProgramData%\SMScolersBridge\config.json`, registers the service with NSSM (`AppExit Default Restart`, delay 5000 ms, stdout/stderr to a rotating log, start type automatic). `uninstall-service.ps1` removes it.
- [ ] **Step 2:** On a Windows machine run the installer, stop the process with `Stop-Process -Force`, and confirm the service restarts within 15 s: `Get-Service SMScolersBridge`. Expected: `Running`.
- [ ] **Step 3:** Document in `README.md`: prerequisites, install, uninstall, log location. **Step 4:** Commit: `feat(bridge): windows service installer`.

---

### Task 10: Migration script (RTDB → Firestore)

**Files:**
- Create: `firebase/migrate.py`, `firebase/tests/test_migrate.py`

**Interfaces:**
- Produces: `convert_user(uid: str, data: dict) -> dict` (legacy role `Student` → `kind: "student"`, `Teacher` → `teacher`, others → `staff`; `class_name` → `className` etc.); `convert_log(key: str, data: dict) -> dict` (document ID kept, `ts` parsed, `date` derived, `direction` via `direction_from_status`, `late`/`earlyLeave` set to `False`); CLI `python firebase/migrate.py [--dry-run]`.

- [ ] **Step 1: Write failing tests** for `convert_user` (a legacy student dict maps every field) and `convert_log` (`"12_20261016082121"` keeps its ID and gets `date == "2026-10-16"`).
- [ ] **Step 2:** Run; expected FAIL. **Step 3:** Implement with batched writes (500 per batch) and `merge=True`, so re-runs are safe. `--dry-run` prints counts and the first 3 converted documents and writes nothing. The real run prints source and destination counts.
- [ ] **Step 4:** Run tests; expected PASS. **Step 5:** Commit: `feat: rtdb to firestore migration script`.

---

### Task 11: Web app scaffold, auth session and role guard

**Files:**
- Create: `apps/web/` via `create-next-app` (TS, Tailwind, App Router), shadcn/ui init; `src/lib/firebase-client.ts`, `src/lib/firebase-admin.ts`, `src/lib/session.ts`, `src/app/api/session/route.ts`, `src/middleware.ts`, `src/app/login/page.tsx`, `src/components/login-backdrop.tsx` (lazy react-three-fiber scene), `src/actions/users.ts`
- Test: `apps/web/src/lib/session.test.ts`

**Interfaces:**
- Produces: `getSession(): Promise<{ uid: string; role: Role; personId?: string } | null>` (verifies the session cookie with the Admin SDK); `requireRole(...roles: Role[]): Promise<Session>` (redirects to `/login` or the role's home); `homeFor(role: Role): string`; `POST /api/session` exchanges an ID token for a 5-day session cookie; server action `setUserRole(uid: string, role: Role, personId?: string): Promise<void>` (admin only; sets the custom claim and writes `users/{uid}`).
- Middleware checks cookie presence only and redirects to `/login`; role checks happen in layouts via `requireRole`.

- [ ] **Step 1: Write failing tests** (Vitest, Admin SDK mocked): `homeFor` returns `/dashboard`, `/team`, `/me`, `/children` for the four roles; `requireRole("admin")` redirects a `staff` session to `/me`; `setUserRole` rejects a non-admin caller.
- [ ] **Step 2:** Run; expected FAIL. **Step 3:** Implement; the login page signs in with the client SDK and posts the ID token to `/api/session`. The 3D backdrop is dynamically imported, `ssr: false`, and renders a static gradient when `prefers-reduced-motion` is set.
- [ ] **Step 4:** Run; expected PASS; `pnpm --filter @hrm/web build` succeeds. **Step 5:** Commit: `feat(web): scaffold, firebase session auth, role guard`.

---

### Task 12: People management

**Files:**
- Create: `src/app/(admin)/layout.tsx`, `src/app/(admin)/people/{page.tsx,[id]/page.tsx}`, `src/components/people/{people-table.tsx,person-form.tsx,csv-import.tsx}`, `src/actions/people.ts`, `src/lib/csv.ts`
- Test: `src/lib/csv.test.ts`, `src/actions/people.test.ts`

**Interfaces:**
- Produces: `createPerson(input: Person): Promise<void>`, `updatePerson(id: string, patch: Partial<Person>): Promise<void>`, `deletePerson(id: string): Promise<void>`, `importPeopleCsv(csv: string): Promise<{ imported: number; errors: { row: number; message: string }[] }>` (admin-only, validated with `PersonSchema`), `syncDeviceUsers(): Promise<void>` (enqueues a `sync_device_users` command); `parsePeopleCsv(csv: string): { rows: Person[]; errors: { row: number; message: string }[] }`; the admin layout is `requireRole("admin")` with sidebar navigation.

- [ ] **Step 1: Write failing tests:** `parsePeopleCsv` returns a row error for a missing `name` and for a duplicate `id` but still returns the valid rows (Review Focus 5); `importPeopleCsv` rejects a non-admin; `createPerson` rejects an invalid `kind`.
- [ ] **Step 2:** Run; expected FAIL. **Step 3:** Implement the actions, the TanStack table (search, kind/class filter, server pagination), the form (React Hook Form + shared Zod schema) and the CSV import dialog showing per-row errors. **Step 4:** Expected PASS. **Step 5:** Commit: `feat(web): people management`.

---

### Task 13: Attendance logs and Present Today

**Files:**
- Create: `src/app/(admin)/attendance/page.tsx`, `src/app/(admin)/today/page.tsx`, `src/components/attendance/{logs-table.tsx,today-board.tsx}`, `src/lib/attendance-queries.ts`, `src/actions/exports.ts`
- Test: `src/lib/attendance-queries.test.ts`

**Interfaces:**
- Produces: `buildLogsQuery(filters: { from: string; to: string; personId?: string; kind?: PersonKind; className?: string }): Query`; `summarizeToday(people: Person[], punches: Attendance[], holidays: string[], today: string): { present: Person[]; absent: Person[]; late: Person[] }` (absent excludes inactive people and returns empty on a holiday); server actions `exportAttendanceCsv(filters): Promise<string>`.

- [ ] **Step 1: Write failing tests** for `summarizeToday`: a person with a `late` punch is present and late; a person without punches is absent; holiday → nobody absent; inactive → excluded. **Step 2:** Run; FAIL. **Step 3:** Implement queries and pages (logs table with date-range filter and CSV export; today board with `onSnapshot`). **Step 4:** PASS. **Step 5:** Commit: `feat(web): attendance logs and present-today`.

---

### Task 14: Dashboard, live feed, bridge status, 3D presence element

**Files:**
- Create: `src/app/(admin)/dashboard/page.tsx`, `src/components/dashboard/{kpi-cards.tsx,live-feed.tsx,bridge-status-chip.tsx,presence-globe.tsx}`, `src/lib/bridge-status.ts`
- Test: `src/lib/bridge-status.test.ts`

**Interfaces:**
- Produces: `bridgeHealth(status: { heartbeat: Date; deviceOnline: boolean } | null, now: Date): { state: "online" | "device-offline" | "bridge-offline"; since?: Date }` — `bridge-offline` when the heartbeat is older than 90 s or absent; `PresenceGlobe({ pulseKey })` pulses when `pulseKey` changes.

- [ ] **Step 1: Write failing tests** for `bridgeHealth` (fresh + online → `online`; fresh + `deviceOnline:false` → `device-offline`; 3 minutes old → `bridge-offline` with `since`; `null` → `bridge-offline`). **Step 2:** FAIL. **Step 3:** Implement; KPI cards (users, SMS today, present, late) from queries; live feed from `onSnapshot` of the 20 latest punches; `PresenceGlobe` lazy via `next/dynamic`, static fallback under `prefers-reduced-motion`. **Step 4:** PASS. **Step 5:** Commit: `feat(web): dashboard with live feed and bridge status`.

---

### Task 15: Statistics and PDF reports

**Files:**
- Create: `src/app/(admin)/statistics/page.tsx`, `src/components/statistics/{range-picker.tsx,attendance-chart.tsx,punch-trend-chart.tsx}`, `src/lib/stats.ts`, `src/actions/reports.ts`, `src/components/pdf/person-report.tsx`
- Test: `src/lib/stats.test.ts`

**Interfaces:**
- Produces: `computeDailyStats(punches: Attendance[], people: Person[], range: { from: string; to: string }, holidays: string[]): { date: string; present: number; absent: number; late: number; punches: number }[]` (one row per non-holiday date); `generatePersonReportPdf(personId: string, range): Promise<Uint8Array>` (admin or manager of that person).

- [ ] **Step 1: Write failing tests** for `computeDailyStats`: two punches by one person on a day count one present and two punches; holidays skipped; range of one day returns one row. **Step 2:** FAIL. **Step 3:** Implement stats and Recharts bar/line charts with presets (7 days, 30 days, custom) and the PDF component with `@react-pdf/renderer`. **Step 4:** PASS. **Step 5:** Commit: `feat(web): statistics and pdf reports`.

---

### Task 16: Settings (schedules, holidays, SMS, devices, bridge, GSM tools)

**Files:**
- Create: `src/app/(admin)/settings/page.tsx`, `src/components/settings/{schedules.tsx,holidays.tsx,sms-templates.tsx,devices.tsx,bridge-settings.tsx,gsm-tools.tsx}`, `src/actions/settings.ts`, `src/actions/commands.ts`
- Test: `src/actions/settings.test.ts`

**Interfaces:**
- Produces: `saveSchedule(schedule: Schedule & { id?: string }): Promise<void>`, `deleteSchedule(id: string)`, `addHoliday(date: string, name: string)`, `removeHoliday(date: string)`, `saveSmsSettings(s: SmsSettings)`, `saveBridgeSettings(s: BridgeSettings)`, `saveDevice(d: Device)`, `enqueueCommand(type: CommandType, payload: object): Promise<string>` returning the command id, `exportBackup(): Promise<string>` (JSON of `people`, `schedules`, `holidays`, `settings`) and `restoreBackup(json: string): Promise<{ restored: Record<string, number> }>` (validates every document with its shared schema before writing, writes nothing if any fail), all admin-only with Zod validation; `gsm-tools.tsx` subscribes to `commands/{id}` and shows the result.

- [ ] **Step 1: Write failing tests:** a non-admin caller is rejected by each action; `saveSchedule` rejects `dismissal: "25:00"`; `saveSmsSettings` rejects a template with an unknown placeholder `{bogus}`; `enqueueCommand("test_sms", …)` writes a `pending` command; `restoreBackup` with one invalid person document writes nothing and reports the failure; an `exportBackup` → `restoreBackup` round trip leaves data unchanged.
- [ ] **Step 2:** FAIL. **Step 3:** Implement actions and the UI tabs (stale-window setting included in bridge settings). **Step 4:** PASS. **Step 5:** Commit: `feat(web): settings and bridge command console`.

---

### Task 17: Manager, staff and guardian views

**Files:**
- Create: `src/app/(manager)/team/page.tsx`, `src/app/(staff)/me/page.tsx`, `src/app/(guardian)/children/page.tsx`, a layout for each group with `requireRole`, `src/lib/scoped-queries.ts`
- Test: `src/lib/scoped-queries.test.ts`

**Interfaces:**
- Produces: `teamPeopleQuery(uid: string): Query` (`managerId == uid`), `selfAttendanceQuery(personId: string, range): Query`, `childrenQuery(uid: string): Query` (`guardianUids array-contains uid`); each page renders an empty state, not an error, when the query returns nothing (a manager with no reports, a guardian with no children).

- [ ] **Step 1: Write failing tests** asserting each builder produces the expected `where` clauses; add Testing Library tests that each page shows its empty state for an empty result. **Step 2:** FAIL. **Step 3:** Implement reusing the attendance table components. **Step 4:** PASS. **Step 5:** Commit: `feat(web): manager, staff and guardian views`.

---

### Task 18: End-to-end tests

**Files:**
- Create: `apps/web/e2e/{auth.setup.ts,login.spec.ts,people.spec.ts,attendance.spec.ts,roles.spec.ts}`, `apps/web/playwright.config.ts`, `firebase/seed.ts` (emulator seed: one user per role, three people, a week of punches)

- [ ] **Step 1:** Write specs against the Auth + Firestore emulators: admin logs in and lands on `/dashboard`; admin adds a person and sees it in the table; seeded punches appear on `/attendance`; a `staff` user visiting `/dashboard` is redirected to `/me`; a `guardian` sees only their linked child.
- [ ] **Step 2:** Run `pnpm --filter @hrm/web e2e`. Expected: PASS. **Step 3:** Commit: `test(web): playwright end-to-end coverage`.

---

### Task 19: CI, docs and release hygiene

**Files:**
- Modify: `.github/workflows/ci.yml`, `README.md`; Create: `docs/deploy.md`

- [ ] **Step 1:** CI jobs: Node (install, lint, typecheck, Vitest, `next build`), Firestore rules tests with the emulator, Python (`pytest apps/bridge/tests`), Playwright on the emulators.
- [ ] **Step 2:** Rewrite `README.md` for the new system (architecture, local dev with emulators, bridge install) and write `docs/deploy.md` (Vercel env vars, Firebase project setup, creating the first admin, running `migrate.py --dry-run` then the real run).
- [ ] **Step 3:** Push the branch and confirm all CI jobs pass. **Step 4:** Commit: `ci: pipeline and documentation`.
