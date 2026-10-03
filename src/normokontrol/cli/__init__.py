"""Command-line entry points used by the skill scripts."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence

from normokontrol.errors import NormokontrolError

EXIT_OK = 0
EXIT_ERROR = 2


def run(main: Callable[[Sequence[str]], str], argv: Sequence[str] | None = None) -> int:
    """Run a command: print its output, or a structured error to stderr; return the exit code."""
    _utf8_streams()
    try:
        output = main(sys.argv[1:] if argv is None else argv)
    except NormokontrolError as exc:
        print(json.dumps(exc.to_dict(), ensure_ascii=False), file=sys.stderr)
        return EXIT_ERROR
    sys.stdout.write(output if output.endswith("\n") else output + "\n")
    return EXIT_OK


def _utf8_streams() -> None:
    """Cyrillic output must survive a Windows console with a legacy code page."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
