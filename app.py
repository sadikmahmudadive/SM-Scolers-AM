"""
SM Scolers Attendance System - Commercial Edition v10.5
MINIMAL DARK UI - Clean, distraction-free, professional
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
from datetime import datetime, date, time as dt_time, timedelta
from typing import Dict, Set, List

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
    "FIREBASE_CRED_PATH": SERVICE_ACCOUNT_FILE,
    "FIREBASE_DB_URL": "https://fir-m-scholars-school-1999b-default-rtdb.firebaseio.com/",
    "POLL_INTERVAL_SEC": 10,
    "USER_PHONE_MAP": {},
    "CLASS_SCHEDULES": {}   # e.g. {"Nursery": {"start": "07:40", "end": "08:10"}, "1": {...}}
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
        ser.close()
        log_cb(f"[GSM] SMS sent to {phone}")
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

def run_ussd_command(config, ussd_code):
    if not SERIAL_LOCK.acquire(timeout=3):
        return "System Busy. Try again."

    result = "No Response"
    try:
        ser = serial.Serial(config["GSM_PORT"], config["GSM_BAUD"], timeout=3)
        time.sleep(1)
        ser.write(b'AT+CMGF=1\r') 
        time.sleep(0.2)
        ser.write(b'AT+CSCS="GSM"\r')
        time.sleep(0.2)
        
        cmd = f'AT+CUSD=1,"{ussd_code}",15\r'
        ser.write(cmd.encode())
        
        start = time.time()
        raw_resp = ""
        while time.time() - start < 8:
            if ser.inWaiting():
                raw_resp += ser.read(ser.inWaiting()).decode('utf-8', errors='ignore')
                if "+CUSD:" in raw_resp:
                    break
            time.sleep(0.5)
        
        match = re.search(r'\+CUSD: \d,\s*"(.*?)",', raw_resp, re.DOTALL)
        if match:
            payload = match.group(1)
            if re.match(r'^[0-9A-Fa-f]+$', payload) and len(payload) % 2 == 0 and len(payload) > 4:
                result = decode_hex_string(payload)
            else:
                result = payload
        else:
            if "+CUSD:" in raw_resp:
                payload = raw_resp.split("+CUSD:")[1].strip()
                if ',' in payload:
                    parts = payload.split(',', 1)
                    if parts[1].strip().startswith('"'):
                        payload = parts[1].strip().strip('"')
                if re.match(r'^[0-9A-Fa-f]+$', payload) and len(payload) % 2 == 0:
                      result = decode_hex_string(payload)
                else:
                      result = payload
            else:
                result = "Timeout/No USSD Reply"
        ser.close()
    except Exception as e:
        result = f"Error: {str(e)}"
    finally:
        SERIAL_LOCK.release()
    return result


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
    try:
        ref = db.reference("attendance_logs")
        data = ref.get(shallow=True) 
        if data:
            if isinstance(data, list):
                for i, v in enumerate(data):
                    if v: existing_keys.add(str(i))
            else:
                existing_keys = set(data.keys())
    except Exception:
        pass

    log_callback(f"[SYSTEM] Engine Started. Polling every {config['POLL_INTERVAL_SEC']}s")

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
                    log_callback("[SYSTEM] Device reconnected - syncing immediately")
                    device_was_offline = False
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
        stop_event.wait(config["POLL_INTERVAL_SEC"])

# ---------------------------
# UI APPLICATION – MINIMAL DARK
# ---------------------------
class AttendanceApp(ttk.Window if THEME_AVAILABLE else tk.Tk):
    def __init__(self):
        if THEME_AVAILABLE:
            # Use darkly theme for clean, minimal dark look
            super().__init__(themename="darkly")
        else:
            super().__init__()
            
        self.title("SM Scolers · Attendance System v10.5")
        self.geometry("1400x850")  # Slightly smaller, more compact
        self.minsize(1200, 700)
        
        # Set application icon
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except Exception as e:
            print(f"Warning: Could not load icon 'icon.ico': {e}")

        # Global color scheme (used only if ttkbootstrap not available)
        self.bg_dark = "#1a1a1a"
        self.bg_medium = "#2a2a2a"
        self.bg_light = "#3a3a3a"
        self.fg = "#ffffff"
        self.accent = "#ffffff"

        # Minimal style overrides – keep it clean
        if THEME_AVAILABLE:
            style = ttk.Style()
            style.configure('Treeview.Heading', font=('Segoe UI', 11, 'bold'), background='#2a2a2a', foreground='#dddddd')
            style.configure('Treeview', font=('Segoe UI', 10), rowheight=30, background='#1e1e1e', fieldbackground='#1e1e1e', foreground='#eeeeee')
            style.configure('TLabel', font=('Segoe UI', 10))
            style.configure('TButton', font=('Segoe UI', 9, 'bold'))
            style.configure('TLabelframe.Label', font=('Segoe UI', 10, 'bold'))
            style.configure('Sidebar.TFrame', background='#1e1e1e')
            style.configure('Panel.TFrame', background='#1a1a1a')

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

        container = ttk.Frame(self, style="Panel.TFrame")
        container.pack(fill="both", expand=True)

        self.create_sidebar(container)
        self.create_main_area(container)
        
        # Process the queue in the main thread
        self.after(100, self.process_queue)
        
        # Start initial data fetch in BACKGROUND THREAD
        self.log_message("[SYSTEM] Application started")
        self.trigger_background_refresh()

        # Periodic UI refresh every 5 seconds
        self.after(5000, self.periodic_ui_refresh)

    # ------------------------------------------------------------
    # SIDEBAR – clean, compact, no decorative elements
    # ------------------------------------------------------------
    def create_sidebar(self, parent):
        # Sidebar Width: 210px (narrow)
        sidebar = ttk.Frame(parent, width=210, style="Sidebar.TFrame")
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False) 
        
        # Brand – clean and simple
        brand_frame = ttk.Frame(sidebar, style="Sidebar.TFrame")
        brand_frame.pack(fill="x", pady=(20, 25), padx=15)
        ttk.Label(brand_frame, text="SM SCOLERS", font=("Segoe UI", 16, "bold"),
                  foreground='#ffffff').pack(anchor="w")
        ttk.Label(brand_frame, text="Attendance System", font=("Segoe UI", 9),
                  foreground='#aaaaaa').pack(anchor="w")

        # Navigation
        self.nav_var = tk.StringVar(value="dashboard")
        nav_frame = ttk.Frame(sidebar, style="Sidebar.TFrame")
        nav_frame.pack(fill="x", expand=False, anchor="n", padx=10)
        
        nav_buttons = [
            ("Dashboard", "dashboard"), 
            ("Statistics", "statistics"),
            ("Present Today", "present"),
            ("Monitor", "monitor"), 
            ("Users", "users"), 
            ("Logs", "logs"), 
            ("Settings", "settings")
        ]
        
        for text, mode in nav_buttons:
            btn = ttk.Radiobutton(
                nav_frame, 
                text=text, 
                variable=self.nav_var, 
                value=mode, 
                command=self.switch_tab, 
                bootstyle="secondary-outline-toolbutton",
                width=18,
                padding=(8, 6)
            )
            btn.pack(pady=2, fill="x")

        # Spacer
        ttk.Frame(sidebar, style="Sidebar.TFrame").pack(expand=True, fill="both")

        # --- DEVICE & SIM STATUS (compact) ---
        status_widget = ttk.Frame(sidebar, style="Sidebar.TFrame")
        status_widget.pack(fill="x", padx=10, pady=(0, 15), side="bottom")

        ttk.Label(status_widget, text="DEVICE", font=("Segoe UI", 8, "bold"),
                  foreground='#aaaaaa').pack(anchor="w")
        self.status_label = ttk.Label(status_widget, text="OFFLINE", font=("Segoe UI", 9, "bold"),
                                      bootstyle="danger")
        self.status_label.pack(anchor="w", pady=(0, 5))

        ttk.Label(status_widget, text="GSM", font=("Segoe UI", 8, "bold"),
                  foreground='#aaaaaa').pack(anchor="w")
        self.lbl_carrier = ttk.Label(status_widget, text="Scanning...", font=("Segoe UI", 9))
        self.lbl_carrier.pack(anchor="w")
        
        self.progress_signal = ttk.Progressbar(status_widget, value=0, maximum=100,
                                               bootstyle="success-striped", length=160)
        self.progress_signal.pack(fill="x", pady=6)

        # SIM Actions
        sim_row = ttk.Frame(status_widget, style="Sidebar.TFrame")
        sim_row.pack(fill="x", pady=(8, 5))
        ttk.Button(sim_row, text="Balance", command=self.check_balance_popup,
                   bootstyle="secondary-outline", width=10).pack(side="left", padx=(0, 5))
        ttk.Button(sim_row, text="⚙", command=self.edit_ussd_popup,
                   bootstyle="secondary-outline", width=3).pack(side="right")

        # --- SYNC BUTTON ---
        self.btn_sync = ttk.Button(
            sidebar, text="▶ START", command=self.toggle_sync,
            bootstyle="success", padding=(8, 10)
        )
        self.btn_sync.pack(fill="x", side="bottom", padx=10, pady=(0, 20))

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
            self.btn_sync.configure(text="⏹ STOP", bootstyle="warning")
            self.sync_thread.join()
            self.btn_sync.configure(text="▶ START", bootstyle="success")
            self.update_connection_status(False)
            self.log_message("[SYSTEM] Engine Stopped.")
        else:
            # Retrieve users
            self.stop_event.clear()
            # user_cache_map needs keys like name, phone, etc.
            user_cache_map = {}
            for u in self.users:
                user_cache_map[u.user_id] = {
                    "name": u.name, "role": u.role, 
                    "phone": u.phone, 
                    "father_phone": u.father_phone, 
                    "mother_phone": u.mother_phone,
                    "class_name": u.class_name,
                    "section": u.section
                }

            self.sync_thread = threading.Thread(
                target=run_sync_loop, 
                args=(self.config_data, self.enqueue_log, self.stop_event, self.update_stats, self.trigger_auto_refresh, self.enqueue_status, self.enqueue_enrollment, user_cache_map, self.enqueue_gsm, self.enqueue_sms_log)
            )
            self.sync_thread.daemon = True
            self.sync_thread.start()
            self.btn_sync.configure(text="⏹ STOP", bootstyle="danger")

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

        # Toast notification removed – using log message instead
        self.log_message(f"[USSD] Dialing {code}...")
        
        def task():
            res = run_ussd_command(self.config_data, code)
            self.after(0, lambda: messagebox.showinfo(f"Balance ({code})", res))
        threading.Thread(target=task, daemon=True).start()

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
        self.after(5000, self.periodic_ui_refresh)

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
            self.is_refreshing = False

    def trigger_background_refresh(self):
        if not self.is_refreshing:
            self.is_refreshing = True
            self.frames["DashboardFrame"].set_loading(True)
            threading.Thread(target=self.bg_fetch_data, daemon=True).start()

    def update_ui_with_data(self, users, records):
        self.users = users
        self.attendance_records = records
        self.is_refreshing = False
        
        self.frames["UsersFrame"].apply_filter()
        self.frames["LogsFrame"].populate(self.attendance_records)
        self.frames["DashboardFrame"].update_metrics(self.users, self.attendance_records)
        self.frames["StatisticsFrame"].populate(self.users, self.attendance_records)
        self.frames["PresentTodayFrame"].populate(self.users, self.attendance_records)
        self.frames["DashboardFrame"].set_loading(False)
        
        # Toast notification removed – using log message instead
        self.log_message("[SYSTEM] Data Updated Successfully")

    # ------------------------------------------------------------
    # UI UPDATES
    # ------------------------------------------------------------
    def update_connection_status(self, is_connected):
        if is_connected:
            self.status_label.configure(text="ONLINE", bootstyle="success")
        else:
            self.status_label.configure(text="OFFLINE", bootstyle="danger")

    def update_gsm_ui(self, carrier, signal):
        self.lbl_carrier.config(text=f"{carrier} {signal}%")
        self.progress_signal['value'] = signal
        if signal < 30: self.progress_signal.configure(bootstyle="danger-striped")
        elif signal < 60: self.progress_signal.configure(bootstyle="warning-striped")
        else: self.progress_signal.configure(bootstyle="success-striped")

    def log_message(self, msg):
        monitor = self.frames["MonitorFrame"]
        ts = datetime.now().strftime("%H:%M:%S")
        monitor.add_log(f"[{ts}] {msg}")

    def update_stats(self, category, count=1):
        self.stats[category] += count
        self.frames["DashboardFrame"].update_counters(self.stats)

# ---------------------------
# UI FRAMES – MINIMAL DARK
# ---------------------------

class DashboardFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="Panel.TFrame")
        self.controller = controller
        
        # Header – clean title only
        ttk.Label(self, text="Dashboard", font=("Segoe UI", 22, "bold")).pack(anchor="w", pady=(0, 20))
        
        # Stats cards – simple frames
        card_container = ttk.Frame(self)
        card_container.pack(fill="x", pady=10)
        
        self.card_users = self.create_stat_card(card_container, "Total Users", "0", 0, "info")
        self.card_present = self.create_stat_card(card_container, "▲ Present Today", "0", 1, "success")
        self.card_absent = self.create_stat_card(card_container, "▼ Absent Today", "0", 2, "danger")
        self.card_sms = self.create_stat_card(card_container, "SMS Sent", "0", 3, "primary")

        role_card_container = ttk.Frame(self)
        role_card_container.pack(fill="x", pady=(0, 10))
        self.card_students_present = self.create_stat_card(role_card_container, "▲ Students Present", "0", 0, "success")
        self.card_teachers_present = self.create_stat_card(role_card_container, "▲ Teachers Present", "0", 1, "success")
        self.card_staff_present = self.create_stat_card(role_card_container, "▲ Staff Present", "0", 2, "success")

        absent_card_container = ttk.Frame(self)
        absent_card_container.pack(fill="x", pady=(0, 10))
        self.card_students_absent = self.create_stat_card(absent_card_container, "▼ Students Absent", "0", 0, "danger")
        self.card_teachers_absent = self.create_stat_card(absent_card_container, "▼ Teachers Absent", "0", 1, "danger")
        self.card_staff_absent = self.create_stat_card(absent_card_container, "▼ Staff Absent", "0", 2, "danger")

        # Recent Activity
        activity_header = ttk.Frame(self)
        activity_header.pack(fill="x", pady=(20, 10))
        ttk.Label(activity_header, text="Recent Activity", font=("Segoe UI", 14, "bold")).pack(side="left")
        self.loading_lbl = ttk.Label(activity_header, text="", font=("Segoe UI", 9, "italic"),
                                     foreground='#888888')
        self.loading_lbl.pack(side="right")
        
        # Treeview
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        self.recent_list = ttk.Treeview(container, columns=("Time", "User", "Status"),
                                        show="headings", height=14)
        self.recent_list.heading("Time", text="Time")
        self.recent_list.heading("User", text="User")
        self.recent_list.heading("Status", text="Status")
        self.recent_list.column("Time", width=120, anchor="center")
        self.recent_list.column("User", width=350, anchor="w")
        self.recent_list.column("Status", width=80, anchor="center")
        self.recent_list.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(container, orient="vertical", command=self.recent_list.yview)
        self.recent_list.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

    def create_stat_card(self, parent, title, value, col, value_bootstyle=None):
        frame = ttk.Frame(parent, padding=12, relief='flat', style='Panel.TFrame')
        frame.grid(row=0, column=col, padx=8, sticky="ew")
        ttk.Label(frame, text=title, font=("Segoe UI", 10), foreground='#aaaaaa').pack(anchor="w")
        val_lbl = ttk.Label(frame, text=value, font=("Segoe UI", 28, "bold"))
        if THEME_AVAILABLE and value_bootstyle:
            try:
                val_lbl.configure(bootstyle=value_bootstyle)
            except Exception:
                pass
        val_lbl.pack(anchor="w")
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
        for r in sorted(todays_recs, key=lambda x: x.timestamp, reverse=True)[:15]:
            t = r.timestamp.split(" ")[1] if " " in r.timestamp else r.timestamp
            user_info = f"{r.user_name} ({r.user_id})"
            status_text = "In" if self._is_check_in_status(r.status) else ("Out" if self._is_check_out_status(r.status) else str(r.status))
            self.recent_list.insert("", "end", values=(t, user_info, status_text))

    def set_loading(self, is_loading):
        self.loading_lbl.config(text="Loading..." if is_loading else "")


class MonitorFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="Panel.TFrame")
        
        ttk.Label(self, text="Monitor", font=("Segoe UI", 22, "bold")).pack(anchor="w", pady=(0, 20))
        
        # Console – plain dark background, no borders
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        
        self.text_area = scrolledtext.ScrolledText(
            container, wrap=tk.WORD, 
            bg='#0e0e0e', fg='#d0d0d0', insertbackground='white',
            font=("Consolas", 9), relief="flat", borderwidth=0,
            padx=8, pady=8
        )
        self.text_area.pack(fill="both", expand=True)
        self.text_area.insert("1.0", "SM Scolers Monitor\n")

    def add_log(self, text):
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        self.text_area.insert(tk.END, f"{timestamp} {text}\n")
        self.text_area.see(tk.END)


class UsersFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="Panel.TFrame")
        self.controller = controller
        
        ttk.Label(self, text="Users", font=("Segoe UI", 22, "bold")).pack(anchor="w", pady=(0, 20))
        
        # --- Filters and Actions (compact) ---
        control_frame = ttk.Frame(self)
        control_frame.pack(fill="x", pady=(0, 15))
        
        # Role Filter
        ttk.Label(control_frame, text="Role:").pack(side="left", padx=(0, 5))
        self.role_var = tk.StringVar(value="All")
        role_menu = ttk.Combobox(control_frame, textvariable=self.role_var,
                                 values=["All", "Student", "Teacher", "Staff", "Admin"],
                                 state="readonly", width=12)
        role_menu.pack(side="left", padx=(0, 15))
        role_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        # Search
        ttk.Label(control_frame, text="Search:").pack(side="left", padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(control_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side="left", padx=(0, 5))
        search_entry.bind('<KeyRelease>', lambda e: self.apply_filter())
        ttk.Button(control_frame, text="Clear", command=self.clear_search,
                   bootstyle="secondary", width=6).pack(side="left", padx=(0, 15))

        # Action Buttons
        ttk.Button(control_frame, text="Add", command=self.add_user_popup,
                   bootstyle="success", width=8).pack(side="left", padx=2)
        ttk.Button(control_frame, text="Edit", command=self.edit_user_popup,
                   bootstyle="info", width=8).pack(side="left", padx=2)
        ttk.Button(control_frame, text="Delete", command=self.delete_user,
                   bootstyle="danger", width=8).pack(side="left", padx=2)

        # Sync Actions
        ttk.Button(control_frame, text="Sync Device", command=self.pull_from_device,
                   bootstyle="warning", width=12).pack(side="right", padx=2)
        ttk.Button(control_frame, text="Refresh", command=controller.trigger_background_refresh,
                   bootstyle="secondary", width=8).pack(side="right", padx=2)

        # --- User Table ---
        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True)
        
        cols = ("ID", "Name", "Role", "Type", "Class/Sec", "Phone", "Parent Info", "Bio")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=18)
        
        for c in cols: 
            self.tree.heading(c, text=c)
        self.tree.column("ID", width=60, anchor="center")
        self.tree.column("Name", width=150)
        self.tree.column("Role", width=80)
        self.tree.column("Type", width=80)
        self.tree.column("Class/Sec", width=100)
        self.tree.column("Phone", width=120)
        self.tree.column("Parent Info", width=160)
        self.tree.column("Bio", width=80, anchor="center")
        
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

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

    def add_user_popup(self):
        existing_ids = [int(u.user_id) for u in self.controller.users if u.user_id.isdigit()]
        next_id = max(existing_ids) + 1 if existing_ids else 1
        
        win = ttk.Toplevel(self)
        win.title("Add New User")
        win.geometry("500x600")
        
        self._user_form(win, str(next_id), "", "Student", "", is_new=True)

    def edit_user_popup(self):
        sel = self.tree.selection()
        if not sel: return
        
        uid = str(self.tree.item(sel[0])['values'][0])
        u_obj = next((u for u in self.controller.users if u.user_id == uid), None)
        if not u_obj: return
        
        win = ttk.Toplevel(self)
        win.title(f"Edit {u_obj.name}")
        win.geometry("500x600")
        
        self._user_form(win, u_obj.user_id, u_obj.name, u_obj.role, u_obj.phone, is_new=False, user_obj=u_obj)

    def _user_form(self, win, uid, name, role, phone, is_new, user_obj=None):
        main_frame = ttk.Frame(win, padding=20)
        main_frame.pack(fill="both", expand=True)
        
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

        def save():
            new_uid = e_id.get().strip()
            if not new_uid: return

            data = {
                "name": e_name.get().strip(),
                "role": e_role.get(),
                "phone": e_phone.get().strip(),
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
            self.controller.trigger_background_refresh()
            
        ttk.Button(main_frame, text="Save User Profile", command=save, bootstyle="success").pack(fill="x", pady=20)

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


class LogsFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="Panel.TFrame")
        self.controller = controller
        
        ttk.Label(self, text="Logs", font=("Segoe UI", 22, "bold")).pack(anchor="w", pady=(0, 20))
        
        # --- Controls ---
        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=(0, 15))

        ttk.Label(controls, text="Search:").pack(side="left", padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(controls, textvariable=self.search_var, width=24)
        search_entry.pack(side="left", padx=(0, 10))
        search_entry.bind("<KeyRelease>", lambda e: self.apply_filter())
        
        ttk.Label(controls, text="Role:").pack(side="left", padx=(0, 5))
        self.role_filter = tk.StringVar(value="All")
        role_menu = ttk.Combobox(controls, textvariable=self.role_filter,
                                 values=["All", "Student", "Teacher", "Staff"],
                                 state="readonly", width=12)
        role_menu.pack(side="left", padx=(0, 15))
        role_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        ttk.Label(controls, text="Status:").pack(side="left", padx=(0, 5))
        self.status_filter = tk.StringVar(value="All")
        status_menu = ttk.Combobox(controls, textvariable=self.status_filter,
                       values=["All", "0", "1", "Check-In", "Check-Out", "Late"],
                       state="readonly", width=10)
        status_menu.pack(side="left", padx=(0, 15))
        status_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        self.today_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls, text="Today only", variable=self.today_only_var,
                command=self.apply_filter, bootstyle="round-toggle").pack(side="left", padx=(0, 15))

        ttk.Label(controls, text="From:").pack(side="left", padx=(0, 5))
        self.from_date_var = tk.StringVar()
        from_entry = ttk.Entry(controls, textvariable=self.from_date_var, width=11)
        from_entry.pack(side="left", padx=(0, 6))
        from_entry.bind("<KeyRelease>", lambda e: self.apply_filter())

        ttk.Label(controls, text="To:").pack(side="left", padx=(0, 5))
        self.to_date_var = tk.StringVar()
        to_entry = ttk.Entry(controls, textvariable=self.to_date_var, width=11)
        to_entry.pack(side="left", padx=(0, 12))
        to_entry.bind("<KeyRelease>", lambda e: self.apply_filter())

        ttk.Label(controls, text="Sort:").pack(side="left", padx=(0, 5))
        self.sort_by_var = tk.StringVar(value="Timestamp")
        sort_menu = ttk.Combobox(controls, textvariable=self.sort_by_var,
                     values=["Timestamp", "User ID", "Name", "Role", "Status"],
                     state="readonly", width=12)
        sort_menu.pack(side="left", padx=(0, 6))
        sort_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        self.sort_order_var = tk.StringVar(value="Desc")
        order_menu = ttk.Combobox(controls, textvariable=self.sort_order_var,
                      values=["Desc", "Asc"], state="readonly", width=7)
        order_menu.pack(side="left", padx=(0, 8))
        order_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        ttk.Button(controls, text="Export CSV", command=self.export_csv,
                   bootstyle="success", width=12).pack(side="right", padx=2)
        ttk.Button(controls, text="Refresh", command=self.apply_filter,
                   bootstyle="secondary", width=8).pack(side="right", padx=2)

        self.result_lbl = ttk.Label(self, text="0 records", font=("Segoe UI", 9), foreground="#aaaaaa")
        self.result_lbl.pack(anchor="w", pady=(0, 8))
        
        # --- Logs Table ---
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        
        cols = ("Timestamp", "User ID", "Name", "Role", "Status")
        self.tree = ttk.Treeview(container, columns=cols, show="headings", height=20)
        for c in cols: 
            self.tree.heading(c, text=c)
        self.tree.column("Timestamp", width=160, anchor="center")
        self.tree.column("User ID", width=80, anchor="center")
        self.tree.column("Name", width=200)
        self.tree.column("Role", width=90, anchor="center")
        self.tree.column("Status", width=90, anchor="center")
        
        scroll = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def apply_filter(self):
        self.populate(self.controller.attendance_records)

    def populate(self, logs):
        self.tree.delete(*self.tree.get_children())
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
            status_str = str(l.status)

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
                haystack = f"{l.timestamp} {l.user_id} {l.user_name} {r_role} {status_str}".lower()
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
            self.tree.insert("", "end", values=(l.timestamp, l.user_id, l.user_name, r_role, l.status))

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
                w.writerow(["Timestamp", "User ID", "Name", "Role", "Status"])
                for item in self.tree.get_children():
                    w.writerow(self.tree.item(item)['values'])
            messagebox.showinfo("Export", "Log exported successfully.")
        except Exception as e:
            messagebox.showerror("Error", str(e))


class PresentTodayFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="Panel.TFrame")
        self.controller = controller

        ttk.Label(self, text="Present Today", font=("Segoe UI", 22, "bold")).pack(anchor="w", pady=(0, 20))

        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=(0, 10))

        self.role_filter = tk.StringVar(value="All")
        ttk.Label(controls, text="Role:").pack(side="left", padx=(0, 6))
        role_menu = ttk.Combobox(
            controls,
            textvariable=self.role_filter,
            values=["All", "Student", "Teacher", "Staff"],
            state="readonly",
            width=12,
        )
        role_menu.pack(side="left", padx=(0, 10))
        role_menu.bind("<<ComboboxSelected>>", lambda e: self.populate(self.controller.users, self.controller.attendance_records))

        self.result_lbl = ttk.Label(controls, text="0 present records", font=("Segoe UI", 9), foreground="#aaaaaa")
        self.result_lbl.pack(side="left", padx=(6, 0))

        ttk.Button(
            controls,
            text="Refresh",
            command=lambda: self.populate(self.controller.users, self.controller.attendance_records),
            bootstyle="secondary",
            width=10,
        ).pack(side="right")
        ttk.Button(
            controls,
            text="Export CSV",
            command=self.export_csv,
            bootstyle="success",
            width=12,
        ).pack(side="right", padx=(0, 6))

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        cols = ("User ID", "Name", "Role", "Check-In", "Check-Out", "Present Rule")
        self.tree = ttk.Treeview(container, columns=cols, show="headings", height=20)
        for c in cols:
            self.tree.heading(c, text=c)

        self.tree.column("User ID", width=90, anchor="center")
        self.tree.column("Name", width=220, anchor="w")
        self.tree.column("Role", width=110, anchor="center")
        self.tree.column("Check-In", width=120, anchor="center")
        self.tree.column("Check-Out", width=120, anchor="center")
        self.tree.column("Present Rule", width=220, anchor="w")

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
            present_rows.append((uid, name, role, check_in_time, check_out_time, present_rule))

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
                writer.writerow(["User ID", "Name", "Role", "Check-In", "Check-Out", "Present Rule"])
                for item in self.tree.get_children():
                    writer.writerow(self.tree.item(item)["values"])
            messagebox.showinfo("Export", "Present-today list exported successfully.")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))


class StatisticsFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="Panel.TFrame")
        self.controller = controller

        ttk.Label(self, text="Statistics", font=("Segoe UI", 22, "bold")).pack(anchor="w", pady=(0, 20))

        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=(0, 12))

        ttk.Label(controls, text="Period:").pack(side="left", padx=(0, 5))
        self.period_var = tk.StringVar(value="Today")
        period_menu = ttk.Combobox(
            controls,
            textvariable=self.period_var,
            values=["Today", "Last 7 Days", "This Month", "Custom"],
            state="readonly",
            width=12,
        )
        period_menu.pack(side="left", padx=(0, 10))
        period_menu.bind("<<ComboboxSelected>>", lambda e: self.populate(self.controller.users, self.controller.attendance_records))

        ttk.Label(controls, text="From:").pack(side="left", padx=(0, 5))
        self.from_var = tk.StringVar()
        from_entry = ttk.Entry(controls, textvariable=self.from_var, width=11)
        from_entry.pack(side="left", padx=(0, 8))
        from_entry.bind("<KeyRelease>", lambda e: self._on_custom_date_change())

        ttk.Label(controls, text="To:").pack(side="left", padx=(0, 5))
        self.to_var = tk.StringVar()
        to_entry = ttk.Entry(controls, textvariable=self.to_var, width=11)
        to_entry.pack(side="left", padx=(0, 10))
        to_entry.bind("<KeyRelease>", lambda e: self._on_custom_date_change())

        ttk.Label(controls, text="Role:").pack(side="left", padx=(0, 5))
        self.role_var = tk.StringVar(value="All")
        role_menu = ttk.Combobox(
            controls,
            textvariable=self.role_var,
            values=["All", "Student", "Teacher", "Staff"],
            state="readonly",
            width=10,
        )
        role_menu.pack(side="left", padx=(0, 10))
        role_menu.bind("<<ComboboxSelected>>", lambda e: self.populate(self.controller.users, self.controller.attendance_records))

        ttk.Button(
            controls,
            text="Apply",
            command=lambda: self.populate(self.controller.users, self.controller.attendance_records),
            bootstyle="primary",
            width=8,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            controls,
            text="Refresh",
            command=lambda: self.populate(self.controller.users, self.controller.attendance_records),
            bootstyle="secondary",
            width=9,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            controls,
            text="Export CSV",
            command=self.export_csv,
            bootstyle="success",
            width=12,
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            controls,
            text="Export PDF",
            command=self.export_pdf,
            bootstyle="info",
            width=12,
        ).pack(side="left")

        kpi_row = ttk.Frame(self)
        kpi_row.pack(fill="x", pady=(0, 10))
        self.kpi_total_users = self._kpi_card(kpi_row, "Users in Scope", 0, 0)
        self.kpi_unique_present = self._kpi_card(kpi_row, "Unique Present", 0, 1)
        self.kpi_unique_absent = self._kpi_card(kpi_row, "Unique Absent", 0, 2)
        self.kpi_att_rate = self._kpi_card(kpi_row, "Attendance Rate", "0%", 3)

        self.range_lbl = ttk.Label(self, text="Range: Today", font=("Segoe UI", 9), foreground="#aaaaaa")
        self.range_lbl.pack(anchor="w", pady=(0, 8))

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

    def _kpi_card(self, parent, title, value, col):
        frame = ttk.Frame(parent, padding=10, style="Panel.TFrame")
        frame.grid(row=0, column=col, padx=6, sticky="ew")
        ttk.Label(frame, text=title, font=("Segoe UI", 10), foreground="#aaaaaa").pack(anchor="w")
        lbl = ttk.Label(frame, text=str(value), font=("Segoe UI", 22, "bold"))
        lbl.pack(anchor="w")
        parent.columnconfigure(col, weight=1)
        return lbl

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

    def populate(self, users, records):
        self.tree.delete(*self.tree.get_children())

        d_from, d_to = self._resolve_date_range()
        if not d_from or not d_to:
            self.range_lbl.config(text="Range: invalid custom dates (use YYYY-MM-DD)")
            self.kpi_total_users.config(text="0")
            self.kpi_unique_present.config(text="0")
            self.kpi_unique_absent.config(text="0")
            self.kpi_att_rate.config(text="0%")
            return

        role_filter = self.role_var.get().lower()
        users_scope = [u for u in users if role_filter == "all" or str(getattr(u, "role", "")).strip().lower() == role_filter]
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

            messagebox.showinfo("Export", "Statistics exported successfully.")
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
            messagebox.showinfo("Export", "Statistics PDF exported successfully.")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))


class SettingsFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="Panel.TFrame")
        self.controller = controller

        ttk.Label(self, text="Settings", font=("Segoe UI", 22, "bold")).pack(anchor="w", pady=(0, 20))

        # Scrollable container
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, bg='#1a1a1a')
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
        self.gsm_output = scrolledtext.ScrolledText(gsm_tools, height=10, wrap="word")
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

    def save_all_settings(self):
        for key, entry in self.entries.items():
            val = entry.get()
            if key in ["ZK_PORT", "GSM_BAUD"]:
                try:
                    val = int(val)
                except:
                    pass
            self.controller.config_data[key] = val
        save_config(self.controller.config_data)
        messagebox.showinfo("Saved", "Settings saved. Please restart the application for changes to take full effect.")


if __name__ == "__main__":
    app = AttendanceApp()
    app.mainloop()