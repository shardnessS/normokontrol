"""Build installable skills: dist/skills/<name>/ with the core copied in, and dist/<name>.zip for claude.ai.

Usage: uv run python tools/build_skills.py [--out dist]
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
CORE_DIR = ROOT / "src" / "normokontrol"
# Фиксированная дата в zip: одинаковые исходники дают побайтово одинаковый архив.
ZIP_DATE = (1980, 1, 1, 0, 0, 0)
_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class SkillError(Exception):
    pass


def read_frontmatter(skill_md: Path) -> dict[str, str]:
    """Minimal parser for the `key: value` frontmatter of SKILL.md."""
    text = skill_md.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise SkillError(f"{skill_md}: нет блока frontmatter между строками ---")
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            raise SkillError(f"{skill_md}: строка frontmatter без «:»: {line!r}")
        fields[key.strip()] = value.strip()
    return fields


def validate_skill(skill_dir: Path) -> None:
    fields = read_frontmatter(skill_dir / "SKILL.md")
    name, description = fields.get("name", ""), fields.get("description", "")
    if name != skill_dir.name:
        raise SkillError(f"{skill_dir.name}: name в SKILL.md ({name!r}) должен совпадать с именем папки")
    if not _NAME.match(name) or len(name) > 64:
        raise SkillError(f"{name}: имя — до 64 символов, строчные латинские буквы, цифры и дефисы")
    if not description or len(description) > 1024:
        raise SkillError(f"{name}: description обязателен и не длиннее 1024 символов")


def build_skill(skill_dir: Path, out: Path) -> Path:
    """Copy one skill with the core into out/skills/<name>/ and zip it to out/<name>.zip."""
    validate_skill(skill_dir)
    target = out / "skills" / skill_dir.name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(skill_dir, target, ignore=_IGNORE)
    if (target / "scripts").is_dir():
        shutil.copytree(CORE_DIR, target / "scripts" / "normokontrol", ignore=_IGNORE)

    archive = out / f"{skill_dir.name}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(p for p in target.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(target.parent).as_posix(), ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())
    return archive


def build_all(out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    skills = sorted(p for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file())
    return [build_skill(skill, out) for skill in skills]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    try:
        archives = build_all(args.out)
    except SkillError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    for archive in archives:
        print(archive)
    return 0


if __name__ == "__main__":
    sys.exit(main())
