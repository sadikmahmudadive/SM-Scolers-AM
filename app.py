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
import re
from datetime import datetime, date, time as dt_time
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

import os
import sys
# Source - https://stackoverflow.com/a/31966932
# Posted by Nautilius, modified by community. See post 'Timeline' for change history
# Retrieved 2026-02-12, License - CC BY-SA 3.0

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if os.path.isabs(relative_path):
        return relative_path

    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

Logo = resource_path("Logo.png")


# ---------------------------
# GLOBAL LOCKS
# ---------------------------
SERIAL_LOCK = threading.Lock()

# ---------------------------
# CONFIGURATION
# ---------------------------
CONFIG_FILE = "config.json"
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
    "FIREBASE_CRED_PATH": "serviceAccountKey.json",
    "FIREBASE_DB_URL": "https://YOUR-PROJECT-ID-default-rtdb.firebaseio.com/",
    "POLL_INTERVAL_SEC": 10,
    "USER_PHONE_MAP": {},
    "CLASS_SCHEDULES": {}   # e.g. {"Nursery": {"start": "07:40", "end": "08:10"}, "1": {...}}
}

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            # Ensure all keys exist (for new fields)
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
    except FileNotFoundError:
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
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
        
        ser.write(b'AT+CSQ\r')
        time.sleep(0.2)
        resp_csq = ser.read(ser.inWaiting()).decode('utf-8', errors='ignore')
        match_csq = re.search(r"\+CSQ:\s*(\d+),", resp_csq)
        if match_csq:
            rssi = int(match_csq.group(1))
            signal = 0 if rssi == 99 else int((rssi / 31) * 100)

        ser.write(b'AT+COPS?\r')
        time.sleep(0.2)
        resp_cops = ser.read(ser.inWaiting()).decode('utf-8', errors='ignore')
        match_cops = re.search(r'\"(.*?)\"', resp_cops)
        if match_cops:
            carrier = match_cops.group(1)
        
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
            cred_path = resource_path(
                config.get("FIREBASE_CRED_PATH", DEFAULT_CONFIG["FIREBASE_CRED_PATH"])
            )
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
        
        for f in (DashboardFrame, MonitorFrame, UsersFrame, LogsFrame, SettingsFrame):
            page_name = f.__name__
            frame = f(parent=self.main_container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")
            
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.switch_tab()

    def switch_tab(self):
        mode = self.nav_var.get()
        mapping = {"dashboard": "DashboardFrame", "monitor": "MonitorFrame", "users": "UsersFrame", "logs": "LogsFrame", "settings": "SettingsFrame"}
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
                cred_path = resource_path(
                    self.config_data.get("FIREBASE_CRED_PATH", DEFAULT_CONFIG["FIREBASE_CRED_PATH"])
                )
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
        self.frames["DashboardFrame"].update_metrics(len(self.users), self.attendance_records)
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
        
        self.card_users = self.create_stat_card(card_container, "Total Users", "0", 0)
        self.card_present = self.create_stat_card(card_container, "Present Today", "0", 1)
        self.card_sms = self.create_stat_card(card_container, "SMS Sent", "0", 2)

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

    def create_stat_card(self, parent, title, value, col):
        frame = ttk.Frame(parent, padding=12, relief='flat', style='Panel.TFrame')
        frame.grid(row=0, column=col, padx=8, sticky="ew")
        ttk.Label(frame, text=title, font=("Segoe UI", 10), foreground='#aaaaaa').pack(anchor="w")
        val_lbl = ttk.Label(frame, text=value, font=("Segoe UI", 28, "bold"))
        val_lbl.pack(anchor="w")
        parent.columnconfigure(col, weight=1)
        return val_lbl

    def update_counters(self, stats):
        self.card_sms.config(text=str(stats["sms"]))

    def update_metrics(self, user_count, records):
        self.card_users.config(text=str(user_count))
        today_str = date.today().strftime("%Y-%m-%d")
        todays_recs = [r for r in records if r.timestamp.startswith(today_str)]
        unique_present = len(set(r.user_id for r in todays_recs))
        self.card_present.config(text=str(unique_present))
        
        self.recent_list.delete(*self.recent_list.get_children())
        for r in sorted(todays_recs, key=lambda x: x.timestamp, reverse=True)[:15]:
            t = r.timestamp.split(" ")[1] if " " in r.timestamp else r.timestamp
            user_info = f"{r.user_name} ({r.user_id})"
            self.recent_list.insert("", "end", values=(t, user_info, "In"))

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
        
        ttk.Label(controls, text="Role:").pack(side="left", padx=(0, 5))
        self.role_filter = tk.StringVar(value="All")
        role_menu = ttk.Combobox(controls, textvariable=self.role_filter,
                                 values=["All", "Student", "Teacher", "Staff"],
                                 state="readonly", width=12)
        role_menu.pack(side="left", padx=(0, 15))
        role_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        ttk.Button(controls, text="Export CSV", command=self.export_csv,
                   bootstyle="success", width=12).pack(side="right", padx=2)
        ttk.Button(controls, text="Refresh", command=self.apply_filter,
                   bootstyle="secondary", width=8).pack(side="right", padx=2)
        
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
        
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        
        for l in logs:
            if target_role != "All" and getattr(l, 'role', 'Student') != target_role:
                continue
            r_role = getattr(l, 'role', 'Student')
            self.tree.insert("", "end", values=(l.timestamp, l.user_id, l.user_name, r_role, l.status))

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

        # --- Class Schedules (fully preserved) ---
        sched_frame = ttk.Labelframe(scrollable_frame, text="Class Schedules", padding=10)
        sched_frame.pack(fill="x", pady=5, padx=5)

        ttk.Label(sched_frame, text="Expected in-time windows per class",
                  font=("Segoe UI", 9, "italic"), foreground='#aaaaaa').pack(anchor="w", pady=(0, 5))

        # Treeview for schedules
        tree_frame = ttk.Frame(sched_frame)
        tree_frame.pack(fill="x", pady=5)

        cols = ("Class", "Start", "End")
        self.schedule_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=6)
        self.schedule_tree.heading("Class", text="Class")
        self.schedule_tree.heading("Start", text="Start")
        self.schedule_tree.heading("End", text="End")
        self.schedule_tree.column("Class", width=100, anchor="center")
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
            self.schedule_tree.insert("", "end", values=(class_name, start, end))

        # Input frame
        input_frame = ttk.Frame(sched_frame)
        input_frame.pack(fill="x", pady=(10, 5))

        ttk.Label(input_frame, text="Class:").grid(row=0, column=0, padx=2, pady=2, sticky="w")
        class_values = ["Nursery", "Play", "KG", "1", "2", "3", "4", "5",
                        "6", "7", "8", "9", "10"]
        self.e_class = ttk.Combobox(input_frame, values=class_values, state="readonly", width=10)
        self.e_class.grid(row=0, column=1, padx=2, pady=2, sticky="w")
        self.e_class.set("")

        ttk.Label(input_frame, text="Start:").grid(row=0, column=2, padx=2, pady=2, sticky="w")
        start_times = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]
        self.e_start = ttk.Combobox(input_frame, values=start_times, state="readonly", width=7)
        self.e_start.grid(row=0, column=3, padx=2, pady=2, sticky="w")
        self.e_start.set("")

        ttk.Label(input_frame, text="End:").grid(row=0, column=4, padx=2, pady=2, sticky="w")
        self.e_end = ttk.Combobox(input_frame, values=start_times, state="readonly", width=7)
        self.e_end.grid(row=0, column=5, padx=2, pady=2, sticky="w")
        self.e_end.set("")

        input_frame.columnconfigure(1, weight=1)
        input_frame.columnconfigure(3, weight=1)
        input_frame.columnconfigure(5, weight=1)

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
    def _add_schedule(self):
        class_val = self.e_class.get().strip()
        start_val = self.e_start.get().strip()
        end_val = self.e_end.get().strip()
        if not class_val or not start_val or not end_val:
            messagebox.showwarning("Incomplete", "Please select class, start and end time.")
            return

        existing = False
        for child in self.schedule_tree.get_children():
            if self.schedule_tree.item(child)['values'][0] == class_val:
                self.schedule_tree.item(child, values=(class_val, start_val, end_val))
                existing = True
                break
        if not existing:
            self.schedule_tree.insert("", "end", values=(class_val, start_val, end_val))

        self.e_class.set("")
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
            start = str(vals[1])
            end = str(vals[2])
            new_schedules[class_name] = {"start": start, "end": end}
        self.controller.config_data["CLASS_SCHEDULES"] = new_schedules
        save_config(self.controller.config_data)
        messagebox.showinfo("Saved", "Class schedules updated successfully.")
        self.controller.log_message("[SCHEDULES] Class schedules updated.")

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