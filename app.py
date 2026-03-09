"""
SM Scolers Attendance System - Commercial Edition v13.0
MODERN DARK UI - Polished, interactive, professional
FEATURE UPDATE: Toast notifications, keyboard shortcuts, status bar,
                absent SMS alerts, daily summary SMS, user attendance history,
                auto backup/restore, multi-device ZK, student report PDF,
                early leave SMS, class filters, holiday calendar, CSV import,
                user photos, theme toggle, PIN lock, notification sounds
ALL ORIGINAL FEATURES PRESERVED - No functionality removed
"""

import csv
import json
import threading
import queue
import time
import sys
import os
import shutil
import re
import hashlib
import winsound
import ctypes
from datetime import datetime, date, time as dt_time, timedelta
from typing import Dict, Set, List

# --- Hide any console window (prevents CMD flash on installed PCs) ---
try:
    ctypes.windll.kernel32.FreeConsole()
except Exception:
    pass

# --- UI Imports ---
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, scrolledtext

# Try importing ttkbootstrap with fallbacks
try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *
    from ttkbootstrap.style import Style
    # ToastNotification import kept but not used
    try:
        from ttkbootstrap.widgets import ToastNotification
    except ImportError:
        try:
            from ttkbootstrap.dialogs import ToastNotification
        except ImportError:
            try:
                from ttkbootstrap.toast import ToastNotification
            except:
                ToastNotification = None
    THEME_AVAILABLE = True
except ImportError:
    import tkinter.ttk as ttk
    THEME_AVAILABLE = False
    ToastNotification = None
    print("WARNING: 'ttkbootstrap' not found. Run 'pip install ttkbootstrap'.")

# --- Hardware/Cloud Imports ---
import serial
from zk import ZK
import firebase_admin
from firebase_admin import credentials, db

# --- Optional: Pillow for user photos ---
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def resource_path(relative_path):
    """Return path to resource, handling PyInstaller _MEIPASS directory."""
    if os.path.isabs(relative_path):
        return relative_path
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ---------------------------
# GLOBAL LOCKS
# ---------------------------
SERIAL_LOCK = threading.Lock()

# ---------------------------
# CONFIGURATION
# ---------------------------
APP_NAME = "SM Scolers Attendance"
DATA_DIR_ENV = "SM_SCOLERS_DATA_DIR"

def get_user_data_dir():
    env_override = os.environ.get(DATA_DIR_ENV)
    base_dir = env_override or os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(os.path.abspath(base_dir), APP_NAME)

USER_DATA_DIR = get_user_data_dir()
CONFIG_FILE = os.path.join(USER_DATA_DIR, "config.json")
SERVICE_ACCOUNT_FILE = os.path.join(USER_DATA_DIR, "serviceAccountKey.json")

DEFAULT_CONFIG = {
    "ZK_IP": "192.168.1.201",
    "ZK_PORT": 4370,
    "ZK_TIMEOUT": 5,
    "GSM_PORT": "COM3",
    "GSM_BAUD": 9600,
    "SMS_SENDING_ENABLED": True,
    "USSD_CODE": "*121#",
    "SMS_TEMPLATE": "Attendance: {name} ({id}) checked in at {time}",
    "LATE_SMS_TEMPLATE": "⚠ LATE: {name} ({id}) punched at {time}. Expected in-time: {start} - {end}",
    "ABSENT_SMS_ENABLED": False,
    "ABSENT_SMS_TIME": "09:30",
    "ABSENT_SMS_TEMPLATE": "⚠ ABSENT: {name} ({id}) was not marked present today ({date}). Please contact the school.",
    "DAILY_SUMMARY_ENABLED": False,
    "DAILY_SUMMARY_TIME": "17:00",
    "ADMIN_PHONE_1": "",
    "ADMIN_PHONE_2": "",
    "DAILY_SUMMARY_TEMPLATE": "📊 Daily Summary ({date}): Present: {present}, Absent: {absent}, Late: {late}, Total: {total}",
    "FIREBASE_CRED_PATH": SERVICE_ACCOUNT_FILE,
    "FIREBASE_DB_URL": "https://fir-m-scholars-school-1999b-default-rtdb.firebaseio.com/",
    "POLL_INTERVAL_SEC": 10,
    "USER_PHONE_MAP": {},
    "CLASS_SCHEDULES": {},   # e.g. {"Nursery": {"start": "07:40", "end": "08:10"}, "1": {...}}
    "EARLY_LEAVE_SMS_ENABLED": False,
    "EARLY_LEAVE_SMS_TEMPLATE": "\u26a0 EARLY LEAVE: {name} ({id}) checked out at {time}. Expected end-time: {end}",
    "ZK_DEVICES": [],  # e.g. [{"ip": "192.168.1.201", "port": 4370, "name": "Main Gate"}]
    "HOLIDAYS": [],  # e.g. ["2026-03-26", "2026-04-14"]
    "APP_PIN": "",  # SHA-256 hash of PIN, empty = no lock
    "THEME": "darkly",  # darkly or flatly
    "NOTIFICATION_SOUND": True,
    "AUTO_BACKUP_ENABLED": False,
    "AUTO_BACKUP_TIME": "23:00",
    "AUTO_BACKUP_DIR": "",
}

def resolve_user_data_path(path):
    if not path:
        return path
    if os.path.isabs(path):
        return path
    return os.path.join(USER_DATA_DIR, path)

def get_service_account_path(config):
    candidate = resolve_user_data_path(config.get("FIREBASE_CRED_PATH", SERVICE_ACCOUNT_FILE) or SERVICE_ACCOUNT_FILE)
    if candidate and os.path.exists(candidate):
        return candidate
    return resource_path("serviceAccountKey.json")

def ensure_user_data_dir():
    os.makedirs(USER_DATA_DIR, exist_ok=True)

def copy_resource_to_user_data(resource_name, destination_path):
    if os.path.exists(destination_path):
        return
    try:
        src_path = resource_path(resource_name)
        if os.path.exists(src_path):
            shutil.copy(src_path, destination_path)
    except Exception as exc:
        print(f"Warning: Failed to copy {resource_name} to {destination_path}: {exc}")

def ensure_service_account_file():
    ensure_user_data_dir()
    copy_resource_to_user_data("serviceAccountKey.json", SERVICE_ACCOUNT_FILE)

def ensure_config_file():
    ensure_user_data_dir()
    if os.path.exists(CONFIG_FILE):
        return
    copy_resource_to_user_data("config.json", CONFIG_FILE)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)

ensure_user_data_dir()
ensure_service_account_file()
ensure_config_file()

def load_config():
    ensure_config_file()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        config = DEFAULT_CONFIG.copy()

    for key, value in DEFAULT_CONFIG.items():
        if key not in config:
            config[key] = value

    config["FIREBASE_CRED_PATH"] = resolve_user_data_path(
        config.get("FIREBASE_CRED_PATH", SERVICE_ACCOUNT_FILE) or SERVICE_ACCOUNT_FILE
    )
    return config

def save_config(config):
    ensure_user_data_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

def format_key(user_id, timestamp_str):
    clean_ts = re.sub(r"[^0-9]", "", timestamp_str)
    return f"{user_id}_{clean_ts}"

# ---------------------------
# DATA MODELS
# ---------------------------
class User:
    def __init__(self, user_id: str, name: str, role: str, phone: str = "", card_id: str = "",
                 # Student Specific:
                 student_type: str = "", class_name: str = "", section: str = "",
                 father_name: str = "", father_phone: str = "",
                 mother_name: str = "", mother_phone: str = ""):
        self.user_id = str(user_id)
        self.name = name
        self.role = role
        self.phone = phone
        self.card_id = card_id
        # Student specific
        self.student_type = student_type  # "School" or "Coaching"
        self.class_name = class_name
        self.section = section
        self.father_name = father_name
        self.father_phone = father_phone
        self.mother_name = mother_name
        self.mother_phone = mother_phone

    @staticmethod
    def from_dict(user_id: str, data: dict) -> 'User':
        return User(
            user_id,
            data.get("name", ""),
            data.get("role", "Student"),
            data.get("phone", ""),
            data.get("card_id", ""),
            data.get("student_type", ""),
            data.get("class_name", ""),
            data.get("section", ""),
            data.get("father_name", ""),
            data.get("father_phone", ""),
            data.get("mother_name", ""),
            data.get("mother_phone", "")
        )

    def to_dict(self):
        return {
            "name": self.name,
            "role": self.role,
            "phone": self.phone,
            "card_id": self.card_id,
            "student_type": self.student_type,
            "class_name": self.class_name,
            "section": self.section,
            "father_name": self.father_name,
            "father_phone": self.father_phone,
            "mother_name": self.mother_name,
            "mother_phone": self.mother_phone
        }

class AttendanceRecord:
    def __init__(self, key: str, user_id: str, timestamp: str, status: str, user_name: str = "", role: str = ""):
        self.key = key
        self.user_id = str(user_id)
        self.timestamp = timestamp
        self.status = status
        self.user_name = user_name
        self.role = role
        try:
            self.datetime = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            self.datetime = datetime.now()

# ---------------------------
# PUNCH STATUS LABELS
# ---------------------------
PUNCH_STATUS_MAP = {
    "0": "Check-In",
    "1": "Check-Out",
    "2": "Break-Out",
    "3": "Break-In",
    "4": "OT-In",
    "5": "OT-Out",
}

def punch_status_label(raw_status):
    """Convert ZK device numeric punch status to a human-readable label."""
    val = str(raw_status).strip()
    return PUNCH_STATUS_MAP.get(val, val)

# ---------------------------
# HARDWARE LOGIC (FULLY PRESERVED)
# ---------------------------
def get_gsm_signal_info(config):
    port = config.get("GSM_PORT", "COM3")
    baud = config.get("GSM_BAUD", 9600)
    carrier = "Searching..."
    signal = 0

    if not SERIAL_LOCK.acquire(timeout=2):
        return ("Busy", 0) 

    try:
        ser = serial.Serial(port, baud, timeout=1)
        time.sleep(0.5)

        def run_cmd(cmd, delay=0.25):
            ser.reset_input_buffer()
            ser.write((cmd + "\r").encode())
            time.sleep(delay)
            return ser.read(ser.inWaiting()).decode('utf-8', errors='ignore')

        resp_cpin = run_cmd('AT+CPIN?', delay=0.35)
        cpin_lower = resp_cpin.lower()
        if "sim not inserted" in cpin_lower:
            ser.close()
            return ("SIM NOT DETECTED", 0)
        if "+cpin: sim pin" in cpin_lower:
            ser.close()
            return ("SIM PIN REQUIRED", 0)
        if "+cpin: ready" not in cpin_lower and "error" in cpin_lower:
            ser.close()
            return ("SIM ERROR", 0)
        
        resp_csq = run_cmd('AT+CSQ', delay=0.25)
        match_csq = re.search(r"\+CSQ:\s*(\d+),", resp_csq)
        if match_csq:
            rssi = int(match_csq.group(1))
            signal = 0 if rssi == 99 else int((rssi / 31) * 100)

        resp_cops = run_cmd('AT+COPS?', delay=0.3)
        match_cops = re.search(r'\"(.*?)\"', resp_cops)
        if match_cops:
            carrier = match_cops.group(1)

        if signal == 0 and not match_cops:
            resp_creg = run_cmd('AT+CREG?', delay=0.25)
            if re.search(r"\+CREG:\s*\d,0", resp_creg):
                carrier = "No Network"
            elif re.search(r"\+CREG:\s*\d,2", resp_creg):
                carrier = "Searching..."
        
        ser.close()
    except Exception:
        carrier = "No Connection"
        signal = 0
    finally:
        SERIAL_LOCK.release()
        
    return (carrier, signal)

def play_notification_sound():
    """Play a short notification beep (Windows only)."""
    try:
        winsound.MessageBeep(winsound.MB_OK)
    except Exception:
        pass


def send_sms_gsm(config, phone, message, log_cb):
    if not config.get("SMS_SENDING_ENABLED", True):
        log_cb(f"[GSM] SMS Skipped (Disabled): {phone}")
        return False

    if not SERIAL_LOCK.acquire(timeout=5):
        log_cb(f"[GSM ERROR] Port busy, could not send SMS to {phone}")
        return False

    try:
        ser = serial.Serial(config["GSM_PORT"], config["GSM_BAUD"], timeout=2)
        time.sleep(1)
        ser.write(b'AT\r')
        time.sleep(0.5)
        ser.write(b'AT+CMGF=1\r')
        time.sleep(0.5)
        ser.write(f'AT+CMGS="{phone}"\r'.encode())
        time.sleep(0.5)
        ser.write(message.encode() + b"\x1A")
        time.sleep(3)
        # Read delivery response
        resp = ""
        if ser.inWaiting():
            resp = ser.read(ser.inWaiting()).decode('utf-8', errors='ignore')
        ser.close()
        # Check for +CMGS: <mr> which confirms message was accepted
        if "+CMGS:" in resp:
            log_cb(f"[GSM] SMS sent to {phone} (confirmed)")
        else:
            log_cb(f"[GSM] SMS sent to {phone} (no +CMGS confirmation)")
        return True
    except Exception as e:
        log_cb(f"[GSM ERROR] {e}")
        return False
    finally:
        SERIAL_LOCK.release()

def decode_hex_string(hex_str):
    try:
        clean_hex = hex_str.replace('"', '').strip()
        try:
            return bytes.fromhex(clean_hex).decode('utf-8')
        except:
            return bytes.fromhex(clean_hex).decode('utf-16-be')
    except Exception:
        return hex_str

def _parse_cusd_response(raw_resp):
    """Parse +CUSD response. Returns (text, session_active).
    session_active=True means the network expects a reply (code 1)."""
    if "+CUSD:" not in raw_resp:
        return ("Timeout/No USSD Reply", False)

    # Standard format: +CUSD: <n>,"<payload>",<dcs>
    match = re.search(r'\+CUSD:\s*(\d),\s*"(.*?)"(?:,\s*(\d+))?', raw_resp, re.DOTALL)
    cusd_code = None
    if match:
        cusd_code = int(match.group(1))
        payload = match.group(2)
        dcs = int(match.group(3)) if match.group(3) else 15
        session_active = (cusd_code == 1)

        # DCS 72 = UCS2, or detect hex that looks like UCS2 (even length, >4 chars, all hex)
        if dcs == 72 or (re.match(r'^[0-9A-Fa-f]+$', payload) and len(payload) % 4 == 0 and len(payload) > 4):
            decoded = decode_hex_string(payload)
            if decoded and decoded != payload:
                return (decoded, session_active)

        # GSM 7-bit hex (even length, all hex, not UCS2)
        if re.match(r'^[0-9A-Fa-f]+$', payload) and len(payload) % 2 == 0 and len(payload) > 4:
            decoded = decode_hex_string(payload)
            if decoded and decoded != payload:
                return (decoded, session_active)

        if payload:
            return (payload, session_active)

    # Fallback: extract whatever follows +CUSD:
    cusd_part = raw_resp.split("+CUSD:")[1].strip()
    # Try to detect cusd code from fallback
    code_match = re.match(r'(\d)', cusd_part)
    session_active = (int(code_match.group(1)) == 1) if code_match else False
    if ',' in cusd_part:
        parts = cusd_part.split(',', 2)
        if len(parts) >= 2 and parts[1].strip().startswith('"'):
            payload = parts[1].strip().strip('"')
            if re.match(r'^[0-9A-Fa-f]+$', payload) and len(payload) % 2 == 0 and len(payload) > 4:
                decoded = decode_hex_string(payload)
                if decoded and decoded != payload:
                    return (decoded, session_active)
            if payload:
                return (payload, session_active)

    return (cusd_part.strip() or "No readable USSD response", session_active)


def run_ussd_command(config, ussd_code):
    """Send a USSD command. Returns (text, session_active) tuple."""
    if not SERIAL_LOCK.acquire(timeout=3):
        return ("System Busy. Try again.", False)

    result = ("No Response", False)
    try:
        ser = serial.Serial(config["GSM_PORT"], config["GSM_BAUD"], timeout=3)
        time.sleep(1)
        ser.write(b'AT+CMGF=1\r') 
        time.sleep(0.2)
        ser.write(b'AT+CSCS="GSM"\r')
        time.sleep(0.2)
        # Cancel any pending USSD session
        ser.write(b'AT+CUSD=2\r')
        time.sleep(0.3)
        ser.reset_input_buffer()

        def _read_cusd_response(ser, timeout_sec=20):
            """Read until +CUSD: response is complete or timeout."""
            start = time.time()
            buf = ""
            found_cusd = False
            while time.time() - start < timeout_sec:
                if ser.inWaiting():
                    buf += ser.read(ser.inWaiting()).decode('utf-8', errors='ignore')
                    if "+CUSD:" in buf:
                        found_cusd = True
                    # Response is complete when we see the closing quote + optional DCS + OK/newline after +CUSD:
                    if found_cusd and ('\nOK' in buf or '\r\nOK' in buf or buf.rstrip().endswith('"') or re.search(r'\+CUSD:\s*\d,".*?",\s*\d+', buf, re.DOTALL)):
                        # Drain any trailing bytes
                        time.sleep(0.5)
                        if ser.inWaiting():
                            buf += ser.read(ser.inWaiting()).decode('utf-8', errors='ignore')
                        break
                time.sleep(0.3)
            return buf

        # First attempt: let modem choose encoding
        cmd = f'AT+CUSD=1,"{ussd_code}"\r'
        ser.write(cmd.encode())
        raw_resp = _read_cusd_response(ser)

        # If no response, retry with explicit GSM encoding (DCS=15)
        if "+CUSD:" not in raw_resp:
            ser.write(b'AT+CUSD=2\r')
            time.sleep(0.3)
            ser.reset_input_buffer()

            cmd = f'AT+CUSD=1,"{ussd_code}",15\r'
            ser.write(cmd.encode())
            raw_resp = _read_cusd_response(ser)

        result = _parse_cusd_response(raw_resp)
        ser.close()
    except Exception as e:
        result = (f"Error: {str(e)}", False)
    finally:
        SERIAL_LOCK.release()
    return result


def run_ussd_reply(config, reply_text):
    """Send a reply to an ongoing USSD session. Returns (text, session_active) tuple."""
    if not SERIAL_LOCK.acquire(timeout=3):
        return ("System Busy. Try again.", False)

    result = ("No Response", False)
    try:
        ser = serial.Serial(config["GSM_PORT"], config["GSM_BAUD"], timeout=3)
        time.sleep(0.5)

        def _read_cusd_response(ser, timeout_sec=20):
            start = time.time()
            buf = ""
            found_cusd = False
            while time.time() - start < timeout_sec:
                if ser.inWaiting():
                    buf += ser.read(ser.inWaiting()).decode('utf-8', errors='ignore')
                    if "+CUSD:" in buf:
                        found_cusd = True
                    if found_cusd and ('\nOK' in buf or '\r\nOK' in buf or buf.rstrip().endswith('"') or re.search(r'\+CUSD:\s*\d,".*?",\s*\d+', buf, re.DOTALL)):
                        time.sleep(0.5)
                        if ser.inWaiting():
                            buf += ser.read(ser.inWaiting()).decode('utf-8', errors='ignore')
                        break
                time.sleep(0.3)
            return buf

        ser.reset_input_buffer()
        cmd = f'AT+CUSD=1,"{reply_text}"\r'
        ser.write(cmd.encode())
        raw_resp = _read_cusd_response(ser)
        result = _parse_cusd_response(raw_resp)
        ser.close()
    except Exception as e:
        result = (f"Error: {str(e)}", False)
    finally:
        SERIAL_LOCK.release()
    return result


def cancel_ussd_session(config):
    """Cancel any ongoing USSD session."""
    if not SERIAL_LOCK.acquire(timeout=3):
        return
    try:
        ser = serial.Serial(config["GSM_PORT"], config["GSM_BAUD"], timeout=2)
        time.sleep(0.3)
        ser.write(b'AT+CUSD=2\r')
        time.sleep(0.5)
        ser.close()
    except Exception:
        pass
    finally:
        SERIAL_LOCK.release()


def read_sms_inbox(config, max_messages=20):
    """Read SMS messages from SIM inbox. Returns list of (index, sender, timestamp, body) tuples."""
    if not SERIAL_LOCK.acquire(timeout=5):
        return []

    messages = []
    try:
        ser = serial.Serial(config["GSM_PORT"], config["GSM_BAUD"], timeout=3)
        time.sleep(0.5)
        ser.write(b'AT+CMGF=1\r')
        time.sleep(0.3)
        ser.write(b'AT+CSCS="GSM"\r')
        time.sleep(0.3)
        ser.reset_input_buffer()
        ser.write(b'AT+CMGL="ALL"\r')

        # Read response with timeout
        start = time.time()
        buf = ""
        while time.time() - start < 10:
            if ser.inWaiting():
                buf += ser.read(ser.inWaiting()).decode('utf-8', errors='ignore')
                if '\nOK' in buf or '\r\nOK' in buf:
                    break
            time.sleep(0.3)

        # Parse: +CMGL: <index>,<stat>,<oa>,<alpha>,<scts>\r\n<body>\r\n
        parts = re.split(r'\+CMGL:\s*', buf)
        for part in parts[1:]:
            lines = part.strip().split('\n', 1)
            if len(lines) < 2:
                continue
            header = lines[0].strip()
            body = lines[1].strip().split('\nOK')[0].split('\n+CMGL')[0].strip()

            # Parse header: index,"status","sender","","timestamp"
            hdr_match = re.match(r'(\d+),"[^"]*","([^"]*)",[^,]*,"([^"]*)"', header)
            if hdr_match:
                idx = int(hdr_match.group(1))
                sender = hdr_match.group(2)
                timestamp = hdr_match.group(3)
                if body:
                    messages.append((idx, sender, timestamp, body))

            if len(messages) >= max_messages:
                break

        ser.close()
    except Exception:
        pass
    finally:
        SERIAL_LOCK.release()

    return messages


def delete_sms(config, index):
    """Delete a single SMS by index."""
    run_at_command(config, f'AT+CMGD={index}', read_seconds=2.0)


def run_at_command(config, command, read_seconds=1.0):
    if not command:
        return ""

    if not SERIAL_LOCK.acquire(timeout=3):
        return "System Busy. Try again."

    response = ""
    try:
        ser = serial.Serial(config["GSM_PORT"], config["GSM_BAUD"], timeout=2)
        time.sleep(0.3)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.write((command.strip() + "\r").encode())
        end_at = time.time() + max(0.2, read_seconds)
        chunks = []
        while time.time() < end_at:
            if ser.inWaiting():
                chunks.append(ser.read(ser.inWaiting()).decode("utf-8", errors="ignore"))
            time.sleep(0.1)
        response = "".join(chunks).strip()
        ser.close()
    except Exception as e:
        response = f"Error: {e}"
    finally:
        SERIAL_LOCK.release()

    return response or "(no response)"


