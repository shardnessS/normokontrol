"""A subset of LaTeX math → Office Math (OMML), so formulas are editable in Word.

Supported: letters, digits, operators; ^ and _; \\frac, \\dfrac, \\sqrt[n]{}; \\sum, \\prod, \\int with
limits; \\left( … \\right); Greek letters; common relations and symbols; \\sin, \\ln, …; \\text{}, \\mathrm{};
spacing commands. Anything else raises MathError with the unknown command.
"""

from __future__ import annotations

from dataclasses import dataclass

from lxml import etree

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _m(tag: str) -> str:
    return f"{{{M_NS}}}{tag}"


class MathError(ValueError):
    pass


GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ϵ", "varepsilon": "ε",
    "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ",
    "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "varpi": "ϖ", "rho": "ρ",
    "varrho": "ϱ", "sigma": "σ", "varsigma": "ς", "tau": "τ", "upsilon": "υ", "phi": "ϕ",
    "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π",
    "Sigma": "Σ", "Upsilon": "Υ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}  # fmt: skip
SYMBOLS = {
    "cdot": "⋅", "times": "×", "div": "÷", "pm": "±", "mp": "∓", "le": "≤", "leq": "≤",
    "ge": "≥", "geq": "≥", "ne": "≠", "neq": "≠", "approx": "≈", "equiv": "≡", "sim": "∼",
    "infty": "∞", "to": "→", "rightarrow": "→", "leftarrow": "←", "Rightarrow": "⇒",
    "partial": "∂", "nabla": "∇", "in": "∈", "notin": "∉", "subset": "⊂", "cup": "∪",
    "cap": "∩", "forall": "∀", "exists": "∃", "cdots": "⋯", "ldots": "…", "dots": "…",
    "circ": "∘", "degree": "°", "prime": "′", "%": "%", "{": "{", "}": "}", "_": "_",
    "lt": "<", "gt": ">",
}  # fmt: skip
NARY = {"sum": "∑", "prod": "∏", "int": "∫", "iint": "∬", "oint": "∮"}
FUNCTIONS = {
    "sin", "cos", "tg", "ctg", "tan", "cot", "arcsin", "arccos", "arctg", "ln", "lg", "log",
    "exp", "max", "min", "lim", "sup", "inf", "det", "sh", "ch", "th", "sinh", "cosh", "tanh",
}  # fmt: skip
SPACES = {",": " ", ";": " ", ":": " ", "quad": " ", "qquad": "  ", "!": ""}
TEXT_COMMANDS = {"text", "mathrm", "operatorname"}
DELIMITERS = {"(": "(", ")": ")", "[": "[", "]": "]", "|": "|", ".": "", "\\{": "{", "\\}": "}"}


@dataclass
class _Token:
    kind: str  # "cmd", "char", "{", "}", "^", "_"
    value: str


def _tokenize(latex: str) -> list[_Token]:
    tokens: list[_Token] = []
    i = 0
    while i < len(latex):
        ch = latex[i]
        if ch.isspace():
            i += 1
        elif ch == "\\":
            j = i + 1
            if j < len(latex) and latex[j].isalpha():
                while j < len(latex) and latex[j].isalpha():
                    j += 1
                name = latex[i + 1 : j]
                tokens.append(_Token("cmd", name))
                i = j
                if name in TEXT_COMMANDS and latex[i : i + 1] == "{":
                    # Аргумент \text{…} — обычный текст с пробелами, читаем как есть.
                    end = latex.find("}", i)
                    if end == -1:
                        raise MathError(f"не закрыта фигурная скобка после \\{name}")
                    tokens.append(_Token("text", latex[i + 1 : end]))
                    i = end + 1
            elif j < len(latex):
                tokens.append(_Token("cmd", latex[j]))
                i = j + 1
            else:
                raise MathError("одиночная «\\» в конце формулы")
        elif ch in "{}^_":
            tokens.append(_Token(ch, ch))
            i += 1
        else:
            tokens.append(_Token("char", ch))
            i += 1
    return tokens


