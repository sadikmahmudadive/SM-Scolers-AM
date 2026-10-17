# SM Scolers HRM

Attendance and people management for a school or office. A ZKTeco biometric
terminal feeds a headless **bridge** service on a school PC, which stores punches
in Firestore and sends attendance SMS through a GSM modem. A **web app** (Next.js)
gives admins, managers, staff and guardians live, role-scoped views of the same data.

## Architecture

```
ZKTeco device --LAN--> Bridge (school PC) --Admin SDK--> Firestore <--client SDK (realtime)-- Web app
                          |   ^                              ^
                          |   +-- commands, settings --------+
                          +-- SIM800L modem (SMS, USSD)      +-- server actions / route handlers (Admin SDK)
```

- The **bridge** (`apps/bridge`, Python) polls the devices, writes punches with
  deterministic ids (re-runs and catch-up are idempotent), computes late and
  early-leave flags, sends SMS, executes commands created from the website and
  writes a heartbeat to `bridgeStatus/main`.
- The **web app** (`apps/web`, Next.js 15, TypeScript, Tailwind) reads through the
  Firebase client SDK with realtime listeners. Writes that carry business logic
  (accounts, roles, people, settings, commands, PDF and CSV reports) go through
  server actions and route handlers that use the Admin SDK and re-check the caller's role.
- **Firestore** is the only link between the two. Clients cannot write attendance,
  SMS log or bridge status; only the bridge can.

## Repository layout

```
apps/web         Next.js web app (deployed on Vercel), Vitest unit tests, Playwright e2e
apps/bridge      Headless Python service and its Windows installer
packages/shared  Zod schemas, roles and permission map, Firestore path constants, shared rule test cases
firebase/        firestore.rules, firestore.indexes.json, rules tests, migrate.py (RTDB -> Firestore)
docs/            Deployment guide (docs/deploy.md) and design notes
legacy/          Archived desktop app (kept for reference only)
```

The repository is a pnpm workspace driven by Turborepo.

## Local development

Prerequisites: Node 22, pnpm (version pinned by `packageManager`; use Corepack),
Java 11+ (the Firebase emulators are JARs; CI pins Java 21), Python 3.12+ for the bridge.

```
pnpm install
```

Tasks across the workspace (the web build needs the four `NEXT_PUBLIC_FIREBASE_*`
variables to exist; any placeholder values do):

```
pnpm turbo run lint typecheck test build
```

Run the web app against the emulators:

```
# terminal 1
firebase/node_modules/.bin/firebase emulators:start --config firebase/firebase.json --only auth,firestore --project demo-hrm
# terminal 2: copy apps/web/.env.example to apps/web/.env.local and set
#   NEXT_PUBLIC_FIREBASE_* to any placeholder values, the project id to demo-hrm,
#   NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099
#   NEXT_PUBLIC_FIRESTORE_EMULATOR_HOST=127.0.0.1:8089
#   FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099
#   FIRESTORE_EMULATOR_HOST=127.0.0.1:8089
pnpm --filter @hrm/web dev
```

Create a local admin to sign in with (see `docs/deploy.md`, "Creating the first admin";
with the emulator variables exported it needs no credentials, only `--project demo-hrm`):

```
pnpm --filter @hrm/web create-admin -- --email admin@example.test --project demo-hrm
```

`pnpm --filter @hrm/web create-admin -- --help` prints all options.

Tests:

| What | Command |
|---|---|
| Everything (includes the rules test, so Java is required) | `pnpm test` |
| Web and shared unit tests only (no Java needed; what the CI `web` job runs) | `pnpm turbo run test --filter='!firebase-tests'` |
| Firestore rules (starts its own emulator) | `pnpm --filter firebase-tests test` |
| End-to-end (Playwright, starts emulators and `next dev` itself) | `pnpm --filter @hrm/web e2e` |
| Bridge | `pytest apps/bridge/tests -q` and `pytest firebase/tests/test_migrate.py -q` after `pip install -e "apps/bridge[dev]"` |

The first e2e run needs `pnpm --filter @hrm/web exec playwright install chromium`
(locally the installed Chrome is used instead). On Windows the emulator `java`
process can outlive a run and keep ports 8089 or 9099 busy; stop it before re-running.
The CI workflow (`.github/workflows/ci.yml`) runs the same four groups.

## The bridge

The bridge runs on one PC on the school LAN as a Windows service. Installation,
configuration, logs and the manual hardware checklist are in
[apps/bridge/README.md](apps/bridge/README.md). Run exactly one bridge per Firebase project.

## Migrating legacy data

Data from the old Realtime Database (`users`, `attendance_logs`) is copied into
Firestore with `firebase/migrate.py` (dry run first, create-only, re-runnable).
See [firebase/MIGRATION.md](firebase/MIGRATION.md).

## Security model

- **Roles** are Firebase Auth custom claims: `admin`, `manager`, `staff`, `guardian`.
  Only server code (Admin SDK) sets them. `users/{uid}` mirrors the role for display only.
- **Session:** after sign-in the browser exchanges its ID token at `/api/session` for an
  httpOnly, `SameSite=Lax` session cookie named `__session` (Secure in production,
  5 days). The endpoint requires a recent sign-in, a JSON content type and a same-origin request.
  Server pages and actions verify the cookie (revocation checked) on every request.
- **Firestore rules** are deny-by-default and read the claim. Admins read everything;
  managers read their reports; staff read their own record; guardians read linked students.
  Clients cannot write `attendance`, `smsLog` or `bridgeStatus`, and writes to `people`,
  `settings` and `commands` are denied too: they go through server actions.
- **Credentials** (service account keys, `.env*`) are never committed. The web config is
  public by design and lives in `NEXT_PUBLIC_*` variables. Production refuses emulator variables.

## Deployment

See [docs/deploy.md](docs/deploy.md): Firebase project, Vercel, the first admin, the
bridge, migration, a smoke checklist and known limitations.

## Legacy

[legacy/](legacy) holds the previous Tkinter desktop application, its installer and the
Flutter skeleton. It is archived for reference only: it is not built, tested or supported,
and it is not part of the new system.