def run_gsm_diagnostic_snapshot(config):
    checks = [
        ("Basic AT", "AT", 0.8),
        ("SIM PIN", "AT+CPIN?", 1.0),
        ("Signal", "AT+CSQ", 1.0),
        ("Registration", "AT+CREG?", 1.0),
        ("Operator", "AT+COPS?", 1.2),
        ("Packet Attach", "AT+CGATT?", 1.0),
        ("Last Error", "AT+CEER", 1.0),
    ]
    results = []
    for label, cmd, delay in checks:
        results.append((label, cmd, run_at_command(config, cmd, delay)))
    return results

def is_time_in_window(punch_time: datetime, window_start: str, window_end: str) -> bool:
    """Check if punch time is within the defined time window (inclusive of start, exclusive of end)."""
    try:
        start = datetime.strptime(window_start, "%H:%M").time()
        end = datetime.strptime(window_end, "%H:%M").time()
        punch = punch_time.time()
        # Simple check: if start <= punch < end
        if start <= end:
            return start <= punch < end
        else:  # overnight window (unlikely for school)
            return punch >= start or punch < end
    except:
        return True  # if schedule invalid, treat as on time

def run_sync_loop(config, log_callback, stop_event, update_stat_callback, trigger_refresh_callback, status_callback, enrollment_callback, user_cache_map, gsm_status_callback, sms_log_callback=None):
    sms_log_callback = sms_log_callback or (lambda *args, **kwargs: None)
    try:
        if not firebase_admin._apps:
            cred_path = get_service_account_path(config)
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred, {"databaseURL": config["FIREBASE_DB_URL"]})
    except Exception as e:
        log_callback(f"[INIT ERROR] Firebase: {e}")
        return

    existing_keys = set()
    keys_loaded = False
    for attempt in range(1, 4):
        try:
            ref = db.reference("attendance_logs")
            data = ref.get(shallow=True) 
            if data:
                if isinstance(data, list):
                    for i, v in enumerate(data):
                        if v: existing_keys.add(str(i))
                else:
                    existing_keys = set(data.keys())
            keys_loaded = True
            break
        except Exception as e:
            log_callback(f"[SYSTEM] Firebase key fetch failed (attempt {attempt}/3): {e}")
            if attempt < 3:
                stop_event.wait(3)
    if not keys_loaded:
        log_callback("[ERROR] Could not load existing keys from Firebase after 3 attempts. Engine aborted to prevent duplicate SMS.")
        return

    log_callback(f"[SYSTEM] Engine Started. {len(existing_keys)} existing records loaded. Polling every {config['POLL_INTERVAL_SEC']}s")

    # Track offline state locally
    device_was_offline = True

    while not stop_event.is_set():
        carrier, signal = get_gsm_signal_info(config)
        gsm_status_callback(carrier, signal)

        new_records_count = 0
        zk = ZK(config["ZK_IP"], port=config["ZK_PORT"], timeout=config["ZK_TIMEOUT"])
        conn = None
        try:
            conn = zk.connect()
            if conn:
                status_callback(True) 
                # Immediate sync if device was offline
                if device_was_offline:
                    log_callback("[SYSTEM] Device reconnected - performing full sync")
                    device_was_offline = False
                    # Re-fetch existing keys from Firebase to ensure accurate diff
                    try:
                        ref_check = db.reference("attendance_logs")
                        check_data = ref_check.get(shallow=True)
                        if check_data:
                            if isinstance(check_data, list):
                                existing_keys = set()
                                for i, v in enumerate(check_data):
                                    if v: existing_keys.add(str(i))
                            else:
                                existing_keys = set(check_data.keys())
                        else:
                            existing_keys = set()
                    except Exception:
                        pass
                conn.disable_device() 
                attendance = conn.get_attendance()
                if attendance:
                    for record in attendance:
                        uid = str(record.user_id)
                        ts_str = str(record.timestamp)
                        key = format_key(uid, ts_str)
                        if key not in existing_keys:
                            new_records_count += 1
                            log_callback(f"[NEW] User {uid} at {ts_str}")
                            # Play notification sound
                            if config.get("NOTIFICATION_SOUND", True):
                                play_notification_sound()
                            # Get user detail for role-based storage if needed
                            u_details = user_cache_map.get(uid, {})
                            u_name = u_details.get("name", "Unknown")
                            u_role = u_details.get("role", "Student")
                            
                            # Store in main log, include role for filtering later
                            db.reference(f"attendance_logs/{key}").set({
                                "user_id": uid, 
                                "timestamp": ts_str, 
                                "status": record.status,
                                "role": u_role,
                                "name": u_name
                            })
                            existing_keys.add(key)
                            
                            # --- SMS Sending Logic ---
                            if config.get("SMS_SENDING_ENABLED", True):
                                # Determine phone numbers based on role
                                phone_self = u_details.get("phone", "")
                                father_phone = u_details.get("father_phone", "")
                                mother_phone = u_details.get("mother_phone", "")
                                recipient_phones = set()

                                # For all roles: send to self if phone exists
                                if phone_self:
                                    recipient_phones.add(phone_self)
                                
                                # For Students: also send to parents
                                if u_role == "Student":
                                    if father_phone:
                                        recipient_phones.add(father_phone)
                                    if mother_phone:
                                        recipient_phones.add(mother_phone)
                                
                                # Check if this punch is LATE (only for Students with class schedule)
                                is_late = False
                                is_early_leave = False
                                schedule_info = None
                                if u_role == "Student":
                                    class_name = u_details.get("class_name", "")
                                    schedules = config.get("CLASS_SCHEDULES", {})
                                    if class_name in schedules:
                                        schedule = schedules[class_name]
                                        start = schedule.get("start", "")
                                        end = schedule.get("end", "")
                                        if start and end:
                                            try:
                                                punch_dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                                                if not is_time_in_window(punch_dt, start, end):
                                                    is_late = True
                                                    schedule_info = (start, end)
                                                # Early leave: check if user already has a punch today (this is checkout) and punch is before end time
                                                if config.get("EARLY_LEAVE_SMS_ENABLED", False) and not is_late:
                                                    punch_date_str = punch_dt.strftime("%Y-%m-%d")
                                                    has_earlier = any(
                                                        k.startswith(f"{uid}__") and punch_date_str in k and k != key
                                                        for k in existing_keys
                                                    )
                                                    if has_earlier:
                                                        try:
                                                            end_dt = datetime.strptime(f"{punch_date_str} {end}", "%Y-%m-%d %H:%M")
                                                            if punch_dt < end_dt:
                                                                is_early_leave = True
                                                                schedule_info = (start, end)
                                                        except Exception:
                                                            pass
                                            except Exception as e:
                                                log_callback(f"[TIME PARSE ERROR] {e}")
                                
                                # Choose appropriate template and send
                                for phone in recipient_phones:
                                    if not phone:
                                        continue
                                    try:
                                        dt_obj = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                                        time_only = dt_obj.strftime("%I:%M %p")
                                        date_only = dt_obj.strftime("%d-%b-%Y")
                                    except:
                                        time_only = ts_str
                                        date_only = ""
                                    
                                    if is_late and schedule_info:
                                        template = config.get("LATE_SMS_TEMPLATE", "⚠ LATE: {name} ({id}) punched at {time}. Expected in-time: {start} - {end}")
                                        try:
                                            msg_body = template.format(
                                                id=uid,
                                                name=u_name,
                                                time=time_only,
                                                date=date_only,
                                                status=record.status,
                                                role=u_role,
                                                start=schedule_info[0],
                                                end=schedule_info[1]
                                            )
                                            sent = send_sms_gsm(config, phone, msg_body, log_callback)
                                            if sent:
                                                sms_log_callback(phone, msg_body)
                                            update_stat_callback("sms")
                                        except Exception as e:
                                            log_callback(f"[SMS LATE ERROR] {e}")
                                    elif is_early_leave and schedule_info:
                                        template = config.get("EARLY_LEAVE_SMS_TEMPLATE", DEFAULT_CONFIG["EARLY_LEAVE_SMS_TEMPLATE"])
                                        try:
                                            msg_body = template.format(
                                                id=uid,
                                                name=u_name,
                                                time=time_only,
                                                date=date_only,
                                                status=record.status,
                                                role=u_role,
                                                end=schedule_info[1]
                                            )
                                            sent = send_sms_gsm(config, phone, msg_body, log_callback)
                                            if sent:
                                                sms_log_callback(phone, msg_body)
                                            update_stat_callback("sms")
                                            log_callback(f"[EARLY LEAVE] {u_name} (ID:{uid}) left at {time_only}, expected end: {schedule_info[1]}")
                                        except Exception as e:
                                            log_callback(f"[SMS EARLY LEAVE ERROR] {e}")
                                    else:
                                        # Normal attendance SMS
                                        template = config.get("SMS_TEMPLATE", "Attendance: {name} ({id}) checked in at {time}")
                                        try:
                                            msg_body = template.format(
                                                id=uid,
                                                name=u_name,
                                                time=time_only,
                                                date=date_only,
                                                status=record.status,
                                                role=u_role
                                            )
                                            sent = send_sms_gsm(config, phone, msg_body, log_callback)
                                            if sent:
                                                sms_log_callback(phone, msg_body)
                                            update_stat_callback("sms")
                                        except Exception as e:
                                            log_callback(f"[SMS ERROR] {e}")
                
                try:
                    device_users = conn.get_users()
                    enrolled_ids = [str(u.user_id) for u in device_users]
                    enrollment_callback(enrolled_ids)
                except Exception as e:
                    log_callback(f"[ZK USER FETCH] {e}")

                conn.enable_device()
                conn.disconnect()
                
                if new_records_count > 0:
                    update_stat_callback("sync", new_records_count)
                trigger_refresh_callback()

        except Exception as e:
            status_callback(False)
            device_was_offline = True  # Mark as offline
            if "timed out" not in str(e):
                log_callback(f"[ZK ERROR] {e}")
        finally:
            if conn:
                try: conn.disconnect()
                except: pass

        # --- Poll additional ZK devices ---
        for extra_dev in config.get("ZK_DEVICES", []):
            ex_ip = extra_dev.get("ip", "")
            ex_port = int(extra_dev.get("port", 4370))
            ex_name = extra_dev.get("name", ex_ip)
            if not ex_ip:
                continue
            ex_conn = None
            try:
                ex_zk = ZK(ex_ip, port=ex_port, timeout=config["ZK_TIMEOUT"])
                ex_conn = ex_zk.connect()
                if ex_conn:
                    ex_conn.disable_device()
                    ex_att = ex_conn.get_attendance()
                    if ex_att:
                        for record in ex_att:
                            uid = str(record.user_id)
                            ts_str = str(record.timestamp)
                            key = format_key(uid, ts_str)
                            if key not in existing_keys:
                                new_records_count += 1
                                log_callback(f"[NEW:{ex_name}] User {uid} at {ts_str}")
                                if config.get("NOTIFICATION_SOUND", True):
                                    play_notification_sound()
                                u_details = user_cache_map.get(uid, {})
                                u_name = u_details.get("name", "Unknown")
                                u_role = u_details.get("role", "Student")
                                db.reference(f"attendance_logs/{key}").set({
                                    "user_id": uid, "timestamp": ts_str,
                                    "status": record.status, "role": u_role, "name": u_name
                                })
                                existing_keys.add(key)
                    ex_conn.enable_device()
                    ex_conn.disconnect()
                    if new_records_count > 0:
                        update_stat_callback("sync", new_records_count)
                        trigger_refresh_callback()
            except Exception as e:
                if "timed out" not in str(e):
                    log_callback(f"[ZK:{ex_name}] {e}")
            finally:
                if ex_conn:
                    try: ex_conn.disconnect()
                    except: pass

        stop_event.wait(config["POLL_INTERVAL_SEC"])

