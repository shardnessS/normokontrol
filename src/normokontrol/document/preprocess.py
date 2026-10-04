"""Numbering and cross-references: headings, figures, tables, formulas, appendices, citations."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from normokontrol.bibliography import formatter
from normokontrol.bibliography.models import Source
from normokontrol.document.markdown_in import (
    Block,
    CodeBlock,
    DocumentError,
    Formula,
    Heading,
    Image,
    ListBlock,
    Paragraph,
    ParsedDocument,
    Table,
)
from normokontrol.presets.schema import Preset

APPENDIX_WORD = "ПРИЛОЖЕНИЕ"
TOC_TITLE = "СОДЕРЖАНИЕ"
_REFERENCE = re.compile(r"\[@([\w:.\-]+)(?:,\s*([^\]]+?))?\]")


@dataclass
class OutHeading:
    kind: Literal["structural", "toc", "bibliography", "section", "appendix"]
    level: int
    text: str  # готовый текст: «1.2 Обзор решений», «ВВЕДЕНИЕ»
    appendix_title: str | None = None  # для приложения — заголовок на второй строке


@dataclass
class OutParagraph:
    text: str


@dataclass
class OutList:
    items: list[str]  # с маркером: «— пункт», «а) пункт», «1) пункт»


@dataclass
class OutFigure:
    path: str
    caption: str
    line: int


@dataclass
class OutTable:
    caption: str
    header: list[str]
    rows: list[list[str]]


@dataclass
class OutFormula:
    latex: str
    number: str | None
    line: int


@dataclass
class OutCode:
    lines: list[str]


@dataclass
class OutBibliography:
    entries: list[str]


OutBlock = OutHeading | OutParagraph | OutList | OutFigure | OutTable | OutFormula | OutCode | OutBibliography


@dataclass
class Prepared:
    blocks: list[OutBlock]
    stats: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class _Context:
    """Where we are: current section, appendix, counters."""

    section: list[int] = field(default_factory=list)
    appendix: str | None = None
    in_structural: bool = False
    awaiting_appendix_title: bool = False
    appendix_count: int = 0
    appendix_sections: int = 0
    counters: dict[str, int] = field(default_factory=dict)


def prepare(document: ParsedDocument, preset: Preset, sources: list[Source], *, name: str) -> Prepared:
    """Resolve numbering and references; returns blocks ready for the docx builder."""
    numbering = _Numbering(document, preset, name)
    labels = numbering.labels
    blocks = document.blocks

    by_id = {source.id: source for source in sources if source.id}
    cited = _citation_order(blocks, labels, by_id, name)
    ordered, warnings = _bibliography_order(sources, cited, document, preset)
    style = formatter.Style(dash=preset.bibliography.dash, content_type=preset.bibliography.content_type)
    result = formatter.format_bibliography(ordered, order="by_citation", numbering="", style=style)
    entries = [
        preset.bibliography.numbering.format(n=n) + text for n, text in enumerate(result.entries, start=1)
    ]
    warnings += [warning.message_ru for warning in result.warnings]
    numbers = {source.id: n for n, source in enumerate(ordered, start=1) if source.id}

    def resolve(text: str, line: int) -> str:
        return _substitute(text, labels, numbers, name, line)

    out: list[OutBlock] = []
    bibliography_placed = False
    in_bibliography = False
    for block, heading in zip(blocks, numbering.headings, strict=True):
        if in_bibliography and not isinstance(block, Heading):
            raise DocumentError(
                f"Список источников («{preset.bibliography.title}») формируется автоматически из sources: "
                "уберите текст под этим заголовком",
                f"{name}:{block.line}",
            )
        if isinstance(block, Heading) and block.level == 1:
            in_bibliography = False
        if heading is not None:
            if heading.kind == "bibliography":
                bibliography_placed = True
                in_bibliography = True
                out.append(heading)
                out.append(OutBibliography(entries))
                continue
            if heading.kind == "appendix" and not bibliography_placed and entries:
                out += [_bibliography_heading(preset), OutBibliography(entries)]
                bibliography_placed = True
            if heading.appendix_title is not None:
                heading.appendix_title = resolve(heading.appendix_title, block.line)
            heading.text = resolve(heading.text, block.line)
            out.append(heading)
        elif isinstance(block, Heading):
            continue  # заголовок приложения, вошедший в предыдущий OutHeading
        elif isinstance(block, Paragraph):
            out.append(OutParagraph(resolve(block.text, block.line)))
        elif isinstance(block, ListBlock):
            out.append(OutList(_list_items(block, preset, resolve)))
        elif isinstance(block, Image):
            caption = preset.figures.caption.format(num=numbering.objects[id(block)], title=block.caption)
            out.append(OutFigure(block.path, resolve(caption, block.line), block.line))
        elif isinstance(block, Table):
            caption = preset.tables.caption.format(num=numbering.objects[id(block)], title=block.caption)
            out.append(
                OutTable(
                    resolve(caption, block.line),
                    [resolve(cell, block.line) for cell in block.header],
                    [[resolve(cell, block.line) for cell in row] for row in block.rows],
                )
            )
        elif isinstance(block, Formula):
            number = numbering.objects.get(id(block))
            out.append(
                OutFormula(
                    block.latex, preset.formulas.format.format(num=number) if number else None, block.line
                )
            )
        else:
            assert isinstance(block, CodeBlock)
            out.append(OutCode(block.lines))
    if not bibliography_placed and entries:
        out += [_bibliography_heading(preset), OutBibliography(entries)]

    stats = {
        "разделов": numbering.sections,
        "рисунков": numbering.count("fig"),
        "таблиц": numbering.count("tbl"),
        "формул": numbering.count("eq"),
        "приложений": numbering.appendices,
        "источников": len(entries),
    }
    return Prepared(out, stats, warnings + numbering.warnings)


class _Numbering:
    """First pass: classify headings and number every object; collect anchor labels."""

    def __init__(self, document: ParsedDocument, preset: Preset, name: str) -> None:
        self.preset = preset
        self.name = name
        self.labels: dict[str, str] = {}
        self.objects: dict[int, str] = {}
        self.headings: list[OutHeading | None] = []
        self.warnings: list[str] = []
        self.sections = 0
        self.appendices = 0
        self._last_appendix: OutHeading | None = None
        self._counts: dict[str, int] = {"fig": 0, "tbl": 0, "eq": 0}
        ctx = _Context()
        for block in document.blocks:
            self.headings.append(self._block(block, ctx))

    def count(self, kind: str) -> int:
        return self._counts[kind]

    def _error(self, message: str, line: int) -> DocumentError:
        return DocumentError(message, f"{self.name}:{line}")

    def _label(self, anchor: str | None, value: str, line: int) -> None:
        if anchor is None:
            return
        if anchor in self.labels:
            raise self._error(f"Метка «{anchor}» использована дважды", line)
        self.labels[anchor] = value

    def _block(self, block: Block, ctx: _Context) -> OutHeading | None:
        if isinstance(block, Heading):
            return self._heading(block, ctx)
        ctx.awaiting_appendix_title = False
        kind = {Image: "fig", Table: "tbl", Formula: "eq"}.get(type(block))
        if kind is None:
            return None
        assert isinstance(block, Image | Table | Formula)
        if isinstance(block, Formula) and block.anchor is None:
            return None  # формулы без метки не нумеруются
        number = self._object_number(kind, ctx, block.line)
        self.objects[id(block)] = number
        self._label(block.anchor, f"({number})" if kind == "eq" else number, block.line)
        return None

    def _object_number(self, kind: str, ctx: _Context, line: int) -> str:
        self._counts[kind] += 1
        scope = ctx.appendix or ""
        numbering = {
            "fig": self.preset.figures.numbering,
            "tbl": self.preset.tables.numbering,
            "eq": self.preset.formulas.numbering,
        }[kind]
        if not scope and numbering == "per_chapter":
            if not ctx.section:
                raise self._error(
                    "Нумерация в пределах раздела: объект стоит вне нумерованного раздела", line
                )
            scope = str(ctx.section[0])
        key = f"{kind}:{scope}"
        ctx.counters[key] = ctx.counters.get(key, 0) + 1
        return f"{scope}.{ctx.counters[key]}" if scope else str(ctx.counters[key])

    def _heading(self, block: Heading, ctx: _Context) -> OutHeading | None:
        text = block.text.strip()
        upper = text.upper()
        titles = self.preset.headings.structural_titles
        if block.level == 1:
            ctx.awaiting_appendix_title = False
            if upper == APPENDIX_WORD or upper.startswith(APPENDIX_WORD + " "):
                return self._appendix(block, ctx)
            if ctx.appendix is not None:
                raise self._error(
                    "После приложений не может быть других разделов: перенесите приложения в конец",
                    block.line,
                )
            ctx.section = []
            if upper == TOC_TITLE:
                ctx.in_structural = True
                return OutHeading("toc", 1, TOC_TITLE)
            if upper == self.preset.bibliography.title:
                ctx.in_structural = True
                return OutHeading("bibliography", 1, upper)
            if upper in titles:
                ctx.in_structural = True
                return OutHeading("structural", 1, upper)
            ctx.in_structural = False
            self.sections += 1
            ctx.section = [self.sections]
            self._label(block.anchor, str(self.sections), block.line)
            return OutHeading("section", 1, self._numbered(ctx.section, text))
        if ctx.appendix is not None:
            if ctx.awaiting_appendix_title and block.level == 2:
                ctx.awaiting_appendix_title = False
                assert self._last_appendix is not None
                self._last_appendix.appendix_title = text
                return None  # заголовок приложения входит в OutHeading приложения
            ctx.appendix_sections += 1
            return OutHeading("section", 2, f"{ctx.appendix}.{ctx.appendix_sections} {text}")
        if ctx.in_structural or not ctx.section:
            raise self._error(
                f"Подзаголовок «{text}» вне нумерованного раздела: "
                "структурные элементы не делятся на подразделы",
                block.line,
            )
        depth = block.level
        if depth > len(ctx.section) + 1:
            raise self._error(f"Пропущен уровень заголовка перед «{text}»", block.line)
        ctx.section = [
            *ctx.section[: depth - 1],
            (ctx.section[depth - 1] + 1) if len(ctx.section) >= depth else 1,
        ]
        self._label(block.anchor, ".".join(map(str, ctx.section)), block.line)
        return OutHeading("section", depth, self._numbered(ctx.section, text))

    def _numbered(self, section: list[int], text: str) -> str:
        style = {1: self.preset.headings.level1, 2: self.preset.headings.level2}.get(len(section))
        pattern = (
            style.number_format
            if style and style.number_format
            else ".".join(f"{{n{i}}}" for i in range(1, len(section) + 1))
        )
        values = {f"n{i}": n for i, n in enumerate(section, start=1)}
        return f"{pattern.format(**values)} {text}"

    def _appendix(self, block: Heading, ctx: _Context) -> OutHeading:
        letters = self.preset.appendices.letters
        if ctx.appendix_count >= len(letters):
            raise self._error("Слишком много приложений: закончились допустимые буквы", block.line)
        letter = letters[ctx.appendix_count]
        ctx.appendix_count += 1
        self.appendices += 1
        ctx.appendix = letter
        ctx.appendix_sections = 0
        ctx.section = []
        ctx.in_structural = False
        ctx.awaiting_appendix_title = True
        self._label(block.anchor, letter, block.line)
        title = self.preset.appendices.title.format(letter=letter)
        self._last_appendix = OutHeading("appendix", 1, title, appendix_title=None)
        return self._last_appendix


def _citation_order(
    blocks: list[Block], labels: dict[str, str], by_id: dict[str, Source], name: str
) -> list[str]:
    order: list[str] = []
    for block in blocks:
        for text in _texts(block):
            for match in _REFERENCE.finditer(text):
                key = match[1]
                if key.split(":", 1)[0] in ("fig", "tbl", "eq", "app"):
                    if key not in labels:
                        raise DocumentError(f"Ссылка на несуществующую метку «{key}»", f"{name}:{block.line}")
                    continue
                if key not in by_id:
                    raise DocumentError(
                        f"Ссылка [@{key}] на источник, которого нет в списке источников (sources)",
                        f"{name}:{block.line}",
                    )
                if key not in order:
                    order.append(key)
    return order


def _texts(block: Block) -> list[str]:
    if isinstance(block, Paragraph | Heading):
        return [block.text]
    if isinstance(block, ListBlock):
        return [item.text for item in block.items]
    if isinstance(block, Image):
        return [block.caption]
    if isinstance(block, Table):
        return [block.caption, *block.header, *(cell for row in block.rows for cell in row)]
    return []


def _bibliography_order(
    sources: list[Source], cited: list[str], document: ParsedDocument, preset: Preset
) -> tuple[list[Source], list[str]]:
    warnings: list[str] = []
    by_id = {source.id: source for source in sources if source.id}
    uncited = [source for source in sources if source.id not in cited]
    for source in uncited:
        label = source.id or source.title
        warnings.append(
            f"Источник «{label}» не упомянут в тексте — добавьте ссылку [@{source.id}] или уберите его"
        )
    ordered = [by_id[key] for key in cited] + uncited
    if (document.front.order or preset.bibliography.order) == "alphabetical":
        style = formatter.Style(dash=preset.bibliography.dash, content_type=preset.bibliography.content_type)
        ordered.sort(key=lambda source: formatter.sort_key(formatter.format_source(source, style)))
    return ordered, warnings


def _substitute(text: str, labels: dict[str, str], numbers: dict[str, int], name: str, line: int) -> str:
    def replace(match: re.Match[str]) -> str:
        key, extra = match[1], match[2]
        if key in labels:
            return labels[key]
        number = numbers[key]
        return f"[{number}, {extra}]" if extra else f"[{number}]"

    return _REFERENCE.sub(replace, text)


def _list_items(block: ListBlock, preset: Preset, resolve: Callable[[str, int], str]) -> list[str]:
    items: list[str] = []
    counters = {"letter": 0, "number": 0}
    for item in block.items:
        if item.marker == "bullet":
            marker = preset.lists.bullet
        else:
            counters[item.marker] += 1
            n = counters[item.marker]
            letters = preset.lists.letters
            marker = f"{letters[n - 1]})" if item.marker == "letter" and n <= len(letters) else f"{n})"
        items.append(f"{marker} {resolve(item.text, item.line)}")
    return items


def _bibliography_heading(preset: Preset) -> OutHeading:
    return OutHeading("bibliography", 1, preset.bibliography.title)
