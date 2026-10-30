"""Configuration loading and OS-specific paths.

Priority: CLI arguments > environment > config file > built-in defaults.
Passwords are deliberately absent from the schema.
"""

from __future__ import annotations

import os
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..core.errors import WorkshopError
from ..core.models import Settings

APP_NAME = "steam-workshop-dl"
ENV_CONFIG = "STEAM_WORKSHOP_CONFIG"
ENV_OUTPUT = "STEAM_WORKSHOP_OUTPUT"


class ConfigError(WorkshopError):
    """Configuration file is unreadable or invalid."""


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else None


def default_config_path() -> Path:
    override = _env_path(ENV_CONFIG)
    if override:
        return override
    if _is_windows():
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = _env_path("XDG_CONFIG_HOME") or Path.home() / ".config"
    return base / APP_NAME / "config.toml"


def default_log_path() -> Path:
    if _is_windows():
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = _env_path("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return base / APP_NAME / "app.log"


def default_output_dir() -> Path:
    return _env_path(ENV_OUTPUT) or Path.home() / "Downloads" / "workshop"


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Read a TOML config.  Missing file is not an error."""

    config_path = path or default_config_path()
    try:
        with config_path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError:
        return {}
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"не удалось прочитать конфиг {config_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"конфиг {config_path} должен быть таблицей")
    return data


def save_config(data: Mapping[str, Any], path: Path | None = None) -> Path:
    """Write a minimal TOML file.  Only flat scalar keys are supported."""

    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    def render(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        text = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{text}"'

    lines = [f"{key} = {render(value)}" for key, value in data.items()]
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config_path


def settings_from_mapping(data: Mapping[str, Any]) -> Settings:
    """Build Settings from a merged mapping; unknown keys are ignored."""

    def pick(*names: str, default: Any = None) -> Any:
        for name in names:
            if name in data and data[name] is not None:
                return data[name]
        return default

    def id_set(value: Any) -> set[str]:
        if not value:
            return set()
        if isinstance(value, str):
            return {part.strip() for part in value.split(",") if part.strip()}
        return {str(part) for part in value}

    output = pick("output", "output_dir", default=default_output_dir())
    steamcmd = pick("steamcmd")
    auth = pick("auth", "auth_mode", default="anonymous")
    only = pick("only", default=())
    exclude = pick("exclude", default=())

    return Settings(
        target=str(pick("target", default="")),
        target_type=str(pick("target_type", default="collection")),
        output_dir=Path(output).expanduser(),
        steamcmd=Path(steamcmd).expanduser() if steamcmd else None,
        bootstrap_steamcmd=bool(
            pick("bootstrap_steamcmd", "download_steamcmd", "steamcmd_bootstrap", default=True)
        ),
        auth_mode=str(auth),
        username=pick("username"),
        validate=bool(pick("validate", default=False)),
        zip_items=bool(pick("zip", "zip_items", default=False)),
        by_app=bool(pick("by_app", default=False)),
        flat=bool(pick("flat", default=False)),
        resume=bool(pick("resume", default=True)),
        force=bool(pick("force", default=False)),
        retries=int(pick("retries", default=2)),
        metadata_workers=int(pick("jobs", "metadata_workers", default=4)),
        timeout=float(pick("timeout", default=30.0)),
        dry_run=bool(pick("dry_run", default=False)),
        only=id_set(only),
        exclude=id_set(exclude),
    )



