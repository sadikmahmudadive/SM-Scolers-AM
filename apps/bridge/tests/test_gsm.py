"""GSM adapter tests: no hardware, serial.Serial is replaced by a fake."""

import time

import pytest
import serial

from bridge import gsm
from bridge.gsm import GsmGateway, decode_hex_string, parse_cusd_response


class FakeSerial:
    """Records writes; answers AT commands from a prefix -> response map."""

    instances: list["FakeSerial"] = []
    responses: dict[str, str] = {}

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.writes: list[bytes] = []
        self.buf = b""
        self.closed = False
        FakeSerial.instances.append(self)

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        if data.endswith(b"\x1a"):
            self.buf += FakeSerial.responses.get("BODY", "").encode()
        else:
            text = data.decode(errors="ignore").strip()
            for prefix, resp in FakeSerial.responses.items():
                if prefix != "BODY" and text.startswith(prefix):
                    self.buf += resp.encode()
        return len(data)

    def inWaiting(self) -> int:  # noqa: N802 - pyserial legacy name
        return len(self.buf)

    def read(self, n: int = 1) -> bytes:
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def reset_input_buffer(self) -> None:
        self.buf = b""

    def reset_output_buffer(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def fake_serial(monkeypatch):
    FakeSerial.instances = []
    FakeSerial.responses = {}
    monkeypatch.setattr(serial, "Serial", FakeSerial)
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    return FakeSerial


def test_send_writes_at_sequence_and_returns_true_on_cmgs(fake_serial):
    fake_serial.responses = {"BODY": "\r\n+CMGS: 7\r\n\r\nOK\r\n"}
    ok = GsmGateway("COM9", 9600).send("01711000000", "hello")
    assert ok is True
    writes = fake_serial.instances[0].writes
    assert writes == [
        b"AT\r",
        b"AT+CMGF=1\r",
        b'AT+CMGS="01711000000"\r',
        b"hello\x1a",
    ]
    assert fake_serial.instances[0].closed
    assert fake_serial.instances[0].args == ("COM9", 9600)


def test_send_returns_false_when_serial_raises(monkeypatch):
    def boom(*_a, **_k):
        raise serial.SerialException("port gone")

    monkeypatch.setattr(serial, "Serial", boom)
    assert GsmGateway("COM9", 9600).send("017", "x") is False


def test_send_returns_false_when_lock_busy(fake_serial):
    gw = GsmGateway("COM9", 9600, send_lock_timeout=0.05)
    assert gsm.SERIAL_LOCK.acquire(timeout=1)
    try:
        assert gw.send("017", "x") is False
    finally:
        gsm.SERIAL_LOCK.release()
    assert fake_serial.instances == []  # never touched the port


def test_send_releases_lock_after_failure(monkeypatch):
    monkeypatch.setattr(serial, "Serial", lambda *a, **k: (_ for _ in ()).throw(OSError("x")))
    GsmGateway("COM9", 9600).send("017", "x")
    assert gsm.SERIAL_LOCK.acquire(timeout=0.1)
    gsm.SERIAL_LOCK.release()


def test_signal_info_parses_csq_and_cops(fake_serial):
    fake_serial.responses = {
        "AT+CPIN?": "\r\n+CPIN: READY\r\n\r\nOK\r\n",
        "AT+CSQ": "\r\n+CSQ: 20,0\r\n\r\nOK\r\n",
        "AT+COPS?": '\r\n+COPS: 0,0,"Grameenphone"\r\n\r\nOK\r\n',
    }
    assert GsmGateway("COM9", 9600).signal_info() == ("Grameenphone", 64)


def test_signal_info_sim_not_detected(fake_serial):
    fake_serial.responses = {"AT+CPIN?": "\r\n+CME ERROR: SIM not inserted\r\n"}
    assert GsmGateway("COM9", 9600).signal_info() == ("SIM NOT DETECTED", 0)


def test_signal_info_no_connection_on_serial_error(monkeypatch):
    def boom(*_a, **_k):
        raise serial.SerialException("nope")

    monkeypatch.setattr(serial, "Serial", boom)
    assert GsmGateway("COM9", 9600).signal_info() == ("No Connection", 0)


def test_signal_info_busy_when_lock_held(fake_serial):
    gw = GsmGateway("COM9", 9600, signal_lock_timeout=0.05)
    assert gsm.SERIAL_LOCK.acquire(timeout=1)
    try:
        assert gw.signal_info() == ("Busy", 0)
    finally:
        gsm.SERIAL_LOCK.release()


def test_run_at_returns_response(fake_serial):
    fake_serial.responses = {"ATI": "\r\nSIM800 R14\r\nOK\r\n"}
    out = GsmGateway("COM9", 9600).run_at("ATI", 0.2)
    assert "SIM800" in out


def test_read_inbox_parses_messages(fake_serial):
    fake_serial.responses = {
        "AT+CMGL": '+CMGL: 1,"REC READ","+8801711000000",,"26/10/16,08:00:00+24"\r\nHi there\r\n'
        '+CMGL: 2,"REC READ","BANK",,"26/10/16,09:00:00+24"\r\nSecond\r\n\r\nOK\r\n'
    }
    msgs = GsmGateway("COM9", 9600).read_inbox(10)
    assert msgs == [
        {"index": 1, "sender": "+8801711000000", "timestamp": "26/10/16,08:00:00+24", "body": "Hi there"},
        {"index": 2, "sender": "BANK", "timestamp": "26/10/16,09:00:00+24", "body": "Second"},
    ]


def test_decode_hex_string_utf8_and_ucs2_and_passthrough():
    assert decode_hex_string("48656C6C6F") == "Hello"
    assert decode_hex_string('"48656C6C6F"') == "Hello"
    assert decode_hex_string("not hex") == "not hex"


def test_decode_hex_string_falls_back_to_utf16():
    # 0x0985 (Bengali A) is invalid utf-8 as bytes 09 85 -> utf-16-be fallback
    assert decode_hex_string("0985") == "\u0985"


def test_parse_cusd_standard_plain_text():
    text, active = parse_cusd_response('\r\n+CUSD: 1,"Balance 50 Tk",15\r\n')
    assert (text, active) == ("Balance 50 Tk", True)


def test_parse_cusd_ucs2_hex_payload():
    payload = "".join(f"{ord(c):04X}" for c in "অব")
    text, active = parse_cusd_response(f'+CUSD: 0,"{payload}",72')
    assert (text, active) == ("অব", False)


def test_parse_cusd_no_cusd_marker():
    assert parse_cusd_response("OK") == ("Timeout/No USSD Reply", False)
