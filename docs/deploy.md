# Deployment guide

Order of work: Firebase project, Vercel, first admin, bridge, migration, smoke checklist, backups.
All names below in angle brackets are placeholders; nothing here is a real project.

## Firestore usage and billing (read this first)

**The system needs the Blaze (pay-as-you-go) plan.** The free Spark quota is 50,000 document
reads per day, and a school with a few hundred students exceeds it on a normal day (estimates
below). Firestore bills per document read and write; check the current prices for your region
on the Firebase pricing page. At list prices the volumes below come to a few US dollars per
month or less, but **create a budget alert** (Google Cloud console, Billing, Budgets and alerts,
for example at 5 USD per month) so a misconfiguration cannot run up a bill unnoticed.

Assumptions for the estimates: one device, `pollIntervalSec` 10 (8,640 polls per day),
S active students, P punches per day, the bridge running all day. Firestore bills at least one
read per query even when it returns nothing.

Bridge, steady state:

| What | How often | Reads per day |
|---|---|---|
| Pending-commands query (never cached) | every poll | about 8,640 |
| `settings/bridge`, `settings/sms`, `settings/app`, the `devices` list (cached 60 s in the bridge) | once a minute | about 1,440 x (3 + number of devices) = 5,760 |
| Heartbeat `bridgeStatus/main` | every 30 s | 0 reads, about 2,880 writes |
| Scheduled pass: holiday check | every 5 min | 288 |
| Scheduled pass with absent SMS enabled: every active student is read | every 5 min | 288 x S (144,000 for S = 500) |
| Enrollment refresh: the enrolled people (plus any device ids not yet enrolled) | every 30 min | about 48 x S (24,000 for S = 500) |
| Each new punch: person, schedule, previous punch, holiday | per punch | about 4 x P (4,000 for P = 1,000) |
| Stored punch ids: the last 7 days at startup, and the range the device log covers after a device reconnects | at startup and per reconnect | 7 x P at startup; up to every punch still in the device log per reconnect |

So a 500-student school with absent SMS enabled reads roughly 190,000 documents per day from
the bridge (about 45,000 without absent SMS). The device log is the main one-off cost: after a
device reconnects the bridge re-reads the stored ids for every date the device still holds, so
clear old records from the terminal from time to time.

Web app, per use:

| Page | Reads |
|---|---|
| Dashboard | today's punches once per open dashboard, then one read per new punch per open dashboard |
| Attendance list and CSV export | up to 5,000 per load |
| Statistics | up to 50,000 per load (every punch in the chosen range) |
| Person PDF | that person's punches in the range (at most 5,000) plus the holidays and `settings/app` |
| Settings, people, accounts | one read per listed document |

A settings change made on the website takes up to 60 seconds to reach the bridge (cache window).

## 1. Firebase project

1. Create a Firebase project (note the **project id**).
2. **Authentication**: enable the Email/Password provider.
3. **Firestore**: create the database in **native mode**, in the region closest to the school.
4. Register a **web app** (Project settings, General, Your apps). Its config gives the four
   public values: API key, auth domain, project id and app id.
5. Deploy rules and indexes from the repository root:

   ```
   firebase deploy --only firestore:rules,firestore:indexes --project <project-id>
   ```

   Use the CLI from `firebase/node_modules/.bin/firebase` (or any installed firebase-tools)
   and run `firebase login` first. The indexes include `attendance (personId asc, date desc)`.
   **Deploy them before using the admin attendance filter by person**: without that index
   the filter fails. Index builds take a few minutes on a populated project; wait until they
   show as Enabled in the console.
6. **Service account keys** (Project settings, Service accounts, Generate new private key):
   - The web app needs one key, stored **only** in Vercel as `FIREBASE_SERVICE_ACCOUNT_JSON`
     (the whole JSON on one line).
   - The bridge needs a key as a file on the school PC (`-ServiceAccountPath` of the installer).
   - Prefer a separate key per consumer so either can be revoked on its own. Never commit a key,
     paste it in chat or put it in a `NEXT_PUBLIC_*` variable.

## 2. Vercel (web app)

Create a project from the Git repository and set:

