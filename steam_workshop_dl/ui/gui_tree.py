"""Checkbox-capable Treeview used by the GUI.

Tkinter has no native checkboxes inside Treeview, so the glyph is part of the
tree cell and the first ~28 px of that cell act as the hit area.  The arrow
indicator keeps its default expand/collapse behaviour.
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


class CheckTree(ttk.Treeview):
    def __init__(self, master: tk.Misc, on_change: Callable[[], None]) -> None:
        super().__init__(master, columns=("size", "status"), show="tree headings", selectmode="browse")
        self.heading("#0", text="Название")
        self.heading("size", text="Размер")
        self.heading("status", text="Статус")
        self.column("#0", width=520, minwidth=260)
        self.column("size", width=100, anchor="e", stretch=False)
        self.column("status", width=120, anchor="w", stretch=False)
        self.tag_configure("unavailable", foreground="#888888")
        self._nodes: dict[str, WorkshopNode] = {}
        self._root: WorkshopNode | None = None
        self._on_change = on_change
        self.bind("<Button-1>", self._on_click)
        self.bind("<space>", self._on_space)

    def populate(self, root: WorkshopNode) -> None:
        self.delete(*self.get_children())
        self._nodes.clear()
        self._root = root
        self._insert(root, "")
        self.item(root.id, open=True)
        self.selection_set(root.id)

    def _insert(self, node: WorkshopNode, parent: str) -> None:
        self._nodes[node.id] = node
        self.insert(
            parent,
            "end",
            iid=node.id,
            text=f"{glyph(node)} {node.title or 'item'} [{node.id}]",
            values=(human_size(node.size) if node.kind is NodeKind.ITEM else "", STATUS_TEXT.get(node.status, "")),
            tags=("unavailable",) if not node.selectable else (),
        )
        for child in node.children:
            self._insert(child, node.id)

    def _on_click(self, event: tk.Event) -> str | None:
        row = self.identify_row(event.y)
        if not row:
            return None
        if "indicator" in (self.identify_element(event.x, event.y) or ""):
            return None
        bbox = self.bbox(row, "#0")
        if not bbox or event.x > bbox[0] + 28:
            return None
        node = self._nodes.get(row)
        if node is None:
            return None
        toggle_selected(node)
        if self._root is not None:
            sync_collection_state(self._root)
        self.refresh()
        self._on_change()
        return "break"

    def _on_space(self, _event: tk.Event) -> str:
        row = self.focus()
        node = self._nodes.get(row)
        if node is not None:
            toggle_selected(node)
            if self._root is not None:
                sync_collection_state(self._root)
            self.refresh()
            self._on_change()
        return "break"

    def select_all(self, selected: bool) -> None:
        if self._root is None:
            return
        set_selected(self._root, selected)
        self.refresh()
        self._on_change()

    def refresh(self) -> None:
        for item_id, node in self._nodes.items():
            if not self.exists(item_id):
                continue
            self.item(
                item_id,
                text=f"{glyph(node)} {node.title or 'item'} [{node.id}]",
                values=(
                    human_size(node.size) if node.kind is NodeKind.ITEM else "",
                    STATUS_TEXT.get(node.status, ""),
                ),
                tags=("unavailable",) if not node.selectable else (),
            )

    def update_status(self, item_id: str, status: ItemStatus) -> None:
        node = self._nodes.get(item_id)
        if node is None:
            return
        node.status = status
        if self.exists(item_id):
            self.set(item_id, "status", STATUS_TEXT.get(status, ""))
