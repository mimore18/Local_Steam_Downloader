"""SteamCMD authentication.

Anonymous mode is fully automatic.  Account mode performs a separate
pre-flight login so the SteamCMD sentry cache is ready before the download
script runs.  Passwords travel only through stdin.
"""

from __future__ import annotations

import getpass
import queue
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Protocol

from ..core.errors import LoginFailedError
from ..core.events import Events, NullEvents
from ..core.models import Settings
from .logging_setup import mask_secrets
from .steamcmd import (
    LOGIN_FAILED_RE,
    LOGIN_OK_RE,
    decode_steamcmd,
    find_steamcmd,
    popen_kwargs,
)

PASSWORD_RE = re.compile(r"password\s*:", re.IGNORECASE)
GUARD_RE = re.compile(r"(steam guard code|two-factor code|two factor code)\s*:", re.IGNORECASE)


class Prompter(Protocol):
    def ask_password(self, username: str) -> str | None: ...

    def ask_steam_guard(self, username: str) -> str | None: ...


class ConsolePrompter:
    def ask_password(self, username: str) -> str | None:
        try:
            return getpass.getpass(f"Пароль Steam для {username}: ")
        except (EOFError, KeyboardInterrupt):
            return None

    def ask_steam_guard(self, username: str) -> str | None:
        try:
            return input("Код Steam Guard: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None


def ensure_login(
    settings: Settings,
    prompter: Prompter,
    events: Events | None = None,
    *,
    executable: Path | None = None,
    timeout: float = 300.0,
) -> Path:
    events = events or NullEvents()
    steamcmd = executable or find_steamcmd(settings.steamcmd)
    if settings.auth_mode == "anonymous":
        _anonymous_login(steamcmd, events, timeout)
    else:
        if not settings.username:
            raise LoginFailedError("Для входа под аккаунтом нужен username.")
        _account_login(steamcmd, settings.username, prompter, events, timeout)
    return steamcmd


def _decode(raw: bytes) -> str:
    return decode_steamcmd(raw)


def _anonymous_login(executable: Path, events: Events, timeout: float) -> None:
    events.log("info", "SteamCMD: анонимный вход и проверка обновлений…")
    try:
        result = subprocess.run(
            [str(executable), "+login", "anonymous", "+quit"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            **popen_kwargs(),  # type: ignore[arg-type]
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LoginFailedError(f"SteamCMD не запустился: {exc}") from exc
    output = _decode(result.stdout or b"")
    if LOGIN_FAILED_RE.search(output) or result.returncode != 0:
        tail = mask_secrets(output.strip().splitlines()[-1] if output.strip() else "без вывода")
        raise LoginFailedError(f"Анонимный вход не удался: {tail}")
    events.log("info", "SteamCMD: вход выполнен.")


def _account_login(
    executable: Path,
    username: str,
    prompter: Prompter,
    events: Events,
    timeout: float,
) -> None:
    events.log("info", f"SteamCMD: вход под аккаунтом {username}…")
    command = [str(executable), "+login", username, "+quit"]
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            **popen_kwargs(),  # type: ignore[arg-type]
        )
    except OSError as exc:
        raise LoginFailedError(f"SteamCMD не запустился: {exc}") from exc
    assert process.stdout is not None
    assert process.stdin is not None

    chunks: queue.Queue[bytes | None] = queue.Queue()

    def read_output() -> None:
        assert process.stdout is not None
        while True:
            chunk = process.stdout.read(4096)
            if not chunk:
                break
            chunks.put(chunk)
        chunks.put(None)

    threading.Thread(target=read_output, daemon=True).start()

    buffer = ""
    password_sent = guard_sent = False
    logged_in = False
    failed = False

    try:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LoginFailedError("Истекло время ожидания входа в Steam.")
            try:
                chunk = chunks.get(timeout=min(0.5, remaining))
            except queue.Empty:
                if process.poll() is not None:
                    break
                continue
            if chunk is None:
                break

            piece = _decode(chunk)
            events.log("debug", mask_secrets(piece.rstrip()))
            buffer += piece
            if LOGIN_FAILED_RE.search(buffer):
                failed = True
            if LOGIN_OK_RE.search(buffer):
                logged_in = True

            if GUARD_RE.search(buffer):
                if guard_sent:
                    buffer = ""
                    continue
                code = prompter.ask_steam_guard(username)
                if code is None:
                    raise LoginFailedError("Ввод кода Steam Guard отменён.")
                _write(process, code)
                guard_sent = True
                buffer = ""
                continue

            if PASSWORD_RE.search(buffer) and not password_sent:
                password = prompter.ask_password(username)
                if password is None:
                    raise LoginFailedError("Ввод пароля отменён.")
                _write(process, password)
                password_sent = True
                buffer = ""
                continue

            if logged_in:
                buffer = ""
    finally:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()

    if failed or not logged_in:
        raise LoginFailedError("SteamCMD не подтвердил вход. Проверьте логин/пароль/Guard.")

    events.log("info", "SteamCMD: вход выполнен, сессия закэширована.")


def _write(process: subprocess.Popen[bytes], value: str) -> None:
    assert process.stdin is not None
    try:
        process.stdin.write((value + "\n").encode("utf-8"))
        process.stdin.flush()
    except OSError as exc:
        raise LoginFailedError(f"SteamCMD закрыл stdin: {exc}") from exc
