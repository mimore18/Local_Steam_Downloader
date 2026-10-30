#!/usr/bin/env python3
"""Launch the Tkinter GUI from the project root."""

from __future__ import annotations

import sys


def main() -> int:
    from steam_workshop_dl.ui.gui import main as gui_main

    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
