import pytest

from normokontrol_mcp.bibliography.names import (
    NBSP,
    InvalidNameError,
    heading,
    parse_name,
    statement_of_responsibility,
)


@pytest.mark.parametrize(
    ("raw", "family", "initials"),
    [
        ("Иванов Иван Иванович", "Иванов", ("И.", "И.")),
        ("Иванов И. И.", "Иванов", ("И.", "И.")),
        ("Иванов И.И.", "Иванов", ("И.", "И.")),
        ("Иванов, Иван Иванович", "Иванов", ("И.", "И.")),
        ("И. И. Иванов", "Иванов", ("И.", "И.")),
        ("И.И. Иванов", "Иванов", ("И.", "И.")),
        ("  Иванов   Иван  ", "Иванов", ("И.",)),
        ("Бонч-Осмоловская Елизавета Александровна", "Бонч-Осмоловская", ("Е.", "А.")),
        ("Дюма Жан-Поль", "Дюма", ("Ж.-П.",)),
        ("Kurkov Yu. B.", "Kurkov", ("Yu.", "B.")),
        ("Smith, John", "Smith", ("J.",)),
        ("Аристотель", "Аристотель", ()),
        (f"Иванов{NBSP}И.{NBSP}И.", "Иванов", ("И.", "И.")),
    ],
)
def test_parse_name(raw: str, family: str, initials: tuple[str, ...]) -> None:
    name = parse_name(raw)
    assert name.family == family
    assert name.initials == initials


@pytest.mark.parametrize("raw", ["", "   ", "И. И."])
def test_parse_name_errors(raw: str) -> None:
    with pytest.raises(InvalidNameError):
        parse_name(raw)


def test_name_forms_use_non_breaking_spaces() -> None:
    name = parse_name("Иванов Иван Иванович")
    assert name.heading() == f"Иванов,{NBSP}И.{NBSP}И."
    assert name.statement() == f"И.{NBSP}И.{NBSP}Иванов"


def test_name_without_initials() -> None:
    name = parse_name("Аристотель")
    assert name.heading() == "Аристотель"
    assert name.statement() == "Аристотель"


@pytest.mark.parametrize(("count", "has_heading"), [(0, False), (1, True), (3, True), (4, False), (5, False)])
def test_heading_only_for_one_to_three_authors(count: int, has_heading: bool) -> None:
    authors = [f"Автор{i} А. А." for i in range(count)]
    assert (heading(authors) is not None) is has_heading


def test_statement_four_authors_lists_all() -> None:
    authors = ["Яскин Е. Г.", "Бойко И. П.", "Снегирева А. В.", "Каторгина Г. И."]
    text = statement_of_responsibility(authors).replace(NBSP, " ")
    assert text == "Е. Г. Яскин, И. П. Бойко, А. В. Снегирева, Г. И. Каторгина"


def test_statement_five_authors_first_three_et_al() -> None:
    # ГОСТ Р 7.0.100-2018, п. 5.2.6.8, пример
    authors = ["Мельников А. В.", "Степанов В. А.", "Вах А. С.", "Четвёртый Г. Г.", "Пятый Д. Д."]
    text = statement_of_responsibility(authors).replace(NBSP, " ")
    assert text == "А. В. Мельников, В. А. Степанов, А. С. Вах [и др.]"
    assert statement_of_responsibility(authors, foreign=True).endswith("[et al.]")
