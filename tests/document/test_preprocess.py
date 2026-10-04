from pathlib import Path

import pytest
import yaml
from pydantic import TypeAdapter

from normokontrol.bibliography.models import Source
from normokontrol.bibliography.names import NBSP
from normokontrol.document.markdown_in import DocumentError, parse
from normokontrol.document.preprocess import (
    OutBibliography,
    OutFigure,
    OutFormula,
    OutHeading,
    OutList,
    OutParagraph,
    OutTable,
    Prepared,
    prepare,
)
from normokontrol.presets.loader import USER_DIR_ENV, load_preset

SOURCES = TypeAdapter(list[Source]).validate_python(
    [
        {
            "id": "b",
            "type": "book",
            "authors": ["Борисов Б. Б."],
            "title": "Книга Б",
            "city": "М",
            "publisher": "П",
            "year": 2020,
            "pages": 10,
        },
        {
            "id": "a",
            "type": "book",
            "authors": ["Андреев А. А."],
            "title": "Книга А",
            "city": "М",
            "publisher": "П",
            "year": 2021,
            "pages": 20,
        },
    ]
)


def run(text: str, preset_id: str = "gost-7.32-2017", sources: list[Source] | None = None) -> Prepared:
    return prepare(parse(text), load_preset(preset_id), SOURCES if sources is None else sources, name="т.md")


def headings(prepared: Prepared) -> list[str]:
    return [block.text for block in prepared.blocks if isinstance(block, OutHeading)]


def plain(text: str) -> str:
    return text.replace(NBSP, " ")


DRAFT = """
# ВВЕДЕНИЕ
Текст [@b].
# Первый раздел
## Обзор
См. рисунок [@fig:x] и таблицу [@tbl:t], формулу [@eq:e], приложение [@app:z], источник [@a, с. 15].
![Схема](a.png){#fig:x}
: Таблица {#tbl:t}

| A |
|---|
| [@b] |

$$ x = 1 $$ {#eq:e}

$$ y = 2 $$

- пункт
а) буква
## Второй подраздел
### Пункт
# Второй раздел
![Ещё](b.png){#fig:y}
# ЗАКЛЮЧЕНИЕ
# ПРИЛОЖЕНИЕ {#app:z}
## Листинг
![В приложении](c.png)
## Раздел приложения
# ПРИЛОЖЕНИЕ
"""


def test_numbering_and_references() -> None:
    prepared = run(DRAFT)
    assert headings(prepared) == [
        "ВВЕДЕНИЕ",
        "1 Первый раздел",
        "1.1 Обзор",
        "1.2 Второй подраздел",
        "1.2.1 Пункт",
        "2 Второй раздел",
        "ЗАКЛЮЧЕНИЕ",
        "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ",
        "ПРИЛОЖЕНИЕ А",
        "А.1 Раздел приложения",
        "ПРИЛОЖЕНИЕ Б",
    ]
    appendix = next(b for b in prepared.blocks if isinstance(b, OutHeading) and b.kind == "appendix")
    assert appendix.appendix_title == "Листинг"
    texts = [b.text for b in prepared.blocks if isinstance(b, OutParagraph)]
    assert texts[0] == "Текст [1]."
    assert texts[1] == "См. рисунок 1 и таблицу 1, формулу (1), приложение А, источник [2, с. 15]."
    figures = [b.caption for b in prepared.blocks if isinstance(b, OutFigure)]
    assert figures == ["Рисунок 1 — Схема", "Рисунок 2 — Ещё", "Рисунок А.1 — В приложении"]
    table = next(b for b in prepared.blocks if isinstance(b, OutTable))
    assert table.caption == "Таблица 1 — Таблица"
    assert table.rows == [["[1]"]]
    formulas = [b.number for b in prepared.blocks if isinstance(b, OutFormula)]
    assert formulas == ["(1)", None]
    lists = [b.items for b in prepared.blocks if isinstance(b, OutList)]
    assert lists == [["— пункт", "а) буква"]]


def test_bibliography_inserted_before_appendices_in_citation_order() -> None:
    prepared = run(DRAFT)
    kinds = [type(b).__name__ for b in prepared.blocks]
    bib_index = kinds.index("OutBibliography")
    assert isinstance(prepared.blocks[bib_index - 1], OutHeading)
    entries = next(b for b in prepared.blocks if isinstance(b, OutBibliography)).entries
    assert plain(entries[0]).startswith("1. Борисов, Б. Б. Книга Б")
    assert plain(entries[1]).startswith("2. Андреев, А. А. Книга А")
    assert prepared.stats == {
        "разделов": 2, "рисунков": 3, "таблиц": 1, "формул": 1, "приложений": 2, "источников": 2
    }  # fmt: skip


def test_bibliography_at_heading_and_alphabetical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "alpha.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "alpha",
                "name": "А",
                "extends": "gost-7.32-2017",
                "source_docs": ["x"],
                "bibliography": {"order": "alphabetical"},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(USER_DIR_ENV, str(tmp_path))
    prepared = run("# ВВЕДЕНИЕ\n[@b] [@a]\n# СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ\n# ЗАКЛЮЧЕНИЕ\n", "alpha")
    assert headings(prepared)[1] == "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ"
    entries = next(b for b in prepared.blocks if isinstance(b, OutBibliography)).entries
    assert plain(entries[0]).startswith("1. Андреев")
    text = next(b for b in prepared.blocks if isinstance(b, OutParagraph)).text
    assert text == "[2] [1]"


def test_per_chapter_numbering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "chap.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "chap",
                "name": "Ч",
                "extends": "gost-7.32-2017",
                "source_docs": ["x"],
                "figures": {"numbering": "per_chapter"},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(USER_DIR_ENV, str(tmp_path))
    prepared = run("# Раздел\n![А](a.png)\n![Б](b.png)\n# Ещё\n![В](c.png)\n", "chap", sources=[])
    assert [b.caption for b in prepared.blocks if isinstance(b, OutFigure)] == [
        "Рисунок 1.1 — А", "Рисунок 1.2 — Б", "Рисунок 2.1 — В"
    ]  # fmt: skip
    with pytest.raises(DocumentError, match="вне нумерованного раздела"):
        run("# ВВЕДЕНИЕ\n![А](a.png)\n", "chap", sources=[])


def test_uncited_source_warning() -> None:
    prepared = run("# ВВЕДЕНИЕ\nТекст [@a].\n")
    assert any("«b» не упомянут в тексте" in warning for warning in prepared.warnings)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("# ВВЕДЕНИЕ\n[@nope]\n", "Ссылка [@nope] на источник, которого нет"),
        ("# ВВЕДЕНИЕ\n[@fig:nope]\n", "несуществующую метку «fig:nope»"),
        ("# Р\n![А](a.png){#fig:x}\n![Б](b.png){#fig:x}\n", "«fig:x» использована дважды"),
        ("# ВВЕДЕНИЕ\n## Подраздел\n", "вне нумерованного раздела"),
        ("# Раздел\n### Пункт\n", "Пропущен уровень заголовка"),
        ("# ПРИЛОЖЕНИЕ\n# Раздел\n", "После приложений не может быть"),
        ("# СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ\nТекст\n", "формируется автоматически"),
    ],
)
def test_errors(text: str, message: str) -> None:
    with pytest.raises(DocumentError, match=message.replace("[", r"\[").replace("]", r"\]")):
        run(text)


def test_too_many_appendices() -> None:
    with pytest.raises(DocumentError, match="закончились допустимые буквы"):
        run("# ПРИЛОЖЕНИЕ\n" * 26, sources=[])
