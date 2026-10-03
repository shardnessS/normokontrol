"""Preset discovery and loading: `extends` inheritance, deep merge, cycle detection, user folder."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from normokontrol.errors import PresetError, PresetNotFoundError, format_validation_errors
from normokontrol.presets.schema import Preset

BUILTIN_DIR = Path(__file__).parent / "data"
USER_DIR_ENV = "NORMOKONTROL_PRESETS_DIR"

# Эти поля описывают сам файл пресета и не наследуются.
_META_KEYS = frozenset({"id", "name", "verified", "source_docs", "extends"})
_NON_RULE_KEYS = _META_KEYS | {"sources", "rules"}


class PresetSummary(BaseModel):
    id: str
    name: str
    country: str | None
    verified: bool
    extends: str | None
    builtin: bool
    error: str | None = None


def preset_dirs() -> list[tuple[Path, bool]]:
    """Folders to search for presets: (path, is_builtin)."""
    dirs = [(BUILTIN_DIR, True)]
    user_dir = os.environ.get(USER_DIR_ENV)
    if user_dir:
        path = Path(user_dir).expanduser()
        if not path.is_dir():
            raise PresetError(
                f"Папка пресетов из переменной {USER_DIR_ENV} не найдена: {path}", location=str(path)
            )
        dirs.append((path, False))
    return dirs


def discover() -> dict[str, tuple[Path, bool]]:
    """Map preset id -> (file, is_builtin). Id equals the file name without `.yaml`."""
    found: dict[str, tuple[Path, bool]] = {}
    for directory, builtin in preset_dirs():
        for path in sorted(directory.rglob("*.yaml")):
            preset_id = path.stem
            if preset_id in found:
                raise PresetError(
                    f"Пресет «{preset_id}» определён дважды: {found[preset_id][0]} и {path}. "
                    "Переименуйте один из файлов.",
                    location=str(path),
                )
            found[preset_id] = (path, builtin)
    return found


def load_preset(preset_id: str) -> Preset:
    """Load a preset with all its `extends` ancestors merged in, and validate it."""
    return _load(preset_id, discover(), chain=())


def list_presets(country: str | None = None) -> list[PresetSummary]:
    """Summaries of all presets. Invalid presets are listed with `error` instead of failing the list."""
    files = discover()
    result: list[PresetSummary] = []
    for preset_id, (path, builtin) in files.items():
        try:
            preset = _load(preset_id, files, chain=())
        except PresetError as exc:
            raw = _safe_raw(path)
            result.append(
                PresetSummary(
                    id=preset_id,
                    name=str(raw.get("name", preset_id)),
                    country=None,
                    verified=False,
                    extends=raw.get("extends"),
                    builtin=builtin,
                    error=exc.message_ru,
                )
            )
            continue
        if country is not None and preset.country != country.upper():
            continue
        result.append(
            PresetSummary(
                id=preset.id,
                name=preset.name,
                country=preset.country,
                verified=preset.verified,
                extends=preset.extends,
                builtin=builtin,
            )
        )
    return result


def dump_yaml(preset: Preset) -> str:
    """Resolved preset as YAML (inheritance already applied)."""
    header = f"# Пресет {preset.id} после применения наследования (extends).\n"
    body = yaml.safe_dump(preset.model_dump(mode="json"), allow_unicode=True, sort_keys=False)
    return header + body


def merge_preset_dicts(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    """Apply a child preset on top of its resolved parent.

    Meta fields are taken only from the child. A source note inherited from the parent is dropped
    for every parameter the child overrides, so a changed value never keeps the parent's reference.
    """
    base = {key: value for key, value in parent.items() if key not in _META_KEYS and key != "sources"}
    overridden = [path for path in _leaf_paths(child) if path.split(".")[0] not in _NON_RULE_KEYS]
    sources = {
        key: note
        for key, note in (parent.get("sources") or {}).items()
        if not any(_related(key, path) for path in overridden)
    }
    sources.update(child.get("sources") or {})
    merged = _deep_merge(base, {key: value for key, value in child.items() if key != "sources"})
    merged["sources"] = sources
    merged.setdefault("verified", False)
    return merged


def _load(preset_id: str, files: dict[str, tuple[Path, bool]], chain: tuple[str, ...]) -> Preset:
    if preset_id in chain:
        cycle = " → ".join((*chain[chain.index(preset_id) :], preset_id))
        raise PresetError(f"Цикл наследования пресетов: {cycle}", location=str(files[preset_id][0]))
    if preset_id not in files:
        if chain:
            raise PresetError(
                f"Пресет «{chain[-1]}» наследует несуществующий пресет «{preset_id}» (поле extends)",
                location=str(files[chain[-1]][0]),
            )
        known = ", ".join(sorted(files)) or "нет ни одного"
        raise PresetNotFoundError(f"Пресет «{preset_id}» не найден. Доступные пресеты: {known}")

    path = files[preset_id][0]
    raw = _read_yaml(path)
    if raw.get("id") != preset_id:
        raise PresetError(
            f"В файле {path.name} поле id должно совпадать с именем файла: «{preset_id}», "
            f"а указано «{raw.get('id')}»",
            location=str(path),
        )
    parent_id = raw.get("extends")
    if parent_id is not None:
        parent = _load(str(parent_id), files, chain=(*chain, preset_id))
        data = merge_preset_dicts(parent.model_dump(), raw)
    else:
        data = raw
    try:
        return Preset.model_validate(data)
    except ValidationError as exc:
        details = format_validation_errors(exc)
        raise PresetError(
            f"Пресет «{preset_id}» ({path}) содержит ошибки:\n{details}", location=str(path)
        ) from None


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f", строка {mark.line + 1}" if mark is not None else ""
        raise PresetError(f"Ошибка синтаксиса YAML в {path.name}{where}: {exc}", location=str(path)) from None
    except UnicodeDecodeError:
        raise PresetError(f"Файл {path.name} должен быть в кодировке UTF-8", location=str(path)) from None
    if not isinstance(data, dict):
        raise PresetError(f"Файл {path.name} должен содержать словарь параметров", location=str(path))
    return data


def _safe_raw(path: Path) -> dict[str, Any]:
    try:
        return _read_yaml(path)
    except PresetError:
        return {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _leaf_paths(data: dict[str, Any], prefix: str = "") -> Iterator[str]:
    for key, value in data.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict) and value:
            yield from _leaf_paths(value, f"{path}.")
        else:
            yield path


def _related(a: str, b: str) -> bool:
    """True if one dotted path equals or contains the other."""
    return a == b or a.startswith(f"{b}.") or b.startswith(f"{a}.")
