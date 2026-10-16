"""GSM modem adapter (SMS, USSD, inbox, raw AT commands).

Ported from legacy/app.py with AT-command timing and behaviour unchanged.
Differences: logging goes through the `logging` module instead of the UI
callback, configuration (port/baud) is held by `GsmGateway`, and the nested
`_read_cusd_response` helper (identical in both USSD functions) is hoisted.
"""

import logging
import re
import threading
import time

import serial

log = logging.getLogger("bridge.gsm")

# One lock for every serial operation: the modem tolerates a single client.
SERIAL_LOCK = threading.Lock()


def decode_hex_string(hex_str: str) -> str:
    try:
        clean_hex = hex_str.replace('"', "").strip()
        try:
            return bytes.fromhex(clean_hex).decode("utf-8")
        except Exception:
            return bytes.fromhex(clean_hex).decode("utf-16-be")
    except Exception:
        return hex_str


def parse_cusd_response(raw_resp: str) -> tuple[str, bool]:
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
        session_active = cusd_code == 1

        # DCS 72 = UCS2, or detect hex that looks like UCS2 (even length, >4 chars, all hex)
        if dcs == 72 or (
            re.match(r"^[0-9A-Fa-f]+$", payload) and len(payload) % 4 == 0 and len(payload) > 4
        ):
            decoded = decode_hex_string(payload)
            if decoded and decoded != payload:
                return (decoded, session_active)

        # GSM 7-bit hex (even length, all hex, not UCS2)
        if re.match(r"^[0-9A-Fa-f]+$", payload) and len(payload) % 2 == 0 and len(payload) > 4:
            decoded = decode_hex_string(payload)
            if decoded and decoded != payload:
                return (decoded, session_active)

        if payload:
            return (payload, session_active)

    # Fallback: extract whatever follows +CUSD:
    cusd_part = raw_resp.split("+CUSD:")[1].strip()
    # Try to detect cusd code from fallback
    code_match = re.match(r"(\d)", cusd_part)
    session_active = (int(code_match.group(1)) == 1) if code_match else False
    if "," in cusd_part:
        parts = cusd_part.split(",", 2)
        if len(parts) >= 2 and parts[1].strip().startswith('"'):
            payload = parts[1].strip().strip('"')
            if re.match(r"^[0-9A-Fa-f]+$", payload) and len(payload) % 2 == 0 and len(payload) > 4:
                decoded = decode_hex_string(payload)
                if decoded and decoded != payload:
                    return (decoded, session_active)
            if payload:
                return (payload, session_active)

    return (cusd_part.strip() or "No readable USSD response", session_active)


def _read_cusd_response(ser, timeout_sec: float = 20) -> str:
    """Read until +CUSD: response is complete or timeout."""
    start = time.time()
    buf = ""
    found_cusd = False
    while time.time() - start < timeout_sec:
        if ser.inWaiting():
            buf += ser.read(ser.inWaiting()).decode("utf-8", errors="ignore")
            if "+CUSD:" in buf:
                found_cusd = True
            # Complete when we see the closing quote + optional DCS + OK/newline after +CUSD:
            if found_cusd and (
                "\nOK" in buf
                or "\r\nOK" in buf
                or buf.rstrip().endswith('"')
                or re.search(r'\+CUSD:\s*\d,".*?",\s*\d+', buf, re.DOTALL)
            ):
                # Drain any trailing bytes
                time.sleep(0.5)
                if ser.inWaiting():
                    buf += ser.read(ser.inWaiting()).decode("utf-8", errors="ignore")
                break
        time.sleep(0.3)
    return buf


