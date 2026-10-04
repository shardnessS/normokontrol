"""`lookup.py <doi|isbn|url> [...]` — find source metadata; prints JSON to confirm with the user."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from typing import Any

from normokontrol.bibliography import lookup
from normokontrol.bibliography.identifiers import classify
from normokontrol.bibliography.inputs import source_to_dict
from normokontrol.cli import run


def main(argv: Sequence[str]) -> str:
    parser = argparse.ArgumentParser(
        prog="lookup.py",
        description="Данные источника по DOI (Crossref), ISBN (Open Library) или ссылке (мета-теги).",
    )
    parser.add_argument("identifiers", nargs="+", help="DOI, ISBN или URL")
    args = parser.parse_args(argv)

    results: list[dict[str, Any]] = []
    for text in args.identifiers:
        identifier = classify(text)
        if identifier is None:
            results.append(
                {"input": text, "error": _error("unrecognized", "Не распознан DOI, ISBN или ссылка")}
            )
            continue
        try:
            source = lookup.lookup(identifier, original=text)
        except lookup.LookupFailed as exc:
            results.append({"input": text, "error": _error(exc.error_code, exc.message_ru)})
            continue
        results.append({"input": text, "source": source_to_dict(source)})
    return json.dumps(results, ensure_ascii=False, indent=2)


def _error(code: str, message: str) -> dict[str, str]:
    return {"error_code": code, "message_ru": message}


def entry() -> int:
    return run(main)
