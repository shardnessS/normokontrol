"""Recognise a DOI, ISBN or URL in a free-form string."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Kind = Literal["doi", "isbn", "url"]

_DOI = re.compile(r"(10\.\d{4,9}/\S+)")
_DOI_PREFIX = re.compile(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)", re.IGNORECASE)
_ISBN_PREFIX = re.compile(r"^isbn(?:-1[03])?:?\s*", re.IGNORECASE)
_URL = re.compile(r"^https?://\S+$", re.IGNORECASE)


@dataclass(frozen=True)
class Identifier:
    kind: Kind
    value: str  # DOI без префикса, ISBN только из цифр (и X), URL как есть


def classify(text: str) -> Identifier | None:
    """DOI, ISBN or URL if the whole string is one of them, otherwise None."""
    text = text.strip().rstrip(".")
    if not text:
        return None
    if _DOI_PREFIX.match(text) or text.startswith("10."):
        match = _DOI.search(_DOI_PREFIX.sub("", text))
        if match:
            return Identifier("doi", match.group(1))
    if _URL.match(text):
        return Identifier("url", text)
    isbn = normalize_isbn(text)
    if isbn is not None:
        return Identifier("isbn", isbn)
    return None


def normalize_isbn(text: str) -> str | None:
    """«ISBN 978-5-534-00129-7» → «9785534001297» if the checksum is valid."""
    candidate = _ISBN_PREFIX.sub("", text.strip())
    if not re.fullmatch(r"[\dXx\- ]+", candidate):
        return None
    digits = re.sub(r"[\- ]", "", candidate).upper()
    if len(digits) == 13 and digits.isdigit():
        total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:12]))
        return digits if (10 - total % 10) % 10 == int(digits[12]) else None
    if len(digits) == 10 and digits[:9].isdigit() and (digits[9].isdigit() or digits[9] == "X"):
        total = sum(int(d) * (10 - i) for i, d in enumerate(digits[:9]))
        check = 10 if digits[9] == "X" else int(digits[9])
        return digits if (total + check) % 11 == 0 else None
    return None
