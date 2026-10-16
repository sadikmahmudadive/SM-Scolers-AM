# HRM Web Platform — Sub-project 1: Foundation + Attendance

Date: 2026-10-16
Status: Draft for review

## 1. Background and intent

SM Scolers Attendance is a Windows Tkinter desktop app (`app.py`, ~4,600 lines). It polls a ZKTeco K50-A fingerprint device over the LAN, writes punches to Firebase Realtime Database, and sends SMS through a SIM800L modem on a COM port.

The goal is a **complete web-based HRM system** for **a single organisation (SM Scolers)**, built with Next.js, Three.js and other modern tech. The full HRM is decomposed into five sub-projects, each with its own spec, plan and build:

1. **Foundation + Attendance** (this spec)
2. Shifts, leave and holidays
3. Payroll
4. Recruitment, performance and documents
5. Public landing site (Three.js hero)

Sub-project 1 is today's app rebuilt for the web. Everything else depends on it.

### Decisions already made

| Topic | Decision |
|---|---|
| Tenancy | Single organisation |
| Data store | Stay on Firebase. Use **Firestore** for the new system, with a one-time migration from Realtime DB |
| Bridge | Keep **Python**, made headless. Runs as an auto-restarting Windows service |
| Offline behaviour | **Catch-up only.** The device keeps its own log. The bridge back-fills when it returns. Stale SMS are not sent late |
| Roles | Admin/HR, Manager, Staff/Teacher (self-service), Guardian/Student |
| Architecture | Monorepo, Next.js with a server layer (Admin SDK), Firestore, Python bridge |

### Success criteria

- Every screen of the desktop app that matters has a web equivalent: users, dashboard, monitor/live feed, logs, present-today, statistics, settings.
- Punches from the device appear on the website within one poll interval while the bridge runs.
- After a bridge or PC outage, all missed punches appear after restart, with no duplicates.
- SMS older than the stale window after an outage are not sent. They are recorded as `skipped-stale`.
- Each role sees only what it is allowed to see, enforced by Firestore rules and server checks, not only by hiding UI.
- The early-leave SMS bug in the desktop app is fixed in the bridge and covered by tests.

## 2. Scope

### In scope

- Auth and roles
- People records (staff, teachers, students) and guardian links
- Attendance: live feed, logs, present/absent/late today
- Dashboard and statistics, CSV and PDF reports
- Settings: schedules, holidays, SMS templates, devices, bridge, backups
- Headless Python bridge with a Windows-service installer
- RTDB-to-Firestore migration script
- Security rules and tests, CI

### Out of scope (later sub-projects)

- Leave, payroll, recruitment, performance, documents
- Public landing site (the large Three.js hero)
- Multi-tenancy
- Cloud push from the device and cloud SMS gateway (a possible later add-on to the catch-up design)

The data model carries `departmentId` and `managerId` on `people` so later modules need no migration.

## 3. Repository layout

```
/                         pnpm workspaces + Turborepo
├─ apps/web               Next.js 15 (App Router), TypeScript, Tailwind, shadcn/ui, react-three-fiber
├─ apps/bridge            Headless Python service (pyzk, pyserial, firebase-admin)
├─ packages/shared        Zod schemas, role/permission map, Firestore path constants, rules test cases
├─ firebase/              firestore.rules, firestore.indexes.json, migrate.py, seed
├─ docs/
└─ legacy/                Old Tkinter app, WiX installer and Flutter skeleton, archived
```

- `build/`, `dist/`, `*.msi`, `*.wixobj`, `*.wixpdb` and the PyInstaller output are removed from git tracking (they are already listed in `.gitignore`).
- `config.json` (real phone numbers and the Firebase URL) is not carried over. A `config.example.json` replaces it.
- `serviceAccountKey.json` is never committed.

## 4. System architecture and data flow

```
ZKTeco device ──LAN──> Bridge (school PC) ──Admin SDK──> Firestore <──client SDK (realtime)── Web app
                          │  ▲                               ▲
                          │  └── commands, settings ─────────┤
                          └── SIM800L modem (SMS, USSD)      └── server actions (Admin SDK): trusted logic
```

