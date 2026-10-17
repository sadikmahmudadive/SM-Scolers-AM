"""Bridge heartbeat: tell the website the service, modem and device are alive."""

import logging
from collections.abc import Callable
from datetime import datetime

from bridge.store import ServiceStore

log = logging.getLogger(__name__)


def beat(
    store: ServiceStore,
    gateway,
    version: str,
    device_online: bool,
    now: datetime | Callable[[], datetime],
) -> None:
    """Write `bridgeStatus/main`. A modem that cannot report signal is
    recorded as ("", 0) rather than failing the heartbeat.

    `now` may be a clock: it is then read right before the write (after the
    modem query), so a long iteration cannot make a healthy bridge look stale."""
    try:
        carrier, signal = gateway.signal_info()
    except Exception as exc:
        log.warning("signal_info failed: %s", exc)
        carrier, signal = "", 0
    stamp = now() if callable(now) else now
    store.write_heartbeat(version, carrier, signal, device_online, stamp)
