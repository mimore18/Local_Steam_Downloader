from pathlib import Path

import pytest

from steam_workshop_dl.core.naming import (
    MAX_FOLDER_NAME,
    ensure_within,
    human_size,
    sanitize_title,
)


def test_sanitize_replaces_windows_forbidden_chars() -> None:
    name = sanitize_title('Bad: name? with* chars <>|/"\\', "123")
    assert name.startswith("Bad_ name_ with_ chars")
    assert name.endswith(" [123]")
    assert not any(char in name for char in '<>:"/\\|?*')


def test_sanitize_strips_trailing_dot_and_space() -> None:
    assert sanitize_title("  name. .  ", "1") == "name [1]"


def test_sanitize_reserved_name() -> None:
    assert sanitize_title("CON", "1") == "_CON [1]"
    assert sanitize_title("com1.txt", "1") == "_com1.txt [1]"


def test_sanitize_empty_and_long() -> None:
    assert sanitize_title("", "42") == "item_42 [42]"
    long_name = sanitize_title("x" * 500, "7")
    assert len(long_name) <= MAX_FOLDER_NAME
    assert long_name.endswith(" [7]")


def test_human_size() -> None:
    assert human_size(None) == "—"
    assert human_size(0) == "0 Б"
    assert human_size(1024) == "1.0 КБ"
    assert human_size(1024 * 1024) == "1.0 МБ"


def test_ensure_within_rejects_escape(tmp_path: Path) -> None:
    inside = ensure_within(tmp_path, tmp_path / "mod")
    assert inside == (tmp_path / "mod").resolve()
    with pytest.raises(ValueError):
        ensure_within(tmp_path, tmp_path.parent / "outside")