- The **bridge** polls each device, writes punches, computes late/early flags, sends SMS and writes a heartbeat.
- The **web app** reads through the Firebase client SDK with realtime listeners. Writes with business logic go through Next.js server actions and route handlers using the Admin SDK. Examples: role changes, bulk import, person deletion, PDF generation.
- The **website controls the bridge** through Firestore: it edits `settings/bridge` and creates `commands/{id}` documents. Example commands: send a test SMS, run USSD, sync device users. The bridge listens, executes and writes the result back to the command document.
- **Auth:** Firebase Auth. Roles are custom claims (`admin`, `manager`, `staff`, `guardian`) set by a server action. A mirror in `users/{uid}` is for display only. Rules read the claim.

## 5. Data model (Firestore)

| Collection | Document ID | Fields |
|---|---|---|
| `people` | `{personId}` (the device user ID) | `name`, `kind` (`staff`/`teacher`/`student`), `phone`, `fatherPhone`, `motherPhone`, `className`, `section`, `departmentId?`, `managerId?`, `guardianUids[]`, `deviceEnrolled`, `active`, `createdAt` |
| `attendance` | `{personId}_{yyyyMMddHHmmss}` | `personId`, `ts` (Timestamp), `date` (`yyyy-MM-dd`), `status` (raw device value), `direction` (`in`/`out`), `deviceId`, `late`, `earlyLeave`, `scheduleId?` |
| `schedules` | `{scheduleId}` | `name`, `start` (`HH:mm`), `end` (`HH:mm`), `graceMin`, `appliesTo` (class names or department IDs) |
| `holidays` | `{yyyy-MM-dd}` | `name` |
| `smsLog` | auto | `personId`, `phone`, `body`, `kind` (`normal`/`late`/`early`/`absent`/`summary`/`test`), `status` (`sent`/`failed`/`skipped-stale`), `punchId?`, `ts` |
| `devices` | `{deviceId}` | `name`, `ip`, `port`, `lastSeen` |
| `commands` | auto | `type`, `payload`, `status` (`pending`/`running`/`done`/`error`), `result?`, `createdBy`, `createdAt` |
| `settings` | `bridge`, `sms`, `app` | bridge: poll interval, timeout, COM port, baud, stale window. sms: templates, enabled flags. app: org name, time zone, notification sound |
| `bridgeStatus` | `main` | `heartbeat`, `version`, `gsmSignal`, `carrier`, `deviceOnline` |
| `users` | `{firebaseUid}` | `role`, `personId?`, `displayName` |

Design choices:

- **Late and early-leave are computed once**, in the bridge, and stored on the attendance document. The desktop app recomputed them in three separate places. The web only reads the flags. The rule function is specified by a shared test-case file (see section 9) that both the TypeScript and Python implementations must pass.
- **Deterministic punch IDs** make the catch-up back-fill idempotent. This is the same idea as today's `format_key`.
- **Guardian access** is through `guardianUids[]` on the person document. Rules check that array.
- **Time zone:** `ts` is stored as a Timestamp. `date` is derived in the configured organisation time zone (`settings/app.timeZone`, default `Asia/Dhaka`), since the device reports local time without a zone.
- **Raw status kept.** The device `status` is stored as-is. `direction` is derived from it with the same `punch_status_label` mapping the desktop app uses.

### Access rules

| Role | `people` | `attendance` | `settings`, `devices`, `commands`, `smsLog`, `bridgeStatus` |
|---|---|---|---|
| `admin` | read/write via server actions, read via client | read | read; writes through server actions |
| `manager` | read own reports (`managerId` match) | read for own reports | `bridgeStatus` read only |
| `staff` | read own record | read own | none |
| `guardian` | read linked students (`guardianUids` contains uid) | read linked students | none |

- Clients can never write `attendance`, `smsLog` or `bridgeStatus`. Only the bridge (Admin SDK) writes them.
- Client writes to `people`, `settings` and `commands` are denied by rules. All of them go through server actions that re-check the role claim.

## 6. Web app

### Routes

```
/login                       Firebase Auth (email/password; Google optional)
/(admin)/dashboard           KPI cards, live feed, bridge status chip
/(admin)/people              Table, filters, add/edit, CSV import, device sync
/(admin)/people/[id]         Profile, attendance history, PDF export
/(admin)/attendance          Logs table, filters, CSV/PDF export
/(admin)/today               Present / absent / late today
/(admin)/statistics          Date-range charts (daily, weekly, punch trends)
/(admin)/settings            Schedules, holidays, SMS templates, devices, bridge, GSM tools, backups
/(manager)/team              Dashboard and attendance for own reports
/(staff)/me                  Own attendance and profile
/(guardian)/children         Linked students' attendance
```

