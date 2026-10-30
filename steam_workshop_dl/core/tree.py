"""Pure helpers for walking and selecting nodes in a resolved tree."""

from __future__ import annotations

from collections.abc import Iterator

from .models import ItemStatus, NodeKind, WorkshopNode


def iter_items(root: WorkshopNode) -> Iterator[WorkshopNode]:
    for node in root.walk():
        if node.kind is NodeKind.ITEM:
            yield node


def find_node(root: WorkshopNode, item_id: str) -> WorkshopNode | None:
    for node in root.walk():
        if node.id == item_id:
            return node
    return None


def set_selected(root: WorkshopNode, selected: bool) -> None:
    """Select or deselect every selectable node in the subtree."""

    for node in root.walk():
        if node.selectable:
            node.selected = selected


def toggle_selected(node: WorkshopNode) -> None:
    if not node.selectable:
        return
    target = not node.selected
    if node.kind is NodeKind.COLLECTION:
        set_selected(node, target)
    else:
        node.selected = target


def sync_collection_state(root: WorkshopNode) -> None:
    """Recalculate collection glyph state after child changes.

    Collections are not clickable in the CLI, but the GUI uses this to draw
    ``☑`` / ``◐`` / ``☐``.  The function is intentionally pure.
    """

    for node in reversed(list(root.walk())):
        if node.kind is not NodeKind.COLLECTION:
            continue
        selectable = [child for child in node.children if child.selectable]
        if not selectable:
            node.selected = False
            continue
        chosen = sum(1 for child in selectable if child.selected)
        node.selected = chosen == len(selectable)
        if chosen == 0:
            node.status = ItemStatus.SKIPPED


def selected_items(root: WorkshopNode, *, only: set[str] | None = None,
                   exclude: set[str] | None = None) -> list[WorkshopNode]:
    """Flatten selection, preserving tree order and removing duplicates."""

    only = only or set()
    exclude = exclude or set()
    seen: set[str] = set()
    result: list[WorkshopNode] = []
    for node in root.selected_items():
        if node.id in seen or node.id in exclude:
            continue
        if only and node.id not in only:
            continue
        seen.add(node.id)
        result.append(node)
    return result


def counts(root: WorkshopNode) -> tuple[int, int]:
    return root.counts()
