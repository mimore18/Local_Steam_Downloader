#!/usr/bin/env python3
"""Launch the interactive CLI.

Run without arguments for the step-by-step wizard.  Any arguments are passed
to the regular CLI, so flags such as ``--login`` and ``--dry-run`` keep working.
"""

from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) > 1:
        from steam_workshop_dl.ui.cli import main as cli_main

        return cli_main(sys.argv[1:])

    from steam_workshop_dl.ui.cli import interactive_main

    return interactive_main()


if __name__ == "__main__":
    raise SystemExit(main())