class _Parser:
    def __init__(self, latex: str) -> None:
        self.tokens = _tokenize(latex)
        self.pos = 0

    def peek(self) -> _Token | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self) -> _Token:
        token = self.peek()
        if token is None:
            raise MathError("формула оборвалась: не хватает аргумента или «}»")
        self.pos += 1
        return token

    def expression(self, stop: str | None = None) -> list[etree._Element]:
        items: list[etree._Element] = []
        while (token := self.peek()) is not None:
            if token.kind == "}" and stop == "}":
                break
            if token.kind == "cmd" and token.value == "right" and stop == "right":
                break
            if token.kind == "}":
                raise MathError("лишняя «}»")
            items.extend(self.scripted())
        return items

    def scripted(self) -> list[etree._Element]:
        base = self.atom()
        sub = sup = None
        while (token := self.peek()) is not None and token.kind in ("^", "_"):
            self.take()
            if token.kind == "^":
                sup = self.argument()
            else:
                sub = self.argument()
        if sub is None and sup is None:
            return base
        nary = base[0] if len(base) == 1 and base[0].tag == _m("nary") else None
        if nary is not None:
            _fill_nary(nary, sub, sup)
            nary_e = nary.find(_m("e"))
            assert nary_e is not None
            for item in self.scripted():  # тело оператора — следующий элемент
                nary_e.append(item)
            return [nary]
        if sub is not None and sup is not None:
            return [_struct("sSubSup", e=base, sub=sub, sup=sup)]
        if sup is not None:
            return [_struct("sSup", e=base, sup=sup)]
        assert sub is not None
        return [_struct("sSub", e=base, sub=sub)]

    def argument(self) -> list[etree._Element]:
        token = self.peek()
        if token is not None and token.kind == "{":
            self.take()
            items = self.expression(stop="}")
            self.take()
            return items
        return self.atom()

    def atom(self) -> list[etree._Element]:
        token = self.take()
        if token.kind == "{":
            items = self.expression(stop="}")
            self.take()
            return items
        if token.kind == "char":
            return [_run(token.value)]
        if token.kind in ("^", "_"):
            raise MathError(f"«{token.value}» без основания")
        return self.command(token.value)

    def command(self, name: str) -> list[etree._Element]:
        if name in ("frac", "dfrac", "tfrac"):
            num = self.argument()
            den = self.argument()
            return [_struct("f", num=num, den=den)]
        if name == "sqrt":
            degree: list[etree._Element] | None = None
            token = self.peek()
            if token is not None and token.kind == "char" and token.value == "[":
                self.take()
                degree = []
                while (t := self.take()).value != "]":
                    degree.extend(self.command(t.value) if t.kind == "cmd" else [_run(t.value)])
            return [_radical(degree, self.argument())]
        if name in NARY:
            return [_nary(NARY[name])]
        if name == "left":
            opening = self._delimiter()
            body = self.expression(stop="right")
            if self.peek() is None:
                raise MathError("\\left без \\right")
            self.take()
            closing = self._delimiter()
            return [_delimited(opening, closing, body)]
        if name in TEXT_COMMANDS:
            return [_run(self._plain_argument(), upright=True)]
        if name in GREEK:
            return [_run(GREEK[name])]
        if name in SYMBOLS:
            return [_run(SYMBOLS[name])]
        if name in FUNCTIONS:
            return [_run(name, upright=True)]
        if name in SPACES:
            return [_run(SPACES[name])] if SPACES[name] else []
        raise MathError(f"команда «\\{name}» не поддерживается")

    def _delimiter(self) -> str:
        token = self.take()
        key = f"\\{token.value}" if token.kind == "cmd" else token.value
        if key not in DELIMITERS:
            raise MathError(f"неподдерживаемая скобка «{key}» после \\left или \\right")
        return DELIMITERS[key]

    def _plain_argument(self) -> str:
        token = self.take()
        if token.kind != "text":
            raise MathError("после \\text нужен аргумент в фигурных скобках")
        return token.value


def latex_to_omml(latex: str) -> etree._Element:
    """<m:oMath> element for a LaTeX formula. Raises MathError on unsupported input."""
    if not latex.strip():
        raise MathError("пустая формула")
    parser = _Parser(latex)
    items = parser.expression()
    math = etree.Element(_m("oMath"), nsmap={"m": M_NS, "w": W_NS})
    for item in items:
        math.append(item)
    return math


def _run(text: str, *, upright: bool = False) -> etree._Element:
    run = etree.Element(_m("r"))
    if upright:
        props = etree.SubElement(run, _m("rPr"))
        etree.SubElement(props, _m("sty"), {_m("val"): "p"})
    t = etree.SubElement(run, _m("t"))
    t.text = text
    if text != text.strip():
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return run


def _struct(tag: str, **parts: list[etree._Element]) -> etree._Element:
    element = etree.Element(_m(tag))
    for name, content in parts.items():
        child = etree.SubElement(element, _m(name))
        for item in content:
            child.append(item)
    return element


def _radical(degree: list[etree._Element] | None, body: list[etree._Element]) -> etree._Element:
    rad = etree.Element(_m("rad"))
    if degree is None:
        props = etree.SubElement(rad, _m("radPr"))
        etree.SubElement(props, _m("degHide"), {_m("val"): "1"})
    deg = etree.SubElement(rad, _m("deg"))
    for item in degree or []:
        deg.append(item)
    e = etree.SubElement(rad, _m("e"))
    for item in body:
        e.append(item)
    return rad


def _nary(char: str) -> etree._Element:
    nary = etree.Element(_m("nary"))
    props = etree.SubElement(nary, _m("naryPr"))
    etree.SubElement(props, _m("chr"), {_m("val"): char})
    etree.SubElement(props, _m("subHide"), {_m("val"): "1"})
    etree.SubElement(props, _m("supHide"), {_m("val"): "1"})
    for name in ("sub", "sup", "e"):
        etree.SubElement(nary, _m(name))
    return nary


def _fill_nary(
    nary: etree._Element, sub: list[etree._Element] | None, sup: list[etree._Element] | None
) -> None:
    props = nary.find(_m("naryPr"))
    assert props is not None
    for name, content in (("sub", sub), ("sup", sup)):
        if content is None:
            continue
        hide = props.find(_m(f"{name}Hide"))
        if hide is not None:
            props.remove(hide)
        target = nary.find(_m(name))
        assert target is not None
        for item in content:
            target.append(item)


def _delimited(opening: str, closing: str, body: list[etree._Element]) -> etree._Element:
    d = etree.Element(_m("d"))
    props = etree.SubElement(d, _m("dPr"))
    etree.SubElement(props, _m("begChr"), {_m("val"): opening})
    etree.SubElement(props, _m("endChr"), {_m("val"): closing})
    e = etree.SubElement(d, _m("e"))
    for item in body:
        e.append(item)
    return d
