"""DOI → Crossref, ISBN → Open Library, URL → page meta tags. Results are Source objects to confirm."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from normokontrol import __version__
from normokontrol.bibliography.identifiers import Identifier
from normokontrol.bibliography.models import Article, Book, BookChapter, Source, Web
from normokontrol.bibliography.names import InvalidNameError, parse_name
from normokontrol.errors import NormokontrolError

OFFLINE_ENV = "NORMOKONTROL_OFFLINE"
CACHE_ENV = "NORMOKONTROL_CACHE_DIR"
TIMEOUT_SECONDS = 10
MAX_BYTES = 2_000_000
USER_AGENT = f"normokontrol/{__version__} (+https://github.com/shardnessS/normokontrol)"
CROSSREF_URL = "https://api.crossref.org/works/"
OPENLIBRARY_URL = "https://openlibrary.org/api/books?format=json&jscmd=data&bibkeys=ISBN:"

_CHAPTER_TYPES = {"book-chapter", "book-section", "book-part", "proceedings-article"}
_BOOK_TYPES = {"book", "monograph", "edited-book", "reference-book"}


class LookupFailed(NormokontrolError):
    """Lookup error; `error_code` is network_unavailable, not_found or unsupported."""

    def __init__(self, message_ru: str, error_code: str, location: str | None = None) -> None:
        super().__init__(message_ru, location)
        self.error_code = error_code


def lookup(identifier: Identifier, *, original: str | None = None, today: dt.date | None = None) -> Source:
    """Find metadata for a DOI, ISBN or URL. `original` keeps the ISBN as the user wrote it."""
    if identifier.kind == "doi":
        return lookup_doi(identifier.value)
    if identifier.kind == "isbn":
        return lookup_isbn(identifier.value, printed=original)
    return lookup_url(identifier.value, today=today or dt.date.today())


def lookup_doi(doi: str) -> Source:
    data = json.loads(fetch(CROSSREF_URL + urllib.parse.quote(doi, safe="/")))
    return from_crossref(data["message"])


def lookup_isbn(isbn: str, *, printed: str | None = None) -> Book:
    data = json.loads(fetch(OPENLIBRARY_URL + isbn))
    entry = data.get(f"ISBN:{isbn}")
    if not entry:
        raise LookupFailed(
            f"Книга с ISBN {isbn} не найдена в Open Library (российские издания там встречаются редко)",
            "not_found",
            location=isbn,
        )
    shown = re.sub(r"^isbn(?:-1[03])?:?\s*", "", printed.strip(), flags=re.IGNORECASE) if printed else isbn
    return from_openlibrary(entry, shown)


def lookup_url(url: str, *, today: dt.date) -> Source:
    return from_html(fetch(url), url, today)


# --- разбор ответов -------------------------------------------------------------------------


def from_crossref(m: dict[str, Any]) -> Source:
    title = _clean(_first(m.get("title")))
    if not title:
        raise LookupFailed("В Crossref нет заглавия для этого DOI", "not_found", location=m.get("DOI"))
    common: dict[str, Any] = {
        "title": title,
        "subtitle": _clean(_first(m.get("subtitle"))) or None,
        "authors": [_crossref_name(a) for a in m.get("author", []) if a.get("family")],
        "doi": m.get("DOI"),
    }
    year = _crossref_year(m)
    kind = m.get("type")
    if kind == "journal-article":
        return Article(
            type="article",
            journal=_clean(_first(m.get("container-title"))) or None,
            year=year,
            volume=m.get("volume"),
            issue=m.get("issue"),
            pages=m.get("page"),
            **common,
        )
    if kind in _CHAPTER_TYPES:
        return BookChapter(
            type="conference_paper" if kind == "proceedings-article" else "book_chapter",
            # Crossref ставит серию («Lecture Notes in …») перед заглавием книги — берём последнее.
            book_title=_clean((m.get("container-title") or [None])[-1]) or None,
            city=m.get("publisher-location"),
            publisher=m.get("publisher"),
            year=year,
            isbn=_first(m.get("ISBN")),
            pages=m.get("page"),
            **common,
        )
    if kind in _BOOK_TYPES:
        return Book(
            type="book",
            city=m.get("publisher-location"),
            publisher=m.get("publisher"),
            year=year,
            isbn=_first(m.get("ISBN")),
            **common,
        )
    raise LookupFailed(
        f"Тип публикации «{kind}» из Crossref пока не поддерживается — оформите источник вручную",
        "unsupported",
        location=m.get("DOI"),
    )


def from_openlibrary(entry: dict[str, Any], isbn: str) -> Book:
    year_match = re.search(r"\d{4}", str(entry.get("publish_date", "")))
    return Book(
        type="book",
        title=_clean(entry.get("title")),
        subtitle=_clean(entry.get("subtitle")) or None,
        authors=[_reorder_name(a["name"]) for a in entry.get("authors", []) if a.get("name")],
        city=_clean(_first([p.get("name") for p in entry.get("publish_places", [])])) or None,
        publisher=_clean(_first([p.get("name") for p in entry.get("publishers", [])])) or None,
        year=int(year_match.group()) if year_match else None,
        pages=entry.get("number_of_pages"),
        isbn=isbn,
    )


def from_html(html: str, url: str, today: dt.date) -> Source:
    meta = _MetaParser.parse(html)
    title = _clean(meta.one("citation_title") or meta.one("og:title") or meta.title)
    if not title:
        raise LookupFailed("На странице не найдено заглавие", "not_found", location=url)
    authors = [a for a in (_clean(x) for x in meta.all("citation_author")) if _valid_name(a)]
    year_match = re.search(r"\d{4}", meta.one("citation_publication_date") or meta.one("citation_date") or "")
    year = int(year_match.group()) if year_match else None
    journal = _clean(meta.one("citation_journal_title"))
    if journal:
        first, last = meta.one("citation_firstpage"), meta.one("citation_lastpage")
        pages = f"{first}–{last}" if first and last else first or None
        return Article(
            type="article",
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            volume=meta.one("citation_volume") or None,
            issue=meta.one("citation_issue") or None,
            pages=pages,
            doi=meta.one("citation_doi") or None,
            url=url,
            accessed=today,
        )
    return Web(
        type="web",
        title=title,
        authors=authors,
        site=_clean(meta.one("og:site_name")) or None,
        year=year,
        url=url,
        accessed=today,
    )


# --- сеть и кэш -----------------------------------------------------------------------------


def fetch(url: str) -> str:
    """GET with a disk cache. Raises LookupFailed when offline, unreachable or not found."""
    cached = _cache_path(url)
    if cached is not None and cached.is_file():
        try:
            return str(json.loads(cached.read_text(encoding="utf-8"))["body"])
        except (OSError, ValueError, KeyError):
            pass
    if os.environ.get(OFFLINE_ENV, "").lower() in ("1", "true", "yes"):
        raise LookupFailed(
            f"Сеть отключена ({OFFLINE_ENV}=1): найдите данные источника вручную", "network_unavailable", url
        )
    body = http_get(url)
    if cached is not None:
        try:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps({"url": url, "body": body}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass  # кэш — только ускорение
    return body


def http_get(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_BYTES)
            charset = response.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise LookupFailed(f"Не найдено: {url}", "not_found", url) from None
        raise LookupFailed(f"Сервер ответил ошибкой {exc.code}: {url}", "network_unavailable", url) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise LookupFailed(
            f"Нет доступа к сети ({reason}): найдите данные источника вручную", "network_unavailable", url
        ) from None
    return str(raw.decode(charset, errors="replace"))


def _cache_path(url: str) -> Path | None:
    base = os.environ.get(CACHE_ENV)
    root = Path(base) if base else Path.home() / ".cache" / "normokontrol"
    return root / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.json"


# --- вспомогательное ------------------------------------------------------------------------


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, list[str]] = {}
        self.title = ""
        self._in_title = False

    @classmethod
    def parse(cls, html: str) -> _MetaParser:
        parser = cls()
        parser.feed(html)
        parser.close()
        return parser

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
        if tag != "meta":
            return
        values = dict(attrs)
        key = (values.get("name") or values.get("property") or "").lower()
        content = values.get("content")
        if key and content:
            self.meta.setdefault(key, []).append(content)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data

    def one(self, key: str) -> str:
        values = self.meta.get(key)
        return values[0].strip() if values else ""

    def all(self, key: str) -> list[str]:
        return self.meta.get(key, [])


def _first(values: Any) -> Any:
    if isinstance(values, list):
        return values[0] if values else None
    return values


def _clean(text: Any) -> str:
    """Strip markup Crossref sometimes keeps in titles and collapse whitespace."""
    if not text:
        return ""
    return " ".join(re.sub(r"<[^>]+>", "", str(text)).split())


def _crossref_name(author: dict[str, Any]) -> str:
    family, given = _clean(author.get("family")), _clean(author.get("given"))
    return f"{family}, {given}" if given else family


def _crossref_year(m: dict[str, Any]) -> int | None:
    for key in ("published-print", "issued", "published-online", "published"):
        parts = (m.get(key) or {}).get("date-parts") or [[]]
        if parts and parts[0] and parts[0][0]:
            return int(parts[0][0])
    return None


def _reorder_name(name: str) -> str:
    """Open Library gives «Roald Dahl»; the parser expects the family name first: «Dahl, Roald»."""
    tokens = _clean(name).split()
    if len(tokens) < 2 or "," in name:
        return _clean(name)
    return f"{tokens[-1]}, {' '.join(tokens[:-1])}"


def _valid_name(name: str) -> bool:
    """Meta tags sometimes hold organisations or junk; keep only plausible personal names."""
    if not re.fullmatch(r"[\w .,'’\-]+", name):
        return False
    try:
        parse_name(name)
    except InvalidNameError:
        return False
    return True