Each route group has its own layout and navigation. Middleware and server components both check the role claim. A wrong-role request redirects.

### Stack

- Next.js 15 App Router, TypeScript, server components by default
- Tailwind and shadcn/ui, light and dark themes
- TanStack Table (server-side filtering and pagination) and TanStack Query
- Recharts for 2D charts (replaces the hand-drawn canvas charts)
- Firestore `onSnapshot` for the live feed and today view
- React Hook Form with Zod schemas from `packages/shared`
- PDF export on the server with `@react-pdf/renderer`. CSV on the client

### Three.js (react-three-fiber and drei)

Kept small in this sub-project:

- **Dashboard:** one optional 3D "live presence" element (rotating globe or particle field) that pulses on each new punch. It is lazy-loaded, and `prefers-reduced-motion` or low-power devices get a static fallback.
- **Login page:** a light animated 3D backdrop.
- The three.js bundle loads only on routes that use it. The full 3D hero belongs to sub-project 5.

## 7. Bridge (`apps/bridge`)

### Modules

`zk_client`, `gsm` (SMS, USSD, inbox, AT commands, moved from `app.py`), `sync_loop`, `rules` (late/early-leave), `firestore_store`, `commands` (executes website commands), `service` (entry point). The Tkinter UI is removed.

### Runtime

- Runs as a Windows service (NSSM or `pywin32`) with auto-start on boot and auto-restart on crash. A PowerShell or MSI installer replaces the old WiX installer.
- Rotating log file. A heartbeat is written to `bridgeStatus/main` about every 30 seconds with version, GSM signal, carrier and device-online state. The website shows "bridge offline since …" when the heartbeat is stale.
- Configuration comes from `settings/bridge`, with a local fallback file for the Firebase credentials path.

### Catch-up and offline behaviour

- On every start, and after any device reconnect, the bridge reads the device log and diffs it against Firestore using the deterministic IDs. It writes only the missing punches.
- Each missing punch is compared with `now`. If it is older than the stale window (default 30 minutes, configurable), it is stored with its flags, but its SMS is recorded as `skipped-stale` and not sent.
- If Firestore cannot be reached on startup after three attempts, the bridge aborts the sync cycle and retries later. This keeps today's rule: do not send SMS when the existing keys could not be loaded, to avoid duplicates.
- A write failure on a single punch is retried next cycle. Its SMS is not sent until the punch is stored.

### Bug fix carried over

The early-leave logic in `app.py` (the `is_late` nesting, the unbound `has_earlier` and the undefined `punch_date_str`) is rewritten in `rules` as a pure function and covered by the shared test cases.

## 8. Migration (`firebase/migrate.py`)

- One-time and re-runnable.
- Reads RTDB `users` and `attendance_logs`. Writes `people` and `attendance` with the same deterministic IDs, so re-running is safe.
- `--dry-run` prints counts and a sample, and exits without writing. The real run prints source and destination counts for comparison.
- Leaves the RTDB data untouched until the user has verified the result.

## 9. Testing

- **Shared rule test cases:** one JSON file in `packages/shared` with inputs (punch time, schedule, earlier punches that day, role) and expected flags. Vitest runs it against the TypeScript rules and pytest runs it against the Python `rules` module.
- **Firestore rules tests** with the emulator: each role against each collection, and "clients cannot write attendance".
- **Bridge tests** with a fake ZK device and a fake modem: catch-up after an outage, idempotent replay, stale-SMS skipping, Firestore-unreachable startup.
- **Playwright end-to-end tests:** login, add a person, view attendance, role-gated route redirects.
- **CI (GitHub Actions):** lint, typecheck, unit tests, rules tests, bridge tests and the Next.js build.

## 10. Security and repository hygiene

- No credentials in git: `serviceAccountKey.json`, `.env*`, real phone numbers.
- Server actions re-verify the caller's role claim. They never trust client-supplied roles.
- Firestore rules are deny-by-default.
- The Firebase web config (public by design) goes in `NEXT_PUBLIC_*` environment variables.
- Hosting: web app on Vercel. The bridge on the school PC.

## 11. Open items (to settle in the implementation plan)

- Default stale-SMS window (proposed: 30 minutes).
- Windows-service wrapper: NSSM versus `pywin32`.
- Whether Google sign-in is enabled alongside email/password.
- `legacy/` keeps the old Tkinter app and Flutter skeleton for reference. Delete later, once the web system is verified in production.
