"""Checkbox-capable Treeview used by the GUI.

Tkinter has no native checkboxes inside Treeview, so the glyph is part of the
tree cell and the first ~28 px of that cell act as the hit area.  The arrow
indicator keeps its default expand/collapse behaviour.

Selection lives on :class:`WorkshopNode` objects, not in the widget, so
filtering or re-rendering never loses the user's choices.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from ..core.models import ItemStatus, NodeKind, WorkshopNode
from ..core.naming import human_size
from ..core.tree import set_selected, sync_collection_state, toggle_selected

STATUS_TEXT = {
    ItemStatus.PENDING: "Ожидает",
    ItemStatus.DOWNLOADING: "Скачивается…",
    ItemStatus.DONE: "Готово",
    ItemStatus.SKIPPED: "Пропущено",
    ItemStatus.FAILED: "Ошибка",
    ItemStatus.UNAVAILABLE: "Недоступен",
    ItemStatus.CANCELED: "Отменено",
}

CHECKBOX_HIT_WIDTH = 28


def glyph(node: WorkshopNode) -> str:
    if not node.selectable:
        return "☐"
    if node.kind is NodeKind.ITEM:
        return "☑" if node.selected else "☐"
    children = [child for child in node.children if child.selectable]
    if not children:
        return "☐"
    chosen = sum(1 for child in children if child.selected)
    if chosen == 0:
        return "☐"
    return "☑" if chosen == len(children) else "◐"


def _matches(node: WorkshopNode, query: str) -> bool:
    if not query:
        return True
    haystack = f"{node.title} {node.id}".casefold()
    return query in haystack


class CheckTree(ttk.Treeview):
    def __init__(self, master: tk.Misc, on_change: Callable[[], None]) -> None:
        super().__init__(
            master,
            columns=("size", "status"),
            show="tree headings",
            selectmode="browse",
        )
        self.heading("#0", text="Название")
        self.heading("size", text="Размер")
        self.heading("status", text="Статус")
        self.column("#0", width=520, minwidth=260)
        self.column("size", width=100, anchor="e", stretch=False)
        self.column("status", width=120, anchor="w", stretch=False)
        self.tag_configure("unavailable", foreground="#888888")
        self.tag_configure("failed", foreground="#b00020")
        self.tag_configure("done", foreground="#1b7f3b")

        self._nodes: dict[str, WorkshopNode] = {}
        self._root: WorkshopNode | None = None
        self._on_change = on_change
        self._query = ""

        self.bind("<Button-1>", self._on_click)
        self.bind("<space>", self._on_space)
        self.bind("<Control-a>", lambda _event: self._select_all_event(True))
        self.bind("<Control-A>", lambda _event: self._select_all_event(True))

    # ------------------------------------------------------------------ data
    def populate(self, root: WorkshopNode) -> None:
        self._root = root
        self._nodes = {node.id: node for node in root.walk()}
        self._render(expand_all=True)
        if self.exists(root.id):
            self.selection_set(root.id)

    def set_filter(self, text: str) -> None:
        """Show only items whose title or id contains *text* (and ancestors)."""

        query = text.strip().casefold()
        if query == self._query:
            return
        self._query = query
        self._render(expand_all=bool(query))

    def clear_filter(self) -> None:
        self.set_filter("")

    def _render(self, *, expand_all: bool = False) -> None:
        open_ids = set(self.get_children("")) | {
            iid for iid in self._nodes if self.exists(iid) and self.item(iid, "open")
        }
        selected = self.focus()
        self.delete(*self.get_children())
        if self._root is None:
            return
        self._insert(self._root, "")
        if expand_all or self._query:
            for iid in list(self._nodes):
                if self.exists(iid) and self._nodes[iid].kind is NodeKind.COLLECTION:
                    self.item(iid, open=True)
        else:
            for iid in open_ids:
                if self.exists(iid):
                    self.item(iid, open=True)
        if selected and self.exists(selected):
            self.selection_set(selected)

    def _visible(self, node: WorkshopNode) -> bool:
        if _matches(node, self._query):
            return True
        if node.kind is NodeKind.COLLECTION:
            return any(self._visible(child) for child in node.children)
        return False

    def _insert(self, node: WorkshopNode, parent: str) -> None:
        if not self._visible(node):
            return
        self._nodes[node.id] = node
        self.insert(
            parent,
            "end",
            iid=node.id,
            text=self._label(node),
            values=self._values(node),
            tags=self._tags(node),
            open=bool(self._query),
        )
        for child in node.children:
            self._insert(child, node.id)

    # ------------------------------------------------------------------ render
    @staticmethod
    def _label(node: WorkshopNode) -> str:
        return f"{glyph(node)} {node.title or f'item {node.id}'} [{node.id}]"

    @staticmethod
    def _values(node: WorkshopNode) -> tuple[str, str]:
        size = human_size(node.size) if node.kind is NodeKind.ITEM else ""
        return size, STATUS_TEXT.get(node.status, "")

    @staticmethod
    def _tags(node: WorkshopNode) -> tuple[str, ...]:
        if not node.selectable:
            return ("unavailable",)
        if node.status is ItemStatus.FAILED:
            return ("failed",)
        if node.status is ItemStatus.DONE:
            return ("done",)
        return ()

    # ------------------------------------------------------------------ events
    def _toggle(self, node: WorkshopNode) -> None:
        toggle_selected(node)
        if self._root is not None:
            sync_collection_state(self._root)
        self.refresh()
        self._on_change()

    def _on_click(self, event: tk.Event) -> str | None:
        row = self.identify_row(event.y)
        if not row:
            return None
        if "indicator" in (self.identify_element(event.x, event.y) or ""):
            return None
        bbox = self.bbox(row, "#0")
        if not bbox or event.x > bbox[0] + CHECKBOX_HIT_WIDTH:
            return None
        node = self._nodes.get(row)
        if node is None or not node.selectable:
            return None
        self._toggle(node)
        return "break"

    def _on_space(self, _event: tk.Event) -> str:
        node = self._nodes.get(self.focus())
        if node is not None and node.selectable:
            self._toggle(node)
        return "break"

    def _select_all_event(self, selected: bool) -> str:
        self.select_all(selected)
        return "break"

    def select_all(self, selected: bool) -> None:
        if self._root is None:
            return
        set_selected(self._root, selected)
        self.refresh()
        self._on_change()

    # ------------------------------------------------------------------ updates
    def refresh(self) -> None:
        for item_id, node in self._nodes.items():
            if not self.exists(item_id):
                continue
            self.item(
                item_id,
                text=self._label(node),
                values=self._values(node),
                tags=self._tags(node),
            )

    def update_status(self, item_id: str, status: ItemStatus) -> None:
        node = self._nodes.get(item_id)
        if node is None:
            return
        node.status = status
        if self.exists(item_id):
            self.item(item_id, values=self._values(node), tags=self._tags(node))
