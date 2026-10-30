"""Plain data models shared by every layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Iterator


class NodeKind(StrEnum):
    COLLECTION = "collection"
    ITEM = "item"


class ItemStatus(StrEnum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"
    CANCELED = "canceled"


@dataclass(slots=True)
class WorkshopNode:
    """A collection or workshop item in the resolved tree."""

    id: str
    kind: NodeKind
    title: str = ""
    appid: int | None = None
    size: int | None = None
    time_updated: int | None = None
    visibility: int | None = None
    banned: bool = False
    selectable: bool = True
    selected: bool = True
    status: ItemStatus = ItemStatus.PENDING
    children: list["WorkshopNode"] = field(default_factory=list)

    def walk(self) -> Iterator["WorkshopNode"]:
        yield self
        for child in self.children:
            yield from child.walk()

    def items(self) -> Iterator["WorkshopNode"]:
        for node in self.walk():
            if node.kind is NodeKind.ITEM:
                yield node

    def selected_items(self) -> Iterator["WorkshopNode"]:
        for node in self.items():
            if node.selected and node.selectable:
                yield node

    def total_size(self, *, selected_only: bool = True) -> int:
        total = 0
        for node in self.items():
            if selected_only and not (node.selected and node.selectable):
                continue
            total += node.size or 0
        return total

    def counts(self) -> tuple[int, int]:
        """Return (available items, selected items)."""

        available = selected = 0
        for node in self.items():
            if not node.selectable:
                continue
            available += 1
            if node.selected:
                selected += 1
        return available, selected


@dataclass(slots=True)
class Settings:
    """Runtime configuration assembled from CLI, config file and defaults."""

    target: str = ""
    target_type: str = "collection"
    output_dir: Path = field(default_factory=lambda: Path.home() / "Downloads" / "workshop")
    steamcmd: Path | None = None
    bootstrap_steamcmd: bool = True
    auth_mode: str = "anonymous"
    username: str | None = None
    validate: bool = False
    zip_items: bool = False
    by_app: bool = False
    flat: bool = False
    resume: bool = True
    force: bool = False
    retries: int = 2
    metadata_workers: int = 4
    timeout: float = 30.0
    dry_run: bool = False
    only: set[str] = field(default_factory=set)
    exclude: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.output_dir = Path(self.output_dir).expanduser()
        if self.target_type not in {"collection", "mod"}:
            raise ValueError(f"unknown target type: {self.target_type!r}")
        if self.auth_mode not in {"anonymous", "login"}:
            raise ValueError(f"unknown auth mode: {self.auth_mode!r}")


@dataclass(slots=True)
class Summary:
    done: int = 0
    skipped: int = 0
    failed: int = 0
    unavailable: int = 0
    canceled: int = 0
    total_bytes: int = 0
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return self.failed == 0 and self.canceled == 0

    def as_text(self) -> str:
        parts = [
            f"скачано: {self.done}",
            f"пропущено: {self.skipped}",
            f"ошибок: {self.failed}",
            f"недоступно: {self.unavailable}",
        ]
        if self.canceled:
            parts.append(f"отменено: {self.canceled}")
        return ", ".join(parts)
