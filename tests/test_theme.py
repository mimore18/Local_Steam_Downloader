from __future__ import annotations

from steam_workshop_dl.ui.theme import (
    DEFAULT_THEME,
    PALETTES,
    normalize_theme,
    palette,
)


def test_normalize_theme() -> None:
    assert normalize_theme("dark") == "dark"
    assert normalize_theme(" Dark ") == "dark"
    assert normalize_theme("light") == "light"
    assert normalize_theme("system") is None
    assert normalize_theme("") is None
    assert normalize_theme(None) is None


def test_palette_fallback() -> None:
    assert palette("dark") == PALETTES["dark"]
    assert palette("unknown") == PALETTES[DEFAULT_THEME]
    assert palette(None) == PALETTES[DEFAULT_THEME]
