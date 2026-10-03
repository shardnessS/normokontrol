"""Source → bibliographic record per GOST R 7.0.100-2018; list ordering and numbering."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from normokontrol.bibliography import names
from normokontrol.bibliography.models import (
    Article,
    Book,
    BookChapter,
    Law,
    Patent,
    Source,
    Standard,
    Thesis,
    Web,
)
from normokontrol.bibliography.names import NBSP

Order = Literal["by_citation", "alphabetical"]


@dataclass(frozen=True)
class Style:
    """Choices the standard leaves to the bibliographing organisation."""

    dash: str = "–"
    # Область вида содержания и средства доступа («Текст : непосредственный») — условно-обязательная.
    content_type: bool = True


@dataclass(frozen=True)
class EntryWarning:
    index: int  # 1-based position in the input list
    source_id: str | None
    message_ru: str


@dataclass
class FormattedList:
    entries: list[str] = field(default_factory=list)
    text: str = ""
    warnings: list[EntryWarning] = field(default_factory=list)


def format_source(source: Source, style: Style | None = None) -> str:
    """One bibliographic record, ending with a full stop."""
    style = style or Style()
    if isinstance(source, Book):
        return _book(source, style)
    if isinstance(source, BookChapter):
        return _chapter(source, style)
    if isinstance(source, Thesis):
        return _thesis(source, style)
    if isinstance(source, Patent):
        return _patent(source, style)
    if isinstance(source, Article):
        return _article(source, style)
    if isinstance(source, Web):
        return _web(source, style)
    if isinstance(source, Law):
        return _law(source, style)
    return _standard(source, style)


def format_bibliography(
    sources: Sequence[Source],
    *,
    order: Order = "by_citation",
    numbering: str = "{n}. ",
    style: Style | None = None,
    indices: Sequence[int] | None = None,
) -> FormattedList:
    """Numbered list. `by_citation` keeps the input order (order of first citation).

    `indices` are the 1-based positions of the sources in the user's input, used in warnings when
    some input items were not sources (e.g. unresolved identifiers).
    """
    style = style or Style()
    positions = list(indices) if indices is not None else list(range(1, len(sources) + 1))
    records = [(format_source(source, style), source) for source in sources]
    warnings = [
        EntryWarning(index, source.id, message)
        for index, source in zip(positions, sources, strict=True)
        for message in missing_fields(source)
    ]
    if order == "alphabetical":
        records.sort(key=lambda item: sort_key(item[0]))
    entries = [numbering.format(n=n) + record for n, (record, _) in enumerate(records, start=1)]
    return FormattedList(entries=entries, text="\n".join(entries), warnings=warnings)


def sort_key(record: str) -> tuple[int, str]:
    """Cyrillic records first, then Latin, then the rest; ё sorts as е."""
    text = record.lstrip('«"„[(').casefold().replace("ё", "е")
    first = text[:1]
    group = 0 if names.is_cyrillic(first) else 1 if first.isascii() and first.isalpha() else 2
    return group, text


def missing_fields(source: Source) -> list[str]:
    """Russian warnings about fields a complete record needs."""
    label = f"«{source.id}»" if source.id else f"«{_shorten(source.title)}»"
    missing: list[str] = []

    def need(value: object, what: str) -> None:
        if value in (None, "", []):
            missing.append(f"Источник {label}: не указано — {what}")

    if isinstance(source, Book):
        need(source.city, "место издания (city)")
        need(source.publisher, "издательство (publisher)")
        need(source.year, "год издания (year)")
        if source.site is None:
            need(source.pages, "количество страниц (pages)")
    elif isinstance(source, BookChapter):
        need(source.book_title, "заглавие книги или сборника (book_title)")
        need(source.year, "год издания (year)")
        if source.url is None:
            need(source.city, "место издания (city)")
            need(source.publisher, "издательство (publisher)")
            need(source.pages, "страницы (pages)")
    elif isinstance(source, Thesis):
        need(source.authors, "автор (authors)")
        need(source.degree, "учёная степень (degree), например «кандидата технических наук»")
        need(source.city, "место защиты или подготовки (city)")
        need(source.year, "год (year)")
        need(source.pages, "количество страниц (pages)")
    elif isinstance(source, Patent):
        need(source.number, "номер патента (number)")
        need(source.application, "номер заявки (application)")
        need(source.filed, "дата подачи заявки (filed)")
        need(source.published, "дата публикации (published)")
    elif isinstance(source, Article):
        need(source.journal, "название журнала (journal)")
        need(source.year, "год (year)")
        if source.url is None:
            need(source.pages, "страницы статьи (pages)")
    elif isinstance(source, Web):
        need(source.url, "адрес страницы (url)")
    elif isinstance(source, Law):
        need(source.act_type, "вид документа (act_type), например «Федеральный закон»")
        if source.number is None:
            need(source.date, "номер (number) или дата (date) документа")
        if source.url is None:
            need(source.publication, "официальное издание (publication) или адрес (url)")
    else:
        need(source.designation, "обозначение стандарта (designation), например «ГОСТ Р 7.0.100–2018»")
        if source.url is None:
            need(source.year, "год издания (year)")
    if source.url is not None:
        need(source.accessed, "дата обращения к ресурсу (accessed)")
    return missing


# --- описания по видам источников -----------------------------------------------------------


def _book(s: Book, style: Style) -> str:
    foreign = not names.is_cyrillic(s.title)
    areas = [
        _with_heading(
            s.authors, _title_area(s.title, s.subtitle, _responsibility(s.authors, s.responsibility, foreign))
        ),
        s.edition,
        _publication(s.city, s.publisher, s.year),
        _extent(s.pages, s.illustrations, foreign),
        f"({s.series})" if s.series else None,
        *s.notes,
    ]
    if s.site is None:
        areas += [*_online(s), _isbn(s.isbn), _doi(s.doi), _content_type(s, style)]
        return _areas(areas, style)
    areas += [_isbn(s.isbn), _doi(s.doi), _content_type(s, style)]
    return _component(_areas(areas, style, final=False), [_host_site(s.site), *_online(s)], style)


def _article(s: Article, style: Style) -> str:
    foreign = not names.is_cyrillic(s.title)
    part = [
        _with_heading(
            s.authors, _title_area(s.title, s.subtitle, _responsibility(s.authors, s.responsibility, foreign))
        ),
        _doi(s.doi),
        _content_type(s, style),
    ]
    numbering = ", ".join(
        item
        for item in (
            f"{'Vol.' if foreign else 'Т.'}{NBSP}{s.volume}" if s.volume else None,
            f"{'no.' if foreign else '№'}{NBSP}{s.issue}" if s.issue else None,
        )
        if item
    )
    host = [
        s.journal,
        str(s.year) if s.year else None,
        numbering or None,
        f"{'P.' if foreign else 'С.'}{NBSP}{_range(s.pages)}" if s.pages else None,
        *s.notes,
        *_online(s),
    ]
    return _component(_areas(part, style, final=False), host, style)


def _chapter(s: BookChapter, style: Style) -> str:
    foreign = not names.is_cyrillic(s.title)
    part = [
        _with_heading(
            s.authors, _title_area(s.title, s.subtitle, _responsibility(s.authors, s.responsibility, foreign))
        ),
        _doi(s.doi),
        _content_type(s, style),
    ]
    host = [
        _title_area(s.book_title or "", s.book_subtitle, " ; ".join(s.book_responsibility) or None) or None,
        s.edition,
        _publication(s.city, s.publisher, s.year),
        _isbn(s.isbn),
        s.part,
        s.section,
        f"{'P.' if foreign else 'С.'}{NBSP}{_range(s.pages)}" if s.pages else None,
        *_online(s),
    ]
    return _component(_areas(part, style, final=False), host, style)


def _thesis(s: Thesis, style: Style) -> str:
    work = "диссертация" if s.kind == "dissertation" else "автореферат диссертации"
    if s.degree:
        work += f" на соискание ученой степени {s.degree}"
    info = " : ".join(
        item for item in (s.subtitle, f"специальность {s.specialty}" if s.specialty else None, work) if item
    )
    # В диссертациях имя автора после косой черты приводят как на титульном листе (полностью).
    responsibility = " ; ".join([", ".join(s.authors), *s.responsibility] if s.authors else s.responsibility)
    areas = [
        _with_heading(s.authors, _title_area(s.title, info, responsibility or None)),
        _publication(s.city, None, s.year),
        _extent(s.pages, s.illustrations, foreign=False),
        *s.notes,
        *_online(s),
        _content_type(s, style),
    ]
    return _areas(areas, style)


def _patent(s: Patent, style: Style) -> str:
    heading = f"Патент №{NBSP}{s.number} {s.country}" if s.number else f"Патент {s.country}"
    if s.classification:
        heading += f", {s.classification}"
    info = [
        f"№{NBSP}{s.application}" if s.application else None,
        f"заявлено {s.filed:%d.%m.%Y}" if s.filed else None,
        f"опубликовано {s.published:%d.%m.%Y}" if s.published else None,
    ]
    responsibility = " ; ".join(
        [", ".join(s.inventors), *s.responsibility] if s.inventors else s.responsibility
    )
    title_area = _title_area(s.title, " : ".join(i for i in info if i) or None, responsibility or None)
    areas = [
        f"{heading}. {title_area}",
        _extent(s.pages, s.illustrations, foreign=False),
        *_online(s),
        _content_type(s, style),
    ]
    return _areas(areas, style)


def _web(s: Web, style: Style) -> str:
    responsibility = _responsibility(s.authors, s.responsibility, not names.is_cyrillic(s.title))
    if s.site is None:  # сайт целиком
        subtitle = s.subtitle or ""
        if "сайт" not in subtitle:
            subtitle = f"{subtitle} : сайт" if subtitle else "сайт"
        areas = [
            _title_area(s.title, subtitle, responsibility),
            _publication(s.city, s.publisher, s.year),
            *_online(s),
            _content_type(s, style),
        ]
        return _areas(areas, style)
    part = [
        _with_heading(s.authors, _title_area(s.title, s.subtitle, responsibility)),
        _content_type(s, style),
    ]
    host = [_host_site(s.site), str(s.year) if s.year else None, s.date, *_online(s)]
    return _component(_areas(part, style, final=False), host, style)


def _law(s: Law, style: Style) -> str:
    act = s.act_type or ""
    if s.date:
        act += f" от {s.date}"
    if s.number:
        act += f" №{NBSP}{s.number}"
    info = " : ".join(item for item in (s.subtitle, act.strip(), *s.details) if item)
    part = [_title_area(s.title, info or None, None), _content_type(s, style)]
    if s.publication is not None:
        host = [
            s.publication,
            str(s.year) if s.year else None,
            f"№{NBSP}{s.issue}" if s.issue else None,
            f"Ст.{NBSP}{s.article}" if s.article else None,
            f"С.{NBSP}{_range(s.pages)}" if s.pages else None,
            *_online(s),
        ]
    else:
        host = [_host_site(s.site) if s.site else None, *_online(s)]
    return _component(_areas(part, style, final=False), host, style)


def _standard(s: Standard, style: Style) -> str:
    info = [s.subtitle, s.kind, *s.details]
    if s.effective_date:
        info.append(f"дата введения {s.effective_date.isoformat()}")
    subtitle = " : ".join(item for item in info if item) or None
    title_area = _title_area(s.title, subtitle, " ; ".join(s.responsibility) or None)
    areas = [
        f"{s.designation}. {title_area}" if s.designation else title_area,
        s.edition,
        _publication(s.city, s.publisher, s.year),
        _extent(s.pages, None, foreign=False),
    ]
    if s.site is None:
        return _areas([*areas, *_online(s), _content_type(s, style)], style)
    return _component(
        _areas([*areas, _content_type(s, style)], style, final=False),
        [_host_site(s.site), *_online(s)],
        style,
    )


# --- элементы и пунктуация ------------------------------------------------------------------


def _title_area(title: str, subtitle: str | None, responsibility: str | None) -> str:
    text = title
    if subtitle:
        text += f" : {subtitle}"
    if responsibility:
        text += f" / {responsibility}"
    return text


def _with_heading(authors: list[str], title_area: str) -> str:
    heading = names.heading(authors)
    return f"{heading} {title_area}" if heading else title_area


def _responsibility(authors: list[str], further: list[str], foreign: bool) -> str | None:
    parts = [names.statement_of_responsibility(authors, foreign=foreign)] if authors else []
    parts += further
    return " ; ".join(parts) or None


def _publication(city: str | None, publisher: str | None, year: int | str | None) -> str | None:
    place = " : ".join(item for item in (city, publisher) if item)
    if year is None:
        return place or None
    return f"{place}, {year}" if place else str(year)


def _extent(pages: int | str | None, illustrations: str | None, foreign: bool) -> str | None:
    if pages is None:
        return None
    text = f"{pages}{NBSP}{'p.' if foreign else 'с.'}"
    return f"{text} : {illustrations}" if illustrations else text


def _doi(doi: str | None) -> str | None:
    return f"DOI {doi}" if doi else None


def _isbn(isbn: str | None) -> str | None:
    return f"ISBN {isbn}" if isbn else None


def _online(s: Source) -> list[str | None]:
    if s.url is None:
        return []
    note = f"URL: {s.url}"
    if s.accessed:
        note += f" (дата обращения: {s.accessed:%d.%m.%Y})"
    return [note, f"Режим доступа: {s.access_mode}" if s.access_mode else None]


def _host_site(site: str) -> str:
    return site if " : " in site else f"{site} : [сайт]"


def _content_type(s: Source, style: Style) -> str | None:
    if not style.content_type:
        return None
    return "Текст : электронный" if s.electronic else "Текст : непосредственный"


def _range(pages: str | int) -> str:
    """«136-144» → «136–144»."""
    return re.sub(r"\s*[-‐‑‒–—]\s*", "–", str(pages).strip())


def _areas(parts: Sequence[str | None], style: Style, *, final: bool = True) -> str:
    """Join description areas with «. – », never doubling a full stop."""
    text = ""
    for part in parts:
        if not part:
            continue
        if not text:
            text = part
        elif text.endswith("."):
            text += f" {style.dash} {part}"
        else:
            text += f". {style.dash} {part}"
    if final and not text.endswith("."):
        text += "."
    return text


def _component(part: str, host: Sequence[str | None], style: Style) -> str:
    """Component part: «description of the part // description of the host resource.»"""
    return f"{part} // {_areas(host, style)}"


def _shorten(text: str, limit: int = 40) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
