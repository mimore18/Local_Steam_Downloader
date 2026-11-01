"""Download orchestration.

Keeps policy (what to download, where, resume, retries) separate from the two
adapters: Steam Web API and SteamCMD.
"""

from __future__ import annotations

import logging
import os
import queue
import shutil
import tempfile
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from ..core.errors import DownloadError
from ..core.events import Events, NullEvents
from ..core.models import ItemStatus, Settings, Summary, WorkshopNode
from ..core.naming import ensure_within, human_size, sanitize_title
from ..core.tree import selected_items
from ..services.auth import ConsolePrompter, Prompter, ensure_login
from ..services.manifest import Manifest
from ..services.steam_api import SteamAPI
from ..services.steamcmd import (
    InteractiveSteamCmd,
    content_path,
    parse_line,
    run_script,
    write_runscript,
)
from ..services.steamcmd_setup import (
    ensure_steamcmd,
    mark_steamcmd_initialized,
    steamcmd_initialized,
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
        items: list[WorkshopNode] | None = None,
        events: Events | None = None,
        prompter: Prompter | None = None,
        cancel: threading.Event | None = None,
    ) -> Summary:
        events = events or NullEvents()
        cancel = cancel or threading.Event()
        started = time.monotonic()
        summary = Summary()

        if root is None:
            root = Resolver(self.api).resolve(
                settings.target,
                settings.target_type,
                events,
                workers=settings.metadata_workers,
            )

        summary.unavailable = sum(
            1 for node in root.items() if node.status is ItemStatus.UNAVAILABLE
        )
        items = items if items is not None else selected_items(
            root, only=settings.only, exclude=settings.exclude
        )
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

        steamcmd = ensure_steamcmd(settings, events)
        # Anonymous mode logs in inside every download worker, so the separate
        # pre-flight process is pure overhead after the first successful run.
        # Account mode still needs the pre-flight step to cache credentials and
        # ask for a password/Steam Guard code once.
        if settings.auth_mode == "login" or not steamcmd_initialized(steamcmd):
            ensure_login(
                settings,
                prompter or ConsolePrompter(),
                events,
                executable=steamcmd,
            )
            mark_steamcmd_initialized(steamcmd)

        total = len(pending)
        for attempt in range(settings.retries + 1):
            if not pending or cancel.is_set():
                break
            if attempt:
                events.log("info", f"Повтор для {len(pending)} предметов (попытка {attempt + 1}).")
                if cancel.wait(2**attempt):
                    break

            install_jobs: queue.Queue[
                tuple[WorkshopNode, Path] | None
            ] = queue.Queue()
            install_failures: dict[str, str] = {}
            notified: set[str] = set()
            notified_lock = threading.Lock()

            def notify(node: WorkshopNode, source: Path) -> None:
                with notified_lock:
                    if node.id in notified:
                        return
                    notified.add(node.id)
                install_jobs.put((node, source))

            installer = threading.Thread(
                target=self._install_worker,
                args=(
                    install_jobs,
                    settings,
                    events,
                    manifest,
                    summary,
                    total,
                    cancel,
                    install_failures,
                ),
                name="swdl-install",
                daemon=True,
            )
            installer.start()
            failed: dict[str, Path | None] = {}
            try:
                failed = self._download_pass(
                    steamcmd, pending, settings, events, cancel, notify
                )
                # ``_download_pass`` normally reports successes as they arrive;
                # this also covers fallback paths and custom download adapters.
                for node in pending:
                    source = failed.get(node.id)
                    if source is not None:
                        notify(node, source)
            finally:
                install_jobs.put(None)
                installer.join()

            still_pending: list[WorkshopNode] = []
            for node in pending:
                if node.status is ItemStatus.DONE:
                    continue
                source = failed.get(node.id)
                if source is None:
                    node.status = ItemStatus.FAILED
                    events.item_status(node.id, ItemStatus.FAILED, "нет папки после SteamCMD")
                    still_pending.append(node)
                elif node.id in install_failures:
                    node.status = ItemStatus.FAILED
                    events.item_status(
                        node.id, ItemStatus.FAILED, install_failures[node.id]
                    )
                    still_pending.append(node)
                else:
                    # Canceled before the installer reached this item.
                    still_pending.append(node)

            pending = still_pending

        if cancel.is_set():
            for node in pending:
                node.status = ItemStatus.CANCELED
                events.item_status(node.id, ItemStatus.CANCELED, "отменено")
                summary.canceled += 1

        summary.elapsed = time.monotonic() - started
        events.finished(summary)
        return summary

    def _install_worker(
        self,
        jobs: queue.Queue[tuple[WorkshopNode, Path] | None],
        settings: Settings,
        events: Events,
        manifest: Manifest,
        summary: Summary,
        total: int,
        cancel: threading.Event,
        failures: dict[str, str],
    ) -> None:
        """Install items while download workers keep running."""

        while True:
            job = jobs.get()
            if job is None:
                return
            node, source = job
            if cancel.is_set():
                continue
            try:
                relative = self._install(node, source, settings)
            except (OSError, DownloadError) as exc:
                log.exception("copy failed for %s", node.id)
                failures[node.id] = str(exc)
                continue
            node.status = ItemStatus.DONE
            manifest.mark(node, relative)
            summary.done += 1
            summary.total_bytes += node.size or 0
            events.item_status(node.id, ItemStatus.DONE, str(relative))
            events.progress(summary.done, total, node.id)

    @staticmethod
    def _worker_count(settings: Settings, item_count: int) -> int:
        if item_count <= 1:
            return 1
        if settings.unstable and settings.download_threads == 0:
            return item_count
        return max(1, min(settings.download_threads, item_count))

    def _download_pass(
        self,
        steamcmd: Path,
        items: list[WorkshopNode],
        settings: Settings,
        events: Events,
        cancel: threading.Event,
        on_downloaded: Callable[[WorkshopNode, Path], None] | None = None,
    ) -> dict[str, Path | None]:
        """Run one SteamCMD pass and return item_id -> source path."""

        workers = self._worker_count(settings, len(items))
        per_mod = settings.unstable and settings.download_threads == 0
        reported: set[str] = set()
        report_lock = threading.Lock()

        def report(node: WorkshopNode, source: Path) -> None:
            if on_downloaded is None:
                return
            with report_lock:
                if node.id in reported:
                    return
                reported.add(node.id)
            on_downloaded(node, source)

        if workers == 1:
            found = self._download_batch(steamcmd, items, settings, events, cancel)
        else:
            if per_mod:
                events.log(
                    "info",
                    f"Нестабильный режим: {workers} SteamCMD одновременно.",
                )
            elif settings.dynamic_queue:
                events.log(
                    "info",
                    f"Динамическая очередь: {workers} поток(ов).",
                )
            else:
                events.log("info", f"Параллельная загрузка: {workers} поток(ов).")
            if settings.dynamic_queue and not per_mod:
                found = self._download_dynamic(
                    steamcmd,
                    items,
                    settings,
                    events,
                    cancel,
                    workers,
                    report,
                )
            else:
                found = self._download_parallel(
                    steamcmd,
                    items,
                    settings,
                    events,
                    cancel,
                    workers,
                    report,
                )
        found = self._apply_fallbacks(steamcmd, items, found)
        if on_downloaded is not None:
            for node in items:
                source = found.get(node.id)
                if source is not None:
                    report(node, source)
        return found

    def _download_batch(
        self,
        steamcmd: Path,
        items: list[WorkshopNode],
        settings: Settings,
        events: Events,
        cancel: threading.Event,
    ) -> dict[str, Path | None]:
        found: dict[str, Path | None] = {node.id: None for node in items}
        by_id = {node.id: node for node in items}
        state: dict[str, object] = {"current": None, "percent": {}}
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
                    on_line=lambda line: self._handle_line(
                        line, found, by_id, state, events
                    ),
                    cancel=cancel.is_set,
                )
            except OSError as exc:
                events.log("error", f"SteamCMD не запустился: {exc}")
        return found

    def _download_parallel(
        self,
        steamcmd: Path,
        items: list[WorkshopNode],
        settings: Settings,
        events: Events,
        cancel: threading.Event,
        workers: int,
        on_downloaded: Callable[[WorkshopNode, Path], None] | None = None,
    ) -> dict[str, Path | None]:
        chunks = self._split_balanced(items, workers)
        events.log(
            "debug",
            "Chunks: " + ", ".join(str(len(chunk)) for chunk in chunks),
        )

        def run_chunk(chunk: list[WorkshopNode]) -> dict[str, Path | None]:
            if cancel.is_set():
                return {node.id: None for node in chunk}
            part = self._download_batch(
                steamcmd, chunk, settings, events, cancel
            )
            if on_downloaded is not None:
                for node in chunk:
                    source = part.get(node.id)
                    if source is not None:
                        on_downloaded(node, source)
            return part

        found: dict[str, Path | None] = {node.id: None for node in items}
        with ThreadPoolExecutor(
            max_workers=len(chunks), thread_name_prefix="swdl"
        ) as pool:
            for part in pool.map(run_chunk, chunks):
                found.update(part)
        return found

    def _download_dynamic(
        self,
        steamcmd: Path,
        items: list[WorkshopNode],
        settings: Settings,
        events: Events,
        cancel: threading.Event,
        workers: int,
        on_downloaded: Callable[[WorkshopNode, Path], None] | None = None,
    ) -> dict[str, Path | None]:
        """Feed one shared queue to long-lived SteamCMD workers.

        Each worker logs in once and then takes the next item as soon as its
        previous download finishes, so fast workers do not wait for slow ones.
        """

        pending: queue.Queue[WorkshopNode] = queue.Queue()
        for node in items:
            pending.put(node)
        found: dict[str, Path | None] = {node.id: None for node in items}
        by_id = {node.id: node for node in items}
        result_lock = threading.Lock()
        login = (
            "anonymous"
            if settings.auth_mode == "anonymous"
            else (settings.username or "")
        )

        def run_worker() -> None:
            if cancel.is_set():
                return
            try:
                worker = InteractiveSteamCmd(
                    steamcmd,
                    login=login,
                    timeout=max(settings.timeout, 120.0),
                )
            except OSError as exc:
                events.log("error", f"SteamCMD не запустился: {exc}")
                return
            state: dict[str, object] = {"current": None, "percent": {}}
            try:
                if not worker.wait_login(
                    lambda line: events.log("debug", line),
                    cancel=cancel.is_set,
                ):
                    events.log(
                        "error",
                        "SteamCMD: не удалось войти в динамическом режиме.",
                    )
                    return
                while not cancel.is_set():
                    try:
                        node = pending.get_nowait()
                    except queue.Empty:
                        break
                    source = worker.download_item(
                        node,
                        lambda line: self._handle_line(
                            line, found, by_id, state, events
                        ),
                        cancel=cancel.is_set,
                        validate=settings.validate,
                    )
                    with result_lock:
                        found[node.id] = source
                    if source is not None and on_downloaded is not None:
                        on_downloaded(node, source)
                    if not worker.alive:
                        break
            except OSError as exc:
                events.log("error", f"SteamCMD: {exc}")
            finally:
                worker.close()

        with ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="swdl"
        ) as pool:
            futures = [pool.submit(run_worker) for _ in range(workers)]
            for future in futures:
                future.result()
        return found

    @staticmethod
    def _split_balanced(
        items: list[WorkshopNode], workers: int
    ) -> list[list[WorkshopNode]]:
        """Split items into balanced chunks, largest first, for worker reuse."""

        buckets: list[list[WorkshopNode]] = [[] for _ in range(workers)]
        loads = [0] * workers
        for node in sorted(items, key=lambda item: item.size or 0, reverse=True):
            index = min(range(workers), key=loads.__getitem__)
            buckets[index].append(node)
            loads[index] += node.size or 0
        return [bucket for bucket in buckets if bucket]

    @staticmethod
    def _apply_fallbacks(
        steamcmd: Path,
        items: list[WorkshopNode],
        found: dict[str, Path | None],
    ) -> dict[str, Path | None]:
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
        by_id: dict[str, WorkshopNode],
        state: dict[str, object],
        events: Events,
    ) -> None:
        events.log("debug", line)
        parsed = parse_line(line)
        if parsed is None:
            return
        if parsed.kind == "start" and parsed.item_id in found:
            state["current"] = parsed.item_id
            node = by_id.get(parsed.item_id)
            if node is not None:
                node.status = ItemStatus.DOWNLOADING
            events.item_status(parsed.item_id, ItemStatus.DOWNLOADING)
            events.item_progress(parsed.item_id, 0.0)
        elif parsed.kind == "progress":
            current = state.get("current")
            if current in found and parsed.percent is not None:
                percents = state["percent"]
                assert isinstance(percents, dict)
                percents[current] = parsed.percent
                events.item_progress(current, parsed.percent)
        elif parsed.kind == "success" and parsed.item_id in found:
            found[parsed.item_id] = parsed.path
            state["current"] = None
            events.item_progress(parsed.item_id, 100.0)
        elif parsed.kind == "failure" and parsed.item_id in found:
            found[parsed.item_id] = None
            state["current"] = None

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
