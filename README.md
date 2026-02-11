# SM Scolers Attendance System - Commercial Edition

A complete desktop application for automated attendance tracking using ZKTeco biometric devices, Firebase database, and GSM notifications.

## Features

- **Automated Sync**: Continuously fetches attendance from ZKTeco K50-A and uploads to Firebase.
- **User Management**: Add, edit, delete students, teachers, and staff with roles and phone numbers.
- **Attendance Reports**: View check-in/check-out times, calculate hours worked, filter by user/date.
- **GSM Notifications**: Send SMS alerts for attendance events.
- **Configurable**: Easy setup for device IPs, ports, Firebase credentials.
- **Real-time Logs**: Monitor sync status and errors.

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up Firebase:
   - Create a Firebase project.
   - Enable Realtime Database.
   - Download service account key JSON and place as `serviceAccountKey.json`.
   - Update `FIREBASE_DB_URL` in `config.json` or app.

3. Configure hardware:
   - Connect ZKTeco K50-A to network.
   - Connect SIM800L to COM port (update in config).
   - Insert SIM card with SMS plan.

4. Run the app:
   ```bash
   python app.py
   ```

## Usage

- **Users Tab**: Manage personnel database.
- **Attendance Tab**: View and filter attendance records.
- **Config Tab**: Adjust settings.
- **Logs & Control**: Start sync, test GSM, view logs.

## Firebase Structure

- `users/{user_id}`: {name, role, phone}
- `attendance_logs/{key}`: {user_id, timestamp, status}

## Commercial License

This software is provided for commercial use. Contact developer for licensing details.

## Support

For issues, check logs or contact support.