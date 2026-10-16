"""Website-issued commands (`commands` collection): execute and record them."""

import logging
from collections.abc import Callable
from datetime import datetime

from bridge.gsm import GsmGateway
from bridge.models import TS_FORMAT, SmsLogEntry
from bridge.store import ServiceStore
from bridge.zk_device import ZkDevice

log = logging.getLogger(__name__)

DEFAULT_INBOX_MAX = 20
MAX_INBOX_MAX = 50
DEFAULT_AT_READ_SECONDS = 1.0
MAX_AT_READ_SECONDS = 30.0


def _require(payload: dict, key: str, command_type: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{command_type}: '{key}' is required")
    return value


def _test_sms(payload: dict, gateway: GsmGateway, store: ServiceStore, now: datetime) -> dict:
    phone = _require(payload, "phone", "test_sms")
    message = _require(payload, "message", "test_sms")
    try:
        sent = bool(gateway.send(phone, message))
    except Exception as exc:
        log.warning("test_sms to %s raised: %s", phone, exc)
        sent = False
    store.log_sms(
        SmsLogEntry(
            person_id="",
            phone=phone,
            body=message,
            kind="test",
            status="sent" if sent else "failed",
            punch_id=None,
            ts=now.strftime(TS_FORMAT),
        )
    )
    return {"sent": sent}


def _ussd(payload: dict, gateway: GsmGateway) -> dict:
    reply = payload.get("reply")
    if isinstance(reply, str) and reply:
        text, active = gateway.ussd_reply_session(reply)
    else:
        text, active = gateway.run_ussd_session(_require(payload, "code", "ussd"))
    return {"text": text, "sessionActive": active}


def execute_command(
    cmd: dict,
    gateway: GsmGateway,
    zk_factory: Callable[[], ZkDevice],
    store: ServiceStore,
    now: datetime,
) -> dict:
    """Run one command and return its result. Raises on failure; an unknown
    type raises ValueError (the caller records status "error")."""
    command_type = cmd.get("type")
    payload = cmd.get("payload") or {}

    if command_type == "test_sms":
        return _test_sms(payload, gateway, store, now)
    if command_type == "ussd":
        return _ussd(payload, gateway)
    if command_type == "read_inbox":
        limit = min(max(int(payload.get("max") or DEFAULT_INBOX_MAX), 1), MAX_INBOX_MAX)
        return {"messages": gateway.read_inbox(limit)}
    if command_type == "at_command":
        command = _require(payload, "command", "at_command")
        seconds = float(payload.get("readSeconds") or DEFAULT_AT_READ_SECONDS)
        seconds = min(max(seconds, 0.0), MAX_AT_READ_SECONDS)
        return {"output": gateway.run_at(command, seconds)}
    if command_type == "sync_device_users":
        users = zk_factory().get_users()
        return {"created": store.upsert_device_users(users), "total": len(users)}
    raise ValueError(f"Unknown command type: {command_type!r}")


def process_commands(
    store: ServiceStore,
    gateway: GsmGateway,
    zk_factory: Callable[[], ZkDevice],
    now: datetime,
) -> int:
    """Run pending commands one at a time: claim, execute, record done/error.

    Each command is claimed only when its turn comes and runs inside its own
    try, so a failure (or a lost claim race) never strands or skips the others.
    Returns how many commands this process executed.
    """
    processed = 0
    for command_id in store.pending_command_ids():
        try:
            cmd = store.claim_command(command_id)
        except Exception:
            log.exception("could not claim command %s", command_id)
            continue
        if cmd is None:  # no longer pending, or another bridge won it
            continue
        processed += 1
        try:
            status, result = "done", execute_command(cmd, gateway, zk_factory, store, now)
        except Exception as exc:
            log.warning("command %s (%s) failed: %s", command_id, cmd.get("type"), exc)
            status, result = "error", {"error": str(exc)}
        try:
            store.finish_command(command_id, status, result)
        except Exception:
            log.exception("could not record result of command %s", command_id)
    return processed
