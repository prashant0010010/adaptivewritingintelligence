"""Logging that never records API keys and is not used for user text."""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_KEY_PATTERN = re.compile(r"(AIza[0-9A-Za-z_\-]{20,}|sk-[0-9A-Za-z_\-]{20,}|key=[^&\s]+)")


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _KEY_PATTERN.sub("[REDACTED]", str(record.getMessage()))
        record.args = ()
        return True


def setup_logging(log_dir: Path | None = None) -> logging.Logger:
    logger = logging.getLogger("awi")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            handlers.append(RotatingFileHandler(log_dir / "app.log", maxBytes=500_000, backupCount=2, encoding="utf-8"))
        except OSError:
            pass
    for h in handlers:
        h.setFormatter(fmt)
        h.addFilter(RedactFilter())
        logger.addHandler(h)
    return logger
