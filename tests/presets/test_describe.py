from pathlib import Path

import pytest
import yaml

from normokontrol.presets.describe import describe_preset
from normokontrol.presets.loader import USER_DIR_ENV, load_preset


def test_describe_base_preset() -> None:
    text = describe_preset(load_preset("gost-7.32-2017"))
    assert text.startswith("# ГОСТ 7.32-2017 (базовый)")
    assert "Сверен с первоисточником: да" in text
    assert "левое 30 мм, правое 15 мм, верхнее 20 мм, нижнее 20 мм _(ГОСТ 7.32-2017, п. 6.1.1)_" in text
    assert "**Межстрочный интервал:** 1,5" in text
    assert "**Абзацный отступ:** 1,25 см" in text
    assert "«Рисунок 1 — Название»" in text
    assert "«Продолжение таблицы 1»" in text
    assert "«ПРИЛОЖЕНИЕ А»" in text
    assert "внизу по центру, на титульном листе: нет" in text
    assert "_(Не ГОСТ: типовое требование вузов)_" in text  # выравнивание по ширине


def test_describe_unverified_preset_warns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(USER_DIR_ENV, str(tmp_path))
    data = {
        "id": "uni",
        "name": "Вуз, ВКР",
        "extends": "gost-7.32-2017",
        "source_docs": ["Методичка 2025"],
        "figures": {"numbering": "per_chapter"},
        "sources": {"figures.numbering": "Методичка 2025, п. 4.2"},
        "rules": {"TYPO-003": "warning"},
    }
    (tmp_path / "uni.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    text = describe_preset(load_preset("uni"))
    assert "Основан на пресете: `gost-7.32-2017`" in text
    assert "Сверен с первоисточником: **нет**" in text
    assert "**Нумерация:** в пределах раздела _(Методичка 2025, п. 4.2)_" in text
    assert "- TYPO-003: предупреждение" in text
