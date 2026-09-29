"""Language-neutral pieces of the ja/en text frontends: LaTeX -> Unicode math, a
tokenizer, and the rules that decide which tokens of a sentence are math (numbers,
operators, single-letter variables, function names, units) and which are prose."""

from __future__ import annotations

import re
from dataclasses import dataclass

FUNC_NAMES = frozenset({"sin", "cos", "tan", "sec", "csc", "cot", "log", "ln", "exp", "lim", "max", "min"})
UNIT_NAMES = frozenset({"mm", "cm", "km", "kg", "mg", "ml", "mL", "kcal", "Hz", "min", "sec"})


_TOKEN = re.compile(
    r"(?P<num>\d+(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)"
    r"|(?P<word>[A-Za-z]+(?:['’][A-Za-z]+)*)"
    r"|(?P<greek>[α-ωΑ-Ω])"
    r"|(?P<op>[-+*/=<>^×÷±≤≥≠≈√∞°%()|])"
    r"|(?P<space>\s+)"
    r"|(?P<other>.)",
    re.S,
)
_OPERATORS = set("+-*/=<>^×÷±≤≥≠≈√")


@dataclass
class Tok:
    kind: str
    text: str
    space_before: bool = False
    math: bool = False


def tokens(text: str) -> list[Tok]:
    toks: list[Tok] = []
    space = False
    for m in _TOKEN.finditer(text):
        kind = m.lastgroup or "other"
        if kind == "space":
            space = True
            continue
        toks.append(Tok(kind, m.group(), space))
        space = False
    return toks


def is_operand(t: Tok | None) -> bool:
    return t is not None and (t.kind in ("num", "greek") or (t.kind == "word" and t.math) or t.text in ")∞")


def mark_math(toks: list[Tok]) -> None:
    """Decides which tokens belong to math: numbers, operators with math operands,
    single-letter variables next to numbers/operators, function names and units."""
    n = len(toks)

    def at(i: int) -> Tok | None:
        return toks[i] if 0 <= i < n else None

    for t in toks:
        t.math = t.kind in ("num", "greek") or t.text in ("√", "∞")
    for _ in range(2):  # a second pass lets `x` in `x = y` see its marked neighbour
        for i, t in enumerate(toks):
            prev, nxt = at(i - 1), at(i + 1)
            if t.kind == "word":
                t.math = t.math or _word_is_math(t, prev, nxt, at(i + 2))
            elif t.kind == "op":
                t.math = _op_is_math(t, prev, nxt)


def _word_is_math(t: Tok, prev: Tok | None, nxt: Tok | None, after: Tok | None) -> bool:
    low = t.text.lower()
    if t.text in UNIT_NAMES and prev is not None and prev.kind == "num":
        return True  # 12 cm, 5kg
    if t.text in ("C", "F") and prev is not None and prev.text == "°" and not t.space_before:
        return True  # 100°C
    if low in FUNC_NAMES and len(t.text) > 1:
        return nxt is not None and not nxt.space_before and (nxt.text == "(" or nxt.kind in ("num", "word"))
    if len(t.text) != 1:
        return False
    if (
        nxt is not None
        and nxt.text == "-"
        and not nxt.space_before
        and after is not None
        and after.kind == "word"
        and len(after.text) > 1
        and not after.space_before
    ):
        return False  # x-axis
    if t.text == "x" and prev is not None and nxt is not None and prev.kind == "num" and nxt.kind == "num":
        return True  # 3 x 4
    if prev is not None and (prev.text in _OPERATORS or (prev.text == "(" and not t.space_before)):
        return True
    if nxt is not None and (nxt.text in _OPERATORS or (nxt.text in "(^" and not nxt.space_before)):
        return True
    glued_prev = prev is not None and not t.space_before and prev.math and prev.kind != "op"
    glued_next = nxt is not None and not nxt.space_before and nxt.math and nxt.kind != "op"
    return glued_prev or glued_next


def _op_is_math(t: Tok, prev: Tok | None, nxt: Tok | None) -> bool:
    op = t.text
    if op in ("√", "∞"):
        return True
    if op in "%°":
        return prev is not None and prev.math
    if op == "(":
        return (
            (prev is not None and prev.math and not t.space_before)
            or is_operand(nxt)
            or (nxt is not None and nxt.text in "-√(")
        )
    if op == ")":
        return is_operand(prev)
    if (
        op == "-"
        and prev is not None
        and nxt is not None
        and prev.kind == nxt.kind == "word"
        and not t.space_before
        and not nxt.space_before
        and (len(prev.text) > 1 or len(nxt.text) > 1)
    ):
        return False  # well-known
    if op in ("-", "+"):
        return is_operand(nxt) or (nxt is not None and nxt.text in "(√") or is_operand(prev)
    return is_operand(prev) or is_operand(nxt) or (nxt is not None and nxt.text in "(√-")


def read_group(toks: list[Tok], i: int) -> tuple[list[Tok], int]:
    """Operand after `^` or `√`: a parenthesised group, a signed token or one token."""
    if i < len(toks) and toks[i].text == "(":
        depth = 0
        for j in range(i, len(toks)):
            if toks[j].text == "(":
                depth += 1
            elif toks[j].text == ")":
                depth -= 1
                if depth == 0:
                    return toks[i + 1 : j], j + 1
        return toks[i + 1 :], len(toks)
    if i + 1 < len(toks) and toks[i].text == "-":
        return toks[i : i + 2], i + 2
    return toks[i : i + 1], i + 1


FULLWIDTH = {i: i - 0xFEE0 for i in range(0xFF01, 0xFF5F)}
_LATEX = {
    r"\times": "×", r"\cdot": "×", r"\div": "÷", r"\pm": "±", r"\leq": "≤", r"\le": "≤",
    r"\geq": "≥", r"\ge": "≥", r"\neq": "≠", r"\ne": "≠", r"\approx": "≈", r"\infty": "∞",
    r"\circ": "°", r"\degree": "°", r"\%": "%", r"\pi": "π", r"\theta": "θ", r"\alpha": "α",
    r"\beta": "β", r"\left": "", r"\right": "", r"\,": " ", r"\;": " ", r"\quad": " ",
}  # fmt: skip


def latex(s: str) -> str:
    if not re.search(r"\\[A-Za-z]+|\$|\^\{|_\{", s):
        return s
    s = re.sub(r"\\\(|\\\)|\\\[|\\\]|\$\$?", " ", s)
    for _ in range(4):  # nested \frac / \sqrt, innermost first
        s = re.sub(r"\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", s)
        s = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"√(\1)", s)
        s = re.sub(r"\\(?:text|mathrm|mathbf|operatorname)\s*\{([^{}]*)\}", r" \1 ", s)
    for k in sorted(_LATEX, key=len, reverse=True):
        s = s.replace(k, _LATEX[k])
    s = re.sub(r"\^\s*\{([^{}]*)\}", r"^(\1)", s)
    s = re.sub(r"_\s*\{([^{}]*)\}|_", " ", s)
    s = re.sub(r"\\([A-Za-z]+)", r" \1 ", s)  # \sin -> sin, unknown commands -> their name
    s = re.sub(r"\((\d+)\)/\((\d+)\)", r"\1/\2", s)  # \frac{3}{4} reads as a fraction
    return s.replace("{", " ").replace("}", " ")
