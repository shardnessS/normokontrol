import pytest
from lxml import etree

from normokontrol.document.math_omml import M_NS, MathError, latex_to_omml


def tags(latex: str) -> list[str]:
    return [
        element.tag.split("}")[1] for element in latex_to_omml(latex).iter() if isinstance(element.tag, str)
    ]


def text(latex: str) -> str:
    return "".join(latex_to_omml(latex).itertext())


def test_simple_expression() -> None:
    assert text("E = mc^2") == "E=mc2"
    assert "sSup" in tags("E = mc^2")


def test_fraction_root_scripts() -> None:
    assert {"f", "num", "den"} <= set(tags(r"\frac{a+b}{c}"))
    assert "rad" in tags(r"\sqrt{x}")
    root = latex_to_omml(r"\sqrt[3]{x}")
    assert root.find(f".//{{{M_NS}}}degHide") is None
    assert "sSubSup" in tags("x_i^2")
    assert "sSub" in tags("t_{max}")


def test_nary_with_limits_and_body() -> None:
    math = latex_to_omml(r"\sum_{i=1}^{N} t_i")
    nary = math.find(f"{{{M_NS}}}nary")
    assert nary is not None
    chr_ = nary.find(f"{{{M_NS}}}naryPr/{{{M_NS}}}chr")
    assert chr_ is not None and chr_.get(f"{{{M_NS}}}val") == "∑"
    assert nary.find(f"{{{M_NS}}}naryPr/{{{M_NS}}}subHide") is None
    assert "".join(nary.find(f"{{{M_NS}}}e").itertext()) == "ti"  # type: ignore[union-attr]


def test_symbols_functions_delimiters_text() -> None:
    assert text(r"\lambda \le \mu \cdot \infty") == "λ≤μ⋅∞"
    assert text(r"\sin x") == "sinx"
    assert "d" in tags(r"\left( x \right)")
    assert text(r"\text{при } x") == "при x"
    assert text(r"a \, b") == "a b"


def test_xml_is_well_formed() -> None:
    xml = etree.tostring(latex_to_omml(r"\frac{1}{1 + \sigma^2}"))
    assert xml.startswith(b"<m:oMath")


@pytest.mark.parametrize(
    ("latex", "message"),
    [
        (r"\unknowncmd x", "«\\unknowncmd» не поддерживается"),
        ("", "пустая формула"),
        (r"\frac{1}", "не хватает аргумента"),
        ("x}", "лишняя «}»"),
        ("^2", "без основания"),
        (r"\left( x", "\\left без \\right"),
        ("x \\", "одиночная"),
    ],
)
def test_errors(latex: str, message: str) -> None:
    with pytest.raises(MathError, match=message.replace("\\", "\\\\").replace("(", r"\(")):
        latex_to_omml(latex)
