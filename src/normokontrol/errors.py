"""Structured errors: every user-facing error carries a code, a Russian message and a location."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from pydantic_core import ErrorDetails


class NormokontrolError(Exception):
    """Base error. `message_ru` is shown to the user as is."""

    error_code: str = "error"

    def __init__(self, message_ru: str, location: str | None = None) -> None:
        super().__init__(message_ru)
        self.message_ru = message_ru
        self.location = location

    def to_dict(self) -> dict[str, Any]:
        return {"error_code": self.error_code, "message_ru": self.message_ru, "location": self.location}


class PresetNotFoundError(NormokontrolError):
    error_code = "preset_not_found"


class PresetError(NormokontrolError):
    """Invalid preset file: YAML syntax, schema violation, bad `extends`."""

    error_code = "preset_invalid"


class InputError(NormokontrolError):
    """Invalid input data for a script (sources file, arguments)."""

    error_code = "input_invalid"


def format_validation_errors(exc: ValidationError) -> str:
    """All pydantic errors as a Russian bullet list."""
    return "\n".join(f"- {format_validation_error(err)}" for err in exc.errors())


_ERROR_MESSAGES = {
    "missing": "обязательный параметр не указан",
    "extra_forbidden": "неизвестный параметр (проверьте написание)",
    "literal_error": "недопустимое значение {input!r}; допустимо: {expected}",
    "greater_than": "значение должно быть больше {gt}",
    "greater_than_equal": "значение должно быть не меньше {ge}",
    "string_pattern_mismatch": "значение {input!r} имеет неверный формат",
    "string_too_short": "значение не должно быть пустым",
    "too_short": "список не должен быть пустым",
    "float_parsing": "ожидалось число, указано {input!r}",
    "float_type": "ожидалось число, указано {input!r}",
    "bool_parsing": "ожидалось true или false, указано {input!r}",
    "bool_type": "ожидалось true или false, указано {input!r}",
    "string_type": "ожидалась строка, указано {input!r}",
    "dict_type": "ожидался набор вложенных параметров",
    "model_type": "ожидался набор вложенных параметров",
    "list_type": "ожидался список",
    "int_parsing": "ожидалось целое число, указано {input!r}",
    "date_parsing": "ожидалась дата ГГГГ-ММ-ДД или ДД.ММ.ГГГГ, указано {input!r}",
    "date_from_datetime_parsing": "ожидалась дата ГГГГ-ММ-ДД или ДД.ММ.ГГГГ, указано {input!r}",
    "union_tag_invalid": "неизвестный тип {tag!r}; допустимо: {expected_tags}",
    "union_tag_not_found": "не указан тип (поле {discriminator})",
}


def format_validation_error(err: ErrorDetails) -> str:
    """One pydantic error in Russian: «путь.к.полю: что не так»."""
    location = ".".join(str(part) for part in err["loc"])
    ctx = err.get("ctx") or {}
    if err["type"] == "value_error":
        message = str(ctx.get("error", err["msg"]))
    elif err["type"] in _ERROR_MESSAGES:
        message = _ERROR_MESSAGES[err["type"]].format(input=err.get("input"), **ctx)
    else:
        message = err["msg"]
    return f"{location}: {message}" if location else message
