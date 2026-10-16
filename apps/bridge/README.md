# SM Scolers bridge service

Headless Windows service: reads ZKTeco terminals, stores punches in Firestore, sends
attendance SMS through a GSM modem, runs website commands and writes a heartbeat.

Run by hand: `sm-scolers-bridge --config %ProgramData%\SMScolersBridge\config.json`
(config holds `service_account_path` and `project_id`; `serviceAccountPath` / `projectId`
are accepted too; the bridge log is `bridge.log` next to the config file).

## Prerequisites

- Windows 10 / Windows Server 2016 or newer, with an elevated (Administrator) PowerShell.
- Python **3.12 or newer** (the `py` launcher or `python.exe` on PATH).
- [NSSM](https://nssm.cc) (`nssm.exe`). The installer does not download it: put it on PATH or
  pass `-NssmPath`.
- A Firebase **service-account JSON key** for the project and the project id.

## Install

From an elevated PowerShell (Windows PowerShell 5.1 or PowerShell 7), in `apps\bridge\installer`:

```powershell
.\install-service.ps1 -ServiceAccountPath C:\keys\serviceAccount.json -ProjectId my-firebase-project
```

Options: `-InstallDir` (default `%ProgramData%\SMScolersBridge`), `-ServiceName`
(default `SMScolersBridge`), `-PythonExe` (default: `py -3.13`, else `python` on PATH; must be
3.12+), `-NssmPath` (default: `nssm.exe` on PATH).

```powershell
.\install-service.ps1 -ServiceAccountPath C:\keys\sa.json -ProjectId my-project `
    -NssmPath C:\tools\nssm\win64\nssm.exe -PythonExe C:\Python313\python.exe
```

Preview everything without changing anything (no elevation needed):

```powershell
.\install-service.ps1 -ServiceAccountPath C:\keys\sa.json -ProjectId my-project -DryRun
```

What it does: creates `InstallDir`; copies the key to `InstallDir\serviceAccountKey.json`
and restricts it to SYSTEM and Administrators; creates `InstallDir\venv` and installs this
package into it; writes `InstallDir\config.json`; registers the service with NSSM (automatic
start at boot, restart 5 s after any exit, `AppStopMethodConsole` 15000 ms, rotated
stdout/stderr log); starts it. Re-running it is safe: an existing service gets its settings
updated; a running service is stopped first (the venv files are in use) and started again afterwards.
The original key file at `-ServiceAccountPath` is left untouched - delete it yourself if you do
not want two copies. The install directory is restricted to SYSTEM and Administrators before the
key is copied in.

## Uninstall

```powershell
.\uninstall-service.ps1                 # stop + remove the service, keep data
.\uninstall-service.ps1 -RemoveData     # also delete InstallDir (config, key copy, logs, venv)
```

`-RemoveData` only deletes a directory that looks like a bridge install (`config.json` plus
`venv\Scripts\sm-scolers-bridge.exe` or a `logs` folder) and refuses junctions/symlinks, drive
roots and `%ProgramData%` itself.

Both scripts accept `-ServiceName`, `-InstallDir`, `-NssmPath` and `-DryRun`.

## Logs

- `%ProgramData%\SMScolersBridge\bridge.log` - the bridge's own rotating log (next to `config.json`).
- `%ProgramData%\SMScolersBridge\logs\service.log` - stdout/stderr captured by NSSM, rotated at
  1 MiB (`AppRotateFiles 1`, `AppRotateBytes 1048576`). Startup crashes show up here.

(Paths change if you used `-InstallDir`.)

## Manual verification checklist (real Windows machine)

The installer is not exercised by automated tests (`installer\Test-Installer.ps1` only checks
syntax and `-DryRun` output). Verify on the target machine:

1. Install: `.\install-service.ps1 -ServiceAccountPath <key.json> -ProjectId <id>`.
2. `Get-Service SMScolersBridge` - expect `Running` (start type Automatic).
3. Kill the bridge's whole process tree. The venv's `sm-scolers-bridge.exe` is a launcher that
   starts `python.exe` as a child, so killing only one of them can leave an orphan. Find the
   PIDs and kill the tree with `/T`:

   ```powershell
   (Get-CimInstance Win32_Service -Filter "Name='SMScolersBridge'").ProcessId   # nssm.exe (service host) - do NOT kill this one
   Get-CimInstance Win32_Process -Filter "Name='sm-scolers-bridge.exe'" | Select-Object ProcessId, ParentProcessId
   taskkill /F /T /PID <ProcessId of sm-scolers-bridge.exe>
   ```

   (`nssm status SMScolersBridge` only reports `SERVICE_RUNNING`, not a PID.) NSSM's
   `AppKillProcessTree` defaults to 1, which also kills the whole tree on a normal stop.
4. Wait up to 15 s and run `Get-Service SMScolersBridge` again - expect `Running`, and a new
   `sm-scolers-bridge.exe` / `python.exe` process id (no orphaned old `python.exe` left behind).
5. Check `bridge.log` and `logs\service.log` for the restart and the new heartbeat.
6. Graceful stop: `Stop-Service SMScolersBridge` should return within 15 s and leave the service
   `Stopped` with no leftover `python.exe` (this exercises the Ctrl-C / `AppStopMethodConsole` path).
7. Optional: reboot and confirm the service comes up by itself.
8. Uninstall: `.\uninstall-service.ps1` (add `-RemoveData` to wipe data); `Get-Service SMScolersBridge`
   should then report that it cannot be found.

**To be confirmed on a real Windows machine:** the automatic restart after the process tree is
killed (steps 3-4), the absence of an orphaned launcher/`python.exe`, and the graceful stop within
15 s (step 6) were designed from NSSM's documented behaviour but have not been run here.

## Operational notes

- **One bridge process per Firebase project.** Run exactly one instance. On start the bridge
  marks commands left in `running` by a previous process as `error` ("bridge restarted"), so a
  second live instance would fail the first one's in-flight commands.
- NSSM `AppStopMethodConsole` must be at least **15000** ms (the installer sets exactly that).
  The service stops by setting an event that the poll loop waits on; Python on Windows may not
  run its signal handler until a blocking wait (up to `pollIntervalSec`) or a modem/device call
  returns, so a shorter value makes NSSM kill the process mid-cycle.
- The service restarts on any exit (`AppExit Default Restart`, `AppRestartDelay 5000`).

## Upgrade note

`smsLog` documents created before the `date` field existed are not seen by the once-per-day
absent/summary SMS check. The first day after upgrading to a version that has the `date` field
may therefore repeat one absent/summary SMS.
