"""ZKTeco terminal adapter (pyzk). Implements `ZkSource`."""

import logging
from contextlib import contextmanager

from zk import ZK

from bridge.models import DeviceUser, RawPunch

log = logging.getLogger(__name__)


class ZkDevice:
    def __init__(self, ip: str, port: int, timeout: int) -> None:
        self.ip = ip
        self.port = port
        self.timeout = timeout
        # The terminal's own clock (naive local), read with the last attendance
        # read; None if it could not be read. Informational only (skew warning).
        self.device_time = None

    @contextmanager
    def _session(self):
        """Connect and quiet the terminal; ALWAYS re-enable and disconnect."""
        conn = ZK(self.ip, port=self.port, timeout=self.timeout).connect()
        try:
            conn.disable_device()
            yield conn
        finally:
            try:
                conn.enable_device()
            except Exception as exc:
                log.warning("enable_device failed on %s: %s", self.ip, exc)
            try:
                conn.disconnect()
            except Exception as exc:
                log.warning("disconnect failed on %s: %s", self.ip, exc)

    def get_attendance(self) -> list[RawPunch]:
        with self._session() as conn:
            records = conn.get_attendance()
            try:
                self.device_time = conn.get_time()
            except Exception as exc:  # never let the clock read break the punch read
                self.device_time = None
                log.debug("get_time failed on %s: %s", self.ip, exc)
        return [
            RawPunch(
                user_id=str(r.user_id),
                timestamp=str(r.timestamp),
                status=str(r.status),
            )
            for r in records
        ]

    def get_users(self) -> list[DeviceUser]:
        with self._session() as conn:
            users = conn.get_users()
        return [DeviceUser(user_id=str(u.user_id), name=str(u.name)) for u in users]
