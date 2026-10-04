"""`build.py <черновик.md> [--preset ID] [--output путь.docx]` — Markdown → .docx по ГОСТ."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from normokontrol.cli import run
from normokontrol.document.build import build_file


def main(argv: Sequence[str]) -> str:
    parser = argparse.ArgumentParser(
        prog="build.py", description="Собирает .docx по ГОСТ 7.32-2017 из черновика в Markdown."
    )
    parser.add_argument("input", type=Path, help="черновик .md")
    parser.add_argument("--preset", help="id пресета (по умолчанию — из блока параметров или gost-7.32-2017)")
    parser.add_argument("--output", type=Path, help="куда сохранить (по умолчанию <имя>_gost.docx рядом)")
    args = parser.parse_args(argv)

    result = build_file(args.input, preset_id=args.preset, output=args.output)
    counts = ", ".join(f"{name}: {value}" for name, value in result.stats.items())
    lines = [f"Готово: {result.output}", counts]
    if result.warnings:
        lines += ["", "Предупреждения:"] + [f"- {warning}" for warning in result.warnings]
    lines += [
        "",
        "Оглавление и номера страниц Word обновит при открытии (подтвердите обновление полей).",
    ]
    return "\n".join(lines)


def entry() -> int:
    return run(main)
