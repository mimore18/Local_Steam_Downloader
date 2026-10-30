"""Event boundary between the application core and its UI shells."""

from __future__ import annotations

from typing import Protocol

from .models import ItemStatus, Summary, WorkshopNode


class Events(Protocol):
    """Implemented by CLI and GUI adapters.

    Every method must be cheap and thread-safe.  The GUI adapter only enqueues
    messages and never touches Tk widgets from a worker thread.
    """

    def log(self, level: str, message: str) -> None: ...

    def tree_ready(self, root: WorkshopNode) -> None: ...

    def tree_updated(self, root: WorkshopNode) -> None: ...

    def metadata_updated(self, root: WorkshopNode) -> None: ...

    def item_status(self, item_id: str, status: ItemStatus, detail: str = "") -> None: ...

    def progress(self, done: int, total: int, current_id: str | None) -> None: ...

    def finished(self, summary: Summary) -> None: ...


class NullEvents:
    """No-op implementation for tests and headless preview calls."""

    def log(self, level: str, message: str) -> None:
        pass

    def tree_ready(self, root: WorkshopNode) -> None:
        pass

    def tree_updated(self, root: WorkshopNode) -> None:
        pass

    def metadata_updated(self, root: WorkshopNode) -> None:
        pass

    def item_status(self, item_id: str, status: ItemStatus, detail: str = "") -> None:
        pass

    def progress(self, done: int, total: int, current_id: str | None) -> None:
        pass

    def finished(self, summary: Summary) -> None:
        pass