# ---------------------------
# UI APPLICATION – MINIMAL DARK
# ---------------------------
class AttendanceApp(ttk.Window if THEME_AVAILABLE else tk.Tk):
    def __init__(self):
        if THEME_AVAILABLE:
            _theme = load_config().get("THEME", "darkly")
            super().__init__(themename=_theme)
        else:
            super().__init__()
            
        self.title("SM Scolers · Attendance System v12.0")
        self.geometry("1440x900")
        self.minsize(1200, 750)
        
        # Set application icon
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except Exception as e:
            print(f"Warning: Could not load icon 'icon.ico': {e}")

        # Modern color palette
        self.bg_dark = "#111318"
        self.bg_medium = "#1a1d24"
        self.bg_light = "#252830"
        self.bg_card = "#1e2128"
        self.fg = "#e8eaed"
        self.fg_dim = "#8b8f98"
        self.accent = "#6c63ff"
        self.accent_light = "#8b83ff"
        self.green = "#2ecc71"
        self.red = "#e74c3c"
        self.orange = "#f39c12"
        self.blue = "#3498db"
        self.border_color = "#2d313a"

        # Modern style overrides
        if THEME_AVAILABLE:
            style = ttk.Style()
            style.configure('Treeview.Heading', font=('Segoe UI Semibold', 10), 
                          background='#252830', foreground='#8b8f98',
                          borderwidth=0, relief='flat')
            style.map('Treeview.Heading', background=[('active', '#2d313a')])
            style.configure('Treeview', font=('Segoe UI', 10), rowheight=36, 
                          background='#1a1d24', fieldbackground='#1a1d24', 
                          foreground='#e8eaed', borderwidth=0)
            style.map('Treeview', background=[('selected', '#6c63ff')],
                     foreground=[('selected', '#ffffff')])
            style.configure('TLabel', font=('Segoe UI', 10))
            style.configure('TButton', font=('Segoe UI Semibold', 9), padding=(12, 6))
            style.configure('TLabelframe', borderwidth=1, relief='solid')
            style.configure('TLabelframe.Label', font=('Segoe UI Semibold', 10, 'bold'),
                          foreground='#8b8f98')
            style.configure('Sidebar.TFrame', background='#141720')
            style.configure('Panel.TFrame', background='#111318')
            style.configure('Card.TFrame', background='#1e2128')
            style.configure('CardTitle.TLabel', font=('Segoe UI', 9), 
                          foreground='#8b8f98', background='#1e2128')
            style.configure('CardValue.TLabel', font=('Segoe UI Semibold', 26, 'bold'),
                          background='#1e2128')
            style.configure('Header.TLabel', font=('Segoe UI Semibold', 24, 'bold'),
                          foreground='#e8eaed')
            style.configure('SubHeader.TLabel', font=('Segoe UI', 13, 'bold'),
                          foreground='#e8eaed')
            style.configure('Dim.TLabel', font=('Segoe UI', 9), foreground='#8b8f98')
            style.configure('NavActive.TLabel', font=('Segoe UI Semibold', 10),
                          foreground='#ffffff', background='#6c63ff')
            style.configure('StatusOnline.TLabel', font=('Segoe UI Semibold', 9, 'bold'),
                          foreground='#2ecc71')
            style.configure('StatusOffline.TLabel', font=('Segoe UI Semibold', 9, 'bold'),
                          foreground='#e74c3c')

        self.config_data = load_config()
        self.log_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.sync_thread = None
        
        # Data Caches
        self.users = []
        self.attendance_records = []
        self.enrolled_ids = [] 
        self.stats = {"sms": 0, "sync": 0}
        self.is_refreshing = False
        self.user_cache_map = {}  # Shared mutable dict, updated in-place for sync thread

        container = ttk.Frame(self, style="Panel.TFrame")
        container.pack(fill="both", expand=True)

        self.create_sidebar(container)
        self.create_main_area(container)
        self.create_status_bar()
        
        # Toast notification layer
        self._toast_queue = []
        self._toast_widget = None
        
        # Process the queue in the main thread
        self.after(100, self.process_queue)
        
        # Start initial data fetch in BACKGROUND THREAD
        self.log_message("[SYSTEM] Application started")
        self.trigger_background_refresh()

        # Periodic UI refresh every 60 seconds (sync engine triggers immediate refresh on new data)
        self.after(60000, self.periodic_ui_refresh)

        # Keyboard shortcuts
        self._bind_shortcuts()

        # Absent & Summary SMS scheduler
        self._absent_sms_sent_today = False
        self._summary_sms_sent_today = False
        self._last_check_date = date.today()
        self.after(30000, self._scheduled_sms_check)  # first check after 30s

    # ------------------------------------------------------------
    # SIDEBAR – Modern, icon-rich, interactive
    # ------------------------------------------------------------
    def create_sidebar(self, parent):
        sidebar = ttk.Frame(parent, width=235, style="Sidebar.TFrame")
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        
        # Brand area with accent line
        brand_frame = ttk.Frame(sidebar, style="Sidebar.TFrame")
        brand_frame.pack(fill="x", pady=(24, 8), padx=18)
        
        accent_bar = tk.Canvas(brand_frame, width=4, height=40, bg='#6c63ff', 
                              highlightthickness=0, bd=0)
        accent_bar.pack(side="left", padx=(0, 12))
        
        brand_text = ttk.Frame(brand_frame, style="Sidebar.TFrame")
        brand_text.pack(side="left", fill="x")
        ttk.Label(brand_text, text="SM SCOLERS", font=("Segoe UI Semibold", 17, "bold"),
                  foreground='#ffffff', background='#141720').pack(anchor="w")
        ttk.Label(brand_text, text="Attendance System", font=("Segoe UI", 9),
                  foreground='#5a5e6b', background='#141720').pack(anchor="w")

        # Separator line
        sep_canvas = tk.Canvas(sidebar, height=1, bg='#2d313a', highlightthickness=0, bd=0)
        sep_canvas.pack(fill="x", padx=18, pady=(12, 16))

        # Navigation with icons
        self.nav_var = tk.StringVar(value="dashboard")
        nav_frame = ttk.Frame(sidebar, style="Sidebar.TFrame")
        nav_frame.pack(fill="x", expand=False, anchor="n", padx=12)
        
        nav_buttons = [
            ("\u25a3  Dashboard", "dashboard"),
            ("\u2637  Statistics", "statistics"),
            ("\u2714  Present Today", "present"),
            ("\u25b6  Monitor", "monitor"),
            ("\u263a  Users", "users"),
            ("\u2630  Logs", "logs"),
            ("\u2699  Settings", "settings")
        ]
        
        self.nav_btn_refs = []
        for text, mode in nav_buttons:
            btn = ttk.Radiobutton(
                nav_frame, 
                text=text, 
                variable=self.nav_var, 
                value=mode, 
                command=self.switch_tab, 
                bootstyle="secondary-outline-toolbutton",
                width=20,
                padding=(10, 8)
            )
            btn.pack(pady=2, fill="x")
            self.nav_btn_refs.append(btn)

        # Spacer
        ttk.Frame(sidebar, style="Sidebar.TFrame").pack(expand=True, fill="both")

        # --- STATUS PANEL (modern card) ---
        status_card = tk.Frame(sidebar, bg='#1a1d24', highlightbackground='#2d313a',
                              highlightthickness=1, bd=0)
        status_card.pack(fill="x", padx=12, pady=(0, 12), side="bottom")
        status_inner = tk.Frame(status_card, bg='#1a1d24', padx=12, pady=10)
        status_inner.pack(fill="x")

        # Device status with live dot
        dev_row = tk.Frame(status_inner, bg='#1a1d24')
        dev_row.pack(fill="x", pady=(0, 6))
        tk.Label(dev_row, text="DEVICE", font=("Segoe UI Semibold", 8),
                fg='#5a5e6b', bg='#1a1d24').pack(side="left")
        
        self.status_dot = tk.Canvas(dev_row, width=10, height=10, bg='#1a1d24',
                                   highlightthickness=0)
        self.status_dot.pack(side="right", padx=(0, 4))
        self.status_dot.create_oval(1, 1, 9, 9, fill='#e74c3c', outline='', tags="dot")
        
        self.status_label = tk.Label(dev_row, text="OFFLINE", font=("Segoe UI Semibold", 9, "bold"),
                                    fg='#e74c3c', bg='#1a1d24')
        self.status_label.pack(side="right", padx=(0, 6))

        # GSM status
        gsm_row = tk.Frame(status_inner, bg='#1a1d24')
        gsm_row.pack(fill="x", pady=(4, 2))
        tk.Label(gsm_row, text="GSM", font=("Segoe UI Semibold", 8),
                fg='#5a5e6b', bg='#1a1d24').pack(side="left")
        self.lbl_carrier = tk.Label(gsm_row, text="Scanning...", font=("Segoe UI", 9),
                                   fg='#8b8f98', bg='#1a1d24')
        self.lbl_carrier.pack(side="right")

        # Signal bar (custom canvas bars)
        self.signal_canvas = tk.Canvas(status_inner, height=16, bg='#1a1d24',
                                      highlightthickness=0)
        self.signal_canvas.pack(fill="x", pady=(6, 4))
        self._draw_signal_bars(0)

        # Hidden progressbar for compatibility
        self.progress_signal = ttk.Progressbar(status_inner, value=0, maximum=100,
                                               bootstyle="success-striped", length=160)

        # SIM Actions
        sim_row = tk.Frame(status_inner, bg='#1a1d24')
        sim_row.pack(fill="x", pady=(8, 2))
        ttk.Button(sim_row, text="\u260e Balance", command=self.check_balance_popup,
                   bootstyle="info-outline", width=11).pack(side="left", padx=(0, 4))
        ttk.Button(sim_row, text="\u2699 USSD", command=self.edit_ussd_popup,
                   bootstyle="secondary-outline", width=8).pack(side="right")

        sim_row2 = tk.Frame(status_inner, bg='#1a1d24')
        sim_row2.pack(fill="x", pady=(4, 2))
        ttk.Button(sim_row2, text="\U0001f4e8 SMS Inbox", command=self.open_sms_inbox_popup,
                   bootstyle="warning-outline", width=22).pack(fill="x")

        # --- SYNC BUTTON (prominent) ---
        sync_frame = tk.Frame(sidebar, bg='#141720')
        sync_frame.pack(fill="x", side="bottom", padx=12, pady=(0, 16))
        self.btn_sync = ttk.Button(
            sync_frame, text="\u25b6  START ENGINE", command=self.toggle_sync,
            bootstyle="success", padding=(10, 12)
        )
        self.btn_sync.pack(fill="x")

    def _draw_signal_bars(self, signal_pct):
        """Draw modern signal strength bars."""
        c = self.signal_canvas
        c.delete("all")
        w = c.winfo_width() if c.winfo_width() > 1 else 180
        bar_count = 8
        gap = 3
        bar_w = max((w - gap * (bar_count - 1)) / bar_count, 4)
        
        for i in range(bar_count):
            threshold = (i + 1) * (100 / bar_count)
            x1 = i * (bar_w + gap)
            x2 = x1 + bar_w
            h = 4 + (i * 1.2)
            y1 = 16 - h
            
            if signal_pct >= threshold:
                if signal_pct >= 60:
                    color = '#2ecc71'
                elif signal_pct >= 30:
                    color = '#f39c12'
                else:
                    color = '#e74c3c'
            else:
                color = '#2d313a'
            
            c.create_rectangle(x1, y1, x2, 16, fill=color, outline='')
    
    def _pulse_status_dot(self):
        """Animate the online status dot."""
        if hasattr(self, '_dot_pulse_on') and self._dot_pulse_on:
            current = self.status_dot.itemcget("dot", "fill")
            new_color = '#1a5e35' if current == '#2ecc71' else '#2ecc71'
            self.status_dot.itemconfig("dot", fill=new_color)
            self._pulse_after_id = self.after(800, self._pulse_status_dot)
    
    def _start_pulse(self):
        self._dot_pulse_on = True
        self._pulse_status_dot()
    
    def _stop_pulse(self):
        self._dot_pulse_on = False
        if hasattr(self, '_pulse_after_id'):
            self.after_cancel(self._pulse_after_id)

    # ------------------------------------------------------------
    # MAIN CONTENT AREA – clean, minimal
    # ------------------------------------------------------------
    def create_main_area(self, parent):
        self.main_container = ttk.Frame(parent, padding=15, style="Panel.TFrame")
        self.main_container.pack(side="right", fill="both", expand=True)
        self.frames = {}
        
        for f in (DashboardFrame, StatisticsFrame, PresentTodayFrame, MonitorFrame, UsersFrame, LogsFrame, SettingsFrame):
            page_name = f.__name__
            frame = f(parent=self.main_container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")
            
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.switch_tab()

    def switch_tab(self):
        mode = self.nav_var.get()
        mapping = {
            "dashboard": "DashboardFrame",
            "statistics": "StatisticsFrame",
            "present": "PresentTodayFrame",
            "monitor": "MonitorFrame",
            "users": "UsersFrame",
            "logs": "LogsFrame",
            "settings": "SettingsFrame",
        }
        target = mapping.get(mode)
        if target:
            self.frames[target].tkraise()

    # ------------------------------------------------------------
    # SYNC TOGGLE (unchanged)
    # ------------------------------------------------------------
    def toggle_sync(self):
        if self.sync_thread and self.sync_thread.is_alive():
            self.stop_event.set()
            self.btn_sync.configure(text="⏹  STOPPING...", bootstyle="warning")
            self.sync_thread.join()
            self.btn_sync.configure(text="▶  START ENGINE", bootstyle="success")
            self.update_connection_status(False)
            self.log_message("[SYSTEM] Engine Stopped.")
            self.show_toast("Sync engine stopped", "warning", 3000)
            self._update_status_bar()
        else:
            # Retrieve users
            self.stop_event.clear()
            # Build user_cache_map in-place (shared with sync thread)
            self.user_cache_map.clear()
            for u in self.users:
                self.user_cache_map[u.user_id] = {
                    "name": u.name, "role": u.role, 
                    "phone": u.phone, 
                    "father_phone": u.father_phone, 
                    "mother_phone": u.mother_phone,
                    "class_name": u.class_name,
                    "section": u.section
                }

            self.sync_thread = threading.Thread(
                target=run_sync_loop, 
                args=(self.config_data, self.enqueue_log, self.stop_event, self.update_stats, self.trigger_auto_refresh, self.enqueue_status, self.enqueue_enrollment, self.user_cache_map, self.enqueue_gsm, self.enqueue_sms_log)
            )
            self.sync_thread.daemon = True
            self.sync_thread.start()
            self.btn_sync.configure(text="⏹  STOP ENGINE", bootstyle="danger")
            self.show_toast("Sync engine started", "success", 3000)
            self._update_status_bar()

    # ------------------------------------------------------------
    # POPUPS (unchanged)
    # ------------------------------------------------------------
    def edit_ussd_popup(self):
        current_code = self.config_data.get("USSD_CODE", "*121#")
        new_code = simpledialog.askstring("SIM Config", "Enter USSD Code:", initialvalue=current_code)
        if new_code:
            self.config_data["USSD_CODE"] = new_code
            save_config(self.config_data)
            messagebox.showinfo("Saved", f"USSD Code updated to {new_code}")

    def check_balance_popup(self):
        code = self.config_data.get("USSD_CODE", "")
        if not code:
            self.edit_ussd_popup()
            code = self.config_data.get("USSD_CODE", "")
            if not code: return

        self.log_message(f"[USSD] Dialing {code}...")
        self.show_toast(f"Dialing {code}...", "info", 3000)

        # --- Interactive USSD Dialog ---
        dlg = tk.Toplevel(self)
        dlg.title(f"USSD — {code}")
        dlg.geometry("620x520")
        dlg.minsize(500, 400)
        dlg.configure(bg="#1a1d24")
        dlg.grab_set()

        # Response display (scrolled text)
        resp_frame = ttk.Frame(dlg)
        resp_frame.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        resp_text = tk.Text(resp_frame, wrap="word", font=("Consolas", 10),
                            bg="#0d1017", fg="#e0e0e0", insertbackground="#e0e0e0",
                            state="disabled", relief="flat", padx=8, pady=8)
        resp_scroll = ttk.Scrollbar(resp_frame, orient="vertical", command=resp_text.yview)
        resp_text.configure(yscrollcommand=resp_scroll.set)
        resp_text.pack(side="left", fill="both", expand=True)
        resp_scroll.pack(side="right", fill="y")

        # Reply input row
        reply_frame = ttk.Frame(dlg)
        reply_frame.pack(fill="x", padx=12, pady=(0, 6))
        ttk.Label(reply_frame, text="Reply:", style="Dim.TLabel").pack(side="left", padx=(0, 6))
        reply_var = tk.StringVar()
        reply_entry = ttk.Entry(reply_frame, textvariable=reply_var, width=20)
        reply_entry.pack(side="left", padx=(0, 6))
        btn_send = ttk.Button(reply_frame, text="Send Reply", bootstyle="info", width=12)
        btn_send.pack(side="left", padx=(0, 6))
        btn_cancel_ussd = ttk.Button(reply_frame, text="End Session", bootstyle="danger-outline", width=12)
        btn_cancel_ussd.pack(side="right")

        # Status label
        status_lbl = ttk.Label(dlg, text="Dialing...", style="Dim.TLabel")
        status_lbl.pack(fill="x", padx=12, pady=(0, 10))

        # Disable reply controls initially
        reply_entry.configure(state="disabled")
        btn_send.configure(state="disabled")

        def append_text(text, tag=None):
            resp_text.configure(state="normal")
            if resp_text.get("1.0", "end-1c"):
                resp_text.insert("end", "\n\n" + "─" * 40 + "\n\n")
            resp_text.insert("end", text)
            resp_text.see("end")
            resp_text.configure(state="disabled")

        def on_ussd_result(text, session_active):
            append_text(text)
            if session_active:
                status_lbl.config(text="Session active — enter reply number and click Send")
                reply_entry.configure(state="normal")
                btn_send.configure(state="normal")
                reply_entry.focus_set()
            else:
                status_lbl.config(text="Session ended")
                reply_entry.configure(state="disabled")
                btn_send.configure(state="disabled")

        def do_initial_dial():
            text, active = run_ussd_command(self.config_data, code)
            dlg.after(0, lambda: on_ussd_result(text, active))

        def do_send_reply():
            reply = reply_var.get().strip()
            if not reply:
                return
            reply_entry.configure(state="disabled")
            btn_send.configure(state="disabled")
            status_lbl.config(text=f"Sending reply '{reply}'...")
            reply_var.set("")
            append_text(f"► You replied: {reply}")

            def task():
                text, active = run_ussd_reply(self.config_data, reply)
                dlg.after(0, lambda: on_ussd_result(text, active))
            threading.Thread(target=task, daemon=True).start()

        def do_cancel():
            reply_entry.configure(state="disabled")
            btn_send.configure(state="disabled")
            status_lbl.config(text="Cancelling session...")
            def task():
                cancel_ussd_session(self.config_data)
                dlg.after(0, lambda: status_lbl.config(text="Session cancelled"))
            threading.Thread(target=task, daemon=True).start()

        btn_send.configure(command=do_send_reply)
        btn_cancel_ussd.configure(command=do_cancel)
        reply_entry.bind("<Return>", lambda e: do_send_reply())

        threading.Thread(target=do_initial_dial, daemon=True).start()

    def open_sms_inbox_popup(self):
        """Open popup to read SMS messages from SIM inbox."""
        dlg = tk.Toplevel(self)
        dlg.title("SMS Inbox")
        dlg.geometry("700x520")
        dlg.minsize(500, 380)
        dlg.configure(bg="#1a1d24")
        dlg.resizable(True, True)
        dlg.grab_set()

        # Header with refresh button
        hdr = ttk.Frame(dlg)
        hdr.pack(fill="x", padx=12, pady=(10, 6))
        ttk.Label(hdr, text="📨 SMS Inbox", font=("Segoe UI", 13, "bold"),
                  foreground="#e0e0e0", background="#1a1d24").pack(side="left")
        status_lbl = ttk.Label(hdr, text="Loading...", style="Dim.TLabel")
        status_lbl.pack(side="right", padx=(0, 6))
        btn_refresh = ttk.Button(hdr, text="↻ Refresh", bootstyle="secondary-outline", width=10)
        btn_refresh.pack(side="right", padx=(0, 6))

        # Treeview for messages
        container = ttk.Frame(dlg)
        container.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        cols = ("From", "Time", "Message")
        tree = ttk.Treeview(container, columns=cols, show="headings", height=12)
        tree.heading("From", text="From")
        tree.heading("Time", text="Time")
        tree.heading("Message", text="Message")
        tree.column("From", width=110, anchor="center")
        tree.column("Time", width=140, anchor="center")
        tree.column("Message", width=320, anchor="w")
        scroll = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Message detail area
        detail_text = tk.Text(dlg, wrap="word", font=("Consolas", 10),
                              bg="#0d1017", fg="#e0e0e0", height=5,
                              state="disabled", relief="flat", padx=8, pady=6)
        detail_text.pack(fill="x", padx=12, pady=(0, 6))

        # Bottom bar with delete button
        bottom = ttk.Frame(dlg)
        bottom.pack(fill="x", padx=12, pady=(0, 10))
        btn_delete = ttk.Button(bottom, text="🗑 Delete Selected", bootstyle="danger-outline", width=16)
        btn_delete.pack(side="right")

        # Store message index mapping
        msg_index_map = {}

        def show_detail(event):
            sel = tree.selection()
            if not sel:
                return
            item = sel[0]
            vals = tree.item(item)["values"]
            detail_text.configure(state="normal")
            detail_text.delete("1.0", "end")
            detail_text.insert("end", f"From: {vals[0]}\nTime: {vals[1]}\n\n{vals[2]}")
            detail_text.configure(state="disabled")

        tree.bind("<<TreeviewSelect>>", show_detail)

        def do_load():
            msgs = read_sms_inbox(self.config_data)
            def update_ui():
                tree.delete(*tree.get_children())
                msg_index_map.clear()
                for idx, sender, ts, body in msgs:
                    iid = tree.insert("", "end", values=(sender, ts, body.replace('\n', ' ')))
                    msg_index_map[iid] = idx
                status_lbl.config(text=f"{len(msgs)} message(s)")
            dlg.after(0, update_ui)

        def do_delete():
            sel = tree.selection()
            if not sel:
                return
            item = sel[0]
            sms_idx = msg_index_map.get(item)
            if sms_idx is None:
                return
            def task():
                delete_sms(self.config_data, sms_idx)
                do_load()
            threading.Thread(target=task, daemon=True).start()

        btn_refresh.configure(command=lambda: threading.Thread(target=do_load, daemon=True).start())
        btn_delete.configure(command=do_delete)

        threading.Thread(target=do_load, daemon=True).start()

    # --- Queue Handlers ---
    def enqueue_log(self, msg): self.log_queue.put(("LOG", msg))
    def trigger_auto_refresh(self): self.log_queue.put(("REFRESH", None))
    def enqueue_status(self, is_connected): self.log_queue.put(("STATUS", is_connected))
    def enqueue_enrollment(self, id_list): self.log_queue.put(("ENROLLED", id_list))
    def enqueue_gsm(self, carrier, signal): self.log_queue.put(("GSM", (carrier, signal)))
    def enqueue_sms_log(self, phone, message): self.log_queue.put(("SMS", (phone, message)))

    def process_queue(self):
        try:
            while True:
                msg_type, content = self.log_queue.get_nowait()
                if msg_type == "LOG": 
                    self.log_message(content)
                elif msg_type == "REFRESH":
                    self.trigger_background_refresh()
                elif msg_type == "DATA_READY":
                    self.update_ui_with_data(content[0], content[1])
                elif msg_type == "STATUS": 
                    self.update_connection_status(content)
                elif msg_type == "ENROLLED":
                    self.enrolled_ids = content
                    self.frames["UsersFrame"].apply_filter()
                elif msg_type == "GSM": 
                    self.update_gsm_ui(content[0], content[1])
                elif msg_type == "SMS":
                    phone, body = content
                    self.log_message(f"[SMS] To {phone}: {body}")
        except queue.Empty: 
            pass
        self.after(100, self.process_queue)

    def periodic_ui_refresh(self):
        self.trigger_background_refresh()
        self.after(60000, self.periodic_ui_refresh)

    # ------------------------------------------------------------
    # DATA FETCH (unchanged)
    # ------------------------------------------------------------
    def bg_fetch_data(self):
        try:
            if not firebase_admin._apps:
                cred_path = get_service_account_path(self.config_data)
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred, {"databaseURL": self.config_data["FIREBASE_DB_URL"]})
            
            # Fetch Users
            u_ref = db.reference("users")
            u_data = u_ref.get()
            fetched_users = []
            if u_data:
                if isinstance(u_data, list):
                    for i, v in enumerate(u_data):
                        if v: fetched_users.append(User.from_dict(str(i), v))
                elif isinstance(u_data, dict):
                    for k, v in u_data.items():
                        fetched_users.append(User.from_dict(k, v))
            
            # Fetch Logs
            l_ref = db.reference("attendance_logs")
            l_data = l_ref.get()
            fetched_records = []
            if l_data and isinstance(l_data, dict):
                for k, v in l_data.items():
                    uid = v.get("user_id")
                    u_obj = next((u for u in fetched_users if u.user_id == uid), None)
                    u_name = u_obj.name if u_obj else "Unknown"
                    u_role = u_obj.role if u_obj else v.get("role", "Unknown")

                    rec = AttendanceRecord(
                        k, uid, v.get("timestamp"), v.get("status"), 
                        u_name, u_role
                    )
                    fetched_records.append(rec)
            
            self.log_queue.put(("DATA_READY", (fetched_users, fetched_records)))

        except Exception as e:
            self.log_queue.put(("LOG", f"[DATA ERROR] {e}"))
        finally:
            self.is_refreshing = False

    def trigger_background_refresh(self):
        if not self.is_refreshing:
            self.is_refreshing = True
            self.frames["DashboardFrame"].set_loading(True)
            threading.Thread(target=self.bg_fetch_data, daemon=True).start()

    def update_ui_with_data(self, users, records):
        self.users = users
        self.attendance_records = records
        
        # Update shared user_cache_map in-place so sync thread sees fresh data
        for u in self.users:
            self.user_cache_map[u.user_id] = {
                "name": u.name, "role": u.role,
                "phone": u.phone,
                "father_phone": u.father_phone,
                "mother_phone": u.mother_phone,
                "class_name": u.class_name,
                "section": u.section
            }
        
        self.frames["UsersFrame"].apply_filter()
        self.frames["LogsFrame"].populate(self.attendance_records)
        self.frames["DashboardFrame"].update_metrics(self.users, self.attendance_records)
        self.frames["StatisticsFrame"].populate(self.users, self.attendance_records)
        self.frames["PresentTodayFrame"].populate(self.users, self.attendance_records)
        self.frames["DashboardFrame"].set_loading(False)
        
        self.show_toast(f"Data synced — {len(users)} users, {len(records)} records", "success", 2500)
        self.log_message("[SYSTEM] Data Updated Successfully")
        self.sb_last_sync.config(text=f"Last sync: {datetime.now().strftime('%H:%M:%S')}")
        self._update_status_bar()

    # ------------------------------------------------------------
    # UI UPDATES
    # ------------------------------------------------------------
    def update_connection_status(self, is_connected):
        if is_connected:
            self.status_label.configure(text="ONLINE", fg='#2ecc71')
            self.status_dot.itemconfig("dot", fill='#2ecc71')
            self._start_pulse()
        else:
            self.status_label.configure(text="OFFLINE", fg='#e74c3c')
            self.status_dot.itemconfig("dot", fill='#e74c3c')
            self._stop_pulse()

    def update_gsm_ui(self, carrier, signal):
        self.lbl_carrier.config(text=f"{carrier} {signal}%")
        self.progress_signal['value'] = signal
        self._draw_signal_bars(signal)

    def log_message(self, msg):
        monitor = self.frames["MonitorFrame"]
        ts = datetime.now().strftime("%H:%M:%S")
        monitor.add_log(f"[{ts}] {msg}")

    def update_stats(self, category, count=1):
        self.stats[category] += count
        self.frames["DashboardFrame"].update_counters(self.stats)

    # ------------------------------------------------------------
    # TOAST NOTIFICATION SYSTEM
    # ------------------------------------------------------------
    def show_toast(self, message, level="info", duration=3000):
        """Show a temporary auto-dismissing notification banner at top-right."""
        colors = {
            "info": ("#3498db", "#1a2d42"),
            "success": ("#2ecc71", "#1a3d2a"),
            "error": ("#e74c3c", "#3d1a1a"),
            "warning": ("#f39c12", "#3d2e0a"),
        }
        icons = {"info": "ℹ", "success": "✓", "error": "✖", "warning": "⚠"}
        fg_color, bg_color = colors.get(level, colors["info"])
        icon = icons.get(level, "ℹ")

        # Remove existing toast
        if self._toast_widget and self._toast_widget.winfo_exists():
            self._toast_widget.destroy()

        toast = tk.Frame(self.main_container, bg=bg_color, highlightbackground=fg_color,
                        highlightthickness=1, bd=0)
        inner = tk.Frame(toast, bg=bg_color, padx=14, pady=8)
        inner.pack(fill="both")
        tk.Label(inner, text=icon, font=("Segoe UI", 13), fg=fg_color, bg=bg_color).pack(side="left", padx=(0, 8))
        tk.Label(inner, text=message, font=("Segoe UI", 10), fg="#e8eaed", bg=bg_color).pack(side="left")
        close_btn = tk.Label(inner, text="✕", font=("Segoe UI", 10), fg="#8b8f98", bg=bg_color, cursor="hand2")
        close_btn.pack(side="right", padx=(12, 0))
        close_btn.bind("<Button-1>", lambda e: toast.destroy())

        toast.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
        self._toast_widget = toast
        self.after(duration, lambda: toast.destroy() if toast.winfo_exists() else None)

    # ------------------------------------------------------------
    # KEYBOARD SHORTCUTS
    # ------------------------------------------------------------
    def _bind_shortcuts(self):
        self.bind("<Control-Key-1>", lambda e: self._shortcut_nav("dashboard"))
        self.bind("<Control-Key-2>", lambda e: self._shortcut_nav("statistics"))
        self.bind("<Control-Key-3>", lambda e: self._shortcut_nav("present"))
        self.bind("<Control-Key-4>", lambda e: self._shortcut_nav("monitor"))
        self.bind("<Control-Key-5>", lambda e: self._shortcut_nav("users"))
        self.bind("<Control-Key-6>", lambda e: self._shortcut_nav("logs"))
        self.bind("<Control-Key-7>", lambda e: self._shortcut_nav("settings"))
        self.bind("<F5>", lambda e: self._shortcut_refresh())
        self.bind("<Control-e>", lambda e: self._shortcut_toggle_engine())
        self.bind("<Escape>", lambda e: self._shortcut_nav("dashboard"))

    def _shortcut_nav(self, tab):
        self.nav_var.set(tab)
        self.switch_tab()

    def _shortcut_refresh(self):
        self.trigger_background_refresh()
        self.show_toast("Refreshing data...", "info", 2000)

    def _shortcut_toggle_engine(self):
        self.toggle_sync()

    # ------------------------------------------------------------
    # STATUS BAR (bottom bar)
    # ------------------------------------------------------------
    def create_status_bar(self):
        self.statusbar = tk.Frame(self, bg="#0d1117", height=28)
        self.statusbar.pack(side="bottom", fill="x")
        self.statusbar.pack_propagate(False)

        inner = tk.Frame(self.statusbar, bg="#0d1117", padx=10)
        inner.pack(fill="both", expand=True)

        self.sb_engine = tk.Label(inner, text="● Engine: Stopped", font=("Segoe UI", 8),
                                  fg="#e74c3c", bg="#0d1117")
        self.sb_engine.pack(side="left", padx=(0, 16))

        self.sb_users = tk.Label(inner, text="Users: 0", font=("Segoe UI", 8),
                                 fg="#8b8f98", bg="#0d1117")
        self.sb_users.pack(side="left", padx=(0, 16))

        self.sb_records = tk.Label(inner, text="Records: 0", font=("Segoe UI", 8),
                                   fg="#8b8f98", bg="#0d1117")
        self.sb_records.pack(side="left", padx=(0, 16))

        self.sb_sms = tk.Label(inner, text="SMS: 0", font=("Segoe UI", 8),
                               fg="#8b8f98", bg="#0d1117")
        self.sb_sms.pack(side="left", padx=(0, 16))

        self.sb_last_sync = tk.Label(inner, text="Last sync: —", font=("Segoe UI", 8),
                                     fg="#8b8f98", bg="#0d1117")
        self.sb_last_sync.pack(side="right")

        self.sb_version = tk.Label(inner, text="v12.0", font=("Segoe UI", 8),
                                   fg="#5a5e6b", bg="#0d1117")
        self.sb_version.pack(side="right", padx=(0, 16))

        self.sb_shortcuts = tk.Label(inner, text="Ctrl+1-7: Navigate  |  F5: Refresh  |  Ctrl+E: Engine",
                                     font=("Segoe UI", 8), fg="#3d4048", bg="#0d1117")
        self.sb_shortcuts.pack(side="right", padx=(0, 16))

    def _update_status_bar(self):
        """Update status bar with current stats."""
        is_running = self.sync_thread and self.sync_thread.is_alive()
        if is_running:
            self.sb_engine.config(text="● Engine: Running", fg="#2ecc71")
        else:
            self.sb_engine.config(text="● Engine: Stopped", fg="#e74c3c")
        self.sb_users.config(text=f"Users: {len(self.users)}")
        self.sb_records.config(text=f"Records: {len(self.attendance_records)}")
        self.sb_sms.config(text=f"SMS: {self.stats.get('sms', 0)}")

    # ------------------------------------------------------------
    # ABSENT NOTIFICATION SMS
    # ------------------------------------------------------------
    def _scheduled_sms_check(self):
        """Periodic check for absent SMS and daily summary triggers."""
        today = date.today()
        now = datetime.now()

        # Reset daily flags on new day
        if today != self._last_check_date:
            self._absent_sms_sent_today = False
            self._summary_sms_sent_today = False
            self._last_check_date = today

        # Absent SMS check
        if (self.config_data.get("ABSENT_SMS_ENABLED", False)
                and not self._absent_sms_sent_today):
            cutoff = self.config_data.get("ABSENT_SMS_TIME", "09:30")
            try:
                cutoff_time = datetime.strptime(cutoff, "%H:%M").time()
                if now.time() >= cutoff_time:
                    self._send_absent_notifications()
                    self._absent_sms_sent_today = True
            except ValueError:
                pass

        # Daily summary SMS check
        if (self.config_data.get("DAILY_SUMMARY_ENABLED", False)
                and not self._summary_sms_sent_today):
            summary_time = self.config_data.get("DAILY_SUMMARY_TIME", "17:00")
            try:
                st = datetime.strptime(summary_time, "%H:%M").time()
                if now.time() >= st:
                    self._send_daily_summary()
                    self._summary_sms_sent_today = True
            except ValueError:
                pass

        self.after(60000, self._scheduled_sms_check)  # check every 60s

    def _send_absent_notifications(self):
        """Send SMS to parents of students who are absent after cutoff."""
        # Skip if today is a holiday
        holidays = self.config_data.get("HOLIDAYS", [])
        today_iso = date.today().strftime("%Y-%m-%d")
        if today_iso in holidays:
            self.log_message(f"[ABSENT] Skipped — today ({today_iso}) is a holiday")
            return

        date_display = date.today().strftime("%d/%m/%Y")
        template = self.config_data.get("ABSENT_SMS_TEMPLATE", DEFAULT_CONFIG["ABSENT_SMS_TEMPLATE"])

        # Find users who checked in today
        present_ids = set()
        for r in self.attendance_records:
            if r.timestamp.startswith(today_iso):
                present_ids.add(str(r.user_id))

        absent_count = 0
        for u in self.users:
            if u.user_id in present_ids:
                continue
            if u.role != "Student":
                continue
            # Get parent phone
            phone = u.father_phone or u.mother_phone or u.phone
            if not phone:
                continue
            msg = template.format(name=u.name, id=u.user_id, date=date_display)
            threading.Thread(target=send_sms_gsm, args=(self.config_data, phone, msg, self.enqueue_log), daemon=True).start()
            absent_count += 1

        if absent_count > 0:
            self.log_message(f"[ABSENT] Sent {absent_count} absent notification SMS")
            self.show_toast(f"Sent {absent_count} absent alerts", "warning", 4000)

    def _send_daily_summary(self):
        """Send end-of-day summary SMS to admin phones."""
        admin_phones = [
            self.config_data.get("ADMIN_PHONE_1", "").strip(),
            self.config_data.get("ADMIN_PHONE_2", "").strip(),
        ]
        admin_phones = [p for p in admin_phones if p]
        if not admin_phones:
            return

        today_str = date.today().strftime("%Y-%m-%d")
        date_display = date.today().strftime("%d/%m/%Y")
        template = self.config_data.get("DAILY_SUMMARY_TEMPLATE", DEFAULT_CONFIG["DAILY_SUMMARY_TEMPLATE"])

        present_ids = set()
        late_count = 0
        for r in self.attendance_records:
            if r.timestamp.startswith(today_str):
                present_ids.add(str(r.user_id))
                if str(r.status).lower() == "late":
                    late_count += 1

        total = len(self.users)
        present = len(present_ids)
        absent = total - present

        msg = template.format(date=date_display, present=present, absent=absent,
                              late=late_count, total=total)

        def task():
            for phone in admin_phones:
                send_sms_gsm(self.config_data, phone, msg, self.enqueue_log)
        threading.Thread(target=task, daemon=True).start()
        self.log_message(f"[SUMMARY] Daily summary SMS sent to {', '.join(admin_phones)}")
        self.show_toast(f"Daily summary sent to {len(admin_phones)} admin(s)", "success", 4000)

