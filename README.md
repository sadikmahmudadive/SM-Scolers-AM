# SM Scolers Attendance System - Commercial Edition

A desktop command center for syncing ZKTeco biometric data to Firebase, keeping parents/guardians informed via SMS, and giving staff a futuristic, monitor-driven UI that logs what the system actually sends.

## Highlights

- **Realtime Sync Engine**: Polls the ZKTeco K50‑A every few seconds, filters out duplicates, and writes attendance into `attendance_logs/{user_id}_{timestamp}` so each entry stays unique.
- **Flexible Roles**: Manage students, teachers, staff, and admins with contact info, class/section metadata, and parent/guardian phone numbers.
- **SMS Transparency**: Every successful SMS is relayed back to the main `Monitor` view (`[SMS] To …`) plus the log window; templates for normal and late punches live in `config.json` and are fully editable.
- **GSM & USSD Tooling**: Test signal strength, carrier, and balance; the same queue that updates the monitor also surfaces GSM responses without threading issues.
- **Futuristic UI**: Tkinter + ttkbootstrap frames themed for the "superhero" palette with golden accents, including dashboards, filters, and lightweight trees.
- **Packaging-Ready**: `app.spec` is provided for PyInstaller builds and can be wrapped in an Inno/WiX installer for commercial distribution.

## Configuration

Edit `config.json` (or use the GUI) to set values for:

- `ZK_IP`, `ZK_PORT`, `ZK_TIMEOUT`, `POLL_INTERVAL_SEC` for the biometric device.
- `GSM_PORT`, `GSM_BAUD`, `USSD_CODE`, and `SMS_SENDING_ENABLED` for SIM800L control.
- `SERVICE_ACCOUNT`, `FIREBASE_DB_URL`, `FIREBASE_CRED_PATH` for Google Firebase.
- `CLASS_SCHEDULES`, `SMS_TEMPLATE`, and `LATE_SMS_TEMPLATE` so the app formats the text the way your school requires.

## Running Locally

```bash
pip install -r requirements.txt
python app.py
```

Once open, the tabs provide:

- **Users**: Filter by role, search, sync device users, and inspect biometrics enrolment.
- **Dashboard**: Instant stats (users/sms/present) plus the most recent activity feed.
- **Monitor**: Live log with GSM + SMS payloads plus `/USSD` actions.
- **Logs & Control**: Start/stop the sync loop, force data refresh, and test the hardware.

## SMS Templates & Monitoring

By default, the app sends two SMS variants:

1. Normal attendance: configured via `SMS_TEMPLATE`, e.g. `Attendance: {name} ({id}) checked in at {time}`.
2. Late punch alerts: `LATE_SMS_TEMPLATE` can include `start`/`end` windows and warns recipients.

Each text is only queued when sending succeeds; the monitor and log tab then show lines like `"[SMS] To 017XXXX: Attendance: ..."`. Disable SMS entirely (`SMS_SENDING_ENABLED: false`) to keep the rest of the workflow running without touching the serial port.

## Packaging for Delivery

1. Build a single-file binary: `pyinstaller --noconfirm app.spec` (uses the existing spec for icon, console suppression, and UPX tweaks).
2. Wrap the generated `dist/app` folder into an installer (Inno Setup/WiX) so you can ship `app.exe`, `config.json`, `serviceAccountKey.json`, and `icon.ico` together.
3. Include the drivers/config instructions from this repo so installers set the COM/ZKTeco defaults correctly.

## Firebase Structure

- `users/{user_id}` → `{name, role, phone, father_phone, mother_phone, class_name, section, …}`
- `attendance_logs/{user_id}_{iso_ts}` → `{user_id, timestamp, status, name, role}`

The GUI also caches enrolled IDs so the Users table marks which records already exist on the device.

## Support & Licensing

This is a commercial product; contact the developer for licensing, customization, and installation bundles.

For issues, review the `Logs & Control` tab or send the log file produced in the `Monitor` view.
