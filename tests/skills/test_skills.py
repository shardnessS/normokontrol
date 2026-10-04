import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from normokontrol import __version__
from normokontrol.bibliography.identifiers import classify
from normokontrol.bibliography.models import SOURCE_TYPES, Source

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import build_skills  # noqa: E402

SKILLS = sorted(p.name for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").is_file())
SCRIPTS = {
    "gost-rules": "presets.py",
    "gost-bibliography": "format_bibliography.py",
    "gost-document": "build.py",
}
BOOK = {"type": "book", "authors": ["Иванов И. И."], "title": "Книга", "city": "Москва", "publisher": "Юрайт"}


def run_script(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )


@pytest.fixture(scope="module")
def dist(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("dist")
    build_skills.build_all(out)
    return out


def test_expected_skills_exist() -> None:
    assert set(SCRIPTS) <= set(SKILLS)


@pytest.mark.parametrize("skill", SKILLS)
def test_skill_frontmatter_valid(skill: str) -> None:
    build_skills.validate_skill(ROOT / "skills" / skill)


def test_validation_catches_bad_frontmatter(tmp_path: Path) -> None:
    skill = tmp_path / "my-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nname: other\ndescription: x\n---\n", encoding="utf-8")
    with pytest.raises(build_skills.SkillError, match="совпадать с именем папки"):
        build_skills.validate_skill(skill)
    (skill / "SKILL.md").write_text("no frontmatter", encoding="utf-8")
    with pytest.raises(build_skills.SkillError, match="нет блока frontmatter"):
        build_skills.validate_skill(skill)


def test_reference_examples_are_valid_sources() -> None:
    text = (ROOT / "skills" / "gost-bibliography" / "references" / "source-format.md").read_text(
        encoding="utf-8"
    )
    blocks = [json.loads(block) for block in re.findall(r"```json\n(.*?)```", text, re.DOTALL)]
    assert len(blocks) >= 11
    adapter: TypeAdapter[Source] = TypeAdapter(Source)
    for block in blocks:
        if isinstance(block, list):  # строки с DOI, ISBN, URL
            assert all(classify(item) is not None for item in block)
        else:
            adapter.validate_python(block)
    documented = {block["type"] for block in blocks if isinstance(block, dict)}
    assert documented == set(SOURCE_TYPES) - {"book_chapter"}  # book_chapter описан вместе с conference_paper


def test_versions_in_sync() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{__version__}"' in pyproject
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert plugin["version"] == __version__
    assert marketplace["plugins"][0]["version"] == __version__
    assert marketplace["plugins"][0]["name"] == plugin["name"]


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_built_skill_uses_bundled_core(dist: Path, tmp_path: Path, skill: str) -> None:
    """Скрипт собранного скилла запускается из чужой папки и берёт ядро из своей копии."""
    script = dist / "skills" / skill / "scripts" / SCRIPTS[skill]
    probe = (
        "import runpy, sys\n"
        f"sys.argv = [{str(script)!r}, '--help']\n"
        "try:\n"
        f"    runpy.run_path({str(script)!r}, run_name='__main__')\n"
        "except SystemExit:\n"
        "    pass\n"
        "import normokontrol\n"
        "print(normokontrol.__file__)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    core_file = Path(result.stdout.strip().splitlines()[-1])
    assert core_file.is_relative_to(dist / "skills" / skill / "scripts" / "normokontrol")


def test_built_bibliography_script(dist: Path, tmp_path: Path) -> None:
    (tmp_path / "sources.json").write_text(json.dumps([BOOK], ensure_ascii=False), encoding="utf-8")
    script = dist / "skills" / "gost-bibliography" / "scripts" / "format_bibliography.py"
    result = run_script(script, "sources.json", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.replace(" ", " ").startswith(
        "1. Иванов, И. И. Книга / И. И. Иванов. – Москва : Юрайт."
    )
    assert "не указано — год издания" in result.stdout


def test_built_bibliography_script_error_exit_code(dist: Path, tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text('[{"type": "book"}]', encoding="utf-8")
    script = dist / "skills" / "gost-bibliography" / "scripts" / "format_bibliography.py"
    result = run_script(script, "bad.json", cwd=tmp_path)
    assert result.returncode == 2
    assert json.loads(result.stderr)["error_code"] == "input_invalid"


def test_built_rules_script(dist: Path, tmp_path: Path) -> None:
    script = dist / "skills" / "gost-rules" / "scripts" / "presets.py"
    result = run_script(script, "rules", "gost-7.32-2017", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "левое 30 мм" in result.stdout


def test_repo_scripts_use_src(tmp_path: Path) -> None:
    """В плагине Claude Code скрипт лежит в skills/<name>/scripts и находит ядро в src/."""
    script = ROOT / "skills" / "gost-rules" / "scripts" / "presets.py"
    result = run_script(script, "list", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "gost-7.32-2017" in result.stdout


def test_zip_layout(dist: Path) -> None:
    with zipfile.ZipFile(dist / "gost-bibliography.zip") as zf:
        names = zf.namelist()
    assert "gost-bibliography/SKILL.md" in names
    assert "gost-bibliography/references/source-format.md" in names
    assert "gost-bibliography/scripts/normokontrol/presets/data/gost-7.32-2017.yaml" in names
    assert not any("__pycache__" in name for name in names)
    with zipfile.ZipFile(dist / "gost-rules.zip") as zf:
        assert "gost-rules/scripts/presets.py" in zf.namelist()


def test_build_is_deterministic(tmp_path: Path) -> None:
    first = build_skills.build_all(tmp_path / "a")
    second = build_skills.build_all(tmp_path / "b")
    for a, b in zip(first, second, strict=True):
        assert a.read_bytes() == b.read_bytes()


def test_built_lookup_script_offline(dist: Path, tmp_path: Path) -> None:
    """Без сети (как в песочнице claude.ai) lookup.py сообщает об этом, а не падает."""
    script = dist / "skills" / "gost-bibliography" / "scripts" / "lookup.py"
    env = {**os.environ, "NORMOKONTROL_OFFLINE": "1", "NORMOKONTROL_CACHE_DIR": str(tmp_path / "cache")}
    result = subprocess.run(
        [sys.executable, str(script), "10.1016/j.patcog.2017.10.013"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)[0]["error"]["error_code"] == "network_unavailable"


def test_built_document_script(dist: Path, tmp_path: Path) -> None:
    """Собранный gost-document собирает пример курсовой из чужой папки."""
    example = tmp_path / "пример"
    shutil.copytree(ROOT / "examples" / "coursework", example, ignore=shutil.ignore_patterns("*.docx"))
    script = dist / "skills" / "gost-document" / "scripts" / "build.py"
    result = run_script(script, str(example / "черновик.md"), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "источников: 6" in result.stdout
    assert (example / "черновик_gost.docx").is_file()
