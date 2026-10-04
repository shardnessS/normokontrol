"""Parse the input Markdown: YAML front matter and a flat list of blocks with line numbers.

Only the subset described in docs/input-format.md is supported; anything else is a plain paragraph.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from normokontrol.errors import NormokontrolError, format_validation_errors


class DocumentError(NormokontrolError):
    """Invalid input document; `location` is «файл:строка»."""

    error_code = "document_invalid"


class FrontMatter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset: str = "gost-7.32-2017"
    work_type: Literal["coursework", "vkr", "report", "essay"] = "coursework"
    title_page: dict[str, Any] = Field(default_factory=dict)
    sources: str | list[Any] = Field(default_factory=list)
    order: Literal["by_citation", "alphabetical"] | None = None


@dataclass
class Heading:
    line: int
    level: int
    text: str
    anchor: str | None = None


@dataclass
class Paragraph:
    line: int
    text: str


@dataclass
class ListItem:
    line: int
    marker: Literal["bullet", "number", "letter"]
    text: str


@dataclass
class ListBlock:
    line: int
    items: list[ListItem]


@dataclass
class Image:
    line: int
    caption: str
    path: str
    anchor: str | None = None


@dataclass
class Table:
    line: int
    caption: str
    header: list[str]
    rows: list[list[str]]
    anchor: str | None = None


@dataclass
class Formula:
    line: int
    latex: str
    anchor: str | None = None


@dataclass
class CodeBlock:
    line: int
    lines: list[str]


Block = Heading | Paragraph | ListBlock | Image | Table | Formula | CodeBlock


@dataclass
class ParsedDocument:
    front: FrontMatter
    blocks: list[Block] = field(default_factory=list)
    path: Path | None = None


_ANCHOR = r"\{#((?:fig|tbl|eq|app):[\w.\-]+)\}"
_HEADING = re.compile(rf"^(#{{1,3}})\s+(.*?)\s*(?:{_ANCHOR})?\s*$")
_IMAGE = re.compile(rf"^!\[(.*?)\]\((.+?)\)\s*(?:{_ANCHOR})?\s*$")
_TABLE_CAPTION = re.compile(rf"^:\s+(.*?)\s*(?:{_ANCHOR})?\s*$")
_FORMULA_END = re.compile(rf"\$\$\s*(?:{_ANCHOR})?\s*$")
_LIST_ITEM = re.compile(r"^\s*(?:([-*+])|(\d+)[.)]|([а-яё])\))\s+(.*)$")
_TABLE_SEPARATOR = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
_ANY_ANCHOR = re.compile(r"\{#([^}]*)\}\s*$")


def parse_file(path: Path) -> ParsedDocument:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise DocumentError(
            f"Не удалось прочитать файл «{path}»: {exc.strerror}", location=str(path)
        ) from None
    except UnicodeDecodeError:
        raise DocumentError(f"Файл «{path}» должен быть в кодировке UTF-8", location=str(path)) from None
    document = parse(text, name=path.name)
    document.path = path
    return document


def parse(text: str, *, name: str = "<вход>") -> ParsedDocument:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    front, start = _front_matter(lines, name)
    return ParsedDocument(front=front, blocks=_Blocks(lines, start, name).parse())


def _front_matter(lines: list[str], name: str) -> tuple[FrontMatter, int]:
    if not lines or lines[0].strip() != "---":
        return FrontMatter(), 0
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() in ("---", "..."))
    except StopIteration:
        raise DocumentError("Блок параметров в начале файла не закрыт строкой «---»", f"{name}:1") from None
    try:
        data = yaml.safe_load("\n".join(lines[1:end])) or {}
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = mark.line + 2 if mark is not None else 1
        raise DocumentError(f"Ошибка в блоке параметров: {exc}", f"{name}:{line}") from None
    if not isinstance(data, dict):
        raise DocumentError("Блок параметров должен быть набором «ключ: значение»", f"{name}:1")
    try:
        return FrontMatter.model_validate(data), end + 1
    except ValidationError as exc:
        details = format_validation_errors(exc)
        raise DocumentError(f"Ошибки в блоке параметров:\n{details}", f"{name}:1") from None


class _Blocks:
    def __init__(self, lines: list[str], start: int, name: str) -> None:
        self.lines = lines
        self.i = start
        self.name = name
        self.blocks: list[Block] = []

    def error(self, message: str, index: int) -> DocumentError:
        return DocumentError(message, f"{self.name}:{index + 1}")

    def parse(self) -> list[Block]:
        while self.i < len(self.lines):
            line = self.lines[self.i]
            stripped = line.strip()
            if not stripped:
                self.i += 1
                continue
            self._check_anchor(stripped, self.i)
            if stripped.startswith("```"):
                self._code()
            elif stripped.startswith("$$"):
                self._formula()
            elif heading := _HEADING.match(stripped):
                self.blocks.append(Heading(self.i + 1, len(heading[1]), heading[2], heading[3]))
                self.i += 1
            elif image := _IMAGE.match(stripped):
                self.blocks.append(Image(self.i + 1, image[1].strip(), image[2].strip(), image[3]))
                self.i += 1
            elif (caption := _TABLE_CAPTION.match(stripped)) and self._table_follows():
                self._table(caption[1], caption[2])
            elif stripped.startswith("|"):
                raise self.error(
                    "Таблица без названия: добавьте перед ней строку «: Название {#tbl:id}»", self.i
                )
            elif _LIST_ITEM.match(line):
                self._list()
            else:
                self._paragraph()
        return self.blocks

    def _check_anchor(self, text: str, index: int) -> None:
        match = _ANY_ANCHOR.search(text)
        if match and not re.fullmatch(r"(?:fig|tbl|eq|app):[\w.\-]+", match[1]):
            raise self.error(
                f"Неверная метка «{{#{match[1]}}}»: допустимо {{#fig:…}}, {{#tbl:…}}, {{#eq:…}}, {{#app:…}}",
                index,
            )

    def _is_block_start(self, index: int) -> bool:
        stripped = self.lines[index].strip()
        return (
            not stripped
            or stripped.startswith(("```", "$$", "|"))
            or bool(_HEADING.match(stripped) or _IMAGE.match(stripped) or _LIST_ITEM.match(self.lines[index]))
            or bool(_TABLE_CAPTION.match(stripped))
        )

    def _paragraph(self) -> None:
        start = self.i
        parts = [self.lines[self.i].strip()]
        self.i += 1
        while self.i < len(self.lines) and not self._is_block_start(self.i):
            parts.append(self.lines[self.i].strip())
            self.i += 1
        # Пояснение к формуле: каждое обозначение с новой строки (ГОСТ 7.32-2017, п. 6.8.2).
        separator = "\n" if parts[0].lower().startswith("где ") and len(parts) > 1 else " "
        self.blocks.append(Paragraph(start + 1, separator.join(parts)))

    def _list(self) -> None:
        start = self.i
        items: list[ListItem] = []
        while self.i < len(self.lines):
            line = self.lines[self.i]
            match = _LIST_ITEM.match(line)
            if match:
                marker: Literal["bullet", "number", "letter"] = (
                    "bullet" if match[1] else "number" if match[2] else "letter"
                )
                items.append(ListItem(self.i + 1, marker, match[4].strip()))
            elif line.startswith((" ", "\t")) and line.strip() and items:
                items[-1].text += " " + line.strip()  # продолжение пункта
            else:
                break
            self.i += 1
        self.blocks.append(ListBlock(start + 1, items))

    def _table_follows(self) -> bool:
        j = self.i + 1
        while j < len(self.lines) and not self.lines[j].strip():
            j += 1
        return j < len(self.lines) and self.lines[j].strip().startswith("|")

    def _table(self, caption: str, anchor: str | None) -> None:
        start = self.i
        self.i += 1
        while not self.lines[self.i].strip():
            self.i += 1
        rows: list[tuple[int, list[str]]] = []
        while self.i < len(self.lines) and self.lines[self.i].strip().startswith("|"):
            rows.append((self.i, _cells(self.lines[self.i])))
            self.i += 1
        if len(rows) < 2 or not _TABLE_SEPARATOR.match(self.lines[rows[1][0]].strip()):
            raise self.error("У таблицы должна быть строка заголовка и разделитель «|---|---|»", rows[0][0])
        header = rows[0][1]
        body = rows[2:]
        for index, cells in body:
            if len(cells) != len(header):
                raise self.error(f"В строке таблицы {len(cells)} ячеек, а в заголовке {len(header)}", index)
        self.blocks.append(Table(start + 1, caption, header, [cells for _, cells in body], anchor))

    def _formula(self) -> None:
        start = self.i
        first = self.lines[self.i].strip()[2:]
        if (end := _FORMULA_END.search(first)) is not None:  # однострочная $$ … $$
            self.blocks.append(Formula(start + 1, first[: end.start()].strip(), end[1]))
            self.i += 1
            return
        parts = [first]
        self.i += 1
        while self.i < len(self.lines):
            line = self.lines[self.i].strip()
            if (end := _FORMULA_END.search(line)) is not None:
                parts.append(line[: end.start()])
                self.blocks.append(Formula(start + 1, " ".join(p for p in parts if p).strip(), end[1]))
                self.i += 1
                return
            parts.append(line)
            self.i += 1
        raise self.error("Формула не закрыта: нет завершающих «$$»", start)

    def _code(self) -> None:
        start = self.i
        self.i += 1
        lines: list[str] = []
        while self.i < len(self.lines):
            if self.lines[self.i].strip().startswith("```"):
                self.blocks.append(CodeBlock(start + 1, lines))
                self.i += 1
                return
            lines.append(self.lines[self.i].rstrip())
            self.i += 1
        raise self.error("Блок кода не закрыт: нет завершающих «```»", start)


def _cells(line: str) -> list[str]:
    inner = line.strip()
    inner = inner[1:] if inner.startswith("|") else inner
    inner = inner[:-1] if inner.endswith("|") else inner
    return [cell.strip() for cell in inner.split("|")]
