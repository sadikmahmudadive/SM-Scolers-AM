"""Diagnostic helper that interrogates the GSM modem before the app starts.

Usage: python gsm_diagnostic.py

It reads port/baud from the existing config.json (or defaults), lists available COM ports,
and then sends standard AT commands while reporting the responses. That makes it easier to
see whether the module is registered, has network/COPS/CSQ info, or is waiting for a PIN.
"""

import json
import os
import argparse
import time
from pathlib import Path

try:
    import serial
    from serial.tools import list_ports
except ImportError as exc:
    print("Please install pyserial (pip install pyserial) before running this script.")
    raise SystemExit(exc)

APP_NAME = "SM Scolers Attendance"
DATA_DIR_ENV = "SM_SCOLERS_DATA_DIR"


def get_user_data_dir() -> Path:
    env_override = os.environ.get(DATA_DIR_ENV)
    base_dir = env_override or os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(os.path.abspath(base_dir)) / APP_NAME


def load_config() -> dict:
    data_dir = get_user_data_dir()
    config_path = data_dir / "config.json"
    if config_path.exists():
        try:
            with config_path.open(encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {
        "GSM_PORT": "COM3",
        "GSM_BAUD": 9600,
    }


def report_serial_ports() -> None:
    print("Detected serial interfaces:")
    ports = list_ports.comports()
    if not ports:
        print("  (No COM ports detected)")
        return
    for port in ports:
        print(f"  {port.device}: {port.description} [{port.hwid}]")


class ModemProbe:
    def __init__(self, port: str, baud: int):
        self.port = port
        self.baud = baud
        self.ser = None

    def __enter__(self):
        print(f"Opening {self.port} @ {self.baud} baud...")
        self.ser = serial.Serial(self.port, self.baud, timeout=1)
        time.sleep(0.2)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def send(self, command: str, delay: float = 0.5) -> str:
        if not self.ser:
            return "(port not open)"
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        payload = (command + "\r").encode("utf-8")
        self.ser.write(payload)
        time.sleep(delay)
        data = self.ser.read_all().decode("utf-8", errors="replace")
        return data.strip()

    def check_command(self, command: str, label: str, expect: str = None) -> None:
        resp = self.send(command, delay=1.0)
        status = "OK" if resp and (expect is None or expect in resp) else "FAIL"
        print(f"{label:<25} -> {status}")
        print(resp or "  (no response)", end="\n---\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GSM modem diagnostic and command helper")
    parser.add_argument("--port", help="Override COM port from config, e.g. COM10")
    parser.add_argument("--baud", type=int, help="Override baud from config, e.g. 9600")
    parser.add_argument(
        "--send",
        action="append",
        dest="commands",
        help="AT command to send (can be repeated), e.g. --send AT+CREG=2 --send AT+CGATT=1",
    )
    parser.add_argument(
        "--register-sequence",
        action="store_true",
        help="Run registration helpers: AT+CREG=2, AT+CGATT=1, then query CREG/COPS/CGATT",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Open an interactive AT shell. Type commands and press Enter. Use 'exit' to quit.",
    )
    return parser.parse_args()


def run_interactive_shell(probe: ModemProbe) -> None:
    print("Interactive GSM shell started.")
    print("Type AT commands (example: AT+CREG?). Type 'exit' to quit.")
    print("---")
    while True:
        try:
            command = input("AT> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting interactive shell.")
            return

        if not command:
            continue
        if command.lower() in {"exit", "quit"}:
            print("Exiting interactive shell.")
            return

        response = probe.send(command, delay=1.0)
        print(response or "(no response)")
        print("---")


def main():
    args = parse_args()
    config = load_config()
    gsm_port = args.port or config.get("GSM_PORT", "COM3")
    gsm_baud = args.baud or config.get("GSM_BAUD", 9600)

    print("=== GSM Diagnostic ===")
    report_serial_ports()
    print()

    try:
        with ModemProbe(gsm_port, gsm_baud) as probe:
            if args.interactive:
                run_interactive_shell(probe)
                return

            if args.commands:
                for command in args.commands:
                    print(f"Sending: {command}")
                    print(probe.send(command, delay=1.0) or "(no response)")
                    print("---")
                return

            if args.register_sequence:
                sequence = [
                    ("AT+CREG=2", "Enable CREG URC"),
                    ("AT+CGATT=1", "Try packet attach"),
                    ("AT+CREG?", "Network registration"),
                    ("AT+COPS?", "Operator status"),
                    ("AT+CGATT?", "Packet attach status"),
                ]
                for command, label in sequence:
                    probe.check_command(command, label)
                return

            probe.check_command("AT", "Basic AT", "OK")
            probe.check_command("AT+CPIN?", "SIM PIN state")
            probe.check_command("AT+CSQ", "Signal strength")
            probe.check_command("AT+CREG?", "Network registration")
            probe.check_command("AT+COPS?", "Operator status")
            probe.check_command("AT+CGATT?", "Packet attach")
            probe.check_command("AT+CEER", "Last error (if any)")
            probe.check_command("AT+CLCC", "Call list (if supported)")
    except serial.SerialException as exc:
        print(f"Failed to open {gsm_port}: {exc}")
    except Exception as exc:
        print(f"Unexpected error: {exc}")


if __name__ == "__main__":
    main()
