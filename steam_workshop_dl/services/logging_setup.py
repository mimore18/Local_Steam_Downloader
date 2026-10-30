"""Logging with secret masking and cross-platform file locations."""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import default_log_path

SECRET_RE = re.compile(
    r"(?i)\b(password|passwd|steam guard code|two-factor code)\b\s*[:=]?\s*\S*"
)


def mask_secrets(text: str) -> str:
    return SECRET_RE.sub(lambda match: f"{match.group(1)}: ***", text)


class SecretFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        masked = mask_secrets(message)
        if masked != message:
            record.msg = masked
            record.args = ()
        return True


def setup_logging(*, verbose: bool = False, log_file: Path | None = None) -> Path:
    """Configure console and rotating file handlers.  Returns the log path."""

    path = (log_file or default_log_path()).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S"))
    console.addFilter(SecretFilter())
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        path, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    file_handler.addFilter(SecretFilter())
    root.addHandler(file_handler)

    return path
