"""Paths to bundled runtime assets (icons)."""

from __future__ import annotations

import sys
from pathlib import Path

_PACKAGE_ASSETS = Path(__file__).resolve().parent / "assets"


def asset_path(name: str) -> Path:
    """Resolve *name* from the package assets, also when built by PyInstaller."""

    candidates: list[Path] = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(
            Path(bundle_root) / "steam_workshop_dl" / "assets" / name
        )
    candidates.append(_PACKAGE_ASSETS / name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[-1]
