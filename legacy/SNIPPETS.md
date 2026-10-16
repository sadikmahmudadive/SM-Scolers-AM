# SM Scolers Attendance System — Features & Code Snippets

This document summarizes the implemented features, key files, and useful code snippets from the project (ZKTeco K50-A + Firebase + SIM800L + Tkinter desktop app).

---

## Files

- `main.py` — CLI sync script (earlier implementation, robust sync + SMS).
- `app.py` — Full Tkinter desktop application (Users, Attendance, Config, Logs).
- `config.json` — Saved app configuration.
- `requirements.txt` — Dependencies: `firebase_admin`, `pyserial`, `pyzk`.
- `README.md` — Installation and usage notes.
- `SNIPPETS.md` — (this file)

---

## High-level Features

- Device sync from ZKTeco K50-A over LAN without clearing device logs.
- Firebase Realtime Database integration (`attendance_logs` and `users` nodes).
- Duplicate protection using unique keys: `UserID_Timestamp`.
- SMS notifications via SIM800L using AT commands.
- Robust background polling loop with error handling and configurable `POLL_INTERVAL_SEC`.
- Tkinter GUI with tabs: Users, Attendance, Config, Logs & Control.
- Thread-safe logging using a `queue.Queue` and `after()` pump.
- Handles Firebase responses shaped as dicts or lists.

---

## How to run

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Update `config.json` or open the app and configure:
- `ZK_IP`, `ZK_PORT`
- `GSM_PORT` (e.g. `COM5`)
- `FIREBASE_CRED_PATH` (service account JSON)
- `FIREBASE_DB_URL`

3. Run the desktop app:

```bash
python app.py
```

4. Use the GUI:
- `Users` tab: add/edit/delete personnel.
- `Attendance` tab: view check-in/out and hours; filter by user/date.
- `Config` tab: change device/GSM/Firebase settings.
- `Logs & Control` tab: Start/Stop sync, Test GSM.

---

## Key snippets

### Firebase initialization
```python
cred = credentials.Certificate(FIREBASE_CRED_PATH)
firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
```

### Unique key formatter
```python
def format_key(user_id, timestamp_str):
    return f"{user_id}_{timestamp_str.replace(' ', '_').replace(':', '-') }"
```

### ZKTeco sync (core)
```python
zk_client = ZK(ZK_IP, port=ZK_PORT, timeout=ZK_TIMEOUT)
conn = zk_client.connect()
conn.disable_device()
records = conn.get_attendance() or []
for r in records:
    key = format_key(str(r.user_id), str(r.timestamp))
    if key not in existing_keys:
        db.reference('attendance_logs').child(key).set({...})
        existing_keys.add(key)
conn.enable_device()
conn.disconnect()
```

### Send SMS (SIM800L) — AT flow
```python
ser = serial.Serial(GSM_PORT, GSM_BAUD, timeout=2)
ser.write(b"AT\r")
time.sleep(0.3)
ser.write(b"AT+CMGF=1\r")
time.sleep(0.3)
ser.write(f'AT+CMGS="{phone}"\r'.encode())
ser.write(message.encode() + b"\x1A")  # Ctrl+Z
time.sleep(2)
ser.close()
```

### Test GSM (AT + CSQ)
```python
ser.write(b"AT\r")
resp = ser.read(100).decode(errors='ignore')
ser.write(b"AT+CSQ\r")
sig = ser.read(100).decode(errors='ignore')
```

### Background polling loop (threaded)
```python
def run_loop(config, log_callback, stop_event):
    existing_keys = fetch_existing_keys(...)
    while not stop_event.is_set():
        sync_attendance(config, log_callback)
        stop_event.wait(config['POLL_INTERVAL_SEC'])
```

- Background threads should use `enqueue_log(msg)` to push messages to the GUI thread.

### Thread-safe GUI logging (Tkinter)
```python
# In AttendanceApp.__init__
self.log_queue = queue.Queue()
self.after(100, self._process_log_queue)

# Called from background threads:
self.enqueue_log(msg)

# _process_log_queue scheduled on main thread:
while True:
    msg = self.log_queue.get_nowait()
    self.log_message(msg)
```

### Fetch users (handles dict or list shapes)
```python
def fetch_users(db_url, cred_path):
    data = db.reference('users').get() or {}
    users = []
    if isinstance(data, dict):
        for uid, udata in data.items():
            users.append(User.from_dict(uid, udata))
    elif isinstance(data, list):
        for idx, udata in enumerate(data):
            if isinstance(udata, dict) and 'name' in udata:
                users.append(User.from_dict(str(idx), udata))
    return users
```

### Attendance grouping (check-in / check-out / hours)
```python
# group by (user_id, date)
daily_records = defaultdict(list)
for r in records:
    daily_records[(r.user_id, r.datetime.date())].append(r)
for (user_id, date), recs in daily_records.items():
    recs.sort(key=lambda x: x.datetime)
    check_in = recs[0].datetime.time()
    check_out = recs[-1].datetime.time() if len(recs) > 1 else None
    if check_in and check_out:
        hours = (datetime.combine(date, check_out) - datetime.combine(date, check_in))
```

---

## Next suggestions (optional)
- Export attendance to CSV/PDF reports.
- Add user import (CSV) and bulk operations.
- Add authentication for app launch and role-based UI.
- Add tests for parsing/grouping logic and mock ZK device.

---

File created: `SNIPPETS.md` in project root.

If you want, I can also:
- generate a printable developer handoff (ZIP) containing the app and README,
- add CSV export and a sample report template,
- or implement role-based access quickly. Which should I do next?
