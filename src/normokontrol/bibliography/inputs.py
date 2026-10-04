"""Reading source lists: JSON/YAML files, structured objects mixed with DOI/ISBN/URL strings."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import TypeAdapter, ValidationError
from pydantic_core import ErrorDetails

from normokontrol.bibliography import lookup
from normokontrol.bibliography.identifiers import classify
from normokontrol.bibliography.models import SOURCE_TYPES, Source
from normokontrol.errors import InputError, format_validation_error

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


@dataclass
class SourceList:
    sources: list[Source] = field(default_factory=list)
    indices: list[int] = field(default_factory=list)  # 1-based positions in the input
    looked_up: list[Resolved] = field(default_factory=list)
    unresolved: list[Unresolved] = field(default_factory=list)


def read_data(path: str) -> Any:
    """JSON or YAML from a file, or from stdin for «-»."""
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


def resolve(items: list[Any], *, location: str) -> SourceList:
    """Validate objects and look up DOI/ISBN/URL strings. Invalid objects raise one InputError."""
    result = SourceList()
    errors: list[str] = []
    for index, item in enumerate(items, start=1):
        if isinstance(item, str):
            identifier = classify(item)
            if identifier is None:
                reason = "не распознан DOI, ISBN или ссылка — нужны данные источника"
                result.unresolved.append(Unresolved(index, item, reason, "unrecognized"))
                continue
            try:
                source = lookup.lookup(identifier, original=item)
            except lookup.LookupFailed as exc:
                result.unresolved.append(Unresolved(index, item, exc.message_ru, exc.error_code))
                continue
            result.looked_up.append(Resolved(index, item, source))
        elif isinstance(item, dict):
            try:
                source = _SOURCE.validate_python(item)
            except ValidationError as exc:
                errors += [_source_error(index, err) for err in exc.errors()]
                continue
        else:
            errors.append(f"источник {index}: ожидался объект источника или строка с DOI, ISBN, ссылкой")
            continue
        result.sources.append(source)
        result.indices.append(index)
    if errors:
        details = "\n".join(f"- {message}" for message in errors)
        raise InputError(f"Ошибки в данных источников:\n{details}", location=location)
    return result


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
