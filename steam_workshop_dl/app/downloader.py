"""Download orchestration.

Keeps policy (what to download, where, resume, retries) separate from the two
adapters: Steam Web API and SteamCMD.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import threading
import time
import zipfile
from pathlib import Path

from ..core.errors import DownloadError
from ..core.events import Events, NullEvents
from ..core.models import ItemStatus, Settings, Summary, WorkshopNode
from ..core.naming import ensure_within, human_size, sanitize_title
from ..core.tree import selected_items
from ..services.auth import ConsolePrompter, Prompter, ensure_login
from ..services.manifest import Manifest
from ..services.steam_api import SteamAPI
from ..services.steamcmd import (
    content_path,
    find_steamcmd,
    parse_line,
    run_script,
    write_runscript,
)
from .resolver import Resolver

log = logging.getLogger(__name__)


class Downloader:
    def __init__(self, api: SteamAPI | None = None) -> None:
        self.api = api or SteamAPI()

    def run(
        self,
        settings: Settings,
        *,
        root: WorkshopNode | None = None,
        events: Events | None = None,
        prompter: Prompter | None = None,
        cancel: threading.Event | None = None,
    ) -> Summary:
        events = events or NullEvents()
        cancel = cancel or threading.Event()
        started = time.monotonic()
        summary = Summary()

        if root is None:
            root = Resolver(self.api).resolve(settings.target, settings.target_type, events)

        summary.unavailable = sum(
            1 for node in root.items() if node.status is ItemStatus.UNAVAILABLE
        )
        items = selected_items(root, only=settings.only, exclude=settings.exclude)
        if not items:
            summary.elapsed = time.monotonic() - started
            events.finished(summary)
            return summary

        settings.output_dir.mkdir(parents=True, exist_ok=True)
        manifest = Manifest.load(settings.output_dir)
        manifest.set_target(root.id, settings.target_type)

        pending: list[WorkshopNode] = []
        for node in items:
            if manifest.should_skip(
                node, resume=settings.resume, force=settings.force
            ):
                node.status = ItemStatus.SKIPPED
                events.item_status(node.id, ItemStatus.SKIPPED, "уже скачано")
                summary.skipped += 1
            else:
                pending.append(node)

        if settings.dry_run:
            for node in pending:
                events.log(
                    "info",
                    f"[dry-run] {node.id} {node.title} ({human_size(node.size)})",
                )
            summary.elapsed = time.monotonic() - started
            events.finished(summary)
            return summary

        if not pending:
            summary.elapsed = time.monotonic() - started
            events.finished(summary)
            return summary

        steamcmd = find_steamcmd(settings.steamcmd)
        ensure_login(
            settings,
            prompter or ConsolePrompter(),
            events,
            executable=steamcmd,
        )

        total = len(pending)
        done = 0
        for attempt in range(settings.retries + 1):
            if not pending or cancel.is_set():
                break
            if attempt:
                events.log("info", f"Повтор для {len(pending)} предметов (попытка {attempt + 1}).")
                if cancel.wait(2**attempt):
                    break

            for node in pending:
                node.status = ItemStatus.DOWNLOADING
                events.item_status(node.id, ItemStatus.DOWNLOADING)

            failed = self._download_pass(
                steamcmd, pending, settings, events, cancel
            )
            still_pending: list[WorkshopNode] = []
            for node in pending:
                source = failed.get(node.id)
                if source is None:
                    node.status = ItemStatus.FAILED
                    events.item_status(node.id, ItemStatus.FAILED, "нет папки после SteamCMD")
                    still_pending.append(node)
                    continue
                try:
                    relative = self._install(node, source, settings)
                except (OSError, DownloadError) as exc:
                    log.exception("copy failed for %s", node.id)
                    node.status = ItemStatus.FAILED
                    events.item_status(node.id, ItemStatus.FAILED, str(exc))
                    still_pending.append(node)
                    continue

                node.status = ItemStatus.DONE
                manifest.mark(node, relative)
                events.item_status(node.id, ItemStatus.DONE, str(relative))
                summary.done += 1
                summary.total_bytes += node.size or 0
                done += 1
                events.progress(done, total, node.id)

            pending = still_pending

        if cancel.is_set():
            for node in pending:
                node.status = ItemStatus.CANCELED
                events.item_status(node.id, ItemStatus.CANCELED, "отменено")
                summary.canceled += 1

        summary.elapsed = time.monotonic() - started
        events.finished(summary)
        return summary

    def _download_pass(
        self,
        steamcmd: Path,
        items: list[WorkshopNode],
        settings: Settings,
        events: Events,
        cancel: threading.Event,
    ) -> dict[str, Path | None]:
        """Run one SteamCMD batch and return item_id -> source path."""

        found: dict[str, Path | None] = {node.id: None for node in items}
        with tempfile.TemporaryDirectory(prefix="swdl-") as tmp:
            script = Path(tmp) / "download.txt"
            write_runscript(
                script,
                items,
                auth_mode=settings.auth_mode,
                username=settings.username,
                validate=settings.validate,
            )
            try:
                run_script(
                    steamcmd,
                    script,
                    on_line=lambda line: self._handle_line(line, found, events),
                    cancel=cancel.is_set,
                )
            except OSError as exc:
                events.log("error", f"SteamCMD не запустился: {exc}")
                return found

        fallbacks = {
            node.id: content_path(steamcmd, node.appid, node.id)
            for node in items
            if node.appid
        }
        for item_id, path in list(found.items()):
            candidate = path or fallbacks.get(item_id)
            if candidate and candidate.is_dir() and any(candidate.iterdir()):
                found[item_id] = candidate
            else:
                found[item_id] = None
        return found

    @staticmethod
    def _handle_line(
        line: str,
        found: dict[str, Path | None],
        events: Events,
    ) -> None:
        events.log("debug", line)
        parsed = parse_line(line)
        if parsed is None:
            return
        if parsed.kind == "success" and parsed.item_id in found:
            found[parsed.item_id] = parsed.path
        elif parsed.kind == "failure" and parsed.item_id in found:
            found[parsed.item_id] = None

    def _install(self, node: WorkshopNode, source: Path, settings: Settings) -> Path:
        """Copy or zip one item.  Returns the path relative to output_dir."""

        base = settings.output_dir / str(node.appid) if settings.by_app else settings.output_dir
        base.mkdir(parents=True, exist_ok=True)
        name = sanitize_title(node.title, node.id)
        target = base / (f"{name}.zip" if settings.zip_items else name)
        ensure_within(settings.output_dir, target)

        if target.exists():
            if not settings.force:
                target = base / (
                    f"{name} ({node.appid})" + (".zip" if settings.zip_items else "")
                )
            else:
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()

        if settings.zip_items:
            self._make_zip(source, target)
        else:
            tmp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
            if tmp.exists():
                shutil.rmtree(tmp, ignore_errors=True)
            shutil.copytree(source, tmp)
            if target.exists():
                shutil.rmtree(target)
            os.replace(tmp, target)

        return target.relative_to(settings.output_dir)

    @staticmethod
    def _make_zip(source: Path, target: Path) -> None:
        tmp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in source.rglob("*"):
                if path.is_file():
                    archive.write(path, arcname=path.relative_to(source).as_posix())
        os.replace(tmp, target)