class GsmGateway:
    """SIM800L-style modem on a serial port. Implements `SmsGateway`."""

    def __init__(
        self,
        port: str,
        baud: int,
        *,
        send_lock_timeout: float = 5,
        signal_lock_timeout: float = 2,
        command_lock_timeout: float = 3,
    ) -> None:
        self.port = port
        self.baud = baud
        self._send_lock_timeout = send_lock_timeout
        self._signal_lock_timeout = signal_lock_timeout
        self._command_lock_timeout = command_lock_timeout

    # -- SMS ---------------------------------------------------------------

    def send(self, phone: str, body: str) -> bool:
        """Send one SMS. Returns False on ANY failure; never raises."""
        try:
            if not SERIAL_LOCK.acquire(timeout=self._send_lock_timeout):
                log.error("[GSM ERROR] Port busy, could not send SMS to %s", phone)
                return False
        except Exception as e:  # pragma: no cover - defensive
            log.error("[GSM ERROR] %s", e)
            return False

        try:
            ser = serial.Serial(self.port, self.baud, timeout=2)
            time.sleep(1)
            ser.write(b"AT\r")
            time.sleep(0.5)
            ser.write(b"AT+CMGF=1\r")
            time.sleep(0.5)
            ser.write(f'AT+CMGS="{phone}"\r'.encode())
            time.sleep(0.5)
            ser.write(body.encode() + b"\x1A")
            time.sleep(3)
            # Read delivery response
            resp = ""
            if ser.inWaiting():
                resp = ser.read(ser.inWaiting()).decode("utf-8", errors="ignore")
            ser.close()
            # +CMGS: <mr> confirms the modem accepted the message
            if "+CMGS:" in resp:
                log.info("[GSM] SMS sent to %s (confirmed)", phone)
            else:
                log.info("[GSM] SMS sent to %s (no +CMGS confirmation)", phone)
            return True
        except Exception as e:
            log.error("[GSM ERROR] %s", e)
            return False
        finally:
            SERIAL_LOCK.release()

    # -- Signal ------------------------------------------------------------

    def signal_info(self) -> tuple[str, int]:
        """Returns (carrier, signal percent)."""
        carrier = "Searching..."
        signal = 0

        if not SERIAL_LOCK.acquire(timeout=self._signal_lock_timeout):
            return ("Busy", 0)

        try:
            ser = serial.Serial(self.port, self.baud, timeout=1)
            time.sleep(0.5)

            def run_cmd(cmd, delay=0.25):
                ser.reset_input_buffer()
                ser.write((cmd + "\r").encode())
                time.sleep(delay)
                return ser.read(ser.inWaiting()).decode("utf-8", errors="ignore")

            resp_cpin = run_cmd("AT+CPIN?", delay=0.35)
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

            resp_csq = run_cmd("AT+CSQ", delay=0.25)
            match_csq = re.search(r"\+CSQ:\s*(\d+),", resp_csq)
            if match_csq:
                rssi = int(match_csq.group(1))
                signal = 0 if rssi == 99 else int((rssi / 31) * 100)

            resp_cops = run_cmd("AT+COPS?", delay=0.3)
            match_cops = re.search(r"\"(.*?)\"", resp_cops)
            if match_cops:
                carrier = match_cops.group(1)

            if signal == 0 and not match_cops:
                resp_creg = run_cmd("AT+CREG?", delay=0.25)
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

    # -- USSD --------------------------------------------------------------

    def run_ussd_session(self, code: str) -> tuple[str, bool]:
        """Send a USSD command. Returns (text, session_active)."""
        if not SERIAL_LOCK.acquire(timeout=self._command_lock_timeout):
            return ("System Busy. Try again.", False)

        result = ("No Response", False)
        try:
            ser = serial.Serial(self.port, self.baud, timeout=3)
            time.sleep(1)
            ser.write(b"AT+CMGF=1\r")
            time.sleep(0.2)
            ser.write(b'AT+CSCS="GSM"\r')
            time.sleep(0.2)
            # Cancel any pending USSD session
            ser.write(b"AT+CUSD=2\r")
            time.sleep(0.3)
            ser.reset_input_buffer()

            # First attempt: let modem choose encoding
            ser.write(f'AT+CUSD=1,"{code}"\r'.encode())
            raw_resp = _read_cusd_response(ser)

            # If no response, retry with explicit GSM encoding (DCS=15)
            if "+CUSD:" not in raw_resp:
                ser.write(b"AT+CUSD=2\r")
                time.sleep(0.3)
                ser.reset_input_buffer()

                ser.write(f'AT+CUSD=1,"{code}",15\r'.encode())
                raw_resp = _read_cusd_response(ser)

            result = parse_cusd_response(raw_resp)
            ser.close()
        except Exception as e:
            result = (f"Error: {str(e)}", False)
        finally:
            SERIAL_LOCK.release()
        return result

    def run_ussd(self, code: str) -> str:
        return self.run_ussd_session(code)[0]

    def ussd_reply_session(self, text: str) -> tuple[str, bool]:
        """Reply to an ongoing USSD session. Returns (text, session_active)."""
        if not SERIAL_LOCK.acquire(timeout=self._command_lock_timeout):
            return ("System Busy. Try again.", False)

        result = ("No Response", False)
        try:
            # Open serial without toggling DTR to preserve the active USSD session
            ser = serial.Serial()
            ser.port = self.port
            ser.baudrate = self.baud
            ser.timeout = 3
            ser.dsrdtr = True
            ser.dtr = False
            ser.open()
            time.sleep(0.3)
            # Ensure GSM charset and text mode for predictable replies
            try:
                ser.write(b"AT+CMGF=1\r")
                time.sleep(0.15)
                ser.write(b'AT+CSCS="GSM"\r')
                time.sleep(0.15)
            except Exception:
                pass

            ser.reset_input_buffer()
            # Escape double-quotes in reply to avoid breaking AT command
            safe_reply = text.replace('"', "'")
            # Send with explicit GSM DCS (15) to improve compatibility
            ser.write(f'AT+CUSD=1,"{safe_reply}",15\r'.encode())
            raw_resp = _read_cusd_response(ser)
            result = parse_cusd_response(raw_resp)
            ser.close()
        except Exception as e:
            result = (f"Error: {str(e)}", False)
        finally:
            SERIAL_LOCK.release()
        return result

    def ussd_reply(self, text: str) -> str:
        return self.ussd_reply_session(text)[0]

    def cancel_ussd(self) -> None:
        """Cancel any ongoing USSD session."""
        if not SERIAL_LOCK.acquire(timeout=self._command_lock_timeout):
            return
        try:
            ser = serial.Serial(self.port, self.baud, timeout=2)
            time.sleep(0.3)
            ser.write(b"AT+CUSD=2\r")
            time.sleep(0.5)
            ser.close()
        except Exception:
            pass
        finally:
            SERIAL_LOCK.release()

    # -- Inbox -------------------------------------------------------------

    def read_inbox(self, max_messages: int = 20) -> list[dict]:
        """Read SIM inbox. Each item: {index, sender, timestamp, body}."""
        if not SERIAL_LOCK.acquire(timeout=self._send_lock_timeout):
            return []

        messages: list[dict] = []
        try:
            ser = serial.Serial(self.port, self.baud, timeout=3)
            time.sleep(0.5)
            ser.write(b"AT+CMGF=1\r")
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
                    buf += ser.read(ser.inWaiting()).decode("utf-8", errors="ignore")
                    if "\nOK" in buf or "\r\nOK" in buf:
                        break
                time.sleep(0.3)

            # Parse: +CMGL: <index>,<stat>,<oa>,<alpha>,<scts>\r\n<body>\r\n
            parts = re.split(r"\+CMGL:\s*", buf)
            for part in parts[1:]:
                lines = part.strip().split("\n", 1)
                if len(lines) < 2:
                    continue
                header = lines[0].strip()
                body = lines[1].strip().split("\nOK")[0].split("\n+CMGL")[0].strip()

                # Parse header: index,"status","sender","","timestamp"
                hdr_match = re.match(r'(\d+),"[^"]*","([^"]*)",[^,]*,"([^"]*)"', header)
                if hdr_match and body:
                    messages.append(
                        {
                            "index": int(hdr_match.group(1)),
                            "sender": hdr_match.group(2),
                            "timestamp": hdr_match.group(3),
                            "body": body,
                        }
                    )

                if len(messages) >= max_messages:
                    break

            ser.close()
        except Exception:
            pass
        finally:
            SERIAL_LOCK.release()

        return messages

    def delete_sms(self, index: int) -> bool:
        """Delete a single SMS by index. True when the modem answered OK."""
        resp = self.run_at(f"AT+CMGD={index}", read_seconds=2.0)
        return "OK" in resp and "ERROR" not in resp.upper()

    # -- Raw AT ------------------------------------------------------------

    def run_at(self, command: str, read_seconds: float = 1.0) -> str:
        if not command:
            return ""

        if not SERIAL_LOCK.acquire(timeout=self._command_lock_timeout):
            return "System Busy. Try again."

        response = ""
        try:
            ser = serial.Serial(self.port, self.baud, timeout=2)
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
