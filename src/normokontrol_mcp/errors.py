"""Structured errors: every user-facing error carries a code, a Russian message and a location."""

from __future__ import annotations

from typing import Any


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
