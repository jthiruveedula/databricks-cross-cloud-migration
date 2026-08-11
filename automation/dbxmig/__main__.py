"""Allow ``python -m dbxmig`` as well as the installed ``dbxmig`` entry point."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
