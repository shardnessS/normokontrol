"""Apply a preset to the page setup and styles of a python-docx Document."""

from __future__ import annotations

from docx.document import Document
from docx.enum.section import WD_ORIENT
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.oxml.xmlchemy import BaseOxmlElement
from docx.shared import Cm, Mm, Pt, RGBColor
from docx.styles.style import ParagraphStyle
from docx.text.paragraph import Paragraph
from lxml import etree

from normokontrol.document import ooxml
from normokontrol.presets.schema import HeadingStyle, Preset

ALIGN = {
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "indent": WD_ALIGN_PARAGRAPH.LEFT,
}
TABLE_TEXT = "GOST Table Text"
CODE = "GOST Code"
CODE_FONT = "Courier New"
_PAGE_SIZE_MM = {"A4": (210, 297)}


def text_width_mm(preset: Preset) -> float:
    width, height = _PAGE_SIZE_MM[preset.page.size]
    if preset.page.orientation == "landscape":
        width = height
    return width - preset.page.margins_mm.left - preset.page.margins_mm.right


def apply_page(document: Document, preset: Preset) -> None:
    width, height = _PAGE_SIZE_MM[preset.page.size]
    margins = preset.page.margins_mm
    for section in document.sections:
        if preset.page.orientation == "landscape":
            section.orientation = WD_ORIENT.LANDSCAPE
            width, height = height, width
        section.page_width = Mm(width)
        section.page_height = Mm(height)
        section.left_margin = Mm(margins.left)
        section.right_margin = Mm(margins.right)
        section.top_margin = Mm(margins.top)
        section.bottom_margin = Mm(margins.bottom)


def apply_styles(document: Document, preset: Preset) -> None:
    text = preset.text
    _doc_defaults(document, preset)

    normal = _paragraph_style(document, "Normal")
    _font(normal, text.font, text.size_pt, bold=False, italic=False)
    fmt = normal.paragraph_format
    fmt.alignment = ALIGN[text.align]
    fmt.first_line_indent = Cm(text.first_line_indent_cm)
    fmt.line_spacing = text.line_spacing
    fmt.space_before = Pt(text.space_before_pt)
    fmt.space_after = Pt(text.space_after_pt)
    fmt.widow_control = True

    for level, style in (
        (1, preset.headings.level1),
        (2, preset.headings.level2),
        (3, preset.headings.level2),
    ):
        _heading_style(document, f"Heading {level}", style, preset)

    caption = _paragraph_style(document, "Caption")
    _font(caption, text.font, text.size_pt, bold=False, italic=False)
    caption.paragraph_format.first_line_indent = Cm(0)
    caption.paragraph_format.line_spacing = preset.figures.caption_line_spacing
    caption.paragraph_format.space_before = Pt(0)
    caption.paragraph_format.space_after = Pt(0)

    table_text = _custom_style(document, TABLE_TEXT)
    _font(table_text, text.font, preset.tables.font_size_pt or text.size_pt, bold=False, italic=False)
    table_text.paragraph_format.first_line_indent = Cm(0)
    table_text.paragraph_format.line_spacing = 1.0
    table_text.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    code = _custom_style(document, CODE)
    _font(code, CODE_FONT, preset.tables.font_size_pt or text.size_pt, bold=False, italic=False)
    code.paragraph_format.first_line_indent = Cm(0)
    code.paragraph_format.line_spacing = 1.0
    code.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT


def heading_format(paragraph: Paragraph, style: HeadingStyle, preset: Preset) -> None:
    """Direct formatting that depends on the heading kind (structural headings share Heading 1)."""
    fmt = paragraph.paragraph_format
    fmt.alignment = ALIGN[style.align]
    fmt.first_line_indent = Cm(preset.text.first_line_indent_cm) if style.align == "indent" else Cm(0)
    fmt.page_break_before = style.new_page


