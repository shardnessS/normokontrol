"""Human-readable Russian description of a resolved preset (output of `get_rules`)."""

from __future__ import annotations

from collections.abc import Callable

from normokontrol_mcp.presets.schema import HeadingStyle, Preset

_ALIGN = {
    "justify": "по ширине",
    "left": "по левому краю",
    "center": "по центру",
    "right": "по правому краю",
    "indent": "с абзацного отступа",
}
_NUMBERING = {"continuous": "сквозная", "per_chapter": "в пределах раздела"}
_POSITION = {"below": "под объектом", "above": "над объектом"}
_PAGE_NUMBER_POSITION = {
    "bottom-center": "внизу по центру",
    "bottom-right": "внизу справа",
    "top-center": "вверху по центру",
    "top-right": "вверху справа",
}
_ORDER = {"by_citation": "по порядку первого упоминания в тексте", "alphabetical": "по алфавиту"}
_ORIENTATION = {"portrait": "книжная", "landscape": "альбомная"}


def _num(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def _yes(value: bool) -> str:
    return "да" if value else "нет"


def _heading(style: HeadingStyle) -> str:
    parts = [
        "прописными буквами" if style.case == "upper" else "с прописной буквы",
        _ALIGN[style.align],
        "полужирным" if style.bold else "обычным начертанием",
        "с новой страницы" if style.new_page else "без разрыва страницы",
    ]
    if style.number_format:
        example = style.number_format.format(n1=1, n2=2, n3=3)
        parts.append(f"номер вида «{example}»")
    return ", ".join(parts)


def _rules(p: Preset) -> list[tuple[str, list[tuple[str, str, Callable[[], str]]]]]:
    m = p.page.margins_mm
    return [
        (
            "Страница",
            [
                ("page.size", "Формат", lambda: p.page.size),
                ("page.orientation", "Ориентация", lambda: _ORIENTATION[p.page.orientation]),
                (
                    "page.margins_mm",
                    "Поля",
                    lambda: (
                        f"левое {_num(m.left)} мм, правое {_num(m.right)} мм, "
                        f"верхнее {_num(m.top)} мм, нижнее {_num(m.bottom)} мм"
                    ),
                ),
            ],
        ),
        (
            "Основной текст",
            [
                ("text.font", "Шрифт", lambda: p.text.font),
                ("text.size_pt", "Размер шрифта", lambda: f"{_num(p.text.size_pt)} пт"),
                (
                    "text.min_size_pt",
                    "Минимально допустимый размер",
                    lambda: f"{_num(p.text.min_size_pt)} пт",
                ),
                ("text.color", "Цвет", lambda: "чёрный" if p.text.color == "000000" else f"#{p.text.color}"),
                ("text.line_spacing", "Межстрочный интервал", lambda: _num(p.text.line_spacing)),
                (
                    "text.first_line_indent_cm",
                    "Абзацный отступ",
                    lambda: f"{_num(p.text.first_line_indent_cm)} см",
                ),
                ("text.align", "Выравнивание", lambda: _ALIGN[p.text.align]),
                (
                    "text.space_before_pt",
                    "Интервал перед абзацем",
                    lambda: f"{_num(p.text.space_before_pt)} пт",
                ),
                ("text.space_after_pt", "Интервал после абзаца", lambda: f"{_num(p.text.space_after_pt)} пт"),
            ],
        ),
        (
            "Заголовки",
            [
                (
                    "headings.structural_titles",
                    "Структурные элементы",
                    lambda: "; ".join(p.headings.structural_titles),
                ),
                (
                    "headings.structural",
                    "Заголовки структурных элементов",
                    lambda: _heading(p.headings.structural) + ", без номера, без точки в конце",
                ),
                (
                    "headings.level1",
                    "Заголовки разделов",
                    lambda: _heading(p.headings.level1) + ", без точки в конце",
                ),
                (
                    "headings.level2",
                    "Заголовки подразделов",
                    lambda: _heading(p.headings.level2) + ", без точки в конце",
                ),
            ],
        ),
        (
            "Нумерация страниц",
            [
                (
                    "page_numbers",
                    "Номер страницы",
                    lambda: (
                        f"арабскими цифрами, {_PAGE_NUMBER_POSITION[p.page_numbers.position]}, "
                        f"на титульном листе: {_yes(p.page_numbers.show_on_title)}"
                    ),
                ),
            ],
        ),
        (
            "Рисунки",
            [
                ("figures.numbering", "Нумерация", lambda: _NUMBERING[p.figures.numbering]),
                (
                    "figures.caption",
                    "Подпись",
                    lambda: f"«{p.figures.caption.format(num='1', title='Название')}»",
                ),
                (
                    "figures.position",
                    "Расположение подписи",
                    lambda: f"{_POSITION[p.figures.position]}, {_ALIGN[p.figures.caption_align]}",
                ),
                (
                    "figures.caption_line_spacing",
                    "Интервал в многострочной подписи",
                    lambda: _num(p.figures.caption_line_spacing),
                ),
            ],
        ),
        (
            "Таблицы",
            [
                ("tables.numbering", "Нумерация", lambda: _NUMBERING[p.tables.numbering]),
                (
                    "tables.caption",
                    "Название",
                    lambda: f"«{p.tables.caption.format(num='1', title='Название')}»",
                ),
                (
                    "tables.position",
                    "Расположение названия",
                    lambda: (
                        f"{_POSITION[p.tables.position]}, {_ALIGN[p.tables.caption_align]}, "
                        "без абзацного отступа"
                    ),
                ),
                (
                    "tables.continuation",
                    "При переносе на другую страницу",
                    lambda: f"«{p.tables.continuation.format(num='1')}»",
                ),
                (
                    "tables.caption_line_spacing",
                    "Интервал в многострочном названии",
                    lambda: _num(p.tables.caption_line_spacing),
                ),
                (
                    "tables.font_size_pt",
                    "Размер шрифта в таблице",
                    lambda: (
                        f"{_num(p.tables.font_size_pt)} пт"
                        if p.tables.font_size_pt
                        else "как в основном тексте"
                    ),
                ),
            ],
        ),
        (
            "Формулы",
            [
                ("formulas.numbering", "Нумерация", lambda: _NUMBERING[p.formulas.numbering]),
                (
                    "formulas.format",
                    "Номер",
                    lambda: f"«{p.formulas.format.format(num='1')}» у правого края строки, формула по центру",
                ),
                (
                    "formulas.blank_line_around",
                    "Свободная строка до и после формулы",
                    lambda: _yes(p.formulas.blank_line_around),
                ),
            ],
        ),
        (
            "Список источников",
            [
                ("bibliography.title", "Заголовок", lambda: p.bibliography.title),
                ("bibliography.order", "Порядок", lambda: _ORDER[p.bibliography.order]),
                (
                    "bibliography.numbering",
                    "Нумерация",
                    lambda: f"«{p.bibliography.numbering.format(n=1).strip()}», с абзацного отступа",
                ),
                ("bibliography.standard", "Описание источников", lambda: "по ГОСТ Р 7.0.100-2018"),
            ],
        ),
        (
            "Приложения",
            [
                (
                    "appendices.title",
                    "Обозначение",
                    lambda: (
                        f"«{p.appendices.title.format(letter=p.appendices.letters[0])}» "
                        "в центре, заголовок — отдельной строкой по центру, полужирным"
                    ),
                ),
                ("appendices.letters", "Допустимые буквы", lambda: ", ".join(p.appendices.letters)),
                ("appendices.new_page", "С новой страницы", lambda: _yes(p.appendices.new_page)),
            ],
        ),
        (
            "Перечисления",
            [
                (
                    "lists",
                    "Маркеры",
                    lambda: (
                        f"«{p.lists.bullet}» перед элементом; если на элемент ссылаются — "
                        f"буквы со скобкой: {', '.join(f'{c})' for c in p.lists.letters[:4])} … "
                        f"(допустимые: {p.lists.letters})"
                    ),
                ),
            ],
        ),
    ]


def _source(preset: Preset, path: str) -> str | None:
    """Most specific source note for a parameter path (the path itself or its nearest parent)."""
    parts = path.split(".")
    for end in range(len(parts), 0, -1):
        note = preset.sources.get(".".join(parts[:end]))
        if note:
            return note
    return None


def describe_preset(preset: Preset) -> str:
    """Markdown description of all rules with their sources."""
    lines = [f"# {preset.name}", "", f"Идентификатор: `{preset.id}`"]
    if preset.extends:
        lines.append(f"Основан на пресете: `{preset.extends}`")
    if preset.verified:
        lines.append("Сверен с первоисточником: да")
    else:
        lines.append(
            "Сверен с первоисточником: **нет** — правила могут не совпадать с актуальной методичкой, "
            "проверьте их перед сдачей работы"
        )
    lines.append("Документы: " + "; ".join(preset.source_docs))
    lines.append("")
    lines.append("Требования без пометки «не ГОСТ» взяты из указанного пункта стандарта.")

    for section, items in _rules(preset):
        lines += ["", f"## {section}", ""]
        for path, label, render in items:
            line = f"- **{label}:** {render()}"
            source = _source(preset, path)
            if source:
                line += f" _({source})_"
            lines.append(line)

    if preset.rules:
        lines += ["", "## Настройка правил проверки", ""]
        names = {"error": "ошибка", "warning": "предупреждение", "info": "замечание", "off": "отключено"}
        lines += [f"- {rule_id}: {names[level]}" for rule_id, level in sorted(preset.rules.items())]
    return "\n".join(lines) + "\n"
