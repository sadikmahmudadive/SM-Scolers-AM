"""Logging for the headless service: rotating file next to the config + console."""

import logging
import logging.handlers
from pathlib import Path

LOG_FILE_NAME = "bridge.log"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 5
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(config_path: str | Path, level: int = logging.INFO) -> Path:
    """Log to `<config dir>/bridge.log` (1 MB x 5 files) and to the console."""
    log_path = Path(config_path).resolve().parent / LOG_FILE_NAME
    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(LOG_FORMAT)
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    console = logging.StreamHandler()
    root = logging.getLogger()
    root.setLevel(level)
    for handler in (file_handler, console):
        handler.setFormatter(formatter)
        root.addHandler(handler)
    return log_path
