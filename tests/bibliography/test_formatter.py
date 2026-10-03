import datetime as dt

import pytest
from pydantic import TypeAdapter, ValidationError

from normokontrol.bibliography.formatter import Style, format_bibliography, format_source, sort_key
from normokontrol.bibliography.models import Article, Book, Law, Source, Standard, Web
from normokontrol.bibliography.names import NBSP

SOURCE = TypeAdapter(Source)


def plain(text: str) -> str:
    return text.replace(NBSP, " ")


def book(**fields: object) -> Book:
    data: dict[str, object] = {
        "type": "book",
        "authors": ["Иванов Иван Иванович"],
        "title": "Основы программирования",
        "city": "Москва",
        "publisher": "Юрайт",
        "year": 2020,
        "pages": 350,
    }
    return Book.model_validate(data | fields)


# --- пунктуация и мелкие правила ------------------------------------------------------------


def test_record_ends_with_single_full_stop() -> None:
    assert format_source(book()).endswith("непосредственный.")
    record = format_source(book(edition="2-е изд., перераб. и доп."), Style(content_type=False))
    assert "доп. – Москва" in record  # точка сокращения не удваивается (ГОСТ Р 7.0.100, п. 4.6.11)
    assert ".." not in record


def test_non_breaking_spaces_in_record() -> None:
    record = format_source(book())
    assert f"Иванов,{NBSP}И.{NBSP}И." in record
    assert f"И.{NBSP}И.{NBSP}Иванов" in record
    assert f"350{NBSP}с." in record


def test_page_range_uses_en_dash() -> None:
    article = Article(type="article", title="Статья", journal="Журнал", year=2020, issue=1, pages="15 - 20")
    assert f"С.{NBSP}15–20." in format_source(article)


def test_volume_and_issue_combined() -> None:
    article = Article(type="article", title="Статья", journal="Журнал", year=2020, volume=5, issue=2, pages=7)
    assert "– 2020. – Т. 5, № 2. – С. 7." in plain(format_source(article))


def test_dash_style() -> None:
    record = format_source(book(), Style(dash="—"))
    assert ". — Москва" in record
    assert "–" not in record


def test_electronic_resource_is_text_electronic() -> None:
    record = format_source(book(url="https://example.org", accessed=dt.date(2026, 9, 1)))
    assert record.endswith("URL: https://example.org (дата обращения: 01.09.2026). – Текст : электронный.")


def test_foreign_book_uses_p() -> None:
    record = plain(format_source(book(title="Programming basics", authors=["Smith John"])))
    assert "350 p." in record


def test_web_page_without_site_or_year() -> None:
    page = Web(type="web", title="Страница", url="https://example.org", accessed=dt.date(2026, 1, 2))
    assert format_source(page) == (
        "Страница : сайт. – URL: https://example.org (дата обращения: 02.01.2026). – Текст : электронный."
    )


def test_law_print_publication_with_content_type() -> None:
    law = Law(
        type="law",
        title="Об исполнительном производстве",
        act_type="Федеральный закон",
        number="229-ФЗ",
        details=["принят Государственной думой 14 сентября 2007 года"],
        publication="Собрание законодательства Российской Федерации",
        year=2007,
        issue=41,
        article=4849,
    )
    assert plain(format_source(law)) == (
        "Об исполнительном производстве : Федеральный закон № 229-ФЗ : принят Государственной думой "
        "14 сентября 2007 года. – Текст : непосредственный // Собрание законодательства Российской "
        "Федерации. – 2007. – № 41. – Ст. 4849."
    )


def test_standard_online() -> None:
    standard = Standard(
        type="standard",
        designation="ГОСТ Р 7.0.100–2018",
        title="Библиографическая запись. Библиографическое описание",
        kind="национальный стандарт Российской Федерации",
        effective_date=dt.date(2019, 7, 1),
        site="Росстандарт",
        url="https://example.org/gost",
        accessed=dt.date(2026, 9, 1),
    )
    assert format_source(standard) == (
        "ГОСТ Р 7.0.100–2018. Библиографическая запись. Библиографическое описание : национальный "
        "стандарт Российской Федерации : дата введения 2019-07-01. – Текст : электронный // "
        "Росстандарт : [сайт]. – URL: https://example.org/gost (дата обращения: 01.09.2026)."
    )


def test_accessed_accepts_russian_date() -> None:
    page = SOURCE.validate_python({"type": "web", "title": "Т", "url": "u", "accessed": "01.09.2026"})
    assert page.accessed == dt.date(2026, 9, 1)


