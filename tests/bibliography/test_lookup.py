import datetime as dt
import io
import json
import urllib.error
from email.message import Message
from pathlib import Path

import pytest

from normokontrol.bibliography import lookup
from normokontrol.bibliography.formatter import format_source
from normokontrol.bibliography.identifiers import Identifier, classify, normalize_isbn
from normokontrol.bibliography.models import Article, Book, BookChapter, Web
from normokontrol.bibliography.names import NBSP
from normokontrol.cli import EXIT_OK, run
from normokontrol.cli import bibliography as bib_cli
from normokontrol.cli import lookup as lookup_cli

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = dt.date(2026, 10, 3)
ARTICLE_DOI = "10.1016/j.patcog.2017.10.013"
CHAPTER_DOI = "10.1007/978-3-319-24574-4_28"
ISBN = "9780140328721"

RESPONSES = {
    lookup.CROSSREF_URL + ARTICLE_DOI: "crossref_journal_article.json",
    lookup.CROSSREF_URL + CHAPTER_DOI: "crossref_book_chapter.json",
    lookup.OPENLIBRARY_URL + ISBN: "openlibrary_book.json",
    "https://example.org/article": "article_page.html",
    "https://example.org/isbn": "web_page.html",
}


def plain(text: str) -> str:
    return text.replace(NBSP, " ")


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Network replaced by fixtures; cache in a temp folder; returns the list of requested URLs."""
    monkeypatch.setenv(lookup.CACHE_ENV, str(tmp_path / "cache"))
    monkeypatch.delenv(lookup.OFFLINE_ENV, raising=False)
    requested: list[str] = []

    def fake_get(url: str) -> str:
        requested.append(url)
        if url in RESPONSES:
            return (FIXTURES / RESPONSES[url]).read_text(encoding="utf-8")
        if url.startswith(lookup.OPENLIBRARY_URL):
            return "{}"
        raise lookup.LookupFailed(f"Не найдено: {url}", "not_found", url)

    monkeypatch.setattr(lookup, "http_get", fake_get)
    return requested


# --- распознавание идентификаторов ---------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "kind", "value"),
    [
        ("10.1016/j.patcog.2017.10.013", "doi", "10.1016/j.patcog.2017.10.013"),
        ("doi: 10.1016/j.patcog.2017.10.013", "doi", "10.1016/j.patcog.2017.10.013"),
        ("https://doi.org/10.1016/j.patcog.2017.10.013.", "doi", "10.1016/j.patcog.2017.10.013"),
        ("https://dx.doi.org/10.1007/978-3-319-24574-4_28", "doi", "10.1007/978-3-319-24574-4_28"),
        ("ISBN 978-5-534-00129-7", "isbn", "9785534001297"),
        ("978-0-14-032872-1", "isbn", "9780140328721"),
        ("0-14-032872-6", "isbn", "0140328726"),
        ("ISBN-10: 0-8044-2957-X", "isbn", "080442957X"),
        ("https://elibrary.ru/item.asp?id=13024552", "url", "https://elibrary.ru/item.asp?id=13024552"),
    ],
)
def test_classify(text: str, kind: str, value: str) -> None:
    assert classify(text) == Identifier(kind, value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "text",
    ["", "Иванов И. И. Основы программирования. М., 2020", "978-5-534-00129-8", "12345", "www.site.ru"],
)
def test_classify_rejects(text: str) -> None:
    assert classify(text) is None


def test_isbn_checksum() -> None:
    assert normalize_isbn("978-5-534-00129-7") == "9785534001297"
    assert normalize_isbn("978-5-534-00129-0") is None
    assert normalize_isbn("0-14-032872-7") is None


# --- разбор ответов ------------------------------------------------------------------------


def test_doi_journal_article() -> None:
    source = lookup.lookup_doi(ARTICLE_DOI)
    assert isinstance(source, Article)
    assert source.journal == "Pattern Recognition"
    assert source.year == 2018
    assert source.volume == "77"
    assert source.authors[0] == "Gu, Jiuxiang"
    assert plain(format_source(source)) == (
        "Recent advances in convolutional neural networks / J. Gu, Z. Wang, J. Kuen [et al.]. – "
        "DOI 10.1016/j.patcog.2017.10.013. – Текст : непосредственный // Pattern Recognition. – 2018. – "
        "Vol. 77. – P. 354–377."
    )


def test_doi_book_chapter_takes_book_title_not_series() -> None:
    source = lookup.lookup_doi(CHAPTER_DOI)
    assert isinstance(source, BookChapter)
    assert source.type == "book_chapter"
    assert source.book_title == "Medical Image Computing and Computer-Assisted Intervention – MICCAI 2015"
    assert source.city == "Cham"
    assert source.publisher == "Springer International Publishing"
    assert source.isbn == "9783319245737"
    assert source.pages == "234-241"


def test_isbn_open_library_reorders_names_and_keeps_printed_isbn() -> None:
    source = lookup.lookup_isbn(ISBN, printed="ISBN 978-0-14-032872-1")
    assert isinstance(source, Book)
    assert source.authors == ["Dahl, Roald"]
    assert source.publisher == "Puffin"
    assert source.year == 1988
    assert source.pages == 96
    assert source.isbn == "978-0-14-032872-1"
    assert plain(format_source(source)).startswith(
        "Dahl, R. Fantastic Mr. Fox / R. Dahl. – Puffin, 1988. – 96 p."
    )


def test_isbn_not_in_open_library() -> None:
    with pytest.raises(lookup.LookupFailed, match="не найдена в Open Library") as info:
        lookup.lookup_isbn("9785534001297")
    assert info.value.error_code == "not_found"


def test_url_article_meta_tags() -> None:
    source = lookup.lookup_url("https://example.org/article", today=TODAY)
    assert isinstance(source, Article)
    assert source.authors == ["Козлова Ирина Ивановна"]  # «Петров & Ко» не похоже на имя и отброшено
    assert source.pages == "25–32"
    assert source.year == 2019
    assert source.volume is None
    assert source.accessed == TODAY
    assert plain(format_source(source)).endswith(
        "// Садоводство и виноградарство. – 2019. – № 2. – С. 25–32. – URL: https://example.org/article "
        "(дата обращения: 03.10.2026)."
    )


def test_url_plain_web_page() -> None:
    source = lookup.lookup_url("https://example.org/isbn", today=TODAY)
    assert isinstance(source, Web)
    assert source.title == "Порядок присвоения номера ISBN"
    assert source.site == "Российская книжная палата"


def test_url_without_title() -> None:
    RESPONSES["https://example.org/empty"] = "web_page.html"
    try:
        with pytest.raises(lookup.LookupFailed, match="не найдено заглавие"):
            lookup.from_html("<html></html>", "https://example.org/empty", TODAY)
    finally:
        del RESPONSES["https://example.org/empty"]


def test_crossref_unsupported_type_and_missing_title() -> None:
    with pytest.raises(lookup.LookupFailed, match="«dataset»") as info:
        lookup.from_crossref({"type": "dataset", "title": ["Data"], "DOI": "10.1/x"})
    assert info.value.error_code == "unsupported"
    with pytest.raises(lookup.LookupFailed, match="нет заглавия"):
        lookup.from_crossref({"type": "journal-article", "title": []})


def test_crossref_cleans_markup_and_uses_issued_year() -> None:
    source = lookup.from_crossref(
        {
            "type": "book",
            "title": ["The <i>Big</i>   Book"],
            "author": [{"family": "Smith", "given": "John"}, {"name": "Consortium"}],
            "issued": {"date-parts": [[2015]]},
        }
    )
    assert isinstance(source, Book)
    assert source.title == "The Big Book"
    assert source.authors == ["Smith, John"]
    assert source.year == 2015


# --- сеть, кэш, офлайн ---------------------------------------------------------------------


def test_cache_avoids_second_request(isolated: list[str]) -> None:
    lookup.lookup_doi(ARTICLE_DOI)
    lookup.lookup_doi(ARTICLE_DOI)
    assert isolated.count(lookup.CROSSREF_URL + ARTICLE_DOI) == 1


def test_offline_uses_cache_only(isolated: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    lookup.lookup_doi(ARTICLE_DOI)
    monkeypatch.setenv(lookup.OFFLINE_ENV, "1")
    assert isinstance(lookup.lookup_doi(ARTICLE_DOI), Article)
    with pytest.raises(lookup.LookupFailed, match="Сеть отключена") as info:
        lookup.lookup_doi(CHAPTER_DOI)
    assert info.value.error_code == "network_unavailable"


def test_broken_cache_file_is_ignored(tmp_path: Path) -> None:
    path = lookup._cache_path(lookup.CROSSREF_URL + ARTICLE_DOI)
    assert path is not None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")
    assert isinstance(lookup.lookup_doi(ARTICLE_DOI), Article)


class _FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, charset: str | None) -> None:
        super().__init__(body)
        self.headers = Message()
        if charset:
            self.headers["Content-Type"] = f"text/html; charset={charset}"


def test_http_get_decodes_charset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()  # вернуть настоящий http_get
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: _FakeResponse("Привет".encode("cp1251"), "windows-1251"),
    )
    assert lookup.http_get("https://example.org") == "Привет"


@pytest.mark.parametrize(
    ("error", "code", "message"),
    [
        (urllib.error.HTTPError("u", 404, "nf", Message(), None), "not_found", "Не найдено"),
        (urllib.error.HTTPError("u", 503, "busy", Message(), None), "network_unavailable", "ошибкой 503"),
        (urllib.error.URLError("dns"), "network_unavailable", "Нет доступа к сети"),
        (TimeoutError("slow"), "network_unavailable", "Нет доступа к сети"),
    ],
)
def test_http_get_errors(monkeypatch: pytest.MonkeyPatch, error: Exception, code: str, message: str) -> None:
    monkeypatch.undo()

    def fail(request: object, timeout: float) -> None:
        raise error

    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(lookup.LookupFailed, match=message) as info:
        lookup.http_get("https://example.org")
    assert info.value.error_code == code


# --- CLI -----------------------------------------------------------------------------------


def test_lookup_cli(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(lookup_cli.main, [ARTICLE_DOI, "ISBN 978-5-534-00129-7", "просто текст"]) == EXIT_OK
    results = json.loads(capsys.readouterr().out)
    assert results[0]["source"]["type"] == "article"
    assert "accessed" not in results[0]["source"]
    assert results[1]["error"]["error_code"] == "not_found"
    assert results[2]["error"]["error_code"] == "unrecognized"


def test_format_mixed_input(tmp_path: Path) -> None:
    items = [
        {
            "type": "book",
            "authors": ["Иванов И. И."],
            "title": "Книга",
            "city": "М.",
            "publisher": "Ю",
            "year": 2020,
            "pages": 10,
        },
        ARTICLE_DOI,
        "Петров П. П. Статья в журнале, 2019",
        "ISBN 978-5-534-00129-7",
    ]
    path = tmp_path / "sources.json"
    path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    out = plain(bib_cli.main([str(path)]))
    lines = out.splitlines()
    assert lines[0].startswith("1. Иванов, И. И. Книга")
    assert lines[1].startswith("2. Recent advances in convolutional neural networks")
    assert (
        "- Источник 2 («10.1016/j.patcog.2017.10.013») найден автоматически — сверьте данные с оригиналом"
        in out
    )
    assert "Не удалось оформить автоматически" in out
    assert "- 3. «Петров П. П. Статья в журнале, 2019»: не распознан DOI, ISBN или ссылка" in out
    assert "- 4. «ISBN 978-5-534-00129-7»: Книга с ISBN 9785534001297 не найдена в Open Library" in out

    data = json.loads(bib_cli.main([str(path), "--json"]))
    assert [item["index"] for item in data["unresolved"]] == [3, 4]
    assert data["looked_up"][0]["source"]["journal"] == "Pattern Recognition"


def test_format_only_unresolved(tmp_path: Path) -> None:
    path = tmp_path / "sources.json"
    path.write_text(json.dumps(["что-то непонятное"], ensure_ascii=False), encoding="utf-8")
    out = bib_cli.main([str(path)])
    assert out.startswith("Не удалось оформить автоматически")


def test_format_rejects_non_source_items(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "sources.json"
    path.write_text("[42]", encoding="utf-8")
    assert run(bib_cli.main, [str(path)]) == 2
    assert "источник 1: ожидался объект источника" in capsys.readouterr().err
