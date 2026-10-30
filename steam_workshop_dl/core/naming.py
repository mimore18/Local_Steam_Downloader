"""Cross-platform file naming helpers.

The same rules must work on Linux and Windows: no reserved device names, no
trailing dots/spaces, no characters forbidden by NTFS, and a bounded length.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WHITESPACE = re.compile(r"\s+")

WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

MAX_FOLDER_NAME = 120


def human_size(size: int | None) -> str:
    if size is None:
        return "—"
    value = float(size)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if value < 1024 or unit == "ТБ":
            return f"{value:.1f} {unit}" if unit != "Б" else f"{int(value)} {unit}"
        value /= 1024
    return f"{value:.1f} ТБ"


def sanitize_title(title: str, item_id: str) -> str:
    """Return a safe folder name: ``<title> [<id>]``."""

    text = unicodedata.normalize("NFC", title or "")
    text = INVALID_CHARS.sub("_", text)
    text = WHITESPACE.sub(" ", text).strip(" .")
    if not text:
        text = f"item_{item_id}"

    suffix = f" [{item_id}]"
    limit = max(1, MAX_FOLDER_NAME - len(suffix))
    text = text[:limit].rstrip(" .") or f"item_{item_id}"

    if text.upper() in WINDOWS_RESERVED or Path(text).stem.upper() in WINDOWS_RESERVED:
        text = f"_{text}"

    return f"{text}{suffix}"


def ensure_within(base: Path, candidate: Path) -> Path:
    """Resolve *candidate* and ensure it stays inside *base*."""

    resolved_base = base.resolve()
    resolved = candidate.resolve()
    if resolved != resolved_base and resolved_base not in resolved.parents:
        raise ValueError(f"path escapes output directory: {candidate}")
    return resolved
