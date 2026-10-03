import json
from pathlib import Path

import pytest

from normokontrol.bibliography.names import NBSP
from normokontrol.cli import EXIT_ERROR, EXIT_OK, run
from normokontrol.cli import bibliography as bib_cli
from normokontrol.cli import presets as presets_cli

BOOK = {
    "type": "book",
    "authors": ["Иванов Иван Иванович", "Петров Пётр Петрович"],
    "title": "Основы программирования",
    "subtitle": "учебник",
    "city": "Москва",
    "publisher": "Юрайт",
    "year": 2020,
    "pages": 350,
}


def write_json(tmp_path: Path, data: object, name: str = "sources.json") -> str:
    path = tmp_path / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


# --- presets ------------------------------------------------------------------------------


def test_presets_list() -> None:
    out = presets_cli.main(["list"])
    assert "gost-7.32-2017 — ГОСТ 7.32-2017 (базовый) (RU, сверен с первоисточником)" in out


def test_presets_list_json() -> None:
    data = json.loads(presets_cli.main(["list", "--json"]))
    assert data[0]["id"] == "gost-7.32-2017"


def test_presets_rules_and_yaml() -> None:
    assert "**Поля:** левое 30 мм" in presets_cli.main(["rules", "gost-7.32-2017"])
    assert "id: gost-7.32-2017" in presets_cli.main(["yaml", "gost-7.32-2017"])


def test_presets_unknown_is_structured_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(presets_cli.main, ["rules", "nope"]) == EXIT_ERROR
    error = json.loads(capsys.readouterr().err)
    assert error["error_code"] == "preset_not_found"
    assert "не найден" in error["message_ru"]


# --- bibliography --------------------------------------------------------------------------


def test_format_from_list(tmp_path: Path) -> None:
    out = bib_cli.main([write_json(tmp_path, [BOOK])]).replace(NBSP, " ")
    assert out == (
        "1. Иванов, И. И. Основы программирования : учебник / И. И. Иванов, П. П. Петров. – "
        "Москва : Юрайт, 2020. – 350 с. – Текст : непосредственный."
    )


def test_format_from_yaml_object_with_options(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text(
        "order: alphabetical\nsources:\n"
        "  - {type: web, title: Яндекс, url: 'https://ya.ru', accessed: 2026-09-01}\n"
        "  - {type: web, title: Альфа, url: 'https://a.ru', accessed: 01.09.2026}\n",
        encoding="utf-8",
    )
    out = bib_cli.main([str(path)])
    assert out.splitlines()[0].startswith("1. Альфа")
    assert "(дата обращения: 01.09.2026)" in out


def test_order_flag_overrides_file(tmp_path: Path) -> None:
    data = {"order": "alphabetical", "sources": [BOOK | {"title": "Я"}, BOOK | {"title": "А"}]}
    out = bib_cli.main([write_json(tmp_path, data), "--order", "by_citation"])
    assert "Я" in out.splitlines()[0]


def test_format_warnings_in_text(tmp_path: Path) -> None:
    out = bib_cli.main([write_json(tmp_path, [{"type": "book", "id": "x", "title": "Книга"}])])
    assert "Предупреждения (данные нужно уточнить у пользователя):" in out
    assert "- Источник «x»: не указано — место издания (city)" in out


def test_format_json_output(tmp_path: Path) -> None:
    data = json.loads(bib_cli.main([write_json(tmp_path, [BOOK, {"type": "web", "title": "Т"}]), "--json"]))
    assert len(data["entries"]) == 2
    assert data["warnings"][0] == {
        "index": 2,
        "source_id": None,
        "message_ru": "Источник «Т»: не указано — адрес страницы (url)",
    }


def test_preset_style_applied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "presets").mkdir()
    (tmp_path / "presets" / "uni.yaml").write_text(
        "id: uni\nname: Вуз\nextends: gost-7.32-2017\nsource_docs: [Методичка]\n"
        "bibliography: {dash: '—', content_type: false}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NORMOKONTROL_PRESETS_DIR", str(tmp_path / "presets"))
    out = bib_cli.main([write_json(tmp_path, [BOOK]), "--preset", "uni"])
    assert ". — Москва" in out
    assert "Текст" not in out


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ([{"type": "book"}], "источник 1 (book), title: обязательный параметр не указан"),
        ([BOOK, {"type": "thesis", "title": "Т"}], "источник 2, неизвестный тип 'thesis'"),
        ([{"title": "Т"}], "источник 1, не указан тип (поле 'type')"),
        ([BOOK | {"autors": ["А"]}], "источник 1 (book), autors: неизвестный параметр"),
        ([BOOK | {"authors": [""]}], "источник 1 (book), authors: пустое имя автора"),
        ([{"type": "web", "title": "Т", "accessed": "вчера"}], "accessed: ожидалась дата"),
        ({"items": []}, "Ожидался список источников"),
    ],
)
def test_input_errors_in_russian(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], data: object, expected: str
) -> None:
    assert run(bib_cli.main, [write_json(tmp_path, data)]) == EXIT_ERROR
    error = json.loads(capsys.readouterr().err)
    assert error["error_code"] == "input_invalid"
    assert expected in error["message_ru"]


def test_unreadable_and_invalid_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(bib_cli.main, [str(tmp_path / "missing.json")]) == EXIT_ERROR
    assert "Не удалось прочитать файл" in capsys.readouterr().err
    bad = tmp_path / "bad.json"
    bad.write_text("[{", encoding="utf-8")
    assert run(bib_cli.main, [str(bad)]) == EXIT_ERROR
    assert "не является корректным JSON/YAML" in capsys.readouterr().err
    cp1251 = tmp_path / "cp1251.json"
    cp1251.write_bytes('[{"title": "Книга"}]'.encode("cp1251"))
    assert run(bib_cli.main, [str(cp1251)]) == EXIT_ERROR
    assert "UTF-8" in capsys.readouterr().err


def test_bad_order_in_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(bib_cli.main, [write_json(tmp_path, {"order": "random", "sources": [BOOK]})]) == EXIT_ERROR
    assert "Неизвестный порядок" in capsys.readouterr().err


def test_stdin_input(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps([BOOK], ensure_ascii=False)))
    assert run(bib_cli.main, ["-"]) == EXIT_OK
    assert capsys.readouterr().out.startswith("1. Иванов")
