import pytest

from normokontrol.document.markdown_in import (
    CodeBlock,
    DocumentError,
    Formula,
    Heading,
    Image,
    ListBlock,
    Paragraph,
    Table,
    parse,
)


def test_front_matter_and_blocks() -> None:
    doc = parse(
        "---\npreset: gost-7.32-2017\nsources: [ ]\n---\n"
        "# ВВЕДЕНИЕ\n\nПервая строка\nвторая строка.\n\n"
        "## Подраздел\n"
    )
    assert doc.front.preset == "gost-7.32-2017"
    heading, paragraph, sub = doc.blocks
    assert isinstance(heading, Heading) and heading.level == 1 and heading.line == 5
    assert isinstance(paragraph, Paragraph) and paragraph.text == "Первая строка вторая строка."
    assert isinstance(sub, Heading) and sub.text == "Подраздел"


def test_explanation_after_formula_keeps_lines() -> None:
    (paragraph,) = parse("где E — энергия;\nm — масса.\n").blocks
    assert isinstance(paragraph, Paragraph)
    assert paragraph.text == "где E — энергия;\nm — масса."


def test_image_table_formula_code_list() -> None:
    doc = parse(
        "![Схема](img/a.png){#fig:a}\n\n"
        ": Сравнение {#tbl:c}\n\n| A | B |\n|---|:---:|\n| 1 | 2 |\n\n"
        "$$ E = mc^2 $$ {#eq:e}\n\n"
        "$$\nx = 1\n$$\n\n"
        "```\ncode  line\n```\n\n"
        "- раз\n  продолжение\n- два\n\nа) буква\n1. цифра\n"
    )
    image, table, formula, unnumbered, code, bullets, mixed = doc.blocks
    assert isinstance(image, Image) and (image.caption, image.path, image.anchor) == (
        "Схема",
        "img/a.png",
        "fig:a",
    )
    assert isinstance(table, Table) and table.header == ["A", "B"] and table.rows == [["1", "2"]]
    assert isinstance(formula, Formula) and (formula.latex, formula.anchor) == ("E = mc^2", "eq:e")
    assert isinstance(unnumbered, Formula) and unnumbered.anchor is None and unnumbered.latex == "x = 1"
    assert isinstance(code, CodeBlock) and code.lines == ["code  line"]
    assert isinstance(bullets, ListBlock) and [i.text for i in bullets.items] == ["раз продолжение", "два"]
    assert isinstance(mixed, ListBlock) and [i.marker for i in mixed.items] == ["letter", "number"]


@pytest.mark.parametrize(
    ("text", "message", "line"),
    [
        ("---\npreset: x\n", "не закрыт строкой «---»", 1),
        ("---\nunknown: 1\n---\n", "unknown: неизвестный параметр", 1),
        ("---\n- a\n---\n", "набором «ключ: значение»", 1),
        ("Текст\n\n| A |\n|---|\n", "Таблица без названия", 3),
        (": Т {#tbl:t}\n| A | B |\n| 1 | 2 |\n", "строка заголовка и разделитель", 2),
        (": Т {#tbl:t}\n| A | B |\n|---|---|\n| 1 |\n", "1 ячеек, а в заголовке 2", 4),
        ("$$\nx = 1\n", "Формула не закрыта", 1),
        ("```\ncode\n", "Блок кода не закрыт", 1),
        ("![Р](a.png){#figure:a}\n", "Неверная метка «{#figure:a}»", 1),
    ],
)
def test_errors_point_to_line(text: str, message: str, line: int) -> None:
    with pytest.raises(DocumentError) as info:
        parse(text, name="работа.md")
    assert message in info.value.message_ru
    assert info.value.location == f"работа.md:{line}"