def no_indent(paragraph: Paragraph) -> None:
    paragraph.paragraph_format.first_line_indent = Cm(0)


def _heading_style(document: Document, name: str, style: HeadingStyle, preset: Preset) -> None:
    heading = _paragraph_style(document, name)
    _font(heading, preset.text.font, preset.text.size_pt, bold=style.bold, italic=False)
    fmt = heading.paragraph_format
    fmt.alignment = ALIGN[style.align]
    fmt.first_line_indent = Cm(preset.text.first_line_indent_cm) if style.align == "indent" else Cm(0)
    fmt.line_spacing = preset.text.line_spacing
    fmt.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)
    fmt.keep_with_next = True
    fmt.page_break_before = style.new_page


def _paragraph_style(document: Document, name: str) -> ParagraphStyle:
    style = document.styles[name]
    assert isinstance(style, ParagraphStyle)
    return style


def _custom_style(document: Document, name: str) -> ParagraphStyle:
    if name in [s.name for s in document.styles]:
        return _paragraph_style(document, name)
    style = document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    assert isinstance(style, ParagraphStyle)
    style.base_style = document.styles["Normal"]
    return style


def _font(style: ParagraphStyle, name: str, size_pt: float, *, bold: bool, italic: bool) -> None:
    font = style.font
    font.name = name
    font.size = Pt(size_pt)
    font.bold = bold
    font.italic = italic
    font.color.rgb = RGBColor(0, 0, 0)
    rpr = style.element.get_or_add_rPr()
    _explicit_fonts(rpr, name)
    color = rpr.find(qn("w:color"))
    if color is not None:
        for attr in ("w:themeColor", "w:themeShade", "w:themeTint"):
            _drop_attribute(color, attr)


def _explicit_fonts(rpr: BaseOxmlElement, name: str) -> None:
    """Set all four font slots and drop theme fonts, which Word would otherwise prefer."""
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for slot in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(slot), name)
    for theme in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        _drop_attribute(rfonts, theme)


def _doc_defaults(document: Document, preset: Preset) -> None:
    styles = document.styles.element
    defaults = styles.find(qn("w:docDefaults"))
    if defaults is None:
        defaults = OxmlElement("w:docDefaults")
        styles.insert(0, defaults)
    rpr_default = defaults.find(qn("w:rPrDefault"))
    if rpr_default is None:
        rpr_default = OxmlElement("w:rPrDefault")
        defaults.insert(0, rpr_default)
    rpr = rpr_default.find(qn("w:rPr"))
    if rpr is None:
        rpr = OxmlElement("w:rPr")
        rpr_default.append(rpr)
    _explicit_fonts(rpr, preset.text.font)
    for tag in ("w:sz", "w:szCs", "w:lang", "w:color"):
        old = rpr.find(qn(tag))
        if old is not None:
            rpr.remove(old)
    half_points = str(round(preset.text.size_pt * 2))
    for tag in ("w:sz", "w:szCs"):
        ooxml.insert_before_successors(rpr, ooxml.element(tag, val=half_points), ooxml.AFTER_SZ)
    lang = ooxml.element("w:lang", val="ru-RU", eastAsia="ru-RU", bidi="ar-SA")
    ooxml.insert_before_successors(rpr, lang, ooxml.AFTER_LANG)

    # Умолчания шаблона python-docx (10 пт после абзаца, интервал 1,15) — обнуляем для всех абзацев.
    spacing = defaults.find(f"{qn('w:pPrDefault')}/{qn('w:pPr')}/{qn('w:spacing')}")
    if spacing is not None:
        spacing.set(qn("w:before"), "0")
        spacing.set(qn("w:after"), "0")
        spacing.set(qn("w:line"), "240")
        spacing.set(qn("w:lineRule"), "auto")


def _drop_attribute(element: etree._Element, name: str) -> None:
    key = qn(name)
    if key in element.attrib:
        del element.attrib[key]
