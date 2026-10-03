"""`format_bibliography.py <file|-> [--order] [--preset] [--json]` — reference list, GOST R 7.0.100-2018."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml
from pydantic import TypeAdapter, ValidationError
from pydantic_core import ErrorDetails

from normokontrol.bibliography import formatter
from normokontrol.bibliography.models import Source
from normokontrol.cli import run
from normokontrol.errors import InputError, format_validation_error
from normokontrol.presets import loader

_SOURCES = TypeAdapter(list[Source])
_SOURCE_TYPES = frozenset({"book", "article", "web", "law", "standard"})


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

    data = _read(args.input)
    if isinstance(data, dict):
        options, raw_sources = data, data.get("sources")
    else:
        options, raw_sources = {}, data
    if not isinstance(raw_sources, list):
        raise InputError("Ожидался список источников или словарь с ключом «sources»", location=args.input)
    try:
        sources = _SOURCES.validate_python(raw_sources)
    except ValidationError as exc:
        details = "\n".join(f"- {_source_error(err)}" for err in exc.errors())
        raise InputError(f"Ошибки в данных источников:\n{details}", location=args.input) from None

    preset = loader.load_preset(args.preset or options.get("preset") or "gost-7.32-2017")
    style = formatter.Style(dash=preset.bibliography.dash, content_type=preset.bibliography.content_type)
    order = args.order or options.get("order") or preset.bibliography.order
    if order not in ("by_citation", "alphabetical"):
        raise InputError(f"Неизвестный порядок «{order}»: допустимо by_citation или alphabetical")
    result = formatter.format_bibliography(
        sources, order=order, numbering=preset.bibliography.numbering, style=style
    )

    if args.json:
        payload = {
            "text": result.text,
            "entries": result.entries,
            "warnings": [vars(warning) for warning in result.warnings],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
    lines = [result.text]
    if result.warnings:
        lines += ["", "Предупреждения (данные нужно уточнить у пользователя):"]
        lines += [f"- {warning.message_ru}" for warning in result.warnings]
    return "\n".join(lines)


def _read(path: str) -> Any:
    try:
        text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"Не удалось прочитать файл «{path}»: {exc.strerror}", location=path) from None
    except UnicodeDecodeError:
        raise InputError(f"Файл «{path}» должен быть в кодировке UTF-8", location=path) from None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise InputError(f"Файл «{path}» не является корректным JSON/YAML: {exc}", location=path) from None


def _source_error(err: ErrorDetails) -> str:
    """«источник 3 (book), authors: …» instead of pydantic's «2.book.authors»."""
    loc = list(err["loc"])
    prefix = ""
    index = loc[0] if loc else None
    if isinstance(index, int):
        prefix = f"источник {index + 1}"
        loc = loc[1:]
        if loc and str(loc[0]) in _SOURCE_TYPES:
            prefix += f" ({loc[0]})"
            loc = loc[1:]
    message = format_validation_error({**err, "loc": tuple(loc)})
    return f"{prefix}, {message}" if prefix else message


def entry() -> int:
    return run(main)
