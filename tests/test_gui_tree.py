"""GUI tree regression tests.

The check tree is a Tk widget, so these tests need a display.  They are
skipped on headless machines instead of failing.
"""

from __future__ import annotations

import tkinter as tk

import pytest

from steam_workshop_dl.core.models import NodeKind, WorkshopNode
from steam_workshop_dl.ui.gui_tree import CheckTree


@pytest.fixture()
def tree() -> CheckTree:
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - depends on the environment
        pytest.skip(f"no display: {exc}")
    root.withdraw()
    widget = CheckTree(root, on_change=lambda: None)
    widget.pack()
    yield widget
    root.destroy()


def _node_tree() -> WorkshopNode:
    root = WorkshopNode(id="100", kind=NodeKind.COLLECTION, title="Root")
    child = WorkshopNode(
        id="1", kind=NodeKind.ITEM, title="One", size=1024, selectable=True
    )
    root.children.append(child)
    return root


def test_tree_does_not_shadow_tk_root(tree: CheckTree) -> None:
    """``self._root`` is a tkinter method; overwriting it breaks every call."""

    root = _node_tree()
    tree.populate(root)

    # These calls go through tkinter and used to raise
    # ``'WorkshopNode' object is not callable``.
    assert tree.exists("100")
    assert tree.exists("1")
    assert tree.get_children("") == ("100",)


def test_rendering_uses_expected_columns(tree: CheckTree) -> None:
    tree.populate(_node_tree())

    assert "Root" in tree.item("100", "text")
    assert tree.item("1", "values")[0] != ""


def test_click_toggles_checkbox_without_crashing(tree: CheckTree) -> None:
    root = _node_tree()
    tree.populate(root)
    child = root.children[0]

    assert child.selected is True
    tree._toggle(child)
    assert child.selected is False
    assert "☐" in tree.item("1", "text")
