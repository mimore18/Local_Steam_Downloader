"""Locate, download and unpack SteamCMD.

SteamCMD is distributed by Valve as a plain archive and self-updates on its
first run.  When no local installation is found, this module downloads the
official archive into a dedicated folder and invokes the executable from
there.  The folder is project-local when running from a source checkout and
otherwise lives in the per-user data directory.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tarfile
import tempfile
import time
import zipfile
from http.client import HTTPException
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from ..core.errors import SteamCmdNotFoundError, WorkshopError
from ..core.events import Events, NullEvents
from ..core.models import Settings
from .config import APP_NAME
from .steamcmd import find_steamcmd

ENV_STEAMCMD_DIR = "STEAM_WORKSHOP_STEAMCMD_DIR"
READY_MARKER = ".steam-workshop-dl-ready"
USER_AGENT = "steam-workshop-dl/0.1 (+https://github.com/mimore18/Local_Steam_Downloader)"

LINUX_ARCHIVE = "steamcmd_linux.tar.gz"
WINDOWS_ARCHIVE = "steamcmd.zip"
BASE_URL = "https://steamcdn-a.akamaihd.net/client/installer/"

DOWNLOAD_ATTEMPTS = 3
DOWNLOAD_TIMEOUT = 120.0


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _fallback_marker(executable: Path) -> Path:
    digest = hashlib.sha256(
        str(executable.resolve()).encode("utf-8")
    ).hexdigest()[:16]
    return _user_data_dir() / APP_NAME / "steamcmd-ready" / f"{digest}.marker"


def steamcmd_initialized(executable: Path) -> bool:
    """Whether SteamCMD completed at least one login/update run."""

    return (
        (executable.parent / READY_MARKER).is_file()
        or _fallback_marker(executable).is_file()
    )


def mark_steamcmd_initialized(executable: Path) -> None:
    """Remember a successful SteamCMD run, even for read-only installs."""

    try:
        (executable.parent / READY_MARKER).touch()
        return
    except OSError:
        pass
    fallback = _fallback_marker(executable)
    try:
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.touch()
    except OSError:
        pass


def _user_data_dir() -> Path:
    if _is_windows():
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    base = os.environ.get("XDG_DATA_HOME")
    return Path(base) if base else Path.home() / ".local" / "share"


def project_root() -> Path:
    """Best-effort source checkout root (two levels above this package)."""

    return Path(__file__).resolve().parents[2]


def default_steamcmd_dir() -> Path:
    """Where an automatically downloaded SteamCMD is stored."""

    override = os.environ.get(ENV_STEAMCMD_DIR)
    if override:
        return Path(override).expanduser()

    root = project_root()
    if (root / "pyproject.toml").is_file() and (root / "steam_workshop_dl").is_dir():
        return root / "steamcmd"

    return _user_data_dir() / APP_NAME / "steamcmd"


def executable_name() -> str:
    return "steamcmd.exe" if _is_windows() else "steamcmd.sh"


def archive_name() -> str:
    return WINDOWS_ARCHIVE if _is_windows() else LINUX_ARCHIVE


def _download_file(url: str, target: Path, *, timeout: float = DOWNLOAD_TIMEOUT) -> None:
    """Download *url* to *target* with a small retry loop."""

    last_error: Exception | None = None
    for attempt in range(DOWNLOAD_ATTEMPTS):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=timeout) as response:
                with target.open("wb") as handle:
                    shutil.copyfileobj(response, handle)
            return
        except (URLError, OSError, TimeoutError, HTTPException) as exc:
            last_error = exc
            if attempt + 1 < DOWNLOAD_ATTEMPTS:
                time.sleep(2**attempt)
    raise WorkshopError(f"Не удалось скачать SteamCMD: {last_error}") from last_error


def _safe_target(base: Path, name: str) -> Path:
    base_resolved = base.resolve()
    target = (base / name).resolve()
    if target != base_resolved and base_resolved not in target.parents:
        raise WorkshopError(f"Архив SteamCMD содержит небезопасный путь: {name}")
    return target


def _extract_tar(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle.getmembers():
            if member.issym() or member.islnk():
                continue
            target = _safe_target(destination, member.name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = bundle.extractfile(member)
            if source is None:
                continue
            with source, target.open("wb") as handle:
                shutil.copyfileobj(source, handle)


def _extract_zip(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            target = _safe_target(destination, info.filename)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as source, target.open("wb") as handle:
                shutil.copyfileobj(source, handle)


def _extract(archive: Path, destination: Path) -> None:
    if archive.suffix == ".zip":
        _extract_zip(archive, destination)
    else:
        _extract_tar(archive, destination)


def bootstrap_steamcmd(
    *,
    destination: Path | None = None,
    events: Events | None = None,
    force: bool = False,
) -> Path:
    """Download and unpack SteamCMD, returning the executable path."""

    events = events or NullEvents()
    folder = Path(destination).expanduser() if destination else default_steamcmd_dir()
    executable = folder / executable_name()

    if executable.is_file() and not force:
        events.log("info", f"SteamCMD: используется {executable}")
        return executable

    if force:
        shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True, exist_ok=True)
    for marker in (folder / READY_MARKER, _fallback_marker(executable)):
        try:
            marker.unlink()
        except OSError:
            pass

    url = BASE_URL + archive_name()
    events.log("info", f"SteamCMD не найден. Скачивание: {url}")
    events.log("info", f"SteamCMD будет установлен в: {folder}")

    with tempfile.TemporaryDirectory(prefix="swdl-steamcmd-") as tmp:
        archive = Path(tmp) / archive_name()
        _download_file(url, archive)
        events.log("info", "SteamCMD: распаковка архива…")
        _extract(archive, folder)

    if not executable.is_file():
        raise SteamCmdNotFoundError(
            f"Архив SteamCMD распакован, но {executable_name()} не найден в {folder}."
        )

    if not _is_windows():
        executable.chmod(executable.stat().st_mode | 0o111)
        for pattern in ("linux32/steamcmd", "linux64/steamcmd"):
            candidate = folder / pattern
            if candidate.is_file():
                candidate.chmod(candidate.stat().st_mode | 0o111)

    events.log("info", f"SteamCMD готов: {executable}")
    return executable


def ensure_steamcmd(settings: Settings, events: Events | None = None) -> Path:
    """Return a usable SteamCMD path, downloading it when allowed."""

    events = events or NullEvents()

    if settings.steamcmd:
        explicit = Path(settings.steamcmd).expanduser()
        if explicit.is_file():
            return explicit
        if explicit.is_dir():
            nested = explicit / executable_name()
            if nested.is_file():
                return nested
        raise SteamCmdNotFoundError(
            f"Указанный SteamCMD не найден: {explicit}. "
            f"Исправьте --steamcmd или уберите его, чтобы скачать автоматически."
        )

    try:
        return find_steamcmd(None)
    except SteamCmdNotFoundError:
        pass

    local = default_steamcmd_dir() / executable_name()
    if local.is_file():
        return local

    if not settings.bootstrap_steamcmd:
        raise SteamCmdNotFoundError(
            "SteamCMD не найден. Установите его вручную, укажите --steamcmd "
            "или включите автоматическую загрузку."
        )

    return bootstrap_steamcmd(destination=default_steamcmd_dir(), events=events)
