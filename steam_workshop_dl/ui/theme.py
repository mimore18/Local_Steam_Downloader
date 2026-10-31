"""Light and dark palettes for the Tkinter GUI.

The GUI uses the ``clam`` ttk theme because it lets us paint every widget
consistently on Linux and Windows.  A palette is also returned to the caller so
plain Tk widgets (Text, Toplevel) and Treeview tags can be recoloured too.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

DEFAULT_THEME = "light"

PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#f2f2f2",
        "surface": "#e7e7e7",
        "field": "#ffffff",
        "fg": "#1f1f1f",
        "muted": "#666666",
        "border": "#b8b8b8",
        "hover": "#dedede",
        "pressed": "#cfcfcf",
        "select": "#306acb",
        "select_fg": "#ffffff",
        "link": "#0b5cad",
        "done": "#1b7f3b",
        "failed": "#b00020",
        "unavailable": "#888888",
    },
    "dark": {
        "bg": "#1e1f22",
        "surface": "#2b2d30",
        "field": "#141518",
        "fg": "#e8e8e8",
        "muted": "#a0a4aa",
        "border": "#3c3f44",
        "hover": "#35373b",
        "pressed": "#3f4247",
        "select": "#2f65b0",
        "select_fg": "#ffffff",
        "link": "#79b8ff",
        "done": "#6fcf8f",
        "failed": "#ff7b72",
        "unavailable": "#8b9098",
    },
}


def normalize_theme(value: str | None) -> str | None:
    """Return a supported theme name for *value*, or ``None``."""

    if not value:
        return None
    cleaned = value.strip().lower()
    return cleaned if cleaned in PALETTES else None


def palette(theme: str | None) -> dict[str, str]:
    """Return the palette for *theme*, falling back to the default."""

    return PALETTES[normalize_theme(theme) or DEFAULT_THEME]


def apply_theme(root: tk.Misc, theme: str | None) -> dict[str, str]:
    """Apply *theme* to ttk and plain Tk widgets and return its palette."""

    colors = palette(theme)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:  # pragma: no cover - clam ships with Tk
        pass

    root.configure(background=colors["bg"])
    root.option_add("*TCombobox*Listbox.background", colors["field"])
    root.option_add("*TCombobox*Listbox.foreground", colors["fg"])
    root.option_add(
        "*TCombobox*Listbox.selectBackground", colors["select"]
    )
    root.option_add("*TCombobox*Listbox.selectForeground", colors["select_fg"])
    root.option_add("*Entry.insertBackground", colors["fg"])
    root.option_add("*Text.insertBackground", colors["fg"])

    style.configure(
        ".",
        background=colors["bg"],
        foreground=colors["fg"],
        fieldbackground=colors["field"],
        bordercolor=colors["border"],
        lightcolor=colors["border"],
        darkcolor=colors["border"],
        troughcolor=colors["bg"],
        selectbackground=colors["select"],
        selectforeground=colors["select_fg"],
    )

    style.configure("TFrame", background=colors["bg"])
    style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])

    style.configure(
        "TButton",
        background=colors["surface"],
        foreground=colors["fg"],
        bordercolor=colors["border"],
        lightcolor=colors["surface"],
        darkcolor=colors["surface"],
        focuscolor=colors["select"],
        padding=(8, 4),
    )
    style.map(
        "TButton",
        background=[
            ("disabled", colors["bg"]),
            ("pressed", colors["pressed"]),
            ("active", colors["hover"]),
        ],
        foreground=[("disabled", colors["muted"])],
        bordercolor=[("focus", colors["select"])],
    )

    for name in ("TRadiobutton", "TCheckbutton"):
        style.configure(
            name,
            background=colors["bg"],
            foreground=colors["fg"],
            indicatorbackground=colors["field"],
            indicatorforeground=colors["select"],
            indicatorcolor=colors["select"],
        )
        style.map(
            name,
            background=[("active", colors["bg"])],
            foreground=[("disabled", colors["muted"])],
            indicatorbackground=[
                ("disabled", colors["bg"]),
                ("selected", colors["field"]),
            ],
            indicatorforeground=[("disabled", colors["muted"])],
        )

    style.configure(
        "TEntry",
        fieldbackground=colors["field"],
        foreground=colors["fg"],
        insertcolor=colors["fg"],
        bordercolor=colors["border"],
        lightcolor=colors["border"],
        darkcolor=colors["border"],
        padding=3,
    )
    style.map(
        "TEntry",
        fieldbackground=[("disabled", colors["bg"])],
        foreground=[("disabled", colors["muted"])],
        bordercolor=[("focus", colors["select"])],
    )

    style.configure(
        "TCombobox",
        fieldbackground=colors["field"],
        background=colors["surface"],
        foreground=colors["fg"],
        arrowcolor=colors["fg"],
        bordercolor=colors["border"],
        lightcolor=colors["border"],
        darkcolor=colors["border"],
        padding=2,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("disabled", colors["bg"]), ("readonly", colors["field"])],
        foreground=[("disabled", colors["muted"]), ("readonly", colors["fg"])],
        arrowcolor=[("disabled", colors["muted"])],
        selectbackground=[("readonly", colors["field"])],
        selectforeground=[("readonly", colors["fg"])],
        bordercolor=[("focus", colors["select"])],
    )

    style.configure(
        "TLabelframe",
        background=colors["bg"],
        foreground=colors["fg"],
        bordercolor=colors["border"],
        lightcolor=colors["border"],
        darkcolor=colors["border"],
    )
    style.configure(
        "TLabelframe.Label", background=colors["bg"], foreground=colors["fg"]
    )

    style.configure(
        "Treeview",
        background=colors["field"],
        fieldbackground=colors["field"],
        foreground=colors["fg"],
        bordercolor=colors["border"],
        lightcolor=colors["border"],
        darkcolor=colors["border"],
        rowheight=24,
    )
    style.map(
        "Treeview",
        background=[("selected", colors["select"])],
        foreground=[("selected", colors["select_fg"])],
    )
    style.configure(
        "Treeview.Heading",
        background=colors["surface"],
        foreground=colors["fg"],
        bordercolor=colors["border"],
        lightcolor=colors["border"],
        darkcolor=colors["border"],
        relief="flat",
        padding=(6, 4),
    )
    style.map(
        "Treeview.Heading",
        background=[("pressed", colors["pressed"]), ("active", colors["hover"])],
    )

    style.configure(
        "TScrollbar",
        background=colors["surface"],
        troughcolor=colors["bg"],
        bordercolor=colors["border"],
        arrowcolor=colors["fg"],
        lightcolor=colors["border"],
        darkcolor=colors["border"],
    )
    style.map(
        "TScrollbar",
        background=[("pressed", colors["pressed"]), ("active", colors["hover"])],
    )

    style.configure(
        "TProgressbar",
        background=colors["select"],
        troughcolor=colors["field"],
        bordercolor=colors["border"],
        lightcolor=colors["select"],
        darkcolor=colors["select"],
    )

    style.configure("TPanedwindow", background=colors["bg"])
    style.configure(
        "Sash",
        background=colors["border"],
        lightcolor=colors["border"],
        darkcolor=colors["border"],
        sashthickness=6,
    )

    return colors


def style_text(widget: tk.Text, colors: dict[str, str]) -> None:
    """Recolour a plain Tk Text widget (the log view)."""

    widget.configure(
        background=colors["field"],
        foreground=colors["fg"],
        insertbackground=colors["fg"],
        selectbackground=colors["select"],
        selectforeground=colors["select_fg"],
        highlightbackground=colors["border"],
        highlightcolor=colors["border"],
        highlightthickness=1,
        relief="flat",
        borderwidth=0,
    )
