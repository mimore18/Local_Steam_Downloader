"""Command-line interface.

The CLI is intentionally thin: it parses arguments, builds Settings, prints
events and delegates everything else to the application layer.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .. import __version__
from ..app.downloader import Downloader
from ..app.resolver import Resolver
from ..core.errors import WorkshopError
from ..core.events import Events
from ..core.models import ItemStatus, NodeKind, Summary, WorkshopNode
from ..core.naming import human_size
from ..services.config import (
    ConfigError,
    default_output_dir,
    load_config,
    settings_from_mapping,
)
from ..services.logging_setup import setup_logging
from ..services.steam_api import SteamAPI

log = logging.getLogger(__name__)

GLYPH = {
    "full": "☑",
    "partial": "◐",
    "empty": "☐",
    "unavailable": "☐",
}


class ConsoleEvents:
    def log(self, level: str, message: str) -> None:
        getattr(log, level if level in {"debug", "info", "warning", "error"} else "info")(
            message
        )

    def tree_ready(self, root: WorkshopNode) -> None:
        pass

    def metadata_updated(self, root: WorkshopNode) -> None:
        pass

    def item_status(self, item_id: str, status: ItemStatus, detail: str = "") -> None:
        if status in {ItemStatus.DONE, ItemStatus.FAILED, ItemStatus.SKIPPED}:
            tail = f" ({detail})" if detail else ""
            if status is not ItemStatus.DONE:
                log.info("%s: %s%s", item_id, status.value, tail)

    def progress(self, done: int, total: int, current_id: str | None) -> None:
        log.info("Прогресс: %s/%s", done, total)

    def finished(self, summary: Summary) -> None:
        log.info("Итог: %s (%.1f c)", summary.as_text(), summary.elapsed)


def _glyph(node: WorkshopNode) -> str:
    if not node.selectable:
        return GLYPH["unavailable"]
    if node.kind is NodeKind.ITEM:
        return GLYPH["full"] if node.selected else GLYPH["empty"]
    available = [child for child in node.children if child.selectable]
    if not available:
        return GLYPH["empty"]
    chosen = sum(1 for child in available if child.selected)
    if chosen == 0:
        return GLYPH["empty"]
    if chosen == len(available):
        return GLYPH["full"]
    return GLYPH["partial"]


def print_tree(root: WorkshopNode) -> None:
    def walk(node: WorkshopNode, prefix: str, last: bool, top: bool) -> None:
        connector = "" if top else ("└── " if last else "├── ")
        available, selected = node.counts() if node.kind is NodeKind.COLLECTION else (0, 0)
        extra = ""
        if node.kind is NodeKind.COLLECTION:
            extra = f" — коллекция, модов: {len(list(node.items()))}"
        elif node.size is not None:
            extra = f" — {human_size(node.size)}"
        if node.status is ItemStatus.UNAVAILABLE:
            extra += " — недоступен"
        title = node.title or f"item {node.id}"
        print(f"{prefix}{connector}{_glyph(node)} {title} [{node.id}]{extra}")
        child_prefix = prefix + ("" if top else ("    " if last else "│   "))
        for index, child in enumerate(node.children):
            walk(child, child_prefix, index == len(node.children) - 1, False)

    walk(root, "", True, True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="steam-workshop-dl",
        description="Скачивание коллекций и модов Steam Workshop через SteamCMD.",
    )
    parser.add_argument("target", nargs="?", help="URL или ID коллекции/мода")
    parser.add_argument(
        "--type",
        choices=("collection", "mod"),
        default=None,
        help="тип цели: коллекция (по умолчанию) или один мод",
    )
    parser.add_argument("-o", "--output", default=None, help="выходная папка")
    parser.add_argument("--steamcmd", default=None, help="путь к SteamCMD")
    auth = parser.add_mutually_exclusive_group()
    auth.add_argument("--anonymous", action="store_true", default=None, help="анонимный вход")
    auth.add_argument("--login", metavar="USER", default=None, help="вход под аккаунтом")
    parser.add_argument("--only", default=None, help="качать только эти ID через запятую")
    parser.add_argument("--exclude", default=None, help="исключить эти ID через запятую")
    parser.add_argument("--list", action="store_true", help="показать дерево и выйти")
    parser.add_argument("--dry-run", action="store_true", default=None, help="показать план")
    parser.add_argument("--force", action="store_true", default=None, help="игнорировать манифест")
    parser.add_argument("--no-resume", dest="resume", action="store_false", default=None)
    parser.add_argument("--retries", type=int, default=None)
    parser.add_argument("--validate", action="store_true", default=None)
    parser.add_argument("--zip", dest="zip_items", action="store_true", default=None)
    parser.add_argument("--by-app", dest="by_app", action="store_true", default=None)
    parser.add_argument("--flat", action="store_true", default=None)
    parser.add_argument("--jobs", type=int, default=None, help="потоков для метаданных")
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--config", default=None, help="путь к config.toml")
    parser.add_argument("--log-file", default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--gui", action="store_true", help="открыть графический интерфейс")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _cli_values(args: argparse.Namespace) -> dict[str, object]:
    values: dict[str, object] = {
        "target": args.target,
        "target_type": args.type,
        "output": args.output,
        "steamcmd": args.steamcmd,
        "validate": args.validate,
        "zip": args.zip_items,
        "by_app": args.by_app,
        "flat": args.flat,
        "resume": args.resume,
        "force": args.force,
        "retries": args.retries,
        "jobs": args.jobs,
        "timeout": args.timeout,
        "dry_run": args.dry_run,
    }
    if args.anonymous:
        values["auth"] = "anonymous"
    elif args.login:
        values["auth"] = "login"
        values["username"] = args.login
    if args.only is not None:
        values["only"] = {item.strip() for item in args.only.split(",") if item.strip()}
    if args.exclude is not None:
        values["exclude"] = {item.strip() for item in args.exclude.split(",") if item.strip()}
    return {key: value for key, value in values.items() if value is not None}


def _build_settings(args: argparse.Namespace):
    config_path = Path(args.config).expanduser() if args.config else None
    config = load_config(config_path)
    merged = {**config, "_cli": _cli_values(args)}
    cli_values = merged.pop("_cli")
    merged.update(cli_values)
    if not merged.get("output"):
        merged["output"] = default_output_dir()
    if not merged.get("target"):
        raise WorkshopError("Не указана ссылка или ID.")
    return settings_from_mapping(merged)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # type: ignore[union-attr]

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.gui:
        try:
            from .gui import run_gui
        except ImportError as exc:
            print(f"GUI недоступен: {exc}. Используйте CLI.", file=sys.stderr)
            return 2
        return run_gui()

    setup_logging(
        verbose=bool(args.verbose),
        log_file=Path(args.log_file).expanduser() if args.log_file else None,
    )

    try:
        settings = _build_settings(args)
    except (ConfigError, WorkshopError, ValueError) as exc:
        log.error("%s", exc)
        return 2

    try:
        if args.list:
            api = SteamAPI(timeout=settings.timeout)
            root = Resolver(api).resolve(
                settings.target, settings.target_type, ConsoleEvents()
            )
            print_tree(root)
            return 0

        summary = Downloader().run(settings, events=ConsoleEvents())
        return 0 if summary.ok else (130 if summary.canceled else 1)
    except KeyboardInterrupt:
        log.warning("Отменено пользователем.")
        return 130
    except WorkshopError as exc:
        log.error("%s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
