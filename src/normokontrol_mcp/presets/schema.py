"""Pydantic model of a fully resolved preset (after `extends` inheritance)."""

from __future__ import annotations

import string
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PositiveFloat = Annotated[float, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]
Severity = Literal["error", "warning", "info", "off"]

# ГОСТ 7.32-2017, 6.17.4 и 6.4.6: буквы, которые не используют для обозначений.
APPENDIX_LETTERS = "АБВГДЕЖИКЛМНПРСТУФХЦШЩЭЮЯ"
LIST_LETTERS = APPENDIX_LETTERS.lower()


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _check_template(value: str, *, required: set[str], allowed: set[str]) -> str:
    """Validate `{placeholder}` usage in a format template."""
    try:
        names = {name for _, name, _, _ in string.Formatter().parse(value) if name is not None}
    except ValueError as exc:
        raise ValueError(f"некорректный шаблон «{value}»: {exc}") from None
    unknown = names - allowed
    if unknown:
        raise ValueError(
            f"неизвестные поля {_braces(unknown)} в шаблоне «{value}»; допустимы: {_braces(allowed)}"
        )
    missing = required - names
    if missing:
        raise ValueError(f"в шаблоне «{value}» не хватает полей {_braces(missing)}")
    return value


def _braces(names: set[str]) -> str:
    return ", ".join("{" + name + "}" for name in sorted(names))


class Margins(_Strict):
    left: PositiveFloat
    right: PositiveFloat
    top: PositiveFloat
    bottom: PositiveFloat


class PageSettings(_Strict):
    size: Literal["A4"]
    orientation: Literal["portrait", "landscape"] = "portrait"
    margins_mm: Margins


class TextSettings(_Strict):
    font: str = Field(min_length=1)
    size_pt: PositiveFloat
    min_size_pt: PositiveFloat
    color: str = Field(pattern=r"^[0-9A-Fa-f]{6}$")
    line_spacing: PositiveFloat
    first_line_indent_cm: NonNegativeFloat
    align: Literal["justify", "left", "center", "right"]
    space_before_pt: NonNegativeFloat
    space_after_pt: NonNegativeFloat

    @model_validator(mode="after")
    def _size_not_below_min(self) -> TextSettings:
        if self.size_pt < self.min_size_pt:
            raise ValueError(
                f"размер шрифта {self.size_pt} пт меньше минимально допустимого {self.min_size_pt} пт"
            )
        return self


class HeadingStyle(_Strict):
    case: Literal["upper", "first_upper"]
    align: Literal["center", "indent", "left"]
    bold: bool
    new_page: bool
    number_format: str | None = None

    @field_validator("number_format")
    @classmethod
    def _number_format(cls, value: str | None) -> str | None:
        if value is not None:
            _check_template(value, required=set(), allowed={"n1", "n2", "n3"})
        return value


class Headings(_Strict):
    structural_titles: list[str] = Field(min_length=1)
    structural: HeadingStyle
    level1: HeadingStyle
    level2: HeadingStyle

    @field_validator("structural_titles")
    @classmethod
    def _upper_titles(cls, value: list[str]) -> list[str]:
        for title in value:
            if title != title.upper():
                raise ValueError(f"наименование структурного элемента «{title}» должно быть прописными")
        return value


class PageNumbers(_Strict):
    position: Literal["bottom-center", "bottom-right", "top-center", "top-right"]
    show_on_title: bool


_NUMBERING = Literal["continuous", "per_chapter"]


class Figures(_Strict):
    numbering: _NUMBERING
    caption: str
    position: Literal["below", "above"]
    caption_align: Literal["center", "left"]
    caption_line_spacing: PositiveFloat

    @field_validator("caption")
    @classmethod
    def _caption(cls, value: str) -> str:
        return _check_template(value, required={"num", "title"}, allowed={"num", "title"})


class Tables(_Strict):
    numbering: _NUMBERING
    caption: str
    continuation: str
    position: Literal["above", "below"]
    caption_align: Literal["left", "center"]
    caption_line_spacing: PositiveFloat
    font_size_pt: PositiveFloat | None = None

    @field_validator("caption")
    @classmethod
    def _caption(cls, value: str) -> str:
        return _check_template(value, required={"num", "title"}, allowed={"num", "title"})

    @field_validator("continuation")
    @classmethod
    def _continuation(cls, value: str) -> str:
        return _check_template(value, required={"num"}, allowed={"num"})


class Formulas(_Strict):
    numbering: _NUMBERING
    format: str
    blank_line_around: bool

    @field_validator("format")
    @classmethod
    def _format(cls, value: str) -> str:
        return _check_template(value, required={"num"}, allowed={"num"})


class Bibliography(_Strict):
    title: str = Field(min_length=1)
    order: Literal["by_citation", "alphabetical"]
    numbering: str
    standard: Literal["gost-r-7.0.100-2018"]

    @field_validator("numbering")
    @classmethod
    def _numbering(cls, value: str) -> str:
        return _check_template(value, required={"n"}, allowed={"n"})


class Appendices(_Strict):
    title: str
    letters: str = Field(min_length=1)
    new_page: bool

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        return _check_template(value, required={"letter"}, allowed={"letter"})


class Lists(_Strict):
    bullet: str = Field(min_length=1)
    letters: str = Field(min_length=1)


class TitlePage(_Strict):
    template: str = Field(min_length=1)


class Preset(_Strict):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9.\-]*$")
    name: str = Field(min_length=1)
    country: str = Field(pattern=r"^[A-Z]{2}$")
    verified: bool
    source_docs: list[str] = Field(min_length=1)
    extends: str | None = None
    page: PageSettings
    text: TextSettings
    headings: Headings
    page_numbers: PageNumbers
    figures: Figures
    tables: Tables
    formulas: Formulas
    bibliography: Bibliography
    appendices: Appendices
    lists: Lists
    title_page: TitlePage
    rules: dict[Annotated[str, Field(pattern=r"^[A-Z]+-\d{3}$")], Severity] = Field(default_factory=dict)
    # Откуда взято каждое требование: "путь.к.полю" -> "ГОСТ 7.32-2017, п. 6.1.1".
    sources: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _cross_checks(self) -> Preset:
        if self.bibliography.title not in self.headings.structural_titles:
            raise ValueError(
                f"заголовок списка источников «{self.bibliography.title}» "
                "должен входить в headings.structural_titles"
            )
        for path in self.sources:
            if not _path_exists(self, path):
                raise ValueError(f"в sources указан несуществующий параметр «{path}»")
        return self


def _path_exists(model: BaseModel, path: str) -> bool:
    node: object = model
    for part in path.split("."):
        if not isinstance(node, BaseModel) or part not in type(node).model_fields:
            return False
        node = getattr(node, part)
    return True
