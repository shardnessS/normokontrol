"""`format_bibliography.py <file|-> [--order] [--preset] [--json]` — reference list, GOST R 7.0.100-2018.

The input list may mix structured sources and strings with a DOI, ISBN or URL: those are looked up.
Strings that cannot be resolved are returned as «нужно уточнить» for Claude to structure.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import TypeAdapter, ValidationError
from pydantic_core import ErrorDetails

from normokontrol.bibliography import formatter, lookup
from normokontrol.bibliography.identifiers import classify
from normokontrol.bibliography.models import SOURCE_TYPES, Source
from normokontrol.cli import run
from normokontrol.errors import InputError, format_validation_error
from normokontrol.presets import loader

_SOURCE: TypeAdapter[Source] = TypeAdapter(Source)


@dataclass
class Unresolved:
    index: int
    input: str
    reason: str
    error_code: str


@dataclass
class Resolved:
    index: int
    input: str
    source: Source


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

    sources, indices, looked_up, unresolved = _resolve(raw_items, location=args.input)
    style = formatter.Style(dash=preset.bibliography.dash, content_type=preset.bibliography.content_type)
    result = formatter.format_bibliography(
        sources, order=order, numbering=preset.bibliography.numbering, style=style, indices=indices
    )
    warnings = [
        f"Источник {item.index} («{item.input}») найден автоматически — сверьте данные с оригиналом"
        for item in looked_up
    ] + [warning.message_ru for warning in result.warnings]

    if args.json:
        payload = {
            "text": result.text,
            "entries": result.entries,
            "warnings": [vars(warning) for warning in result.warnings],
            "looked_up": [
                {"index": item.index, "input": item.input, "source": source_to_dict(item.source)}
                for item in looked_up
            ],
            "unresolved": [vars(item) for item in unresolved],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
    sections = [result.text] if result.text else []
    if warnings:
        sections.append(
            "Предупреждения (данные нужно уточнить у пользователя):\n"
            + "\n".join(f"- {message}" for message in warnings)
        )
    if unresolved:
        sections.append(
            "Не удалось оформить автоматически (структурируйте эти источники и запустите снова):\n"
            + "\n".join(f"- {item.index}. «{item.input}»: {item.reason}" for item in unresolved)
        )
    return "\n\n".join(sections)


def _resolve(
    raw_items: list[Any], *, location: str
) -> tuple[list[Source], list[int], list[Resolved], list[Unresolved]]:
    sources: list[Source] = []
    indices: list[int] = []
    looked_up: list[Resolved] = []
    unresolved: list[Unresolved] = []
    errors: list[str] = []
    for index, item in enumerate(raw_items, start=1):
        if isinstance(item, str):
            identifier = classify(item)
            if identifier is None:
                unresolved.append(
                    Unresolved(
                        index,
                        item,
                        "не распознан DOI, ISBN или ссылка — нужны данные источника",
                        "unrecognized",
                    )
                )
                continue
            try:
                source = lookup.lookup(identifier, original=item)
            except lookup.LookupFailed as exc:
                unresolved.append(Unresolved(index, item, exc.message_ru, exc.error_code))
                continue
            looked_up.append(Resolved(index, item, source))
        elif isinstance(item, dict):
            try:
                source = _SOURCE.validate_python(item)
            except ValidationError as exc:
                errors += [_source_error(index, err) for err in exc.errors()]
                continue
        else:
            errors.append(f"источник {index}: ожидался объект источника или строка с DOI, ISBN, ссылкой")
            continue
        sources.append(source)
        indices.append(index)
    if errors:
        details = "\n".join(f"- {message}" for message in errors)
        raise InputError(f"Ошибки в данных источников:\n{details}", location=location)
    return sources, indices, looked_up, unresolved


def read_data(path: str) -> Any:
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


def source_to_dict(source: Source) -> dict[str, Any]:
    """Source as JSON without empty fields — ready to paste into sources.json."""
    data = source.model_dump(mode="json", exclude_none=True)
    return {key: value for key, value in data.items() if value != []}


def _source_error(index: int, err: ErrorDetails) -> str:
    """«источник 3 (book), authors: …» instead of pydantic's «book.authors»."""
    loc = list(err["loc"])
    prefix = f"источник {index}"
    if loc and str(loc[0]) in SOURCE_TYPES:
        prefix += f" ({loc[0]})"
        loc = loc[1:]
    message = format_validation_error({**err, "loc": tuple(loc)})
    return f"{prefix}, {message}"


def entry() -> int:
    return run(main)
