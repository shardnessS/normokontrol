"""Small helpers for raw OOXML: Word rejects files whose child elements break the schema order."""

from __future__ import annotations

from collections.abc import Sequence

from docx.oxml.ns import qn
from lxml import etree

# Элементы, которые по схеме идут ПОСЛЕ вставляемого (ECMA-376, CT_RPr и CT_Settings).
AFTER_SZ = (
    "w:highlight", "w:u", "w:effect", "w:bdr", "w:shd", "w:fitText", "w:vertAlign", "w:rtl", "w:cs",
    "w:em", "w:lang", "w:eastAsianLayout", "w:specVanish", "w:oMath",
)  # fmt: skip
AFTER_LANG = ("w:eastAsianLayout", "w:specVanish", "w:oMath")
AFTER_UPDATE_FIELDS = (
    "w:hdrShapeDefaults", "w:footnotePr", "w:endnotePr", "w:compat", "w:docVars", "w:rsids",
    "m:mathPr", "w:attachedSchema", "w:themeFontLang", "w:clrSchemeMapping",
    "w:doNotIncludeSubdocsInStats", "w:doNotAutoCompressPictures", "w:forceUpgrade", "w:captions",
    "w:readModeInkLockDown", "w:smartTagType", "w:schemaLibrary", "w:shapeDefaults",
    "w:doNotEmbedSmartTags", "w:decimalSymbol", "w:listSeparator",
)  # fmt: skip


def insert_before_successors(
    parent: etree._Element, child: etree._Element, successors: Sequence[str]
) -> None:
    """Insert `child` before the first existing element from `successors`, otherwise append."""
    tags = {qn(name) for name in successors}
    for index, existing in enumerate(parent):
        if existing.tag in tags:
            parent.insert(index, child)
            return
    parent.append(child)


def element(tag: str, **attributes: str) -> etree._Element:
    from docx.oxml import OxmlElement

    node: etree._Element = OxmlElement(tag)
    for name, value in attributes.items():
        node.set(qn(f"w:{name}"), value)
    return node