| Setting | Value |
|---|---|
| Framework preset | Next.js |
| Root Directory | `apps/web` (enable "Include source files outside of the Root Directory") |
| Install Command | `cd ../.. && pnpm install --frozen-lockfile` |
| Build Command | `cd ../.. && pnpm turbo run build --filter=@hrm/web` |
| Node.js version | 22.x |

pnpm is picked from the `packageManager` field in the root `package.json`.

### Environment variables

Set them for Production (and Preview if used). Values come from `apps/web/.env.example`.

| Variable | Secret | Notes |
|---|---|---|
| `NEXT_PUBLIC_FIREBASE_API_KEY` | no | Web app config; public by design, embedded in the client bundle |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | no | Web app config |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | no | Web app config; also used by the Admin SDK |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | no | Web app config |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | **yes** | Service account JSON on a single line. Mark as Sensitive |
| `GOOGLE_APPLICATION_CREDENTIALS` | yes | Path to a key file. Not usable on Vercel (no file); leave unset there |
| `NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST` | no | Local development only. **Leave unset** |
| `NEXT_PUBLIC_FIRESTORE_EMULATOR_HOST` | no | Local development only. **Leave unset** |
| `FIREBASE_AUTH_EMULATOR_HOST` | no | Local development only. **Leave unset** |
| `FIRESTORE_EMULATOR_HOST` | no | Local development only. **Leave unset** |

`NEXT_PUBLIC_*` values are inlined at build time: redeploy after changing them.

Notes:

- **Session cookie.** Sign-in sets an httpOnly cookie named `__session`. It is `Secure` in production, so the site
  must be served over **HTTPS**; Vercel domains are. Plain HTTP will not keep a session.
- **Origin check.** `/api/session` (and `/api/live-token`) compare the request's `Origin` header
  with the origin derived from the request URL and answer 403 on a mismatch. If a reverse proxy or
  custom domain sits in front of Vercel, it must preserve the `Host` and `X-Forwarded-Proto`
  headers, otherwise sign-in fails with "Cross-origin request rejected".
- **Emulators are refused in production by design.** If any of the four emulator variables is set
  when `NODE_ENV=production`, the server throws on first use, because an emulator would disable
  token signature checks. Remove the variable instead of working around the check.
- Add the production domain under Authentication, Settings, Authorized domains.

## 3. Creating the first admin

A new project has no accounts, and only an admin can create accounts in the app. Create the
first one from your own machine with the Admin SDK script:

```
pnpm --filter @hrm/web create-admin -- --email admin@school.example --name "Head Office" --project <project-id>
```

Run it from the repository root exactly as shown. The `--` after `create-admin` is forwarded by
pnpm and stripped by the script (only one leading `--`; any other unknown flag or stray argument
is a usage error, exit code 2). `pnpm --filter @hrm/web create-admin -- --help` prints the usage.

Credentials come from `FIREBASE_SERVICE_ACCOUNT_JSON` or `GOOGLE_APPLICATION_CREDENTIALS`
(a path to the key file). The script **refuses to run against a real project unless
`--project` is given and equals the credentials' project id**. Examples:

```
# bash
export GOOGLE_APPLICATION_CREDENTIALS=/secure/path/key.json
pnpm --filter @hrm/web create-admin -- --email admin@school.example --project <project-id>

# PowerShell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\secure\key.json"
pnpm --filter @hrm/web create-admin -- --email admin@school.example --project <project-id>
```

The password is read from a prompt that does not echo (asked twice). **Do not type the password
into your shell** (command line or `export ADMIN_PASSWORD=...`): it would land in shell history.
`ADMIN_PASSWORD` exists for non-interactive use (for example a secret injected by automation);
minimum 10 characters.
The script never prints the password or the credentials.

It sets the custom claim `{ role: "admin" }`, writes `users/{uid}` and revokes existing refresh
tokens. If the email already exists it asks for confirmation (`--yes` skips it, required when stdin
is not a terminal), keeps the current password unless `--reset-password` is passed, and still
(re)sets the admin claim. Sign in again afterwards.

Manual check against the emulators (no credentials needed; the CLI exports the emulator hosts):

