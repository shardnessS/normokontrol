from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import TypeAdapter

from normokontrol_mcp.bibliography.formatter import Style, format_source
from normokontrol_mcp.bibliography.models import Source
from normokontrol_mcp.bibliography.names import NBSP

CASES: list[dict[str, Any]] = yaml.safe_load(
    (Path(__file__).parent / "golden" / "cases.yaml").read_text(encoding="utf-8")
)
SOURCE = TypeAdapter(Source)


def test_enough_golden_cases() -> None:
    assert len(CASES) >= 30
    assert len({case["name"] for case in CASES}) == len(CASES), "имена кейсов должны быть уникальны"
    for case in CASES:
        assert case.get("ref"), f"у кейса {case['name']} нет ссылки на источник эталона"


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_golden(case: dict[str, Any]) -> None:
    source = SOURCE.validate_python(case["source"])
    record = format_source(source, Style(**case.get("style", {})))
    assert record.replace(NBSP, " ") == case["expected"]
