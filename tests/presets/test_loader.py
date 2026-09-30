from pathlib import Path

import pytest
import yaml

from normokontrol_mcp.errors import PresetError, PresetNotFoundError
from normokontrol_mcp.presets import loader
from normokontrol_mcp.presets.loader import USER_DIR_ENV, list_presets, load_preset, merge_preset_dicts

BASE = "gost-7.32-2017"


@pytest.fixture
def user_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(USER_DIR_ENV, str(tmp_path))
    return tmp_path


def write(directory: Path, preset_id: str, data: dict[str, object] | str) -> Path:
    path = directory / f"{preset_id}.yaml"
    text = data if isinstance(data, str) else yaml.safe_dump(data, allow_unicode=True)
    path.write_text(text, encoding="utf-8")
    return path


def child(preset_id: str, extends: str = BASE, **extra: object) -> dict[str, object]:
    return {
        "id": preset_id,
        "name": f"Пресет {preset_id}",
        "source_docs": ["Методичка"],
        "extends": extends,
    } | extra


# --- базовый пресет -------------------------------------------------------------------------


def test_base_preset_matches_gost_7_32() -> None:
    preset = load_preset(BASE)
    assert preset.verified is True
    assert preset.page.size == "A4"
    margins = preset.page.margins_mm
    assert (margins.left, margins.right, margins.top, margins.bottom) == (30, 15, 20, 20)
    assert preset.text.font == "Times New Roman"
    assert preset.text.min_size_pt == 12
    assert preset.text.line_spacing == 1.5
    assert preset.text.first_line_indent_cm == 1.25
    assert preset.page_numbers.position == "bottom-center"
    assert preset.page_numbers.show_on_title is False
    assert preset.bibliography.order == "by_citation"
    assert "ПЕРЕЧЕНЬ СОКРАЩЕНИЙ И ОБОЗНАЧЕНИЙ" in preset.headings.structural_titles
    for excluded in "ЁЗЙОЧЪЫЬ":
        assert excluded not in preset.appendices.letters
        assert excluded.lower() not in preset.lists.letters


def test_base_preset_every_setting_has_source() -> None:
    preset = load_preset(BASE)
    sections = ["page", "text", "headings", "page_numbers", "figures", "tables", "formulas"]
    sections += ["bibliography", "appendices", "lists"]
    for section in sections:
        value = getattr(preset, section)
        if section in preset.sources:
            continue
        for field in type(value).model_fields:
            assert f"{section}.{field}" in preset.sources, f"нет источника для {section}.{field}"


# --- наследование ---------------------------------------------------------------------------


def test_extends_deep_merge(user_dir: Path) -> None:
    write(user_dir, "uni", child("uni", figures={"numbering": "per_chapter"}, text={"size_pt": 13}))
    preset = load_preset("uni")
    assert preset.extends == BASE
    assert preset.figures.numbering == "per_chapter"
    assert preset.figures.caption == "Рисунок {num} — {title}"  # унаследовано
    assert preset.text.size_pt == 13
    assert preset.text.font == "Times New Roman"  # соседний параметр не потерян
    assert preset.page.margins_mm.left == 30


def test_verified_and_source_docs_are_not_inherited(user_dir: Path) -> None:
    write(user_dir, "uni", child("uni"))
    preset = load_preset("uni")
    assert preset.verified is False
    assert preset.source_docs == ["Методичка"]
    assert preset.name == "Пресет uni"


def test_overridden_value_drops_parent_source(user_dir: Path) -> None:
    data = child(
        "uni", figures={"numbering": "per_chapter"}, sources={"figures.numbering": "Методичка, п. 3"}
    )
    write(user_dir, "uni", data)
    write(user_dir, "uni2", child("uni2", text={"font": "Arial"}))
    preset = load_preset("uni")
    assert preset.sources["figures.numbering"] == "Методичка, п. 3"
    assert preset.sources["figures.caption"].startswith("ГОСТ 7.32-2017")
    assert "text.font" not in load_preset("uni2").sources


def test_override_nested_value_drops_parent_group_source(user_dir: Path) -> None:
    write(user_dir, "uni", child("uni", page={"margins_mm": {"left": 25}}))
    preset = load_preset("uni")
    assert preset.page.margins_mm.left == 25
    assert preset.page.margins_mm.right == 15
    assert "page.margins_mm" not in preset.sources


def test_extends_chain(user_dir: Path) -> None:
    write(user_dir, "uni", child("uni", figures={"numbering": "per_chapter"}))
    write(user_dir, "uni-master", child("uni-master", extends="uni", text={"size_pt": 12}))
    preset = load_preset("uni-master")
    assert preset.figures.numbering == "per_chapter"
    assert preset.text.size_pt == 12
    assert preset.extends == "uni"


def test_extends_cycle(user_dir: Path) -> None:
    write(user_dir, "a", child("a", extends="b"))
    write(user_dir, "b", child("b", extends="a"))
    with pytest.raises(PresetError, match="Цикл наследования пресетов: a → b → a"):
        load_preset("a")


def test_extends_self(user_dir: Path) -> None:
    write(user_dir, "a", child("a", extends="a"))
    with pytest.raises(PresetError, match="Цикл наследования"):
        load_preset("a")


