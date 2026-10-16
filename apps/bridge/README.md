# SM Scolers bridge service

Headless Windows service: reads ZKTeco terminals, stores punches in Firestore, sends
attendance SMS through a GSM modem, runs website commands and writes a heartbeat.

Run: `sm-scolers-bridge --config %ProgramData%\SMScolersBridge\config.json`
(config holds `serviceAccountPath` and `projectId`; logs go to `bridge.log` next to it).

## Notes for the installer task (NSSM)

- Set `AppStopMethodConsole` to at least **15000** ms. The service stops by setting an
  event that the poll loop waits on; Python on Windows may not run its signal handler
  until a blocking wait (up to `pollIntervalSec`) or a modem/device call returns, so a
  shorter value makes NSSM kill the process mid-cycle.
- Set the service to restart on failure; on start the bridge marks commands left
  `running` by a previous process as `error` ("bridge restarted").
- The bridge expects one running instance per Firebase project.
