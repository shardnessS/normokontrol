"""`format_bibliography.py <file|-> [--order] [--preset] [--json]` — reference list, GOST R 7.0.100-2018.

The input list may mix structured sources and strings with a DOI, ISBN or URL: those are looked up.
Strings that cannot be resolved are returned as «нужно уточнить» for Claude to structure.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from normokontrol.bibliography import formatter
from normokontrol.bibliography.inputs import read_data, resolve, source_to_dict
from normokontrol.cli import run
from normokontrol.errors import InputError
from normokontrol.presets import loader


def main(argv: Sequence[str]) -> str:
    parser = argparse.ArgumentParser(
        prog="format_bibliography.py",
        description="Список литературы по ГОСТ Р 7.0.100-2018 из файла JSON/YAML со списком источников.",
    )
    parser.add_argument("input", help="файл JSON/YAML или «-» для чтения из stdin")
    parser.add_argument(
        "--order", choices=["by_citation", "alphabetical"], help="порядок (по умолчанию — из пресета)"
    )
    parser.add_argument("--preset", help="id пресета (по умолчанию gost-7.32-2017)")
    parser.add_argument("--json", action="store_true", help="вывод в JSON")
    args = parser.parse_args(argv)

    data = read_data(args.input)
    if isinstance(data, dict):
        options, raw_items = data, data.get("sources")
    else:
        options, raw_items = {}, data
    if not isinstance(raw_items, list):
        raise InputError("Ожидался список источников или словарь с ключом «sources»", location=args.input)

    preset = loader.load_preset(args.preset or options.get("preset") or "gost-7.32-2017")
    order = args.order or options.get("order") or preset.bibliography.order
    if order not in ("by_citation", "alphabetical"):
        raise InputError(f"Неизвестный порядок «{order}»: допустимо by_citation или alphabetical")

    items = resolve(raw_items, location=args.input)
    style = formatter.Style(dash=preset.bibliography.dash, content_type=preset.bibliography.content_type)
    result = formatter.format_bibliography(
        items.sources,
        order=order,
        numbering=preset.bibliography.numbering,
        style=style,
        indices=items.indices,
    )
    warnings = [
        f"Источник {item.index} («{item.input}») найден автоматически — сверьте данные с оригиналом"
        for item in items.looked_up
    ] + [warning.message_ru for warning in result.warnings]

    if args.json:
        payload = {
            "text": result.text,
            "entries": result.entries,
            "warnings": [vars(warning) for warning in result.warnings],
            "looked_up": [
                {"index": item.index, "input": item.input, "source": source_to_dict(item.source)}
                for item in items.looked_up
            ],
            "unresolved": [vars(item) for item in items.unresolved],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
    sections = [result.text] if result.text else []
    if warnings:
        sections.append(
            "Предупреждения (данные нужно уточнить у пользователя):\n"
            + "\n".join(f"- {message}" for message in warnings)
        )
    if items.unresolved:
        sections.append(
            "Не удалось оформить автоматически (структурируйте эти источники и запустите снова):\n"
            + "\n".join(f"- {item.index}. «{item.input}»: {item.reason}" for item in items.unresolved)
        )
    return "\n\n".join(sections)


def entry() -> int:
    return run(main)
