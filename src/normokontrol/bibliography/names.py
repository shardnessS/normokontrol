"""Personal names: parsing, initials, heading and statement-of-responsibility forms (GOST R 7.0.100-2018)."""

from __future__ import annotations

import re
from dataclasses import dataclass

NBSP = "\u00a0"  # неразрывный пробел
# ГОСТ Р 7.0.100-2018: при сокращении сведений об ответственности приводят имена
# одного–четырёх авторов; при пяти и более — первых трёх и «[и др.]».
MAX_LISTED_AUTHORS = 4
LISTED_BEFORE_ET_AL = 3
# Заголовок записи (имя первого автора перед заглавием) — при одном–трёх авторах;
# при четырёх и более запись составляют под заглавием.
MAX_AUTHORS_IN_HEADING = 3

_CYRILLIC = re.compile(r"[а-яёА-ЯЁ]")
_INITIAL = re.compile(r"^(\w{1,2})\.(?:-(\w{1,2})\.)?$")


class InvalidNameError(ValueError):
    """Raised for a name that cannot be parsed."""


@dataclass(frozen=True)
class PersonName:
    family: str
    initials: tuple[str, ...]  # «И.», «Ж.-П.», «Yu.»

    @property
    def initials_text(self) -> str:
        return NBSP.join(self.initials)

    def heading(self) -> str:
        """«Иванов, И. И.» — form used in the heading of a record."""
        if not self.initials:
            return self.family
        return f"{self.family},{NBSP}{self.initials_text}"

    def statement(self) -> str:
        """«И. И. Иванов» — form used after the slash."""
        if not self.initials:
            return self.family
        return f"{self.initials_text}{NBSP}{self.family}"


def is_cyrillic(text: str) -> bool:
    return bool(_CYRILLIC.search(text))


def parse_name(raw: str) -> PersonName:
    """Parse «Иванов Иван Иванович», «Иванов И. И.», «Иванов, Иван», «И. И. Иванов», «Smith, John»."""
    text = " ".join(raw.replace(NBSP, " ").split())
    if not text:
        raise InvalidNameError("пустое имя автора")
    if "," in text:
        family, _, given = text.partition(",")
        return PersonName(family.strip(), _initials(given))

    # «И.И.Иванов» → «И. И. Иванов»: отделяем инициалы, слитые без пробелов.
    tokens = re.sub(r"(\w\.)(?=\w)", r"\1 ", text).split()
    if _is_initial(tokens[0]):
        split = next((i for i, token in enumerate(tokens) if not _is_initial(token)), len(tokens))
        if split == len(tokens):
            raise InvalidNameError(f"не удалось найти фамилию в имени «{raw}»")
        return PersonName(" ".join(tokens[split:]), _initials(" ".join(tokens[:split])))
    return PersonName(tokens[0], _initials(" ".join(tokens[1:])))


def heading(authors: list[str]) -> str | None:
    """Heading of the record: the first author for 1–3 authors, otherwise none (record under title)."""
    if 1 <= len(authors) <= MAX_AUTHORS_IN_HEADING:
        return parse_name(authors[0]).heading()
    return None


def statement_of_responsibility(authors: list[str], *, foreign: bool = False) -> str:
    """«И. И. Иванов, П. П. Петров»; five or more authors — first three and «[и др.]»."""
    names = [parse_name(author).statement() for author in authors]
    if len(names) > MAX_LISTED_AUTHORS:
        et_al = "[et al.]" if foreign else f"[и{NBSP}др.]"
        return ", ".join(names[:LISTED_BEFORE_ET_AL]) + f" {et_al}"
    return ", ".join(names)


def _is_initial(token: str) -> bool:
    return bool(_INITIAL.match(token))


def _initials(given: str) -> tuple[str, ...]:
    result: list[str] = []
    for token in re.sub(r"(\w\.)(?=\w)", r"\1 ", given).split():
        if _is_initial(token):
            result.append(token)
        elif "-" in token:  # Жан-Поль → Ж.-П.
            result.append("-".join(f"{part[0]}." for part in token.split("-") if part))
        else:
            result.append(f"{token[0]}.")
    return tuple(result)
