from __future__ import annotations

import os
import shutil
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from steam_workshop_dl.core.errors import SteamCmdNotFoundError
from steam_workshop_dl.core.events import NullEvents
from steam_workshop_dl.core.models import Settings
from steam_workshop_dl.services import steamcmd_setup


def make_archive(path: Path, executable: str) -> None:
    payload = b"#!/bin/sh\necho fake steamcmd\n"
    if path.suffix == ".zip":
        with zipfile.ZipFile(path, "w") as bundle:
            bundle.writestr(executable, payload)
            bundle.writestr("public/steam_cmd_public.txt", "data")
        return
    with tarfile.open(path, "w:gz") as bundle:
        info = tarfile.TarInfo(executable)
        info.size = len(payload)
        info.mode = 0o644
        bundle.addfile(info, BytesIO(payload))
        folder = tarfile.TarInfo("public")
        folder.type = tarfile.DIRTYPE
        folder.mode = 0o755
        bundle.addfile(folder)
        extra = b"data"
        info = tarfile.TarInfo("public/steam_cmd_public.txt")
        info.size = len(extra)
        bundle.addfile(info, BytesIO(extra))


def test_default_dir_can_be_overridden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(steamcmd_setup.ENV_STEAMCMD_DIR, str(tmp_path / "custom"))
    assert steamcmd_setup.default_steamcmd_dir() == tmp_path / "custom"


def test_bootstrap_downloads_and_extracts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    archive = tmp_path / steamcmd_setup.archive_name()
    executable = steamcmd_setup.executable_name()
    make_archive(archive, executable)

    def fake_download(_url: str, target: Path, *, timeout: float = 0) -> None:
        shutil.copyfile(archive, target)

    monkeypatch.setattr(steamcmd_setup, "_download_file", fake_download)

    folder = tmp_path / "steamcmd"
    result = steamcmd_setup.bootstrap_steamcmd(
        destination=folder, events=NullEvents()
    )

    assert result == folder / executable
    assert result.is_file()
    assert (folder / "public" / "steam_cmd_public.txt").is_file()
    if os.name != "nt":
        assert os.access(result, os.X_OK)


def test_bootstrap_reuses_existing_install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = tmp_path / "steamcmd"
    folder.mkdir()
    executable = folder / steamcmd_setup.executable_name()
    executable.write_text("#!/bin/sh\n", encoding="utf-8")

    def fail(*_args, **_kwargs):
        raise AssertionError("must not download")

    monkeypatch.setattr(steamcmd_setup, "_download_file", fail)

    assert steamcmd_setup.bootstrap_steamcmd(destination=folder) == executable


def test_ensure_prefers_existing_explicit_path(tmp_path: Path) -> None:
    executable = tmp_path / steamcmd_setup.executable_name()
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    assert steamcmd_setup.ensure_steamcmd(Settings(steamcmd=executable)) == executable


def test_ensure_rejects_missing_explicit_path(tmp_path: Path) -> None:
    with pytest.raises(SteamCmdNotFoundError):
        steamcmd_setup.ensure_steamcmd(Settings(steamcmd=tmp_path / "missing"))


def test_ensure_bootstraps_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def missing(_explicit=None):
        raise SteamCmdNotFoundError("not found")

    destination = tmp_path / "auto"
    monkeypatch.setattr(steamcmd_setup, "find_steamcmd", missing)
    monkeypatch.setattr(steamcmd_setup, "default_steamcmd_dir", lambda: destination)

    def fake_bootstrap(*, destination, events=None, force=False):
        assert destination == tmp_path / "auto"
        assert events is not None
        return destination / steamcmd_setup.executable_name()

    monkeypatch.setattr(steamcmd_setup, "bootstrap_steamcmd", fake_bootstrap)

    result = steamcmd_setup.ensure_steamcmd(Settings(), NullEvents())
    assert result == destination / steamcmd_setup.executable_name()

    with pytest.raises(SteamCmdNotFoundError):
        steamcmd_setup.ensure_steamcmd(
            Settings(bootstrap_steamcmd=False), NullEvents()
        )
