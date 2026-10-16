# firebase-tests

Firestore security rules and their emulator tests.

- Run: `pnpm --filter firebase-tests test` (starts and stops the Firestore emulator itself via `firebase emulators:exec`; no separate emulator needed).
- Requires Java 11+ on the machine (the Firestore emulator is a JAR; downloaded on first run). Uses the demo project id `demo-hrm`, so no Firebase project is needed.
- Windows: the emulator java process can outlive the run and keep port 8089 busy; kill it before re-running.
