# Deployment guide

Order of work: Firebase project, Vercel, first admin, bridge, migration, smoke checklist.
All names below in angle brackets are placeholders; nothing here is a real project.

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

## 7. Known limitations and follow-ups

- **Bengali in PDFs.** Bengali glyphs are not rendered in the person PDF (it uses Helvetica).
  Follow-up: bundle an OFL Noto Sans Bengali font and register it with `Font.register`.
- **Heartbeat timing.** The heartbeat is stamped at the **start** of a bridge iteration. A very long
  iteration (many SMS, USSD or AT commands up to 30 s each, several device timeouts) can make a
  healthy bridge look offline (over 90 s) on the dashboard. Follow-up: stamp at write time or beat
  between stages.
- **Hardware untested.** The real ZKTeco device, the SIM800L modem and the Windows service
  install and restart behaviour were never exercised in development. Run the manual checklist
  in [apps/bridge/README.md](../apps/bridge/README.md).
- **Live updates tested on emulators only.** The realtime path was exercised only against the
  Firebase emulators, not against a production project.
- **Absent counts.** People created after a date are counted as absent for that earlier date.
- **Last-admin guard.** The guard that prevents removing or demoting the last admin is not transactional;
  two concurrent requests can bypass it.
- **Report cap.** Statistics and the person PDF read at most 50,000 punches.
- **Backups restore.** A restore is not atomic across batches; an interrupted restore can leave a partial state.
- **Unverified: GitHub Actions.** The CI workflow's commands were replayed locally, but the workflow
  itself had not been run on GitHub when this was written.