def test_invalid_author_rejected() -> None:
    with pytest.raises(ValidationError, match="пустое имя автора"):
        SOURCE.validate_python({"type": "book", "title": "Т", "authors": [" "]})


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        SOURCE.validate_python({"type": "book", "title": "Т", "autors": ["Иванов И. И."]})


# --- список целиком -------------------------------------------------------------------------


def test_numbering_and_citation_order() -> None:
    result = format_bibliography([book(title="Б-книга"), book(title="А-книга")], numbering="{n}. ")
    assert result.entries[0].startswith("1. Иванов")
    assert "Б-книга" in result.entries[0]
    assert result.text == "\n".join(result.entries)


def test_alphabetical_order_cyrillic_then_latin() -> None:
    sources = [
        book(authors=["Smith John"], title="Zebra"),
        book(authors=["Яковлев Я. Я."], title="Книга"),
        book(authors=["Ёлкин Е. Е."], title="Книга"),
        book(authors=["Абрамов А. А."], title="Книга"),
        book(authors=["Adams John"], title="Apple"),
    ]
    result = format_bibliography(sources, order="alphabetical", numbering="{n} ")
    firsts = [entry.split(" ", 1)[1].split(",")[0] for entry in result.entries]
    assert firsts == ["Абрамов", "Ёлкин", "Яковлев", "Adams", "Smith"]


def test_sort_key_ignores_leading_quotes() -> None:
    assert sort_key("«Мы хорошие»")[1].startswith("мы")


def test_formatting_is_deterministic() -> None:
    sources = [book(), book(title="Другая")]
    assert format_bibliography(sources).text == format_bibliography(sources).text


# --- предупреждения о недостающих полях -----------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ({"type": "book", "title": "Книга"}, ["место издания", "издательство", "год издания", "страниц"]),
        ({"type": "article", "title": "Статья"}, ["название журнала", "год", "страницы статьи"]),
        ({"type": "web", "title": "Сайт"}, ["адрес страницы"]),
        ({"type": "web", "title": "Сайт", "url": "https://x.ru"}, ["дата обращения"]),
        (
            {"type": "law", "title": "Закон"},
            ["вид документа", "номер (number) или дата", "официальное издание"],
        ),
        ({"type": "standard", "title": "Стандарт"}, ["обозначение стандарта", "год издания"]),
        (
            {"type": "book_chapter", "title": "Глава"},
            ["заглавие книги", "год издания", "место издания", "издательство", "страницы"],
        ),
        (
            {"type": "conference_paper", "title": "Доклад", "url": "https://x.ru", "accessed": "2026-01-01"},
            ["заглавие книги", "год издания"],
        ),
        (
            {"type": "thesis", "title": "Диссертация"},
            ["автор", "учёная степень", "место защиты", "год", "количество страниц"],
        ),
        (
            {"type": "patent", "title": "Патент"},
            ["номер патента", "номер заявки", "дата подачи", "дата публикации"],
        ),
    ],
)
def test_missing_field_warnings(source: dict[str, object], expected: list[str]) -> None:
    result = format_bibliography([SOURCE.validate_python(source)])
    messages = [warning.message_ru for warning in result.warnings]
    assert len(messages) == len(expected)
    for message, fragment in zip(messages, expected, strict=True):
        assert fragment in message


def test_complete_sources_have_no_warnings() -> None:
    article = Article(type="article", title="Статья", journal="Журнал", year=2020, issue=1, pages="1-2")
    assert format_bibliography([book(), article]).warnings == []


def test_warning_points_to_source() -> None:
    result = format_bibliography([book(), Book(type="book", id="petrov2021", title="Без данных")])
    assert {w.index for w in result.warnings} == {2}
    assert all(w.source_id == "petrov2021" for w in result.warnings)
    assert "«petrov2021»" in result.warnings[0].message_ru


def test_new_types_without_optional_parts() -> None:
    thesis = SOURCE.validate_python({"type": "thesis", "title": "Тема", "city": "Москва", "year": 2020})
    assert format_source(thesis) == "Тема : диссертация. – Москва, 2020. – Текст : непосредственный."
    patent = SOURCE.validate_python({"type": "patent", "title": "Устройство"})
    assert format_source(patent) == "Патент Российская Федерация. Устройство. – Текст : непосредственный."
    chapter = SOURCE.validate_python(
        {"type": "book_chapter", "title": "Chapter", "book_title": "Book", "pages": "1-2", "doi": "10.1/x"}
    )
    assert plain(format_source(chapter)) == (
        "Chapter. – DOI 10.1/x. – Текст : непосредственный // Book. – P. 1–2."
    )
    with_doi = book(doi="10.1/y")
    assert "ISBN" not in format_source(with_doi)
    assert "– DOI 10.1/y. – Текст" in format_source(with_doi)
