from pathlib import Path

import pytest

from steam_workshop_dl.services.config import (
    ConfigError,
    load_config,
    save_config,
    settings_from_mapping,
)


def test_load_config_reads_toml(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        'output = "~/Downloads/mod"\nretries = 5\nvalidate = true\n',
        encoding="utf-8",
    )
    data = load_config(path)
    assert data["retries"] == 5
    assert data["validate"] is True


def test_load_config_missing_is_empty(tmp_path: Path) -> None:
    assert load_config(tmp_path / "missing.toml") == {}


def test_load_config_broken_raises(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("not valid = [", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)


def test_save_config_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "config.toml"
    save_config({"output": "/tmp/out", "retries": 3, "validate": False}, path)
    assert load_config(path) == {"output": "/tmp/out", "retries": 3, "validate": False}


def test_settings_from_mapping() -> None:
    settings = settings_from_mapping(
        {
            "target": "123",
            "target_type": "mod",
            "output": "~/somewhere",
            "auth": "login",
            "username": "user",
            "zip": True,
            "only": {"1", "2"},
        }
    )
    assert settings.target == "123"
    assert settings.target_type == "mod"
    assert settings.output_dir == Path("~/somewhere").expanduser()
    assert settings.auth_mode == "login"
    assert settings.username == "user"
    assert settings.zip_items is True
    assert settings.only == {"1", "2"}
    assert settings.bootstrap_steamcmd is True


def test_settings_bootstrap_can_be_disabled() -> None:
    settings = settings_from_mapping({"bootstrap_steamcmd": False})
    assert settings.bootstrap_steamcmd is False
