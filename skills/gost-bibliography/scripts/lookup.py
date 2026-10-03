#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2.7,<3", "pyyaml>=6"]
# ///
"""Source metadata by DOI, ISBN or URL: lookup.py 10.1016/... 978-5-534-00129-7 https://..."""

import sys
from pathlib import Path


def _find_core() -> None:
    here = Path(__file__).resolve().parent
    # Собранный скилл: ядро лежит рядом (scripts/normokontrol). Плагин Claude Code: src/ репозитория.
    for root in (here, here.parent.parent.parent / "src"):
        if (root / "normokontrol" / "__init__.py").is_file():
            sys.path.insert(0, str(root))
            return
    sys.exit("Не найдено ядро normokontrol: переустановите скилл.")


_find_core()

from normokontrol.cli.lookup import entry  # noqa: E402

sys.exit(entry())