# ---------------------------
# UI FRAMES – MINIMAL DARK
# ---------------------------

class DashboardFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="Panel.TFrame")
        self.controller = controller
        
        # Header row with title + loading indicator
        header_row = ttk.Frame(self, style="Panel.TFrame")
        header_row.pack(fill="x", pady=(0, 16))
        ttk.Label(header_row, text="Dashboard", style="Header.TLabel").pack(side="left")
        
        self.loading_lbl = ttk.Label(header_row, text="", font=("Segoe UI", 9, "italic"),
                                     foreground='#6c63ff')
        self.loading_lbl.pack(side="right")
        
        # Date display
        today_str = date.today().strftime("%A, %B %d, %Y")
        ttk.Label(header_row, text=today_str, style="Dim.TLabel").pack(side="right", padx=(0, 20))
        
        # === MAIN STATS ROW ===
        card_container = ttk.Frame(self, style="Panel.TFrame")
        card_container.pack(fill="x", pady=(0, 6))
        
        self.card_users = self._create_modern_card(card_container, "Total Users", "0", 0, "#6c63ff", "\u263a")
        self.card_present = self._create_modern_card(card_container, "Present Today", "0", 1, "#2ecc71", "\u25b2")
        self.card_absent = self._create_modern_card(card_container, "Absent Today", "0", 2, "#e74c3c", "\u25bc")
        self.card_sms = self._create_modern_card(card_container, "SMS Sent", "0", 3, "#3498db", "\u2709")

        # === ROLE BREAKDOWN (present) ===
        role_card_container = ttk.Frame(self, style="Panel.TFrame")
        role_card_container.pack(fill="x", pady=(0, 4))
        self.card_students_present = self._create_mini_card(role_card_container, "Students \u25b2", "0", 0, "#2ecc71")
        self.card_teachers_present = self._create_mini_card(role_card_container, "Teachers \u25b2", "0", 1, "#2ecc71")
        self.card_staff_present = self._create_mini_card(role_card_container, "Staff \u25b2", "0", 2, "#2ecc71")

        # === ROLE BREAKDOWN (absent) ===
        absent_card_container = ttk.Frame(self, style="Panel.TFrame")
        absent_card_container.pack(fill="x", pady=(0, 10))
        self.card_students_absent = self._create_mini_card(absent_card_container, "Students \u25bc", "0", 0, "#e74c3c")
        self.card_teachers_absent = self._create_mini_card(absent_card_container, "Teachers \u25bc", "0", 1, "#e74c3c")
        self.card_staff_absent = self._create_mini_card(absent_card_container, "Staff \u25bc", "0", 2, "#e74c3c")

        # === RECENT ACTIVITY ===
        activity_header = ttk.Frame(self, style="Panel.TFrame")
        activity_header.pack(fill="x", pady=(8, 8))
        ttk.Label(activity_header, text="Recent Activity", style="SubHeader.TLabel").pack(side="left")
        ttk.Button(activity_header, text="\u21bb Refresh", 
                  command=controller.trigger_background_refresh,
                  bootstyle="secondary-outline", width=10).pack(side="right")
        
        # Treeview with modern styling
        container = ttk.Frame(self, style="Panel.TFrame")
        container.pack(fill="both", expand=True)

        self.recent_list = ttk.Treeview(container, columns=("Time", "User", "Role", "Status"),
                                        show="headings", height=12)
        self.recent_list.heading("Time", text="Time")
        self.recent_list.heading("User", text="User")
        self.recent_list.heading("Role", text="Role")
        self.recent_list.heading("Status", text="Status")
        self.recent_list.column("Time", width=100, anchor="center")
        self.recent_list.column("User", width=300, anchor="w")
        self.recent_list.column("Role", width=100, anchor="center")
        self.recent_list.column("Status", width=80, anchor="center")
        self.recent_list.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(container, orient="vertical", command=self.recent_list.yview)
        self.recent_list.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

    def _create_modern_card(self, parent, title, value, col, accent_color, icon):
        """Create a modern stat card with accent border and icon."""
        outer = tk.Frame(parent, bg='#1e2128', highlightbackground=accent_color,
                        highlightthickness=0, bd=0, padx=0, pady=0)
        outer.grid(row=0, column=col, padx=6, sticky="nsew")
        
        # Top accent line
        accent_line = tk.Canvas(outer, height=3, bg=accent_color, highlightthickness=0, bd=0)
        accent_line.pack(fill="x")
        
        inner = tk.Frame(outer, bg='#1e2128', padx=16, pady=12)
        inner.pack(fill="both", expand=True)
        
        # Icon + title row
        title_row = tk.Frame(inner, bg='#1e2128')
        title_row.pack(fill="x")
        tk.Label(title_row, text=icon, font=("Segoe UI", 14),
                fg=accent_color, bg='#1e2128').pack(side="left", padx=(0, 8))
        tk.Label(title_row, text=title, font=("Segoe UI", 9),
                fg='#8b8f98', bg='#1e2128').pack(side="left")
        
        # Value
        val_lbl = tk.Label(inner, text=value, font=("Segoe UI Semibold", 28, "bold"),
                          fg=accent_color, bg='#1e2128')
        val_lbl.pack(anchor="w", pady=(4, 0))
        
        parent.columnconfigure(col, weight=1)
        return val_lbl

    def _create_mini_card(self, parent, title, value, col, accent_color):
        """Create a compact role breakdown card."""
        outer = tk.Frame(parent, bg='#1e2128', padx=14, pady=8)
        outer.grid(row=0, column=col, padx=6, sticky="nsew")
        
        title_row = tk.Frame(outer, bg='#1e2128')
        title_row.pack(fill="x")
        tk.Label(title_row, text=title, font=("Segoe UI", 9),
                fg='#8b8f98', bg='#1e2128').pack(side="left")
        
        val_lbl = tk.Label(title_row, text=value, font=("Segoe UI Semibold", 18, "bold"),
                          fg=accent_color, bg='#1e2128')
        val_lbl.pack(side="right")
        
        parent.columnconfigure(col, weight=1)
        return val_lbl

    def update_counters(self, stats):
        self.card_sms.config(text=str(stats["sms"]))

    def _is_check_in_status(self, status_value):
        value = str(status_value).strip().lower()
        return value in {"0", "in", "check-in", "checkin", "punch in"}

    def _is_check_out_status(self, status_value):
        value = str(status_value).strip().lower()
        return value in {"1", "out", "check-out", "checkout", "punch out"}

    def _get_assigned_schedule(self, user_obj, role):
        schedules = self.controller.config_data.get("CLASS_SCHEDULES", {}) or {}
        role_text = str(role or "Student").strip()

        if role_text.lower() == "student" and user_obj is not None:
            class_name = (getattr(user_obj, "class_name", "") or "").strip()
            if class_name and class_name in schedules:
                return schedules.get(class_name)

        for key in (role_text, role_text.title(), role_text.lower(), role_text.upper()):
            if key in schedules:
                return schedules.get(key)

        return None

    def _is_on_time(self, event_dt, schedule):
        if not schedule:
            return True
        start = (schedule.get("start") or "").strip()
        end = (schedule.get("end") or "").strip()
        if not start or not end:
            return True
        return is_time_in_window(event_dt, start, end)

    def update_metrics(self, users, records):
        self.card_users.config(text=str(len(users)))
        today_str = date.today().strftime("%Y-%m-%d")
        todays_recs = [r for r in records if r.timestamp.startswith(today_str)]

        total_students = sum(1 for u in users if str(getattr(u, "role", "")).strip().lower() == "student")
        total_teachers = sum(1 for u in users if str(getattr(u, "role", "")).strip().lower() == "teacher")
        total_staff = sum(1 for u in users if str(getattr(u, "role", "")).strip().lower() == "staff")

        users_by_id = {str(u.user_id): u for u in users}
        recs_by_user = {}
        for rec in todays_recs:
            recs_by_user.setdefault(str(rec.user_id), []).append(rec)

        present_total = 0
        present_students = 0
        present_teachers = 0
        present_staff = 0

        for uid, user_recs in recs_by_user.items():
            ordered = sorted(user_recs, key=lambda x: getattr(x, "datetime", datetime.min))
            first_check_in = next((x for x in ordered if self._is_check_in_status(x.status)), None)
            first_check_out = next((x for x in ordered if self._is_check_out_status(x.status)), None)

            user_obj = users_by_id.get(uid)
            role = (getattr(user_obj, "role", "") or (ordered[0].role if ordered else "Student") or "Student").strip()
            schedule = self._get_assigned_schedule(user_obj, role)

            has_valid_check_in = bool(first_check_in and self._is_on_time(first_check_in.datetime, schedule))
            has_valid_check_out = bool(first_check_out and self._is_on_time(first_check_out.datetime, schedule))

            is_present = False
            if role.lower() == "teacher":
                is_present = has_valid_check_in
            else:
                is_present = has_valid_check_in and has_valid_check_out
                if first_check_in and first_check_out and first_check_out.datetime < first_check_in.datetime:
                    is_present = False

            if not is_present:
                continue

            present_total += 1
            role_lower = role.lower()
            if role_lower == "student":
                present_students += 1
            elif role_lower == "teacher":
                present_teachers += 1
            elif role_lower == "staff":
                present_staff += 1

        self.card_present.config(text=str(present_total))
        self.card_absent.config(text=str(max(len(users) - present_total, 0)))
        self.card_students_present.config(text=str(present_students))
        self.card_teachers_present.config(text=str(present_teachers))
        self.card_staff_present.config(text=str(present_staff))
        self.card_students_absent.config(text=str(max(total_students - present_students, 0)))
        self.card_teachers_absent.config(text=str(max(total_teachers - present_teachers, 0)))
        self.card_staff_absent.config(text=str(max(total_staff - present_staff, 0)))
        
        self.recent_list.delete(*self.recent_list.get_children())
        for r in sorted(todays_recs, key=lambda x: x.timestamp, reverse=True)[:20]:
            t = r.timestamp.split(" ")[1] if " " in r.timestamp else r.timestamp
            user_info = f"{r.user_name} ({r.user_id})"
            role_text = str(getattr(r, 'role', 'Student'))
            status_text = punch_status_label(r.status)
            self.recent_list.insert("", "end", values=(t, user_info, role_text, status_text))

    def set_loading(self, is_loading):
        if is_loading:
            self.loading_lbl.config(text="● Syncing...")
        else:
            self.loading_lbl.config(text="")


class MonitorFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="Panel.TFrame")
        self.controller = controller
        
        # Header with controls
        header = ttk.Frame(self, style="Panel.TFrame")
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Monitor", style="Header.TLabel").pack(side="left")
        ttk.Button(header, text="✖ Clear", command=self.clear_logs,
                  bootstyle="secondary-outline", width=8).pack(side="right")
        
        # Console with modern terminal look
        container = ttk.Frame(self, style="Panel.TFrame")
        container.pack(fill="both", expand=True)
        
        self.text_area = scrolledtext.ScrolledText(
            container, wrap=tk.WORD, 
            bg='#0d1117', fg='#c9d1d9', insertbackground='#6c63ff',
            font=("Cascadia Mono", 9), relief="flat", borderwidth=0,
            padx=12, pady=10, selectbackground='#6c63ff',
            selectforeground='#ffffff'
        )
        self.text_area.pack(fill="both", expand=True)
        
        # Configure color tags for different log types
        self.text_area.tag_configure("system", foreground="#6c63ff")
        self.text_area.tag_configure("error", foreground="#e74c3c")
        self.text_area.tag_configure("success", foreground="#2ecc71")
        self.text_area.tag_configure("warning", foreground="#f39c12")
        self.text_area.tag_configure("sms", foreground="#3498db")
        self.text_area.tag_configure("timestamp", foreground="#5a5e6b")
        
        self.text_area.insert("1.0", "SM Scolers Monitor v11.0\n", "system")
        self.text_area.insert(tk.END, "Ready for operations.\n\n", "system")

    def add_log(self, text):
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        
        # Determine tag based on content
        tag = None
        text_lower = text.lower()
        if "error" in text_lower or "fail" in text_lower:
            tag = "error"
        elif "[gsm]" in text_lower or "[sms]" in text_lower:
            tag = "sms"
        elif "success" in text_lower or "[new]" in text_lower or "sent" in text_lower:
            tag = "success"
        elif "warn" in text_lower or "late" in text_lower:
            tag = "warning"
        elif "[system]" in text_lower:
            tag = "system"
        
        self.text_area.insert(tk.END, f"{timestamp} ", "timestamp")
        if tag:
            self.text_area.insert(tk.END, f"{text}\n", tag)
        else:
            self.text_area.insert(tk.END, f"{text}\n")
        self.text_area.see(tk.END)
    
    def clear_logs(self):
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", "Log cleared.\n", "system")


class UsersFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="Panel.TFrame")
        self.controller = controller
        
        # Header
        header = ttk.Frame(self, style="Panel.TFrame")
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Users", style="Header.TLabel").pack(side="left")
        self.user_count_lbl = ttk.Label(header, text="0 users", style="Dim.TLabel")
        self.user_count_lbl.pack(side="left", padx=(12, 0))
        
        # --- Filters Row ---
        filter_frame = ttk.Frame(self, style="Panel.TFrame")
        filter_frame.pack(fill="x", pady=(0, 8))
        
        # Role Filter
        ttk.Label(filter_frame, text="Role:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.role_var = tk.StringVar(value="All")
        role_menu = ttk.Combobox(filter_frame, textvariable=self.role_var,
                                 values=["All", "Student", "Teacher", "Staff", "Admin"],
                                 state="readonly", width=10)
        role_menu.pack(side="left", padx=(0, 12))
        role_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        # Search with icon hint
        ttk.Label(filter_frame, text="\U0001f50d", font=("Segoe UI", 10)).pack(side="left", padx=(0, 4))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=self.search_var, width=22)
        search_entry.pack(side="left", padx=(0, 4))
        search_entry.bind('<KeyRelease>', lambda e: self.apply_filter())
        ttk.Button(filter_frame, text="\u2716", command=self.clear_search,
                   bootstyle="secondary-outline", width=3).pack(side="left", padx=(0, 12))

        # Action Buttons (modern styled)
        btn_frame = ttk.Frame(filter_frame, style="Panel.TFrame")
        btn_frame.pack(side="left")
        ttk.Button(btn_frame, text="+ Add", command=self.add_user_popup,
                   bootstyle="success", width=7).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="\u270e Edit", command=self.edit_user_popup,
                   bootstyle="info", width=7).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="\u2716 Delete", command=self.delete_user,
                   bootstyle="danger-outline", width=8).pack(side="left", padx=3)

        # Right-side actions
        ttk.Button(filter_frame, text="\u21c4 Sync Device", command=self.pull_from_device,
                   bootstyle="warning", width=13).pack(side="right", padx=3)
        ttk.Button(filter_frame, text="📥 CSV Import", command=self.import_csv,
                   bootstyle="info-outline", width=12).pack(side="right", padx=3)
        ttk.Button(filter_frame, text="\u21bb Refresh", command=controller.trigger_background_refresh,
                   bootstyle="secondary-outline", width=10).pack(side="right", padx=3)

        # --- User Table ---
        table_frame = ttk.Frame(self, style="Panel.TFrame")
        table_frame.pack(fill="both", expand=True)
        
        cols = ("ID", "Name", "Role", "Type", "Class/Sec", "Phone", "Parent Info", "Bio")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=18)
        
        for c in cols: 
            self.tree.heading(c, text=c)
        self.tree.column("ID", width=55, anchor="center")
        self.tree.column("Name", width=160)
        self.tree.column("Role", width=80, anchor="center")
        self.tree.column("Type", width=75, anchor="center")
        self.tree.column("Class/Sec", width=90, anchor="center")
        self.tree.column("Phone", width=120)
        self.tree.column("Parent Info", width=160)
        self.tree.column("Bio", width=60, anchor="center")
        
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        
        # Double-click to edit
        self.tree.bind("<Double-1>", lambda e: self.edit_user_popup())

        # Right-click context menu
        self.ctx_menu = tk.Menu(self, tearoff=0, bg="#1e2128", fg="#e8eaed",
                               activebackground="#6c63ff", activeforeground="#ffffff",
                               font=("Segoe UI", 9))
        self.ctx_menu.add_command(label="✎  Edit User", command=self.edit_user_popup)
        self.ctx_menu.add_command(label="📋  Attendance History", command=self.show_user_history)
        self.ctx_menu.add_command(label="📄  Student Report PDF", command=self.export_student_pdf)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="✖  Delete User", command=self.delete_user)
        self.tree.bind("<Button-3>", self._show_context_menu)

    # --- All original user management methods (unchanged) ---
    def clear_search(self):
        self.search_var.set("")
        self.apply_filter()

    def apply_filter(self):
        self.populate(self.controller.users)

    def populate(self, users):
        self.tree.delete(*self.tree.get_children())
        filter_role = self.role_var.get()
        search_term = self.search_var.get().strip().lower()
        
        # Sort by numerical ID safely
        try:
            users.sort(key=lambda u: int(u.user_id) if u.user_id.isdigit() else 999999)
        except:
            pass

        count = 0
        for u in users:
            if filter_role != "All" and u.role != filter_role:
                continue

            if search_term:
                searchable_text = f"{u.user_id} {u.name} {u.role} {u.phone} {u.class_name} {u.section} {u.father_name} {u.mother_name}".lower()
                if search_term not in searchable_text:
                    continue

            fp_status = "OK" if u.user_id in self.controller.enrolled_ids else "No"
            class_sec = f"{u.class_name}-{u.section}" if u.class_name else ""
            parent_info = ""
            if u.role == "Student":
                p_name = u.father_name if u.father_name else u.mother_name
                p_phone = u.father_phone if u.father_phone else u.mother_phone
                parent_info = f"{p_name} ({p_phone})"
            
            student_type = u.student_type if u.role == "Student" else ""
            
            self.tree.insert("", "end", values=(
                u.user_id, u.name, u.role, student_type, class_sec, u.phone, parent_info, fp_status
            ))
            count += 1

        if hasattr(self, 'user_count_lbl'):
            self.user_count_lbl.config(text=f"{count} users")

    def pull_from_device(self):
        self.controller.log_message("[SYNC] Pulling users from device in background...")
        
        def task():
            try:
                zk = ZK(self.controller.config_data["ZK_IP"], port=self.controller.config_data["ZK_PORT"], timeout=5)
                conn = zk.connect()
                if conn:
                    conn.disable_device()
                    users = conn.get_users()
                    conn.enable_device()
                    conn.disconnect()
                    
                    count = 0
                    for dev_u in users:
                        uid = str(dev_u.user_id)
                        exists = next((x for x in self.controller.users if x.user_id == uid), None)
                        if not exists:
                            new_u = {
                                "name": dev_u.name,
                                "role": "Student",
                                "student_type": "School",
                                "card_id": str(dev_u.card) if hasattr(dev_u, 'card') else "",
                                "phone": "",
                                "class_name": "", "section": "",
                                "father_name": "", "mother_name": "",
                            }
                            db.reference(f"users/{uid}").set(new_u)
                            count += 1
                    
                    self.controller.log_queue.put(("LOG", f"[SYNC] Imported {count} new users from device"))
                    self.controller.trigger_background_refresh()
                else:
                    self.controller.log_queue.put(("LOG", "[SYNC ERROR] Could not connect to device"))
            except Exception as e:
                self.controller.log_queue.put(("LOG", f"[SYNC ERROR] {e}"))
        
        threading.Thread(target=task, daemon=True).start()

    def import_csv(self):
        """Bulk import users from CSV file."""
        filepath = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if not filepath:
            return

        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except Exception as e:
            messagebox.showerror("CSV Error", f"Could not read file: {e}")
            return

        if not rows:
            messagebox.showwarning("Empty", "CSV file has no rows.")
            return

        required = {"id", "name"}
        headers = {h.strip().lower() for h in rows[0].keys()}
        if not required.issubset(headers):
            messagebox.showerror("Missing Columns", f"CSV must have columns: id, name.\nFound: {', '.join(rows[0].keys())}")
            return

        count = 0
        skipped = 0
        for row in rows:
            # Normalize keys to lowercase
            r = {k.strip().lower(): v.strip() for k, v in row.items()}
            uid = r.get("id", "").strip()
            name_val = r.get("name", "").strip()
            if not uid or not name_val:
                skipped += 1
                continue

            data = {
                "name": name_val,
                "role": r.get("role", "Student"),
                "student_type": r.get("student_type", r.get("type", "School")),
                "phone": r.get("phone", ""),
                "class_name": r.get("class", r.get("class_name", "")),
                "section": r.get("section", ""),
                "father_name": r.get("father_name", ""),
                "father_phone": r.get("father_phone", ""),
                "mother_name": r.get("mother_name", ""),
                "mother_phone": r.get("mother_phone", ""),
            }
            db.reference(f"users/{uid}").update(data)
            count += 1

        messagebox.showinfo("Import Done", f"Imported {count} users. Skipped {skipped} invalid rows.")
        self.controller.log_message(f"[CSV IMPORT] {count} users imported from {os.path.basename(filepath)}")
        self.controller.trigger_background_refresh()

    def add_user_popup(self):
        existing_ids = [int(u.user_id) for u in self.controller.users if u.user_id.isdigit()]
        next_id = max(existing_ids) + 1 if existing_ids else 1
        
        win = ttk.Toplevel(self)
        win.title("Add New User")
        win.geometry("520x640")
        win.resizable(False, False)
        
        self._user_form(win, str(next_id), "", "Student", "", is_new=True)

    def edit_user_popup(self):
        sel = self.tree.selection()
        if not sel: return
        
        uid = str(self.tree.item(sel[0])['values'][0])
        u_obj = next((u for u in self.controller.users if u.user_id == uid), None)
        if not u_obj: return
        
        win = ttk.Toplevel(self)
        win.title(f"Edit · {u_obj.name}")
        win.geometry("520x640")
        win.resizable(False, False)
        
        self._user_form(win, u_obj.user_id, u_obj.name, u_obj.role, u_obj.phone, is_new=False, user_obj=u_obj)

    def _user_form(self, win, uid, name, role, phone, is_new, user_obj=None):
        main_frame = ttk.Frame(win, padding=20)
        main_frame.pack(fill="both", expand=True)

        # --- Header with Photo ---
        header_row = ttk.Frame(main_frame)
        header_row.pack(fill="x", pady=(0, 12))

        title_text = "New User" if is_new else f"Edit · {name}"
        ttk.Label(header_row, text=title_text, style="SubHeader.TLabel").pack(side="left")

        # Photo area
        photo_path_var = tk.StringVar()
        photo_label = tk.Label(header_row, text="No Photo", width=10, height=5,
                               bg="#2b2b2b", fg="#888888", relief="groove")
        photo_label.pack(side="right", padx=(10, 0))

        def _load_photo(path):
            if PIL_AVAILABLE and path and os.path.isfile(path):
                try:
                    img = Image.open(path)
                    img.thumbnail((80, 80))
                    photo_img = ImageTk.PhotoImage(img)
                    photo_label.configure(image=photo_img, text="")
                    photo_label._photo_ref = photo_img
                except Exception:
                    pass

        def _choose_photo():
            fp = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")])
            if fp:
                os.makedirs("photos", exist_ok=True)
                ext = os.path.splitext(fp)[1]
                dest = os.path.join("photos", f"{e_id.get()}{ext}")
                shutil.copy2(fp, dest)
                photo_path_var.set(dest)
                _load_photo(dest)

        if PIL_AVAILABLE:
            ttk.Button(header_row, text="📷", command=_choose_photo,
                       bootstyle="secondary-outline", width=3).pack(side="right", padx=2)

        # Try to load existing photo
        existing_photo = ""
        for ext in (".png", ".jpg", ".jpeg", ".bmp"):
            p = os.path.join("photos", f"{uid}{ext}")
            if os.path.isfile(p):
                existing_photo = p
                break
        if existing_photo:
            photo_path_var.set(existing_photo)
            _load_photo(existing_photo)
        
        # --- Basic Info ---
        row1 = ttk.Frame(main_frame); row1.pack(fill="x", pady=5)
        ttk.Label(row1, text="ID:", width=10).pack(side="left")
        e_id = ttk.Entry(row1, width=15)
        e_id.insert(0, uid)
        if not is_new: e_id.configure(state="readonly")
        e_id.pack(side="left")
        
        ttk.Label(row1, text="Role:", width=8).pack(side="left", padx=(10,0))
        e_role = ttk.Combobox(row1, values=["Student", "Teacher", "Staff", "Admin"], state="readonly", width=15)
        e_role.set(role)
        e_role.pack(side="left")

        row2 = ttk.Frame(main_frame); row2.pack(fill="x", pady=5)
        ttk.Label(row2, text="Name:", width=10).pack(side="left")
        e_name = ttk.Entry(row2)
        e_name.insert(0, name)
        e_name.pack(side="left", fill="x", expand=True)

        row3 = ttk.Frame(main_frame); row3.pack(fill="x", pady=5)
        ttk.Label(row3, text="Phone (Self):", width=10).pack(side="left")
        e_phone = ttk.Entry(row3)
        e_phone.insert(0, phone)
        e_phone.pack(side="left", fill="x", expand=True)

        ttk.Separator(main_frame, orient="horizontal").pack(fill="x", pady=15)

        # --- Student Specific Fields ---
        student_frame = ttk.Labelframe(main_frame, text="Student Details")
        student_frame.pack(fill="x", expand=True, pady=10)

        # Student Type
        s_row0 = ttk.Frame(student_frame); s_row0.pack(fill="x", pady=5, padx=10)
        ttk.Label(s_row0, text="Type:", width=10).pack(side="left")
        e_type = ttk.Combobox(s_row0, values=["School", "Coaching"], state="readonly", width=15)
        e_type.set("School")
        e_type.pack(side="left")

        # Class / Sec
        s_row1 = ttk.Frame(student_frame); s_row1.pack(fill="x", pady=5, padx=10)
        ttk.Label(s_row1, text="Class:").pack(side="left")
        class_values = ["Nursery", "Play", "KG", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
        e_class = ttk.Combobox(s_row1, values=class_values, state="readonly", width=12)
        e_class.pack(side="left", padx=5)
        ttk.Label(s_row1, text="Section:").pack(side="left")
        e_sec = ttk.Entry(s_row1, width=10)
        e_sec.pack(side="left", padx=5)

        # Father
        s_row2 = ttk.Frame(student_frame); s_row2.pack(fill="x", pady=5, padx=10)
        ttk.Label(s_row2, text="Father Name:", width=12).pack(side="left")
        e_fname = ttk.Entry(s_row2)
        e_fname.pack(side="left", fill="x", expand=True)
        
        s_row3 = ttk.Frame(student_frame); s_row3.pack(fill="x", pady=5, padx=10)
        ttk.Label(s_row3, text="Father Phone:", width=12).pack(side="left")
        e_fphone = ttk.Entry(s_row3)
        e_fphone.pack(side="left", fill="x", expand=True)

        # Mother
        s_row4 = ttk.Frame(student_frame); s_row4.pack(fill="x", pady=5, padx=10)
        ttk.Label(s_row4, text="Mother Name:", width=12).pack(side="left")
        e_mname = ttk.Entry(s_row4)
        e_mname.pack(side="left", fill="x", expand=True)

        s_row5 = ttk.Frame(student_frame); s_row5.pack(fill="x", pady=5, padx=10)
        ttk.Label(s_row5, text="Mother Phone:", width=12).pack(side="left")
        e_mphone = ttk.Entry(s_row5)
        e_mphone.pack(side="left", fill="x", expand=True)

        if user_obj:
            e_type.set(user_obj.student_type or "School")
            e_class.set(user_obj.class_name or "")
            e_sec.insert(0, user_obj.section or "")
            e_fname.insert(0, user_obj.father_name or "")
            e_fphone.insert(0, user_obj.father_phone or "")
            e_mname.insert(0, user_obj.mother_name or "")
            e_mphone.insert(0, user_obj.mother_phone or "")
        
        def toggle_student_fields(event=None):
            if e_role.get() == "Student":
                student_frame.pack(fill="x", expand=True, pady=10)
            else:
                student_frame.pack_forget()
        
        e_role.bind("<<ComboboxSelected>>", toggle_student_fields)
        toggle_student_fields()

        # Validation error label
        try:
            _bg = main_frame.winfo_toplevel().cget("background")
        except Exception:
            _bg = "#111318"
        err_lbl = tk.Label(main_frame, text="", font=("Segoe UI", 9), fg="#e74c3c", bg=_bg)
        err_lbl.pack(anchor="w", pady=(8, 0))

        def save():
            new_uid = e_id.get().strip()
            name_val = e_name.get().strip()
            role_val = e_role.get()
            phone_val = e_phone.get().strip()

            # Validation
            if not new_uid:
                err_lbl.config(text="⚠ User ID is required.")
                return
            if not name_val:
                err_lbl.config(text="⚠ Name is required.")
                return
            if not role_val:
                err_lbl.config(text="⚠ Please select a role.")
                return
            if phone_val and not re.match(r'^[\d+\-\s]{7,15}$', phone_val):
                err_lbl.config(text="⚠ Invalid phone format (7-15 digits).")
                return

            # Check duplicate ID for new users
            if is_new:
                existing = next((u for u in self.controller.users if u.user_id == new_uid), None)
                if existing:
                    err_lbl.config(text=f"⚠ User ID {new_uid} already exists.")
                    return

            err_lbl.config(text="")

            data = {
                "name": name_val,
                "role": role_val,
                "phone": phone_val,
                "student_type": e_type.get().strip(),
                "class_name": e_class.get().strip(),
                "section": e_sec.get().strip(),
                "father_name": e_fname.get().strip(),
                "father_phone": e_fphone.get().strip(),
                "mother_name": e_mname.get().strip(),
                "mother_phone": e_mphone.get().strip(),
            }
            db.reference(f"users/{new_uid}").update(data)
            
            primary_phone = data["phone"]
            if data["role"] == "Student" and not primary_phone:
                primary_phone = data["father_phone"] or data["mother_phone"]
            
            if primary_phone:
                self.controller.config_data["USER_PHONE_MAP"][new_uid] = primary_phone
                save_config(self.controller.config_data)
            
            win.destroy()
            action = "created" if is_new else "updated"
            self.controller.show_toast(f"User {name_val} {action}", "success", 3000)
            self.controller.trigger_background_refresh()
            
        ttk.Button(main_frame, text="💾  Save User Profile", command=save,
                   bootstyle="success", padding=(10, 8)).pack(fill="x", pady=(20, 0))

    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.ctx_menu.tk_popup(event.x_root, event.y_root)

    def show_user_history(self):
        """Show attendance history for the selected user in a popup."""
        sel = self.tree.selection()
        if not sel:
            return
        uid = str(self.tree.item(sel[0])['values'][0])
        u_obj = next((u for u in self.controller.users if u.user_id == uid), None)
        name = u_obj.name if u_obj else "Unknown"

        win = ttk.Toplevel(self)
        win.title(f"Attendance History · {name} (ID: {uid})")
        win.geometry("700x500")
        win.resizable(True, True)

        header = ttk.Frame(win, padding=(16, 12))
        header.pack(fill="x")
        ttk.Label(header, text=f"📋  {name}", style="SubHeader.TLabel").pack(side="left")
        ttk.Label(header, text=f"ID: {uid}  ·  {u_obj.role if u_obj else ''}", style="Dim.TLabel").pack(side="left", padx=(12, 0))

        # Stats row
        records = [r for r in self.controller.attendance_records if str(r.user_id) == uid]
        records.sort(key=lambda r: r.datetime, reverse=True)

        today_str = date.today().strftime("%Y-%m-%d")
        today_count = sum(1 for r in records if r.timestamp.startswith(today_str))
        total_days = len(set(r.timestamp[:10] for r in records))

        stats_frame = ttk.Frame(win, padding=(16, 4))
        stats_frame.pack(fill="x")
        ttk.Label(stats_frame, text=f"Total punches: {len(records)}  |  Days present: {total_days}  |  Today: {today_count}",
                  style="Dim.TLabel").pack(side="left")

        # Treeview
        container = ttk.Frame(win, padding=(16, 8))
        container.pack(fill="both", expand=True)

        cols = ("Date", "Time", "Status", "Role")
        tree = ttk.Treeview(container, columns=cols, show="headings", height=16)
        for c in cols:
            tree.heading(c, text=c)
        tree.column("Date", width=120, anchor="center")
        tree.column("Time", width=100, anchor="center")
        tree.column("Status", width=100, anchor="center")
        tree.column("Role", width=100, anchor="center")

        scroll = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        for r in records:
            d = r.datetime.strftime("%Y-%m-%d")
            t = r.datetime.strftime("%H:%M:%S")
            tree.insert("", "end", values=(d, t, punch_status_label(r.status), r.role))

        # Close button
        ttk.Button(win, text="Close", command=win.destroy, bootstyle="secondary",
                   width=10).pack(pady=(4, 12))

    def export_student_pdf(self):
        """Generate per-student monthly attendance report PDF."""
        sel = self.tree.selection()
        if not sel:
            return
        uid = str(self.tree.item(sel[0])['values'][0])
        u_obj = next((u for u in self.controller.users if u.user_id == uid), None)
        if not u_obj:
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"report_{u_obj.name}_{date.today().isoformat()}.pdf",
        )
        if not path:
            return

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas as pdf_canvas
        except ImportError:
            messagebox.showerror("Missing Library", "PDF export requires 'reportlab'.\nInstall: pip install reportlab")
            return

        records = [r for r in self.controller.attendance_records if str(r.user_id) == uid]
        records.sort(key=lambda r: r.datetime)

        page_w, page_h = A4
        pdf = pdf_canvas.Canvas(path, pagesize=A4)
        y = page_h - 40

        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(40, y, "SM Scolers - Student Attendance Report")
        y -= 25
        pdf.setFont("Helvetica", 11)
        pdf.drawString(40, y, f"Name: {u_obj.name}    ID: {uid}    Role: {u_obj.role}    Class: {u_obj.class_name or 'N/A'}")
        y -= 18
        pdf.drawString(40, y, f"Generated: {datetime.now().strftime('%d-%b-%Y %H:%M')}")
        y -= 8
        pdf.line(40, y, page_w - 40, y)
        y -= 20

        # Summary
        total_days = len(set(r.timestamp[:10] for r in records))
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(40, y, f"Total Punches: {len(records)}    Days Present: {total_days}")
        y -= 25

        # Table header
        headers = ["#", "Date", "Time", "Status"]
        col_x = [40, 70, 180, 300]
        pdf.setFont("Helvetica-Bold", 10)
        for i, h in enumerate(headers):
            pdf.drawString(col_x[i], y, h)
        y -= 5
        pdf.line(40, y, page_w - 40, y)
        y -= 15

        pdf.setFont("Helvetica", 9)
        for idx, r in enumerate(records, 1):
            if y < 50:
                pdf.showPage()
                y = page_h - 40
                pdf.setFont("Helvetica", 9)
            pdf.drawString(col_x[0], y, str(idx))
            pdf.drawString(col_x[1], y, r.datetime.strftime("%Y-%m-%d"))
            pdf.drawString(col_x[2], y, r.datetime.strftime("%H:%M:%S"))
            pdf.drawString(col_x[3], y, punch_status_label(r.status))
            y -= 14

        pdf.save()
        messagebox.showinfo("PDF Saved", f"Report saved to:\n{path}")
        self.controller.log_message(f"[PDF] Student report for {u_obj.name} saved")

    def delete_user(self):
        sel = self.tree.selection()
        if not sel: return
        uid = str(self.tree.item(sel[0])['values'][0])
        
        if messagebox.askyesno("Delete", f"Are you sure you want to delete User {uid}?"):
            db.reference(f"users/{uid}").delete()
            if uid in self.controller.config_data["USER_PHONE_MAP"]:
                del self.controller.config_data["USER_PHONE_MAP"][uid]
                save_config(self.controller.config_data)
            self.controller.trigger_background_refresh()
            self.controller.show_toast(f"User {uid} deleted", "warning", 3000)


class LogsFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="Panel.TFrame")
        self.controller = controller

        # --- Header ---
        header_row = ttk.Frame(self)
        header_row.pack(fill="x", pady=(0, 16))
        ttk.Label(header_row, text="Logs", style="Header.TLabel").pack(side="left")

        # --- Filter Row 1: Search + Role + Status + Today toggle ---
        row1 = ttk.Frame(self)
        row1.pack(fill="x", pady=(0, 8))

        ttk.Label(row1, text="🔍", font=("Segoe UI", 11)).pack(side="left", padx=(0, 4))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(row1, textvariable=self.search_var, width=22)
        search_entry.pack(side="left", padx=(0, 12))
        search_entry.bind("<KeyRelease>", lambda e: self.apply_filter())

        ttk.Label(row1, text="Role:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.role_filter = tk.StringVar(value="All")
        role_menu = ttk.Combobox(row1, textvariable=self.role_filter,
                                 values=["All", "Student", "Teacher", "Staff"],
                                 state="readonly", width=10)
        role_menu.pack(side="left", padx=(0, 12))
        role_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        ttk.Label(row1, text="Status:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.status_filter = tk.StringVar(value="All")
        status_menu = ttk.Combobox(row1, textvariable=self.status_filter,
                       values=["All", "Check-In", "Check-Out", "Break-Out", "Break-In", "OT-In", "OT-Out", "Late"],
                       state="readonly", width=10)
        status_menu.pack(side="left", padx=(0, 12))
        status_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        self.today_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row1, text="Today only", variable=self.today_only_var,
                command=self.apply_filter, bootstyle="round-toggle").pack(side="left", padx=(0, 12))

        ttk.Button(row1, text="📊 Export CSV", command=self.export_csv,
                   bootstyle="success-outline", width=14).pack(side="right", padx=2)
        ttk.Button(row1, text="↻ Refresh", command=self.apply_filter,
                   bootstyle="secondary-outline", width=10).pack(side="right", padx=2)

        # --- Filter Row 2: Date quick-buttons + Date range + Sort ---
        row2 = ttk.Frame(self)
        row2.pack(fill="x", pady=(0, 10))

        def _set_date_range(days_back):
            today = date.today()
            self.to_date_var.set(today.isoformat())
            self.from_date_var.set((today - timedelta(days=days_back)).isoformat())
            self.apply_filter()

        def _set_today():
            t = date.today().isoformat()
            self.from_date_var.set(t)
            self.to_date_var.set(t)
            self.apply_filter()

        def _set_yesterday():
            y = (date.today() - timedelta(days=1)).isoformat()
            self.from_date_var.set(y)
            self.to_date_var.set(y)
            self.apply_filter()

        def _clear_dates():
            self.from_date_var.set("")
            self.to_date_var.set("")
            self.apply_filter()

        ttk.Button(row2, text="Today", command=_set_today,
                   bootstyle="info-outline", width=6).pack(side="left", padx=(0, 3))
        ttk.Button(row2, text="Yesterday", command=_set_yesterday,
                   bootstyle="info-outline", width=9).pack(side="left", padx=(0, 3))
        ttk.Button(row2, text="7 Days", command=lambda: _set_date_range(7),
                   bootstyle="info-outline", width=7).pack(side="left", padx=(0, 3))
        ttk.Button(row2, text="30 Days", command=lambda: _set_date_range(30),
                   bootstyle="info-outline", width=7).pack(side="left", padx=(0, 3))
        ttk.Button(row2, text="Clear", command=_clear_dates,
                   bootstyle="secondary-outline", width=5).pack(side="left", padx=(0, 8))

        ttk.Label(row2, text="From:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.from_date_var = tk.StringVar()
        from_entry = ttk.Entry(row2, textvariable=self.from_date_var, width=11)
        from_entry.pack(side="left", padx=(0, 8))
        from_entry.bind("<KeyRelease>", lambda e: self.apply_filter())

        ttk.Label(row2, text="To:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.to_date_var = tk.StringVar()
        to_entry = ttk.Entry(row2, textvariable=self.to_date_var, width=11)
        to_entry.pack(side="left", padx=(0, 16))
        to_entry.bind("<KeyRelease>", lambda e: self.apply_filter())

        ttk.Label(row2, text="Sort:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.sort_by_var = tk.StringVar(value="Timestamp")
        sort_menu = ttk.Combobox(row2, textvariable=self.sort_by_var,
                     values=["Timestamp", "User ID", "Name", "Role", "Status"],
                     state="readonly", width=11)
        sort_menu.pack(side="left", padx=(0, 6))
        sort_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        self.sort_order_var = tk.StringVar(value="Desc")
        order_menu = ttk.Combobox(row2, textvariable=self.sort_order_var,
                      values=["Desc", "Asc"], state="readonly", width=6)
        order_menu.pack(side="left", padx=(0, 8))
        order_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        self.result_lbl = ttk.Label(row2, text="0 records", style="Dim.TLabel")
        self.result_lbl.pack(side="right")

        # --- Logs Table ---
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        cols = ("Timestamp", "User ID", "Name", "Role", "Class", "Status")
        self.tree = ttk.Treeview(container, columns=cols, show="headings", height=20)
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.column("Timestamp", width=160, anchor="center")
        self.tree.column("User ID", width=80, anchor="center")
        self.tree.column("Name", width=180)
        self.tree.column("Role", width=80, anchor="center")
        self.tree.column("Class", width=90, anchor="center")
        self.tree.column("Status", width=90, anchor="center")

        scroll = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def apply_filter(self):
        self.populate(self.controller.attendance_records)

    def populate(self, logs):
        self.tree.delete(*self.tree.get_children())
        users_by_id = {str(u.user_id): u for u in self.controller.users}
        target_role = self.role_filter.get()
        target_status = self.status_filter.get()
        search_query = self.search_var.get().strip().lower()
        today_only = self.today_only_var.get()

        def parse_date_safe(value):
            value = (value or "").strip()
            if not value:
                return None
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                return None

        from_date = parse_date_safe(self.from_date_var.get())
        to_date = parse_date_safe(self.to_date_var.get())

        filtered = []
        for l in logs:
            r_role = str(getattr(l, 'role', 'Student'))
            status_str = punch_status_label(l.status)

            if target_role != "All" and r_role != target_role:
                continue
            if target_status != "All" and status_str.lower() != target_status.lower():
                continue

            if today_only and getattr(l, "datetime", None):
                if l.datetime.date() != date.today():
                    continue

            if getattr(l, "datetime", None):
                row_date = l.datetime.date()
                if from_date and row_date < from_date:
                    continue
                if to_date and row_date > to_date:
                    continue

            if search_query:
                u_obj = users_by_id.get(str(l.user_id))
                cls = (getattr(u_obj, "class_name", "") or "") if u_obj else ""
                haystack = f"{l.timestamp} {l.user_id} {l.user_name} {r_role} {cls} {status_str}".lower()
                if search_query not in haystack:
                    continue

            filtered.append(l)

        sort_by = self.sort_by_var.get()
        reverse = self.sort_order_var.get() == "Desc"

        def sort_key(record):
            role = str(getattr(record, 'role', 'Student'))
            if sort_by == "Timestamp":
                return getattr(record, "datetime", datetime.min)
            if sort_by == "User ID":
                return str(record.user_id)
            if sort_by == "Name":
                return str(record.user_name).lower()
            if sort_by == "Role":
                return role.lower()
            return str(record.status).lower()

        filtered.sort(key=sort_key, reverse=reverse)

        for l in filtered:
            r_role = getattr(l, 'role', 'Student')
            u_obj = users_by_id.get(str(l.user_id))
            cls = (getattr(u_obj, "class_name", "") or "") if u_obj else ""
            self.tree.insert("", "end", values=(l.timestamp, l.user_id, l.user_name, r_role, cls, punch_status_label(l.status)))

        date_suffix = ""
        if from_date or to_date:
            from_text = from_date.isoformat() if from_date else "..."
            to_text = to_date.isoformat() if to_date else "..."
            date_suffix = f" | {from_text} → {to_text}"
        self.result_lbl.config(text=f"{len(filtered)} records{date_suffix}")

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path: return
        try:
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["Timestamp", "User ID", "Name", "Role", "Class", "Status"])
                for item in self.tree.get_children():
                    w.writerow(self.tree.item(item)['values'])
            self.controller.show_toast("Log exported successfully", "success", 3000)
        except Exception as e:
            messagebox.showerror("Error", str(e))


class PresentTodayFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="Panel.TFrame")
        self.controller = controller

        # --- Header ---
        header_row = ttk.Frame(self)
        header_row.pack(fill="x", pady=(0, 16))
        ttk.Label(header_row, text="Present Today", style="Header.TLabel").pack(side="left")

        # --- Controls ---
        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=(0, 10))

        ttk.Label(controls, text="Role:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.role_filter = tk.StringVar(value="All")
        role_menu = ttk.Combobox(
            controls,
            textvariable=self.role_filter,
            values=["All", "Student", "Teacher", "Staff"],
            state="readonly",
            width=10,
        )
        role_menu.pack(side="left", padx=(0, 12))
        role_menu.bind("<<ComboboxSelected>>", lambda e: self.populate(self.controller.users, self.controller.attendance_records))

        ttk.Label(controls, text="Class:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.class_filter = tk.StringVar(value="All")
        all_classes = ["All", "Play", "Nursery", "KG"] + [str(i) for i in range(1, 11)] + ["SSC", "11", "12", "HSC"]
        class_menu = ttk.Combobox(controls, textvariable=self.class_filter,
                                  values=all_classes, state="readonly", width=8)
        class_menu.pack(side="left", padx=(0, 12))
        class_menu.bind("<<ComboboxSelected>>", lambda e: self.populate(self.controller.users, self.controller.attendance_records))

        self.result_lbl = ttk.Label(controls, text="0 present", style="Dim.TLabel")
        self.result_lbl.pack(side="left", padx=(6, 0))

        ttk.Button(
            controls,
            text="↻ Refresh",
            command=lambda: self.populate(self.controller.users, self.controller.attendance_records),
            bootstyle="secondary-outline",
            width=10,
        ).pack(side="right")
        ttk.Button(
            controls,
            text="📊 Export CSV",
            command=self.export_csv,
            bootstyle="success-outline",
            width=14,
        ).pack(side="right", padx=(0, 6))

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        cols = ("User ID", "Name", "Role", "Class", "Check-In", "Check-Out", "Present Rule")
        self.tree = ttk.Treeview(container, columns=cols, show="headings", height=20)
        for c in cols:
            self.tree.heading(c, text=c)

        self.tree.column("User ID", width=90, anchor="center")
        self.tree.column("Name", width=200, anchor="w")
        self.tree.column("Role", width=90, anchor="center")
        self.tree.column("Class", width=100, anchor="center")
        self.tree.column("Check-In", width=120, anchor="center")
        self.tree.column("Check-Out", width=120, anchor="center")
        self.tree.column("Present Rule", width=200, anchor="w")

        yscroll = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

    def _is_check_in_status(self, status_value):
        value = str(status_value).strip().lower()
        return value in {"0", "in", "check-in", "checkin", "punch in"}

    def _is_check_out_status(self, status_value):
        value = str(status_value).strip().lower()
        return value in {"1", "out", "check-out", "checkout", "punch out"}

    def _get_assigned_schedule(self, user_obj, role):
        schedules = self.controller.config_data.get("CLASS_SCHEDULES", {}) or {}
        role_text = str(role or "Student").strip()

        if role_text.lower() == "student" and user_obj is not None:
            class_name = (getattr(user_obj, "class_name", "") or "").strip()
            if class_name and class_name in schedules:
                return schedules.get(class_name)

        for key in (role_text, role_text.title(), role_text.lower(), role_text.upper()):
            if key in schedules:
                return schedules.get(key)

        return None

    def _is_on_time(self, event_dt, schedule):
        if not schedule:
            return True
        start = (schedule.get("start") or "").strip()
        end = (schedule.get("end") or "").strip()
        if not start or not end:
            return True
        return is_time_in_window(event_dt, start, end)

    def populate(self, users, records):
        self.tree.delete(*self.tree.get_children())

        target_role = self.role_filter.get()
        today_str = date.today().strftime("%Y-%m-%d")
        todays_recs = [r for r in records if r.timestamp.startswith(today_str)]

        users_by_id = {str(u.user_id): u for u in users}
        recs_by_user = {}
        for rec in todays_recs:
            recs_by_user.setdefault(str(rec.user_id), []).append(rec)

        present_rows = []

        for uid, user_recs in recs_by_user.items():
            ordered = sorted(user_recs, key=lambda x: getattr(x, "datetime", datetime.min))
            first_check_in = next((x for x in ordered if self._is_check_in_status(x.status)), None)
            first_check_out = next((x for x in ordered if self._is_check_out_status(x.status)), None)

            user_obj = users_by_id.get(uid)
            role = (getattr(user_obj, "role", "") or (ordered[0].role if ordered else "Student") or "Student").strip()
            if target_role != "All" and role.lower() != target_role.lower():
                continue

            user_class = (getattr(user_obj, "class_name", "") or "") if user_obj else ""
            target_class = self.class_filter.get()
            if target_class != "All" and user_class != target_class:
                continue

            schedule = self._get_assigned_schedule(user_obj, role)

            has_valid_check_in = bool(first_check_in and self._is_on_time(first_check_in.datetime, schedule))
            has_valid_check_out = bool(first_check_out and self._is_on_time(first_check_out.datetime, schedule))

            is_present = False
            present_rule = ""
            if role.lower() == "teacher":
                is_present = has_valid_check_in
                present_rule = "Teacher: valid check-in"
            else:
                is_present = has_valid_check_in and has_valid_check_out
                present_rule = "Student/Staff: valid check-in + check-out"
                if first_check_in and first_check_out and first_check_out.datetime < first_check_in.datetime:
                    is_present = False

            if not is_present:
                continue

            check_in_time = first_check_in.datetime.strftime("%H:%M:%S") if first_check_in else "-"
            check_out_time = first_check_out.datetime.strftime("%H:%M:%S") if first_check_out else "-"
            name = getattr(user_obj, "name", "") if user_obj else (ordered[0].user_name if ordered else "Unknown")
            class_name = (getattr(user_obj, "class_name", "") or "") if user_obj else ""
            present_rows.append((uid, name, role, class_name, check_in_time, check_out_time, present_rule))

        present_rows.sort(key=lambda row: (row[2], row[1].lower()))
        for row in present_rows:
            self.tree.insert("", "end", values=row)

        self.result_lbl.config(text=f"{len(present_rows)} present records")

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"present_today_{date.today().isoformat()}.csv",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["User ID", "Name", "Role", "Class", "Check-In", "Check-Out", "Present Rule"])
                for item in self.tree.get_children():
                    writer.writerow(self.tree.item(item)["values"])
            self.controller.show_toast("Present-today list exported", "success", 3000)
        except Exception as e:
            messagebox.showerror("Export Error", str(e))


class StatisticsFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="Panel.TFrame")
        self.controller = controller

        # --- Header ---
        ttk.Label(self, text="Statistics", style="Header.TLabel").pack(anchor="w", pady=(0, 16))

        # --- Controls Row 1: Period + Date + Role ---
        row1 = ttk.Frame(self)
        row1.pack(fill="x", pady=(0, 8))

        ttk.Label(row1, text="Period:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.period_var = tk.StringVar(value="Today")
        period_menu = ttk.Combobox(
            row1, textvariable=self.period_var,
            values=["Today", "Last 7 Days", "This Month", "Custom"],
            state="readonly", width=11,
        )
        period_menu.pack(side="left", padx=(0, 12))
        period_menu.bind("<<ComboboxSelected>>", lambda e: self.populate(self.controller.users, self.controller.attendance_records))

        ttk.Label(row1, text="From:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.from_var = tk.StringVar()
        from_entry = ttk.Entry(row1, textvariable=self.from_var, width=11)
        from_entry.pack(side="left", padx=(0, 8))
        from_entry.bind("<KeyRelease>", lambda e: self._on_custom_date_change())

        ttk.Label(row1, text="To:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.to_var = tk.StringVar()
        to_entry = ttk.Entry(row1, textvariable=self.to_var, width=11)
        to_entry.pack(side="left", padx=(0, 12))
        to_entry.bind("<KeyRelease>", lambda e: self._on_custom_date_change())

        ttk.Label(row1, text="Role:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.role_var = tk.StringVar(value="All")
        role_menu = ttk.Combobox(
            row1, textvariable=self.role_var,
            values=["All", "Student", "Teacher", "Staff"],
            state="readonly", width=9,
        )
        role_menu.pack(side="left", padx=(0, 12))
        role_menu.bind("<<ComboboxSelected>>", lambda e: self.populate(self.controller.users, self.controller.attendance_records))

        ttk.Label(row1, text="Class:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.class_var = tk.StringVar(value="All")
        all_classes = ["All", "Play", "Nursery", "KG"] + [str(i) for i in range(1, 11)] + ["SSC", "11", "12", "HSC"]
        class_menu = ttk.Combobox(row1, textvariable=self.class_var,
                                  values=all_classes, state="readonly", width=8)
        class_menu.pack(side="left", padx=(0, 12))
        class_menu.bind("<<ComboboxSelected>>", lambda e: self.populate(self.controller.users, self.controller.attendance_records))

        ttk.Button(row1, text="↻ Apply", command=lambda: self.populate(self.controller.users, self.controller.attendance_records),
                   bootstyle="primary-outline", width=9).pack(side="left", padx=(0, 6))

        # --- Controls Row 2: Chart modes + Export ---
        row2 = ttk.Frame(self)
        row2.pack(fill="x", pady=(0, 10))

        ttk.Label(row2, text="Att Chart:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.att_chart_mode_var = tk.StringVar(value="Bar")
        att_mode_menu = ttk.Combobox(row2, textvariable=self.att_chart_mode_var,
            values=["Bar", "Line"], state="readonly", width=6)
        att_mode_menu.pack(side="left", padx=(0, 12))
        att_mode_menu.bind("<<ComboboxSelected>>", lambda e: self._redraw_charts_from_cache())

        ttk.Label(row2, text="Punch Chart:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.punch_chart_mode_var = tk.StringVar(value="Bar")
        punch_mode_menu = ttk.Combobox(row2, textvariable=self.punch_chart_mode_var,
            values=["Bar", "Line"], state="readonly", width=6)
        punch_mode_menu.pack(side="left", padx=(0, 12))
        punch_mode_menu.bind("<<ComboboxSelected>>", lambda e: self._redraw_charts_from_cache())

        ttk.Button(row2, text="📊 Export CSV", command=self.export_csv,
                   bootstyle="success-outline", width=14).pack(side="right", padx=2)
        ttk.Button(row2, text="📄 Export PDF", command=self.export_pdf,
                   bootstyle="info-outline", width=14).pack(side="right", padx=2)

        # --- KPI Cards ---
        kpi_row = ttk.Frame(self)
        kpi_row.pack(fill="x", pady=(0, 10))
        kpi_colors = ["#6c63ff", "#2ecc71", "#e74c3c", "#3498db"]
        kpi_icons = ["☺", "✔", "✖", "◉"]
        kpi_titles = ["Users in Scope", "Unique Present", "Unique Absent", "Attendance Rate"]
        kpi_defaults = ["0", "0", "0", "0%"]
        self.kpi_total_users = None
        self.kpi_unique_present = None
        self.kpi_unique_absent = None
        self.kpi_att_rate = None
        kpi_refs = []
        for i in range(4):
            card = tk.Frame(kpi_row, bg="#1e2128", highlightbackground="#2d313a", highlightthickness=1)
            card.grid(row=0, column=i, padx=6, sticky="nsew")
            accent_bar = tk.Frame(card, bg=kpi_colors[i], height=3)
            accent_bar.pack(fill="x")
            inner = tk.Frame(card, bg="#1e2128", padx=12, pady=8)
            inner.pack(fill="both", expand=True)
            tk.Label(inner, text=f"{kpi_icons[i]}  {kpi_titles[i]}", bg="#1e2128", fg="#8b8f98",
                     font=("Segoe UI", 9)).pack(anchor="w")
            val_lbl = tk.Label(inner, text=kpi_defaults[i], bg="#1e2128", fg=kpi_colors[i],
                               font=("Segoe UI", 22, "bold"))
            val_lbl.pack(anchor="w")
            kpi_refs.append(val_lbl)
            kpi_row.columnconfigure(i, weight=1)
        self.kpi_total_users = kpi_refs[0]
        self.kpi_unique_present = kpi_refs[1]
        self.kpi_unique_absent = kpi_refs[2]
        self.kpi_att_rate = kpi_refs[3]

        self.range_lbl = ttk.Label(self, text="Range: Today", style="Dim.TLabel")
        self.range_lbl.pack(anchor="w", pady=(0, 8))

        charts_row = ttk.Frame(self)
        charts_row.pack(fill="x", pady=(0, 10))

        att_chart_frame = ttk.Labelframe(charts_row, text="Attendance Trend", padding=6)
        att_chart_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.chart_attendance = tk.Canvas(att_chart_frame, height=220, bg="#111318", highlightthickness=0)
        self.chart_attendance.pack(fill="both", expand=True)

        punch_chart_frame = ttk.Labelframe(charts_row, text="Punch Trend", padding=6)
        punch_chart_frame.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self.chart_punch = tk.Canvas(punch_chart_frame, height=220, bg="#111318", highlightthickness=0)
        self.chart_punch.pack(fill="both", expand=True)

        self._chart_payload = None
        self.chart_attendance.bind("<Configure>", lambda e: self._redraw_charts_from_cache())
        self.chart_punch.bind("<Configure>", lambda e: self._redraw_charts_from_cache())

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        cols = ("Date", "Present Students", "Present Teachers", "Present Staff", "Total Present", "Total Absent", "Check-Ins", "Check-Outs")
        self.tree = ttk.Treeview(container, columns=cols, show="headings", height=18)
        for c in cols:
            self.tree.heading(c, text=c)

        self.tree.column("Date", width=110, anchor="center")
        self.tree.column("Present Students", width=130, anchor="center")
        self.tree.column("Present Teachers", width=130, anchor="center")
        self.tree.column("Present Staff", width=120, anchor="center")
        self.tree.column("Total Present", width=110, anchor="center")
        self.tree.column("Total Absent", width=110, anchor="center")
        self.tree.column("Check-Ins", width=95, anchor="center")
        self.tree.column("Check-Outs", width=95, anchor="center")

        yscroll = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

    def _on_custom_date_change(self):
        if self.period_var.get() == "Custom":
            self.populate(self.controller.users, self.controller.attendance_records)

    def _is_check_in_status(self, status_value):
        value = str(status_value).strip().lower()
        return value in {"0", "in", "check-in", "checkin", "punch in"}

    def _is_check_out_status(self, status_value):
        value = str(status_value).strip().lower()
        return value in {"1", "out", "check-out", "checkout", "punch out"}

    def _get_assigned_schedule(self, user_obj, role):
        schedules = self.controller.config_data.get("CLASS_SCHEDULES", {}) or {}
        role_text = str(role or "Student").strip()

        if role_text.lower() == "student" and user_obj is not None:
            class_name = (getattr(user_obj, "class_name", "") or "").strip()
            if class_name and class_name in schedules:
                return schedules.get(class_name)

        for key in (role_text, role_text.title(), role_text.lower(), role_text.upper()):
            if key in schedules:
                return schedules.get(key)

        return None

    def _is_on_time(self, event_dt, schedule):
        if not schedule:
            return True
        start = (schedule.get("start") or "").strip()
        end = (schedule.get("end") or "").strip()
        if not start or not end:
            return True
        return is_time_in_window(event_dt, start, end)

    def _resolve_date_range(self):
        today = date.today()
        period = self.period_var.get()

        if period == "Today":
            return today, today
        if period == "Last 7 Days":
            return today.replace(day=today.day) - timedelta(days=6), today
        if period == "This Month":
            first = today.replace(day=1)
            return first, today

        from_text = self.from_var.get().strip()
        to_text = self.to_var.get().strip()
        if not from_text or not to_text:
            return None, None
        try:
            d_from = datetime.strptime(from_text, "%Y-%m-%d").date()
            d_to = datetime.strptime(to_text, "%Y-%m-%d").date()
            if d_from > d_to:
                return None, None
            return d_from, d_to
        except ValueError:
            return None, None

    def _draw_dual_bar_chart(self, canvas_widget, labels, series_a, series_b, color_a, color_b, legend_a, legend_b):
        canvas_widget.delete("all")

        width = max(canvas_widget.winfo_width(), 480)
        height = max(canvas_widget.winfo_height(), 220)
        left = 42
        right = width - 14
        top = 24
        bottom = height - 32

        canvas_widget.create_line(left, top, left, bottom, fill="#666666")
        canvas_widget.create_line(left, bottom, right, bottom, fill="#666666")

        if not labels:
            canvas_widget.create_text(width // 2, height // 2, text="No data", fill="#aaaaaa", font=("Segoe UI", 10, "bold"))
            return

        max_val = max(max(series_a or [0]), max(series_b or [0]), 1)
        groups = len(labels)
        slot_width = (right - left) / max(groups, 1)
        bar_w = max(min(slot_width * 0.32, 18), 5)

        for i in range(groups):
            x_center = left + i * slot_width + slot_width / 2
            a_val = series_a[i] if i < len(series_a) else 0
            b_val = series_b[i] if i < len(series_b) else 0

            a_h = (a_val / max_val) * (bottom - top - 12)
            b_h = (b_val / max_val) * (bottom - top - 12)

            x1a = x_center - bar_w - 2
            x2a = x_center - 2
            y1a = bottom - a_h
            canvas_widget.create_rectangle(x1a, y1a, x2a, bottom, fill=color_a, outline="")

            x1b = x_center + 2
            x2b = x_center + bar_w + 2
            y1b = bottom - b_h
            canvas_widget.create_rectangle(x1b, y1b, x2b, bottom, fill=color_b, outline="")

            if groups <= 14 or i % max(1, groups // 7) == 0:
                short_label = labels[i][5:] if len(labels[i]) >= 10 else labels[i]
                canvas_widget.create_text(x_center, bottom + 11, text=short_label, fill="#bdbdbd", font=("Segoe UI", 8))

        canvas_widget.create_rectangle(left + 5, 4, left + 16, 14, fill=color_a, outline="")
        canvas_widget.create_text(left + 20, 9, text=legend_a, anchor="w", fill="#d0d0d0", font=("Segoe UI", 8, "bold"))
        canvas_widget.create_rectangle(left + 110, 4, left + 121, 14, fill=color_b, outline="")
        canvas_widget.create_text(left + 125, 9, text=legend_b, anchor="w", fill="#d0d0d0", font=("Segoe UI", 8, "bold"))

        for marker in (0, max_val // 2 if max_val > 1 else 1, max_val):
            y = bottom - (marker / max_val) * (bottom - top - 12)
            canvas_widget.create_line(left - 3, y, left, y, fill="#888888")
            canvas_widget.create_text(left - 6, y, text=str(int(marker)), anchor="e", fill="#aaaaaa", font=("Segoe UI", 7))

    def _draw_dual_line_chart(self, canvas_widget, labels, series_a, series_b, color_a, color_b, legend_a, legend_b):
        canvas_widget.delete("all")

        width = max(canvas_widget.winfo_width(), 480)
        height = max(canvas_widget.winfo_height(), 220)
        left = 42
        right = width - 14
        top = 24
        bottom = height - 32

        canvas_widget.create_line(left, top, left, bottom, fill="#666666")
        canvas_widget.create_line(left, bottom, right, bottom, fill="#666666")

        if not labels:
            canvas_widget.create_text(width // 2, height // 2, text="No data", fill="#aaaaaa", font=("Segoe UI", 10, "bold"))
            return

        max_val = max(max(series_a or [0]), max(series_b or [0]), 1)
        points_count = len(labels)
        step_x = (right - left) / max(points_count - 1, 1)

        points_a = []
        points_b = []
        for i in range(points_count):
            x = left + i * step_x
            a_val = series_a[i] if i < len(series_a) else 0
            b_val = series_b[i] if i < len(series_b) else 0
            y_a = bottom - (a_val / max_val) * (bottom - top - 12)
            y_b = bottom - (b_val / max_val) * (bottom - top - 12)
            points_a.extend([x, y_a])
            points_b.extend([x, y_b])

            if points_count <= 14 or i % max(1, points_count // 7) == 0:
                short_label = labels[i][5:] if len(labels[i]) >= 10 else labels[i]
                canvas_widget.create_text(x, bottom + 11, text=short_label, fill="#bdbdbd", font=("Segoe UI", 8))

        if len(points_a) >= 4:
            canvas_widget.create_line(*points_a, fill=color_a, width=2, smooth=True)
        if len(points_b) >= 4:
            canvas_widget.create_line(*points_b, fill=color_b, width=2, smooth=True)

        for i in range(0, len(points_a), 2):
            x, y = points_a[i], points_a[i + 1]
            canvas_widget.create_oval(x - 2, y - 2, x + 2, y + 2, fill=color_a, outline="")
        for i in range(0, len(points_b), 2):
            x, y = points_b[i], points_b[i + 1]
            canvas_widget.create_oval(x - 2, y - 2, x + 2, y + 2, fill=color_b, outline="")

        canvas_widget.create_rectangle(left + 5, 4, left + 16, 14, fill=color_a, outline="")
        canvas_widget.create_text(left + 20, 9, text=legend_a, anchor="w", fill="#d0d0d0", font=("Segoe UI", 8, "bold"))
        canvas_widget.create_rectangle(left + 110, 4, left + 121, 14, fill=color_b, outline="")
        canvas_widget.create_text(left + 125, 9, text=legend_b, anchor="w", fill="#d0d0d0", font=("Segoe UI", 8, "bold"))

        for marker in (0, max_val // 2 if max_val > 1 else 1, max_val):
            y = bottom - (marker / max_val) * (bottom - top - 12)
            canvas_widget.create_line(left - 3, y, left, y, fill="#888888")
            canvas_widget.create_text(left - 6, y, text=str(int(marker)), anchor="e", fill="#aaaaaa", font=("Segoe UI", 7))

    def _draw_chart_by_mode(self, mode, canvas_widget, labels, series_a, series_b, color_a, color_b, legend_a, legend_b):
        if str(mode).lower() == "line":
            self._draw_dual_line_chart(canvas_widget, labels, series_a, series_b, color_a, color_b, legend_a, legend_b)
            return
        self._draw_dual_bar_chart(canvas_widget, labels, series_a, series_b, color_a, color_b, legend_a, legend_b)

    def _redraw_charts_from_cache(self):
        if not self._chart_payload:
            return
        labels, present_vals, absent_vals, checkin_vals, checkout_vals = self._chart_payload
        self._draw_chart_by_mode(
            self.att_chart_mode_var.get(),
            self.chart_attendance,
            labels,
            present_vals,
            absent_vals,
            "#2fbf71",
            "#d9534f",
            "Present",
            "Absent",
        )
        self._draw_chart_by_mode(
            self.punch_chart_mode_var.get(),
            self.chart_punch,
            labels,
            checkin_vals,
            checkout_vals,
            "#4da3ff",
            "#f0ad4e",
            "Check-In",
            "Check-Out",
        )

    def populate(self, users, records):
        self.tree.delete(*self.tree.get_children())

        d_from, d_to = self._resolve_date_range()
        if not d_from or not d_to:
            self.range_lbl.config(text="Range: invalid custom dates (use YYYY-MM-DD)")
            self.kpi_total_users.config(text="0")
            self.kpi_unique_present.config(text="0")
            self.kpi_unique_absent.config(text="0")
            self.kpi_att_rate.config(text="0%")
            self._chart_payload = ([], [], [], [], [])
            self._redraw_charts_from_cache()
            return

        role_filter = self.role_var.get().lower()
        class_filter = self.class_var.get()
        users_scope = [u for u in users if role_filter == "all" or str(getattr(u, "role", "")).strip().lower() == role_filter]
        if class_filter != "All":
            users_scope = [u for u in users_scope if getattr(u, "class_name", "") == class_filter]
        users_by_id = {str(u.user_id): u for u in users_scope}

        in_range = []
        for rec in records:
            dt_val = getattr(rec, "datetime", None)
            if not dt_val:
                continue
            if str(rec.user_id) not in users_by_id:
                continue
            day_val = dt_val.date()
            if d_from <= day_val <= d_to:
                in_range.append(rec)

        by_day_user = {}
        daily_stats = {}
        unique_present_ids = set()

        for rec in in_range:
            day_key = rec.datetime.date().isoformat()
            uid = str(rec.user_id)
            by_day_user.setdefault(day_key, {}).setdefault(uid, []).append(rec)

            stats = daily_stats.setdefault(day_key, {
                "students": 0,
                "teachers": 0,
                "staff": 0,
                "checkins": 0,
                "checkouts": 0,
                "present_total": 0,
            })
            if self._is_check_in_status(rec.status):
                stats["checkins"] += 1
            elif self._is_check_out_status(rec.status):
                stats["checkouts"] += 1

        for day_key, user_map in by_day_user.items():
            for uid, user_recs in user_map.items():
                ordered = sorted(user_recs, key=lambda x: getattr(x, "datetime", datetime.min))
                first_check_in = next((x for x in ordered if self._is_check_in_status(x.status)), None)
                first_check_out = next((x for x in ordered if self._is_check_out_status(x.status)), None)

                user_obj = users_by_id.get(uid)
                role = (getattr(user_obj, "role", "") or (ordered[0].role if ordered else "Student") or "Student").strip().lower()
                schedule = self._get_assigned_schedule(user_obj, role)

                has_valid_check_in = bool(first_check_in and self._is_on_time(first_check_in.datetime, schedule))
                has_valid_check_out = bool(first_check_out and self._is_on_time(first_check_out.datetime, schedule))

                is_present = False
                if role == "teacher":
                    is_present = has_valid_check_in
                else:
                    is_present = has_valid_check_in and has_valid_check_out
                    if first_check_in and first_check_out and first_check_out.datetime < first_check_in.datetime:
                        is_present = False

                if not is_present:
                    continue

                unique_present_ids.add(uid)
                day_stats = daily_stats.setdefault(day_key, {
                    "students": 0,
                    "teachers": 0,
                    "staff": 0,
                    "checkins": 0,
                    "checkouts": 0,
                    "present_total": 0,
                })
                day_stats["present_total"] += 1
                if role == "student":
                    day_stats["students"] += 1
                elif role == "teacher":
                    day_stats["teachers"] += 1
                elif role == "staff":
                    day_stats["staff"] += 1

        total_users_scope = len(users_scope)
        unique_present = len(unique_present_ids)
        unique_absent = max(total_users_scope - unique_present, 0)
        rate = (unique_present / total_users_scope * 100.0) if total_users_scope else 0.0

        self.kpi_total_users.config(text=str(total_users_scope))
        self.kpi_unique_present.config(text=str(unique_present))
        self.kpi_unique_absent.config(text=str(unique_absent))
        self.kpi_att_rate.config(text=f"{rate:.1f}%")
        self.range_lbl.config(text=f"Range: {d_from.isoformat()} → {d_to.isoformat()}")

        day_count = (d_to - d_from).days + 1
        day_keys = [(d_from + timedelta(days=idx)).isoformat() for idx in range(day_count)]
        for day_key in sorted(day_keys, reverse=True):
            st = daily_stats.get(day_key, {
                "students": 0,
                "teachers": 0,
                "staff": 0,
                "checkins": 0,
                "checkouts": 0,
                "present_total": 0,
            })
            self.tree.insert(
                "",
                "end",
                values=(
                    day_key,
                    st["students"],
                    st["teachers"],
                    st["staff"],
                    st["present_total"],
                    max(total_users_scope - st["present_total"], 0),
                    st["checkins"],
                    st["checkouts"],
                ),
            )

        chart_labels = day_keys[-14:]
        present_vals = [daily_stats.get(d, {}).get("present_total", 0) for d in chart_labels]
        absent_vals = [max(total_users_scope - daily_stats.get(d, {}).get("present_total", 0), 0) for d in chart_labels]
        checkin_vals = [daily_stats.get(d, {}).get("checkins", 0) for d in chart_labels]
        checkout_vals = [daily_stats.get(d, {}).get("checkouts", 0) for d in chart_labels]
        self._chart_payload = (chart_labels, present_vals, absent_vals, checkin_vals, checkout_vals)
        self._redraw_charts_from_cache()

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"statistics_{date.today().isoformat()}.csv",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Period", self.period_var.get()])
                writer.writerow(["Role", self.role_var.get()])
                writer.writerow(["Range", self.range_lbl.cget("text").replace("Range: ", "")])
                writer.writerow(["Users in Scope", self.kpi_total_users.cget("text")])
                writer.writerow(["Unique Present", self.kpi_unique_present.cget("text")])
                writer.writerow(["Unique Absent", self.kpi_unique_absent.cget("text")])
                writer.writerow(["Attendance Rate", self.kpi_att_rate.cget("text")])
                writer.writerow([])
                writer.writerow(["Date", "Present Students", "Present Teachers", "Present Staff", "Total Present", "Total Absent", "Check-Ins", "Check-Outs"])

                for item in self.tree.get_children():
                    writer.writerow(self.tree.item(item)["values"])

            self.controller.show_toast("Statistics CSV exported", "success", 3000)
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def export_pdf(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"statistics_{date.today().isoformat()}.pdf",
        )
        if not path:
            return

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
        except ImportError:
            messagebox.showerror(
                "Missing Dependency",
                "PDF export requires 'reportlab'.\nInstall it with: pip install reportlab",
            )
            return

        try:
            pdf = canvas.Canvas(path, pagesize=A4)
            page_w, page_h = A4

            y = page_h - 40
            pdf.setFont("Helvetica-Bold", 16)
            pdf.drawString(40, y, "SM Scolers Attendance - Statistics Report")

            y -= 28
            pdf.setFont("Helvetica", 10)
            meta_lines = [
                f"Period: {self.period_var.get()}",
                f"Role: {self.role_var.get()}",
                f"Range: {self.range_lbl.cget('text').replace('Range: ', '')}",
                f"Users in Scope: {self.kpi_total_users.cget('text')}",
                f"Unique Present: {self.kpi_unique_present.cget('text')}",
                f"Unique Absent: {self.kpi_unique_absent.cget('text')}",
                f"Attendance Rate: {self.kpi_att_rate.cget('text')}",
            ]
            for line in meta_lines:
                pdf.drawString(40, y, line)
                y -= 14

            y -= 8
            pdf.setFont("Helvetica-Bold", 10)
            headers = ["Date", "Stu", "Tch", "Stf", "Present", "Absent", "In", "Out"]
            x_positions = [40, 115, 155, 195, 235, 300, 365, 410]
            for header, x in zip(headers, x_positions):
                pdf.drawString(x, y, header)

            y -= 12
            pdf.line(40, y, page_w - 40, y)
            y -= 12

            pdf.setFont("Helvetica", 9)
            for item in self.tree.get_children():
                values = self.tree.item(item)["values"]
                row = [
                    str(values[0]),
                    str(values[1]),
                    str(values[2]),
                    str(values[3]),
                    str(values[4]),
                    str(values[5]),
                    str(values[6]),
                    str(values[7]),
                ]

                if y < 45:
                    pdf.showPage()
                    y = page_h - 40
                    pdf.setFont("Helvetica-Bold", 10)
                    for header, x in zip(headers, x_positions):
                        pdf.drawString(x, y, header)
                    y -= 12
                    pdf.line(40, y, page_w - 40, y)
                    y -= 12
                    pdf.setFont("Helvetica", 9)

                for cell, x in zip(row, x_positions):
                    pdf.drawString(x, y, cell)
                y -= 12

            pdf.save()
            self.controller.show_toast("Statistics PDF exported", "success", 3000)
        except Exception as e:
            messagebox.showerror("Export Error", str(e))


class SettingsFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="Panel.TFrame")
        self.controller = controller

        # --- Header ---
        ttk.Label(self, text="Settings", style="Header.TLabel").pack(anchor="w", pady=(0, 16))

        # Scrollable container
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, bg='#111318')
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=(0, 5))
        scrollbar.pack(side="right", fill="y")

        # --- Device & Network Settings ---
        dev_frame = ttk.Labelframe(scrollable_frame, text="Hardware", padding=10)
        dev_frame.pack(fill="x", pady=5, padx=5)

        self.entries = {}
        fields = [
            ("ZK IP", "ZK_IP"),
            ("ZK Port", "ZK_PORT"),
            ("GSM Port", "GSM_PORT"),
            ("GSM Baud", "GSM_BAUD"),
        ]

        for lbl, key in fields:
            row = ttk.Frame(dev_frame)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=lbl, width=12).pack(side="left")
            e = ttk.Entry(row)
            val = self.controller.config_data.get(key, "")
            e.insert(0, str(val))
            e.pack(side="right", fill="x", expand=True)
            self.entries[key] = e

        # --- SMS Templates ---
        sms_frame = ttk.Labelframe(scrollable_frame, text="SMS", padding=10)
        sms_frame.pack(fill="x", pady=5, padx=5)

        row_norm = ttk.Frame(sms_frame)
        row_norm.pack(fill="x", pady=3)
        ttk.Label(row_norm, text="Standard:", width=12).pack(side="left")
        e_norm = ttk.Entry(row_norm)
        e_norm.insert(0, self.controller.config_data.get("SMS_TEMPLATE", DEFAULT_CONFIG["SMS_TEMPLATE"]))
        e_norm.pack(side="right", fill="x", expand=True)
        self.entries["SMS_TEMPLATE"] = e_norm

        row_late = ttk.Frame(sms_frame)
        row_late.pack(fill="x", pady=3)
        ttk.Label(row_late, text="Late:", width=12).pack(side="left")
        e_late = ttk.Entry(row_late)
        e_late.insert(0, self.controller.config_data.get("LATE_SMS_TEMPLATE", DEFAULT_CONFIG["LATE_SMS_TEMPLATE"]))
        e_late.pack(side="right", fill="x", expand=True)
        self.entries["LATE_SMS_TEMPLATE"] = e_late

        row_ussd = ttk.Frame(sms_frame)
        row_ussd.pack(fill="x", pady=3)
        ttk.Label(row_ussd, text="USSD:", width=12).pack(side="left")
        e_ussd = ttk.Entry(row_ussd)
        e_ussd.insert(0, self.controller.config_data.get("USSD_CODE", DEFAULT_CONFIG["USSD_CODE"]))
        e_ussd.pack(side="right", fill="x", expand=True)
        self.entries["USSD_CODE"] = e_ussd

        # --- Absent SMS Settings ---
        absent_frame = ttk.Labelframe(scrollable_frame, text="Absent Notifications", padding=10)
        absent_frame.pack(fill="x", pady=5, padx=5)

        row_absent_enable = ttk.Frame(absent_frame)
        row_absent_enable.pack(fill="x", pady=3)
        ttk.Label(row_absent_enable, text="Enabled:", width=12).pack(side="left")
        self.absent_enabled_var = tk.BooleanVar(value=self.controller.config_data.get("ABSENT_SMS_ENABLED", False))
        ttk.Checkbutton(row_absent_enable, variable=self.absent_enabled_var,
                        bootstyle="round-toggle").pack(side="left")

        row_absent_time = ttk.Frame(absent_frame)
        row_absent_time.pack(fill="x", pady=3)
        ttk.Label(row_absent_time, text="Cutoff Time:", width=12).pack(side="left")
        e_absent_time = ttk.Entry(row_absent_time, width=8)
        e_absent_time.insert(0, self.controller.config_data.get("ABSENT_SMS_TIME", "09:30"))
        e_absent_time.pack(side="left")
        ttk.Label(row_absent_time, text="  (HH:MM — SMS sent after this time)", style="Dim.TLabel").pack(side="left")
        self.entries["ABSENT_SMS_TIME"] = e_absent_time

        row_absent_tmpl = ttk.Frame(absent_frame)
        row_absent_tmpl.pack(fill="x", pady=3)
        ttk.Label(row_absent_tmpl, text="Template:", width=12).pack(side="left")
        e_absent_tmpl = ttk.Entry(row_absent_tmpl)
        e_absent_tmpl.insert(0, self.controller.config_data.get("ABSENT_SMS_TEMPLATE", DEFAULT_CONFIG["ABSENT_SMS_TEMPLATE"]))
        e_absent_tmpl.pack(side="right", fill="x", expand=True)
        self.entries["ABSENT_SMS_TEMPLATE"] = e_absent_tmpl

        # --- Daily Summary SMS Settings ---
        summary_frame = ttk.Labelframe(scrollable_frame, text="Daily Summary SMS", padding=10)
        summary_frame.pack(fill="x", pady=5, padx=5)

        row_sum_enable = ttk.Frame(summary_frame)
        row_sum_enable.pack(fill="x", pady=3)
        ttk.Label(row_sum_enable, text="Enabled:", width=12).pack(side="left")
        self.summary_enabled_var = tk.BooleanVar(value=self.controller.config_data.get("DAILY_SUMMARY_ENABLED", False))
        ttk.Checkbutton(row_sum_enable, variable=self.summary_enabled_var,
                        bootstyle="round-toggle").pack(side="left")

        row_sum_time = ttk.Frame(summary_frame)
        row_sum_time.pack(fill="x", pady=3)
        ttk.Label(row_sum_time, text="Send Time:", width=12).pack(side="left")
        e_sum_time = ttk.Entry(row_sum_time, width=8)
        e_sum_time.insert(0, self.controller.config_data.get("DAILY_SUMMARY_TIME", "17:00"))
        e_sum_time.pack(side="left")
        ttk.Label(row_sum_time, text="  (HH:MM — summary sent at this time)", style="Dim.TLabel").pack(side="left")
        self.entries["DAILY_SUMMARY_TIME"] = e_sum_time

        row_admin1 = ttk.Frame(summary_frame)
        row_admin1.pack(fill="x", pady=3)
        ttk.Label(row_admin1, text="Admin 1 Phone:", width=14).pack(side="left")
        e_admin1 = ttk.Entry(row_admin1, width=20)
        e_admin1.insert(0, self.controller.config_data.get("ADMIN_PHONE_1", ""))
        e_admin1.pack(side="left")
        self.entries["ADMIN_PHONE_1"] = e_admin1

        row_admin2 = ttk.Frame(summary_frame)
        row_admin2.pack(fill="x", pady=3)
        ttk.Label(row_admin2, text="Admin 2 Phone:", width=14).pack(side="left")
        e_admin2 = ttk.Entry(row_admin2, width=20)
        e_admin2.insert(0, self.controller.config_data.get("ADMIN_PHONE_2", ""))
        e_admin2.pack(side="left")
        self.entries["ADMIN_PHONE_2"] = e_admin2

        row_sum_tmpl = ttk.Frame(summary_frame)
        row_sum_tmpl.pack(fill="x", pady=3)
        ttk.Label(row_sum_tmpl, text="Template:", width=12).pack(side="left")
        e_sum_tmpl = ttk.Entry(row_sum_tmpl)
        e_sum_tmpl.insert(0, self.controller.config_data.get("DAILY_SUMMARY_TEMPLATE", DEFAULT_CONFIG["DAILY_SUMMARY_TEMPLATE"]))
        e_sum_tmpl.pack(side="right", fill="x", expand=True)
        self.entries["DAILY_SUMMARY_TEMPLATE"] = e_sum_tmpl

        # --- GSM Toolbox (phone-like controls) ---
        gsm_tools = ttk.Labelframe(scrollable_frame, text="GSM Toolbox", padding=10)
        gsm_tools.pack(fill="x", pady=5, padx=5)

        quick_btns = ttk.Frame(gsm_tools)
        quick_btns.pack(fill="x", pady=(0, 8))
        ttk.Button(quick_btns, text="Quick Diagnose", command=self.run_quick_diagnose,
               bootstyle="info-outline", width=16).pack(side="left", padx=(0, 5))
        ttk.Button(quick_btns, text="Register SIM", command=self.run_register_sequence,
               bootstyle="warning-outline", width=14).pack(side="left", padx=(0, 5))
        ttk.Button(quick_btns, text="Run USSD", command=self.run_ussd_from_settings,
               bootstyle="secondary-outline", width=12).pack(side="left")

        at_row = ttk.Frame(gsm_tools)
        at_row.pack(fill="x", pady=4)
        ttk.Label(at_row, text="AT Command:", width=12).pack(side="left")
        self.at_command_entry = ttk.Entry(at_row)
        self.at_command_entry.insert(0, "AT+CREG?")
        self.at_command_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(at_row, text="Send", command=self.run_custom_at_command,
               bootstyle="primary-outline", width=8).pack(side="left")

        sms_row = ttk.Frame(gsm_tools)
        sms_row.pack(fill="x", pady=4)
        ttk.Label(sms_row, text="Test SMS:", width=12).pack(side="left")
        self.test_sms_phone = ttk.Entry(sms_row, width=18)
        self.test_sms_phone.pack(side="left", padx=(0, 5))
        self.test_sms_body = ttk.Entry(sms_row)
        self.test_sms_body.insert(0, "Test SMS from SM Scolers GSM Toolbox")
        self.test_sms_body.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(sms_row, text="Send SMS", command=self.send_test_sms,
               bootstyle="success-outline", width=10).pack(side="left")

        ttk.Label(gsm_tools, text="Output", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 4))
        self.gsm_output = scrolledtext.ScrolledText(gsm_tools, height=10, wrap="word",
            font=("Cascadia Mono", 9), bg="#0d1117", fg="#e8eaed",
            insertbackground="#e8eaed", selectbackground="#6c63ff")
        self.gsm_output.pack(fill="both", expand=True)
        self.gsm_output.insert("end", "GSM toolbox ready. Use Quick Diagnose or send AT commands.\n")
        self.gsm_output.configure(state="disabled")

        # --- Class Schedules (fully preserved) ---
        sched_frame = ttk.Labelframe(scrollable_frame, text="Class Schedules", padding=10)
        sched_frame.pack(fill="x", pady=5, padx=5)

        ttk.Label(sched_frame, text="Expected in-time windows per class",
                  font=("Segoe UI", 9, "italic"), foreground='#aaaaaa').pack(anchor="w", pady=(0, 5))

        # Treeview for schedules
        tree_frame = ttk.Frame(sched_frame)
        tree_frame.pack(fill="x", pady=5)

        cols = ("Class", "Type", "Start", "End")
        self.schedule_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=6)
        self.schedule_tree.heading("Class", text="Class")
        self.schedule_tree.heading("Type", text="Type")
        self.schedule_tree.heading("Start", text="Start")
        self.schedule_tree.heading("End", text="End")
        self.schedule_tree.column("Class", width=80, anchor="center")
        self.schedule_tree.column("Type", width=80, anchor="center")
        self.schedule_tree.column("Start", width=80, anchor="center")
        self.schedule_tree.column("End", width=80, anchor="center")
        self.schedule_tree.pack(side="left", fill="both", expand=True)

        scroll_tree = ttk.Scrollbar(tree_frame, orient="vertical", command=self.schedule_tree.yview)
        self.schedule_tree.configure(yscrollcommand=scroll_tree.set)
        scroll_tree.pack(side="right", fill="y")

        # Load existing schedules
        schedules = self.controller.config_data.get("CLASS_SCHEDULES", {})
        for class_name, times in schedules.items():
            start = times.get("start", "")
            end = times.get("end", "")
            schedule_type = times.get("type", "School")
            self.schedule_tree.insert("", "end", values=(class_name, schedule_type, start, end))

        # Class subsections
        self.schedule_type_var = tk.StringVar(value="School")
        class_section_frame = ttk.Frame(sched_frame)
        class_section_frame.pack(fill="x", pady=(10, 5))

        # School classes
        school_frame = ttk.Labelframe(class_section_frame, text="School", padding=6)
        school_frame.pack(side="left", fill="x", expand=True, padx=(0, 5))
        school_classes = ["Play", "Nursery", "KG"] + [str(i) for i in range(1, 11)]
        self.school_class_combo = ttk.Combobox(school_frame, values=school_classes, state="readonly", width=12)
        self.school_class_combo.pack(fill="x")
        self.school_class_combo.set("")

        # Coaching classes
        coaching_frame = ttk.Labelframe(class_section_frame, text="Coaching", padding=6)
        coaching_frame.pack(side="left", fill="x", expand=True, padx=(5, 0))
        coaching_classes = [str(i) for i in range(4, 11)] + ["SSC", "11", "12", "HSC"]
        self.coaching_class_combo = ttk.Combobox(coaching_frame, values=coaching_classes, state="readonly", width=12)
        self.coaching_class_combo.pack(fill="x")
        self.coaching_class_combo.set("")

        def _set_type(value):
            self.schedule_type_var.set(value)
        self.school_class_combo.bind("<<ComboboxSelected>>", lambda e: _set_type("School"))
        self.coaching_class_combo.bind("<<ComboboxSelected>>", lambda e: _set_type("Coaching"))

        # Time selectors
        time_frame = ttk.Frame(sched_frame)
        time_frame.pack(fill="x", pady=(5, 0))

        ttk.Label(time_frame, text="Start:").grid(row=0, column=0, padx=2, pady=2, sticky="w")
        time_options = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]
        self.e_start = ttk.Combobox(time_frame, values=time_options, state="readonly", width=7)
        self.e_start.grid(row=0, column=1, padx=2, pady=2, sticky="w")
        self.e_start.set("")

        ttk.Label(time_frame, text="End:").grid(row=0, column=2, padx=2, pady=2, sticky="w")
        self.e_end = ttk.Combobox(time_frame, values=time_options, state="readonly", width=7)
        self.e_end.grid(row=0, column=3, padx=2, pady=2, sticky="w")
        self.e_end.set("")

        time_frame.columnconfigure(3, weight=1)

        # Buttons
        btn_frame = ttk.Frame(sched_frame)
        btn_frame.pack(fill="x", pady=(5, 0))

        ttk.Button(btn_frame, text="Add/Update", command=self._add_schedule,
               bootstyle="success", width=12).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Delete", command=self._delete_schedule,
                   bootstyle="danger", width=8).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Save", command=self._save_schedules,
                   bootstyle="primary", width=8).pack(side="right", padx=2)

        # --- Early Leave SMS ---
        early_frame = ttk.Labelframe(scrollable_frame, text="Early Leave SMS", padding=10)
        early_frame.pack(fill="x", pady=5, padx=5)

        row_el_en = ttk.Frame(early_frame); row_el_en.pack(fill="x", pady=3)
        ttk.Label(row_el_en, text="Enabled:", width=12).pack(side="left")
        self.early_leave_var = tk.BooleanVar(value=self.controller.config_data.get("EARLY_LEAVE_SMS_ENABLED", False))
        ttk.Checkbutton(row_el_en, variable=self.early_leave_var, bootstyle="round-toggle").pack(side="left")

        row_el_tmpl = ttk.Frame(early_frame); row_el_tmpl.pack(fill="x", pady=3)
        ttk.Label(row_el_tmpl, text="Template:", width=12).pack(side="left")
        e_el_tmpl = ttk.Entry(row_el_tmpl)
        e_el_tmpl.insert(0, self.controller.config_data.get("EARLY_LEAVE_SMS_TEMPLATE", DEFAULT_CONFIG["EARLY_LEAVE_SMS_TEMPLATE"]))
        e_el_tmpl.pack(side="right", fill="x", expand=True)
        self.entries["EARLY_LEAVE_SMS_TEMPLATE"] = e_el_tmpl

        # --- Holiday / Off-day Calendar ---
        holiday_frame = ttk.Labelframe(scrollable_frame, text="Holidays / Off-days", padding=10)
        holiday_frame.pack(fill="x", pady=5, padx=5)

        ttk.Label(holiday_frame, text="Absent SMS is skipped on holidays",
                  font=("Segoe UI", 9, "italic"), foreground='#aaaaaa').pack(anchor="w", pady=(0, 5))

        hol_tree_frame = ttk.Frame(holiday_frame)
        hol_tree_frame.pack(fill="x", pady=5)
        self.holiday_listbox = tk.Listbox(hol_tree_frame, height=5, bg="#0d1117", fg="#e8eaed",
                                          selectbackground="#6c63ff", font=("Cascadia Mono", 9))
        self.holiday_listbox.pack(side="left", fill="both", expand=True)
        hol_scroll = ttk.Scrollbar(hol_tree_frame, orient="vertical", command=self.holiday_listbox.yview)
        self.holiday_listbox.configure(yscrollcommand=hol_scroll.set)
        hol_scroll.pack(side="right", fill="y")

        for h in self.controller.config_data.get("HOLIDAYS", []):
            self.holiday_listbox.insert("end", h)

        hol_input = ttk.Frame(holiday_frame)
        hol_input.pack(fill="x", pady=(5, 0))
        ttk.Label(hol_input, text="Date (YYYY-MM-DD):").pack(side="left")
        self.holiday_entry = ttk.Entry(hol_input, width=14)
        self.holiday_entry.pack(side="left", padx=5)
        ttk.Button(hol_input, text="Add", command=self._add_holiday,
                   bootstyle="success", width=6).pack(side="left", padx=2)
        ttk.Button(hol_input, text="Remove", command=self._remove_holiday,
                   bootstyle="danger", width=8).pack(side="left", padx=2)
        ttk.Button(hol_input, text="Save", command=self._save_holidays,
                   bootstyle="primary", width=6).pack(side="right", padx=2)

        # --- App Preferences ---
        pref_frame = ttk.Labelframe(scrollable_frame, text="App Preferences", padding=10)
        pref_frame.pack(fill="x", pady=5, padx=5)

        # Theme
        row_theme = ttk.Frame(pref_frame); row_theme.pack(fill="x", pady=3)
        ttk.Label(row_theme, text="Theme:", width=12).pack(side="left")
        self.theme_var = tk.StringVar(value=self.controller.config_data.get("THEME", "darkly"))
        theme_combo = ttk.Combobox(row_theme, textvariable=self.theme_var,
                                   values=["darkly", "flatly", "superhero", "cosmo", "journal", "litera"],
                                   state="readonly", width=14)
        theme_combo.pack(side="left")
        ttk.Label(row_theme, text="  (restart app to apply)", style="Dim.TLabel").pack(side="left")

        # Notification Sound
        row_sound = ttk.Frame(pref_frame); row_sound.pack(fill="x", pady=3)
        ttk.Label(row_sound, text="Sound:", width=12).pack(side="left")
        self.sound_var = tk.BooleanVar(value=self.controller.config_data.get("NOTIFICATION_SOUND", True))
        ttk.Checkbutton(row_sound, variable=self.sound_var, bootstyle="round-toggle").pack(side="left")
        ttk.Label(row_sound, text="  Play sound on new attendance", style="Dim.TLabel").pack(side="left")

        # PIN Lock
        row_pin = ttk.Frame(pref_frame); row_pin.pack(fill="x", pady=3)
        ttk.Label(row_pin, text="PIN Lock:", width=12).pack(side="left")
        ttk.Button(row_pin, text="Set PIN", command=self._set_pin,
                   bootstyle="warning-outline", width=10).pack(side="left", padx=(0, 5))
        ttk.Button(row_pin, text="Remove PIN", command=self._remove_pin,
                   bootstyle="danger-outline", width=10).pack(side="left")

        # --- Auto Backup ---
        backup_frame = ttk.Labelframe(scrollable_frame, text="Auto Backup", padding=10)
        backup_frame.pack(fill="x", pady=5, padx=5)

        row_bk_en = ttk.Frame(backup_frame); row_bk_en.pack(fill="x", pady=3)
        ttk.Label(row_bk_en, text="Enabled:", width=12).pack(side="left")
        self.backup_enabled_var = tk.BooleanVar(value=self.controller.config_data.get("AUTO_BACKUP_ENABLED", False))
        ttk.Checkbutton(row_bk_en, variable=self.backup_enabled_var, bootstyle="round-toggle").pack(side="left")

        row_bk_dir = ttk.Frame(backup_frame); row_bk_dir.pack(fill="x", pady=3)
        ttk.Label(row_bk_dir, text="Directory:", width=12).pack(side="left")
        self.backup_dir_entry = ttk.Entry(row_bk_dir)
        self.backup_dir_entry.insert(0, self.controller.config_data.get("AUTO_BACKUP_DIR", "backups"))
        self.backup_dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(row_bk_dir, text="Browse", command=self._browse_backup_dir,
                   bootstyle="secondary-outline", width=8).pack(side="left")

        row_bk_btns = ttk.Frame(backup_frame); row_bk_btns.pack(fill="x", pady=3)
        ttk.Button(row_bk_btns, text="Backup Now", command=self._backup_now,
                   bootstyle="info", width=12).pack(side="left", padx=2)
        ttk.Button(row_bk_btns, text="Restore", command=self._restore_backup,
                   bootstyle="warning", width=10).pack(side="left", padx=2)

        # --- Multi-device ZK ---
        device_frame = ttk.Labelframe(scrollable_frame, text="Multi-device ZK", padding=10)
        device_frame.pack(fill="x", pady=5, padx=5)

        ttk.Label(device_frame, text="Additional ZK devices (main device set above in Hardware)",
                  font=("Segoe UI", 9, "italic"), foreground='#aaaaaa').pack(anchor="w", pady=(0, 5))

        dev_tree_frame = ttk.Frame(device_frame)
        dev_tree_frame.pack(fill="x", pady=5)
        dev_cols = ("Name", "IP", "Port")
        self.device_tree = ttk.Treeview(dev_tree_frame, columns=dev_cols, show="headings", height=4)
        self.device_tree.heading("Name", text="Name")
        self.device_tree.heading("IP", text="IP")
        self.device_tree.heading("Port", text="Port")
        self.device_tree.column("Name", width=120)
        self.device_tree.column("IP", width=140)
        self.device_tree.column("Port", width=60, anchor="center")
        self.device_tree.pack(side="left", fill="both", expand=True)

        for dev in self.controller.config_data.get("ZK_DEVICES", []):
            self.device_tree.insert("", "end", values=(dev.get("name", ""), dev.get("ip", ""), dev.get("port", 4370)))

        dev_input = ttk.Frame(device_frame)
        dev_input.pack(fill="x", pady=(5, 0))
        ttk.Label(dev_input, text="Name:").pack(side="left")
        self.dev_name_entry = ttk.Entry(dev_input, width=12)
        self.dev_name_entry.pack(side="left", padx=3)
        ttk.Label(dev_input, text="IP:").pack(side="left")
        self.dev_ip_entry = ttk.Entry(dev_input, width=14)
        self.dev_ip_entry.pack(side="left", padx=3)
        ttk.Label(dev_input, text="Port:").pack(side="left")
        self.dev_port_entry = ttk.Entry(dev_input, width=6)
        self.dev_port_entry.insert(0, "4370")
        self.dev_port_entry.pack(side="left", padx=3)
        ttk.Button(dev_input, text="Add", command=self._add_device,
                   bootstyle="success", width=5).pack(side="left", padx=2)
        ttk.Button(dev_input, text="Remove", command=self._remove_device,
                   bootstyle="danger", width=7).pack(side="left", padx=2)
        ttk.Button(dev_input, text="Save", command=self._save_devices,
                   bootstyle="primary", width=6).pack(side="right", padx=2)

        # --- Save All Button ---
        save_btn = ttk.Button(scrollable_frame, text="Save All Settings",
                              command=self.save_all_settings, bootstyle="primary",
                              padding=(10, 8))
        save_btn.pack(fill="x", pady=20, padx=5)

    # --- Schedule helpers (unchanged) ---
    def _get_selected_class(self):
        if self.schedule_type_var.get() == "Coaching":
            return self.coaching_class_combo.get().strip()
        return self.school_class_combo.get().strip()

    def _clear_class_selection(self):
        self.school_class_combo.set("")
        self.coaching_class_combo.set("")
        self.schedule_type_var.set("School")

    def _add_schedule(self):
        class_val = self._get_selected_class()
        start_val = self.e_start.get().strip()
        end_val = self.e_end.get().strip()
        schedule_type = self.schedule_type_var.get() or "School"
        if not class_val or not start_val or not end_val:
            messagebox.showwarning("Incomplete", "Please select class, start and end time.")
            return

        existing = False
        for child in self.schedule_tree.get_children():
            if self.schedule_tree.item(child)['values'][0] == class_val:
                self.schedule_tree.item(child, values=(class_val, schedule_type, start_val, end_val))
                existing = True
                break
        if not existing:
            self.schedule_tree.insert("", "end", values=(class_val, schedule_type, start_val, end_val))

        self._clear_class_selection()
        self.e_start.set("")
        self.e_end.set("")

    def _delete_schedule(self):
        selected = self.schedule_tree.selection()
        if selected:
            self.schedule_tree.delete(selected[0])

    def _save_schedules(self):
        new_schedules = {}
        for child in self.schedule_tree.get_children():
            vals = self.schedule_tree.item(child)['values']
            class_name = str(vals[0])
            schedule_type = str(vals[1]) if len(vals) > 3 else "School"
            start = str(vals[2])
            end = str(vals[3])
            new_schedules[class_name] = {"start": start, "end": end, "type": schedule_type}
        self.controller.config_data["CLASS_SCHEDULES"] = new_schedules
        save_config(self.controller.config_data)
        messagebox.showinfo("Saved", "Class schedules updated successfully.")
        self.controller.log_message("[SCHEDULES] Class schedules updated.")

    def append_gsm_output(self, text):
        self.gsm_output.configure(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.gsm_output.insert("end", f"[{ts}] {text}\n")
        self.gsm_output.see("end")
        self.gsm_output.configure(state="disabled")

    def run_custom_at_command(self):
        command = self.at_command_entry.get().strip()
        if not command:
            messagebox.showwarning("Missing Command", "Please enter an AT command.")
            return

        def task():
            response = run_at_command(self.controller.config_data, command, 1.2)
            self.after(0, lambda: self.append_gsm_output(f"{command} -> {response}"))
        threading.Thread(target=task, daemon=True).start()

    def run_quick_diagnose(self):
        def task():
            results = run_gsm_diagnostic_snapshot(self.controller.config_data)
            self.after(0, lambda: self.append_gsm_output("=== Quick GSM Diagnose ==="))
            for label, cmd, response in results:
                self.after(0, lambda l=label, c=cmd, r=response: self.append_gsm_output(f"{l} | {c} -> {r}"))
        threading.Thread(target=task, daemon=True).start()

    def run_register_sequence(self):
        sequence = [
            "AT+CREG=2",
            "AT+CGATT=1",
            "AT+CREG?",
            "AT+COPS?",
            "AT+CGATT?",
        ]

        def task():
            self.after(0, lambda: self.append_gsm_output("=== Register SIM Sequence ==="))
            for command in sequence:
                response = run_at_command(self.controller.config_data, command, 1.2)
                self.after(0, lambda c=command, r=response: self.append_gsm_output(f"{c} -> {r}"))
        threading.Thread(target=task, daemon=True).start()

    def run_ussd_from_settings(self):
        code = self.entries["USSD_CODE"].get().strip() or self.controller.config_data.get("USSD_CODE", "")
        if not code:
            messagebox.showwarning("Missing USSD", "Please set a USSD code first.")
            return

        def task():
            response = run_ussd_command(self.controller.config_data, code)
            self.after(0, lambda: self.append_gsm_output(f"USSD {code} -> {response}"))
        threading.Thread(target=task, daemon=True).start()

    def send_test_sms(self):
        phone = self.test_sms_phone.get().strip()
        body = self.test_sms_body.get().strip()
        if not phone or not body:
            messagebox.showwarning("Incomplete", "Please enter phone and message for test SMS.")
            return

        def task():
            sent = send_sms_gsm(
                self.controller.config_data,
                phone,
                body,
                lambda msg: self.after(0, lambda m=msg: self.append_gsm_output(m))
            )
            self.after(0, lambda: self.append_gsm_output(f"Test SMS result: {'SENT' if sent else 'FAILED'}"))
        threading.Thread(target=task, daemon=True).start()

    # --- Holiday helpers ---
    def _add_holiday(self):
        val = self.holiday_entry.get().strip()
        if not val:
            return
        try:
            datetime.strptime(val, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("Invalid Date", "Use YYYY-MM-DD format.")
            return
        items = list(self.holiday_listbox.get(0, "end"))
        if val not in items:
            self.holiday_listbox.insert("end", val)
        self.holiday_entry.delete(0, "end")

    def _remove_holiday(self):
        sel = self.holiday_listbox.curselection()
        if sel:
            self.holiday_listbox.delete(sel[0])

    def _save_holidays(self):
        holidays = list(self.holiday_listbox.get(0, "end"))
        self.controller.config_data["HOLIDAYS"] = holidays
        save_config(self.controller.config_data)
        messagebox.showinfo("Saved", f"{len(holidays)} holidays saved.")

    # --- PIN helpers ---
    def _set_pin(self):
        pin = simpledialog.askstring("Set PIN", "Enter new PIN (4+ digits):", show="*")
        if not pin or len(pin) < 4:
            messagebox.showwarning("Invalid", "PIN must be at least 4 characters.")
            return
        confirm = simpledialog.askstring("Confirm PIN", "Re-enter PIN:", show="*")
        if pin != confirm:
            messagebox.showerror("Mismatch", "PINs do not match.")
            return
        self.controller.config_data["APP_PIN"] = hashlib.sha256(pin.encode()).hexdigest()
        save_config(self.controller.config_data)
        messagebox.showinfo("PIN Set", "App PIN lock has been set.")

    def _remove_pin(self):
        if messagebox.askyesno("Remove PIN", "Are you sure you want to remove the PIN lock?"):
            self.controller.config_data["APP_PIN"] = ""
            save_config(self.controller.config_data)
            messagebox.showinfo("Removed", "PIN lock removed.")

    # --- Backup helpers ---
    def _browse_backup_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.backup_dir_entry.delete(0, "end")
            self.backup_dir_entry.insert(0, d)

    def _backup_now(self):
        bk_dir = self.backup_dir_entry.get().strip() or "backups"
        os.makedirs(bk_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(bk_dir, f"backup_{ts}.json")

        def task():
            try:
                ref_users = db.reference("users").get() or {}
                ref_logs = db.reference("attendance_logs").get() or {}
                payload = {"users": ref_users, "attendance_logs": ref_logs, "backup_time": ts}
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                self.after(0, lambda: messagebox.showinfo("Backup", f"Backup saved to {filepath}"))
                self.after(0, lambda: self.controller.log_message(f"[BACKUP] Saved to {filepath}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Backup Error", str(e)))
        threading.Thread(target=task, daemon=True).start()

    def _restore_backup(self):
        filepath = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not filepath:
            return
        if not messagebox.askyesno("Restore", "This will OVERWRITE current Firebase data. Continue?"):
            return

        def task():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if "users" in payload:
                    db.reference("users").set(payload["users"])
                if "attendance_logs" in payload:
                    db.reference("attendance_logs").set(payload["attendance_logs"])
                self.after(0, lambda: messagebox.showinfo("Restored", f"Data restored from {filepath}"))
                self.after(0, lambda: self.controller.log_message(f"[RESTORE] Data restored from {filepath}"))
                self.after(0, lambda: self.controller.trigger_background_refresh())
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Restore Error", str(e)))
        threading.Thread(target=task, daemon=True).start()

    # --- Multi-device helpers ---
    def _add_device(self):
        name = self.dev_name_entry.get().strip()
        ip = self.dev_ip_entry.get().strip()
        port = self.dev_port_entry.get().strip() or "4370"
        if not name or not ip:
            messagebox.showwarning("Incomplete", "Name and IP are required.")
            return
        self.device_tree.insert("", "end", values=(name, ip, port))
        self.dev_name_entry.delete(0, "end")
        self.dev_ip_entry.delete(0, "end")
        self.dev_port_entry.delete(0, "end")
        self.dev_port_entry.insert(0, "4370")

    def _remove_device(self):
        sel = self.device_tree.selection()
        if sel:
            self.device_tree.delete(sel[0])

    def _save_devices(self):
        devices = []
        for child in self.device_tree.get_children():
            vals = self.device_tree.item(child)['values']
            devices.append({"name": str(vals[0]), "ip": str(vals[1]), "port": int(vals[2])})
        self.controller.config_data["ZK_DEVICES"] = devices
        save_config(self.controller.config_data)
        messagebox.showinfo("Saved", f"{len(devices)} extra devices saved.")

    def save_all_settings(self):
        for key, entry in self.entries.items():
            val = entry.get()
            if key in ["ZK_PORT", "GSM_BAUD"]:
                try:
                    val = int(val)
                except:
                    pass
            self.controller.config_data[key] = val

        # Save toggle values not in entries dict
        self.controller.config_data["ABSENT_SMS_ENABLED"] = self.absent_enabled_var.get()
        self.controller.config_data["DAILY_SUMMARY_ENABLED"] = self.summary_enabled_var.get()
        self.controller.config_data["EARLY_LEAVE_SMS_ENABLED"] = self.early_leave_var.get()
        self.controller.config_data["THEME"] = self.theme_var.get()
        self.controller.config_data["NOTIFICATION_SOUND"] = self.sound_var.get()
        self.controller.config_data["AUTO_BACKUP_ENABLED"] = self.backup_enabled_var.get()
        self.controller.config_data["AUTO_BACKUP_DIR"] = self.backup_dir_entry.get().strip() or "backups"

        save_config(self.controller.config_data)
        self.controller.show_toast("Settings saved successfully", "success", 3000)
        self.controller.log_message("[SETTINGS] Configuration saved")


if __name__ == "__main__":
    # --- App PIN Lock ---
    _cfg = load_config()
    _pin_hash = _cfg.get("APP_PIN", "")
    if _pin_hash:
        import tkinter as _tk_lock
        _lock_root = _tk_lock.Tk()
        _lock_root.withdraw()
        _attempts = [0]
        _unlocked = [False]
        while _attempts[0] < 3:
            _entered = simpledialog.askstring("SM Scolers — PIN Lock", "Enter PIN to unlock:", show="*", parent=_lock_root)
            if _entered is None:
                break
            if hashlib.sha256(_entered.encode()).hexdigest() == _pin_hash:
                _unlocked[0] = True
                break
            _attempts[0] += 1
            messagebox.showerror("Wrong PIN", f"Incorrect PIN. {3 - _attempts[0]} attempt(s) left.", parent=_lock_root)
        _lock_root.destroy()
        if not _unlocked[0]:
            sys.exit(0)

    app = AttendanceApp()
    app.mainloop()