```
firebase/node_modules/.bin/firebase emulators:exec --config firebase/firebase.json --only auth,firestore --project demo-hrm "cd apps/web && node scripts/create-first-admin.mjs --email admin@example.test --project demo-hrm --yes"
```

Set `ADMIN_PASSWORD` to a dummy value in the environment for that run. In emulator mode both
`FIREBASE_AUTH_EMULATOR_HOST` and `FIRESTORE_EMULATOR_HOST` must be set to loopback addresses, and the
project id comes from `--project` or `GCLOUD_PROJECT`.

Notes: the interactive prompts need a real terminal (TTY). Without one, the password must come from
`ADMIN_PASSWORD`, and an already existing account additionally needs `--yes`. The script is not atomic
(user, claims, `users/{uid}` and token revocation are separate calls); if it fails part-way, run it again
to finish. CI pins Java 21 for the emulators; locally Java 11+ is the minimum.

## 4. The bridge on the school PC

Install the Windows service as described in [apps/bridge/README.md](../apps/bridge/README.md)
(elevated PowerShell, NSSM, Python 3.12+, the bridge's own service account key and the project id).
**Run exactly one bridge per Firebase project**: on start a bridge fails commands left in `running`
by a previous process, so a second live instance breaks the first one's in-flight commands.
Then work through the manual verification checklist in that README on the real hardware.

## 5. Migrating legacy data

Copy the old Realtime Database data into Firestore with `firebase/migrate.py`. **Always do the
dry run first**, compare the counts, then run for real. Create-only and safe to re-run; the legacy
data is never modified. Steps, options and verification: [firebase/MIGRATION.md](../firebase/MIGRATION.md).

**Device enrollment after a migration.** People created by the migration, the web form or a
CSV import start with `deviceEnrolled: false`, and absent-student SMS only go to enrolled
students. The bridge refreshes `deviceEnrolled` automatically from the devices' user lists: on
its first clean cycle after it starts and then every 30 minutes (only when every configured
device was read cleanly). It sets `true` for existing people found on a device and `false` for
people no longer on any device, never creates people and changes no other field. To do it
immediately, use Settings, GSM tools, **Sync device users** (that command also creates missing people).

## 6. Post-deploy smoke checklist

- [ ] The site loads over HTTPS and `/login` renders.
- [ ] Signing in as the first admin lands on the dashboard; the `__session` cookie is set, httpOnly and Secure.
- [ ] Signing out clears the cookie and a protected URL redirects to `/login`.
- [ ] Accounts: create a test staff account and a guardian account, and sign in as each; each sees only its own views.
- [ ] People: add a person; it appears in the list.
- [ ] Settings page loads and saves.
- [ ] Bridge: the dashboard shows the bridge online (heartbeat under 90 s) after the service starts.
- [ ] Send a test SMS command from the website; the command ends `done` (or shows the modem error).
- [ ] A real punch on the device appears in Attendance and updates live without a reload.
- [ ] Attendance filtered by person works (confirms the `personId, date` index is built).
- [ ] A person PDF and a CSV export download.
- [ ] Rules sanity: a signed-in non-admin cannot open admin routes (redirected or 403).
- [ ] Delete the test accounts and test people.

## 7. Backups

**Settings, Configuration backup** in the web app downloads a **configuration backup**
(`hrm-configuration-backup-<date>.json`, `"kind": "configuration"`): people, schedules,
holidays, devices and settings. **It does not contain attendance history or SMS logs.** Use it
to copy or roll back configuration; restoring it overwrites documents with the same id and
deletes nothing.

To back up everything (attendance, smsLog, commands, bridgeStatus and the configuration),
use Firestore's own tools:

- **Managed export** to a Cloud Storage bucket (Blaze plan; the bucket must be in a compatible
  location):

  ```
  gcloud firestore export gs://<bucket>/<path> --project <project-id>
  ```

  Restore with `gcloud firestore import gs://<bucket>/<path> --project <project-id>`. Run the
  export on a schedule (for example Cloud Scheduler) if you want regular copies.
- **Point-in-time recovery (PITR)** keeps a rolling 7-day history that can be read or restored
  to any minute; enable it on the database (Firestore console, Disaster recovery, or
  `gcloud firestore databases update --enable-pitr`).
- **Scheduled backups** (Firestore console, Disaster recovery) keep daily or weekly backups
  for a retention period you choose.

None of this is automated by the repository; set up what fits your recovery needs and test a
restore into a separate project once.

## Security note: legacy secrets in git history

Before commit `9b836a2` the repository's root `config.json` held real values from the legacy
system: the Realtime Database URL, a phone-number map with six phone numbers, the device IP
address and the USSD code. The file is gone from the current tree but **every value is still
retrievable from git history**. The values are deliberately not repeated here.

- If this repository is, or will be, public or shared with anyone outside the school, **treat
  those phone numbers as exposed** (inform the people concerned if your privacy obligations
  require it).
- **Check the legacy Realtime Database rules now.** With a known database URL, open rules let
  anyone read and overwrite the data. Once the migration has been verified, lock the legacy
  database completely:

  ```
  { "rules": { ".read": false, ".write": false } }
  ```

- **Before making the repository public**, either rewrite the history (for example with
  `git filter-repo --path config.json --invert-paths`, then force-push and have every clone
  re-cloned) or publish a fresh repository that starts from a clean commit.
- **Rotate service account keys** that were ever stored on a developer machine or near the
  repository (Google Cloud console, IAM, Service accounts, Keys: create a new key, deploy it,
  then delete the old one).

## 8. Known limitations and follow-ups

- **Bengali in PDFs.** Bengali glyphs are not rendered in the person PDF (it uses Helvetica).
  Follow-up: bundle an OFL Noto Sans Bengali font and register it with `Font.register`.
- **Device clock skew is not corrected.** Punch times come from the terminal's clock. The bridge
  logs a warning once when a device clock is more than 5 minutes from the PC clock (and an info
  line when it is back), but it never changes the device clock; set it on the terminal.
- **Catch-up on first install.** The first cycle stores every punch still in the device log and
  writes one `skipped-stale` smsLog row per recipient for each of them (no SMS is sent). Clear
  old records from the terminal before the first start if that is unwanted.
- **Multi-device catch-up ordering.** Punches are processed per device in time order, not merged
  across devices, so during a catch-up the duplicate-scan and early-leave checks can see another
  device's earlier punch late.
- **Person id contract.** The web app only addresses people whose id matches `^[A-Za-z0-9]+$`.
  `firebase/migrate.py` lists up to 10 ids that do not match (dry run and real run); the bridge
  stores such punches, but those people cannot be opened or reported on in the web app.
- **Hardware and Windows service unverified.** The real ZKTeco device, the SIM800L modem and the
  Windows service install and restart behaviour were never exercised in development. Run the
  manual checklist in [apps/bridge/README.md](../apps/bridge/README.md).
- **Live updates tested on emulators only.** The realtime path was exercised only against the
  Firebase emulators, not against a production project.
- **Unverified: GitHub Actions.** The CI workflow's commands were replayed locally, but the workflow
  itself had not been run on GitHub when this was written.
- **Reports.** Statistics read at most 50,000 punches (a notice says when the range has more) and
  have no weekly or punch-trend charts; `/attendance` has a CSV export but no PDF export. The person
  PDF reads only that person's punches, at most 5,000 (a larger range answers 413 and asks for a
  narrower one); it treats a day as a school day unless it is a holiday or one of the weekend days
  set under Settings, General (default Friday and Saturday), and a school day without a punch is an
  absence.
- **Absent counts.** People created after a date are counted as absent for that earlier date.
- **Last-admin guard.** The guard that prevents removing or demoting the last admin is not transactional;
  two concurrent requests can bypass it.
- **Configuration backup restore.** A restore is not atomic across batches; an interrupted restore can leave a
  partial state. The configuration backup excludes attendance and SMS logs (see "Backups").
- **Stored but unused.** `settings/app.notificationSound` is saved but nothing plays a sound yet, and
  `devices.lastSeen` is never written by the bridge (the dashboard uses the heartbeat instead).
- **USSD replies.** The bridge can continue a USSD session (`ussd_reply_session`), but the web app has
  no UI to send a reply; only the initial USSD code can be run.