def test_extends_unknown(user_dir: Path) -> None:
    write(user_dir, "a", child("a", extends="nope"))
    with pytest.raises(PresetError, match="наследует несуществующий пресет «nope»"):
        load_preset("a")


def test_merge_replaces_lists() -> None:
    parent = {"headings": {"structural_titles": ["А", "Б"]}, "sources": {}}
    merged = merge_preset_dicts(parent, {"headings": {"structural_titles": ["В"]}})
    assert merged["headings"]["structural_titles"] == ["В"]


# --- ошибки валидации на русском -------------------------------------------------------------


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"text": {"fnt": "Arial"}}, "text.fnt: неизвестный параметр"),
        ({"page": {"size": "A5"}}, "page.size: недопустимое значение 'A5'"),
        ({"page": {"margins_mm": {"left": -1}}}, "page.margins_mm.left: значение должно быть больше 0"),
        ({"text": {"size_pt": "большой"}}, "text.size_pt: ожидалось число"),
        ({"headings": {"structural": {"bold": "жирный"}}}, "ожидалось true или false"),
        ({"text": {"size_pt": 10}}, "размер шрифта 10.0 пт меньше минимально допустимого 12.0 пт"),
        ({"figures": {"caption": "Рисунок {n} — {title}"}}, "неизвестные поля {n}"),
        ({"tables": {"caption": "Таблица {num}"}}, "не хватает полей {title}"),
        ({"headings": {"structural_titles": ["Введение"]}}, "должно быть прописными"),
        ({"bibliography": {"title": "СПИСОК ЛИТЕРАТУРЫ"}}, "должен входить в headings.structural_titles"),
        ({"sources": {"text.fnt": "x"}}, "несуществующий параметр «text.fnt»"),
        ({"rules": {"typo-1": "error"}}, "значение 'typo-1' имеет неверный формат"),
    ],
)
def test_validation_errors_in_russian(user_dir: Path, override: dict[str, object], expected: str) -> None:
    write(user_dir, "bad", child("bad", **override))
    with pytest.raises(PresetError) as info:
        load_preset("bad")
    assert expected in info.value.message_ru
    assert info.value.location is not None
    assert info.value.location.endswith("bad.yaml")


def test_missing_required_field(user_dir: Path) -> None:
    write(user_dir, "bare", {"id": "bare", "name": "Без базы", "country": "RU", "source_docs": ["x"]})
    with pytest.raises(PresetError) as info:
        load_preset("bare")
    assert "page: обязательный параметр не указан" in info.value.message_ru


def test_id_must_match_file_name(user_dir: Path) -> None:
    write(user_dir, "uni", child("other"))
    with pytest.raises(PresetError, match="должно совпадать с именем файла"):
        load_preset("uni")


def test_yaml_syntax_error_has_line(user_dir: Path) -> None:
    write(user_dir, "broken", "id: broken\nname: [не закрыто\n")
    with pytest.raises(PresetError, match=r"Ошибка синтаксиса YAML в broken\.yaml, строка \d"):
        load_preset("broken")


def test_yaml_must_be_mapping(user_dir: Path) -> None:
    write(user_dir, "list", "- a\n- b\n")
    with pytest.raises(PresetError, match="должен содержать словарь"):
        load_preset("list")


# --- поиск пресетов -------------------------------------------------------------------------


def test_unknown_preset() -> None:
    with pytest.raises(PresetNotFoundError, match=f"Пресет «nope» не найден.*{BASE}"):
        load_preset("nope")


def test_duplicate_id_in_user_dir(user_dir: Path) -> None:
    write(user_dir, BASE, child(BASE))
    with pytest.raises(PresetError, match="определён дважды"):
        load_preset(BASE)


def test_user_dir_must_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(USER_DIR_ENV, str(tmp_path / "missing"))
    with pytest.raises(PresetError, match=USER_DIR_ENV):
        list_presets()


def test_user_presets_in_subfolders(user_dir: Path) -> None:
    (user_dir / "sub").mkdir()
    write(user_dir / "sub", "uni", child("uni"))
    assert load_preset("uni").id == "uni"


def test_cyrillic_user_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = tmp_path / "Мои пресеты"
    directory.mkdir()
    monkeypatch.setenv(USER_DIR_ENV, str(directory))
    write(directory, "uni", child("uni"))
    assert load_preset("uni").name == "Пресет uni"


def test_list_presets(user_dir: Path) -> None:
    write(user_dir, "uni", child("uni", country="BY"))
    write(user_dir, "broken", "id: broken\nname: Сломанный\nextends: nope\n")
    summaries = {s.id: s for s in list_presets()}
    assert summaries[BASE].builtin is True
    assert summaries[BASE].verified is True
    assert summaries["uni"].builtin is False
    assert summaries["uni"].extends == BASE
    assert summaries["broken"].name == "Сломанный"
    assert summaries["broken"].error is not None
    assert "nope" in summaries["broken"].error

    by_country = {s.id for s in list_presets("by")}
    assert "uni" in by_country
    assert BASE not in by_country


def test_builtin_dir_is_inside_package() -> None:
    assert (loader.BUILTIN_DIR / f"{BASE}.yaml").is_file()
