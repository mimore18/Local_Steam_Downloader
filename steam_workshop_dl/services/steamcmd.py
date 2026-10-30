"""SteamCMD process management and output parsing."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..core.errors import SteamCmdNotFoundError
from ..core.models import WorkshopNode

SUCCESS_RE = re.compile(r'Success\. Downloaded item (\d+) to "(.+)"')
FAILED_RE = re.compile(r"ERROR! Download item (\d+) failed")
LOGIN_FAILED_RE = re.compile(r"(?i)(FAILED login|Invalid Password|Rate Limit Exceeded)")
LOGIN_OK_RE = re.compile(r"(?i)(Logged in OK|Log On successful|Waiting for user info\.\.\.OK)")

ENV_STEAMCMD = "STEAMCMD_PATH"


@dataclass(frozen=True)
class SteamCmdLine:
    kind: Literal["success", "failure", "info"]
    item_id: str | None = None
    path: Path | None = None


def find_steamcmd(explicit: str | Path | None = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    env_value = os.environ.get(ENV_STEAMCMD)
    if env_value:
        candidates.append(Path(env_value).expanduser())
    for name in ("steamcmd", "steamcmd.sh", "steamcmd.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    home = Path.home()
    if sys.platform.startswith("win"):
        candidates.extend(
            [
                home / "steamcmd" / "steamcmd.exe",
                Path(r"C:\steamcmd\steamcmd.exe"),
            ]
        )
    else:
        candidates.extend(
            [
                home / "steamcmd" / "steamcmd.sh",
                home / ".steam" / "steamcmd" / "steamcmd.sh",
                Path("/usr/games/steamcmd"),
            ]
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SteamCmdNotFoundError(
        "SteamCMD не найден. Укажите --steamcmd или переменную STEAMCMD_PATH."
    )


def build_command(executable: Path, runscript: Path) -> list[str]:
    """Single place to change how SteamCMD is invoked (tests monkeypatch this)."""

    return [str(executable), "+runscript", str(runscript), "+quit"]


def write_runscript(
    path: Path,
    items: Iterable[WorkshopNode],
    *,
    auth_mode: str,
    username: str | None,
    validate: bool = False,
) -> Path:
    login = "anonymous" if auth_mode == "anonymous" else (username or "")
    lines = [
        "@ShutdownOnFailedCommand 0",
        "@NoPromptForPassword 1",
        f"login {login}",
    ]
    for item in items:
        if not item.appid:
            continue
        suffix = " validate" if validate else ""
        lines.append(f" workshop_download_item {item.appid} {item.id}{suffix}".strip())
    lines.append("quit")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def parse_line(line: str) -> SteamCmdLine | None:
    success = SUCCESS_RE.search(line)
    if success:
        return SteamCmdLine("success", success.group(1), Path(success.group(2)))
    failed = FAILED_RE.search(line)
    if failed:
        return SteamCmdLine("failure", failed.group(1))
    return None


def content_path(executable: Path, appid: int, item_id: str) -> Path:
    return executable.parent / "steamapps" / "workshop" / "content" / str(appid) / item_id


def popen_kwargs() -> dict[str, object]:
    """Platform-specific flags for a detached, cancellable child process."""

    if sys.platform.startswith("win"):
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
        except OSError:
            pass


def run_script(
    executable: Path,
    runscript: Path,
    *,
    on_line: Callable[[str], None],
    cancel: Callable[[], bool] | None = None,
    timeout: float | None = None,
) -> int:
    """Run a prepared script and stream decoded lines to *on_line*."""

    command = build_command(executable, runscript)
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        **popen_kwargs(),  # type: ignore[arg-type]
    )
    assert process.stdout is not None
    try:
        for raw in process.stdout:
            text = raw.decode("utf-8", errors="replace").rstrip()
            on_line(text)
            if cancel and cancel():
                terminate_process(process)
                break
        return process.wait(timeout=timeout)
    except BaseException:
        terminate_process(process)
        raise
