"""`presets.py list | rules <id> | yaml <id>` — formatting presets for the gost-rules skill."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from normokontrol.cli import run
from normokontrol.presets import loader
from normokontrol.presets.describe import describe_preset


def main(argv: Sequence[str]) -> str:
    parser = argparse.ArgumentParser(prog="presets.py", description="Пресеты оформления (ГОСТ и вузы).")
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="список пресетов")
    listing.add_argument("--country", help="код страны, например RU")
    listing.add_argument("--json", action="store_true", help="вывод в JSON")
    rules = commands.add_parser("rules", help="требования пресета человеческим языком")
    rules.add_argument("preset_id")
    dump = commands.add_parser("yaml", help="пресет после наследования в YAML")
    dump.add_argument("preset_id")
    args = parser.parse_args(argv)

    if args.command == "list":
        summaries = loader.list_presets(args.country)
        if args.json:
            return json.dumps([s.model_dump() for s in summaries], ensure_ascii=False, indent=2)
        return "\n".join(_summary_line(s) for s in summaries) or "Пресеты не найдены."
    preset = loader.load_preset(args.preset_id)
    if args.command == "rules":
        return describe_preset(preset)
    return loader.dump_yaml(preset)


def _summary_line(summary: loader.PresetSummary) -> str:
    if summary.error:
        return f"{summary.id} — ОШИБКА: {summary.error}"
    verified = "сверен с первоисточником" if summary.verified else "НЕ сверен с методичкой"
    parent = f", основан на {summary.extends}" if summary.extends else ""
    return f"{summary.id} — {summary.name} ({summary.country}, {verified}{parent})"


def entry() -> int:
    return run(main)
