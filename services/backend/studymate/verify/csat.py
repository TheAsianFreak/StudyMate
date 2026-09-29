"""CSAT (수능) math that SymPy can check: 수학Ⅰ·Ⅱ, 확률과 통계, 미적분, 기하.

The computational core of those subjects when a problem is fully stated in math (LaTeX,
plain text or both, mixed with Korean / Japanese / English prose):

- limits (two-sided, one-sided, at infinity) and definite integrals, finite and infinite sums
- derivative values f'(a), f''(a) of explicitly given functions, d/dx
- exponents, roots, logarithms (log_a b, log b, ln b), trigonometric values (radians or degrees)
- nCr, nPr, nHr, nΠr, n!, binomial coefficients, the coefficient of x^k in an expansion
- explicit, arithmetic / geometric and recursive (a_{n+1} = f(a_n)) sequences, partial sums
- event probabilities P(A ∩ B), P(B | A), P_A(B) (with independence), binomial / normal moments
- vectors (components, dot product, length), points and segment lengths
- templates read from standard prose: local extrema / extrema on an interval, enclosed areas,
  distance travelled, tangent slopes (explicit, parametric, implicit curves), conic foci and
  axes - also when the prose names the value ("넓이를 S라 할 때 6S의 값")

Unknown constants are solved from the stated equations; the answer is accepted only when
every solution gives the same value. A condition we did not read (it is only in prose) can
only remove solutions, so a unique value stays correct - and anything we cannot read
entirely (piecewise functions, conditions (가)(나), tables, figures, word problems) returns
None so the caller falls back to re-solve agreement instead of reporting a false failure.
"""

from __future__ import annotations

import contextlib
import contextvars
import re
import threading
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import sympy

from studymate.verify.latex import numbers_equal, repair_escapes, sym

TIMEOUT = 6.0  # seconds for one analysis (SymPy limits/integrals can be slow on odd input)
MAX_TOKENS = 400
MAX_UNKNOWNS = 4

_CJK = r"\uac00-\ud7a3\u3131-\u318e\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f"


class _Err(Exception):
    """The math could not be read (never escapes this module)."""


# ---------------------------------------------------------------------------------------
# Detection and multiple choice
# ---------------------------------------------------------------------------------------

_CSAT_MARK = re.compile(
    r"\\(?:lim|int|sum|log|ln|sin|cos|tan|sec|csc|cot|binom|dbinom|vec|overrightarrow|prime|infty|Pi)(?![A-Za-z])"
    r"|(?<![\\A-Za-z])(?:lim|log|ln|sin|cos|tan)(?![A-Za-z])|[∫∑Σ∞′]"
    r"|[A-Za-z]\s*'+\s*\(|[A-Za-z]\s*\^\s*\{\s*\\prime"
    r"|_\s*\{?\s*\d+\s*\}?\s*(?:\\mathrm\s*\{\s*)?[CPH](?![A-Za-z])|\d\s*[CPH]\s*\d"
    r"|(?:\d|\))\s*!(?!=)"
    r"|(?<![A-Za-z\\])[a-z]\s*_\s*\{?\s*(?:n|k|\d+)\b"
    r"|(?<![A-Za-z])[fghv]\s*\(\s*[a-z]\s*\)\s*="
    r"|P\s*\(\s*(?:\\overline\s*\{?\s*)?[A-Z]"
    r"|등차수열|등비수열|수열|이항분포|정규분포|확률변수|미분계수|도함수|정적분|극댓값|극솟값|둘러싸인|움직인\s*거리|벡터"
    r"|접선|닫힌구간|전개식|계수|상수항|매개변수|媒介変数|parametric|좌표공간|座標空間|coordinate space"
    r"|타원|쌍곡선|초점|楕円|双曲線|焦点|ellipse|hyperbola|foci|focus"
    r"|(?:실근|해)의\s*(?:합|곱|개수)|(?:정수|자연수)\s*\$?[a-z]\$?\s*의\s*개수"
    r"|(?:実数解|解)の(?:和|積|個数)|(?:整数|自然数)\s*\$?[a-z]\$?\s*の個数"
    r"|(?:sum|product|number) of (?:all )?(?:the )?(?:distinct )?(?:real )?(?:solutions|roots)"
    r"|number of (?:integers|natural numbers|positive integers)"
    r"|(?:삼각형|三角形|triangle)\s*\$?\s*[A-Z]{3}(?![A-Za-z])|\\angle"
    r"|\\frac\s*\{\s*d\s*y\s*\}|[A-Z]\s*\(\s*-?\d+\s*,\s*-?\d+\s*,\s*-?\d+\s*\)"
    r"|等差数列|等比数列|数列|二項分布|正規分布|確率変数|微分係数|導関数|定積分|極大値|極小値|囲まれた|道のり|ベクトル"
    r"|接線|閉区間|展開式|係数|定数項|coefficient|constant term"
    r"|arithmetic sequence|geometric sequence|binomial distribution|normal distribution|random variable"
    r"|local (?:maximum|minimum)|region (?:bounded|enclosed)|area of the region|distance travel|tangent",
    re.IGNORECASE,
)


def looks_csat(text: str) -> bool:
    """True when the problem uses high-school (수학Ⅰ and beyond) notation or topics."""
    return bool(_CSAT_MARK.search(text or ""))


_CIRCLED = {chr(0x2460 + i): i + 1 for i in range(20)} | {chr(0x2776 + i): i + 1 for i in range(10)}
_CIRCLED_RE = re.compile("[" + "".join(_CIRCLED) + "]")
_POINTS = re.compile(r"[\[(（［]\s*\d\s*(?:점|点|points?|pts?\.?)\s*[\])）］]", re.IGNORECASE)


def split_choices(text: str) -> tuple[str, list[str]]:
    """(stem, choices) for a 5지선다-style problem ("... ① 1 ② 2 ③ 3 ④ 4 ⑤ 5").

    At least four circled numbers, in order from ①, count as choices; fewer are labels of
    equations ("① x+y=5 ② x-y=1") and stay in the stem.
    """
    marks = [(m.start(), _CIRCLED[m.group(0)]) for m in _CIRCLED_RE.finditer(text or "")]
    if len(marks) < 4 or [n for _, n in marks] != list(range(1, len(marks) + 1)):
        return text, []
    stem = text[: marks[0][0]]
    choices = []
    for i, (pos, _) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        choices.append(text[pos + 1 : end].strip(" \t\n,;/|$"))
    if any(not c for c in choices):
        return text, []
    return stem, choices


def has_point_marker(text: str) -> bool:
    """ "[3점]"-style score marker: a CSAT problem (단답형 answers are integers 0~999)."""
    return bool(_POINTS.search(text or ""))


# ---------------------------------------------------------------------------------------
# Preparation: LaTeX / Unicode / prose -> clean LaTeX-ish text
# ---------------------------------------------------------------------------------------

_UNICODE_TEX = {
    "−": "-",
    "–": "-",
    "—": "-",
    "×": " \\times ",
    "·": " \\cdot ",
    "∙": " \\cdot ",
    "⋅": " \\cdot ",
    "÷": " \\div ",
    "≤": " \\le ",
    "≦": " \\le ",
    "≥": " \\ge ",
    "≧": " \\ge ",
    "≠": " \\ne ",
    "√": " \\sqrt ",
    "π": " \\pi ",
    "∞": " \\infty ",
    "→": " \\to ",
    "∑": " \\sum ",
    "Σ": " \\sum ",
    "∫": " \\int ",
    "θ": " \\theta ",
    "α": " \\alpha ",
    "β": " \\beta ",
    "σ": " \\sigma ",
    "Π": " \\Pi ",
    "′": "'",
    "″": "''",
    "°": "^\\circ ",
    "∪": " \\cup ",
    "∩": " \\cap ",
    "∣": "|",
    "｜": "|",
    "²": "^2",
    "³": "^3",
    "≒": " \\approx ",
    "≈": " \\approx ",
}
_FUNC_WORDS = ("lim", "log", "ln", "sin", "cos", "tan", "sec", "csc", "cot", "exp", "sqrt")
_TEXT_CMDS = (
    "text",
    "textrm",
    "textbf",
    "textit",
    "mathrm",
    "mathbf",
    "mathit",
    "mbox",
    "operatorname",
    "rm",
)
_EN_SMALL = "is|of|if|in|to|by|an|at|or|as|be|it|so|we|on|no"
_PROSE = re.compile(
    rf"[{_CJK}]+|\$|\n|[?？。、:：]|(?<![\\A-Za-z])(?:[A-Za-z]{{3,}}|(?:{_EN_SMALL}))(?![A-Za-z])"
)


def _read_braced(s: str, i: int) -> tuple[str, int] | None:
    """Content of the {...} group starting at s[i] (after optional spaces) and the index after it."""
    while i < len(s) and s[i] == " ":
        i += 1
    if i >= len(s) or s[i] != "{":
        return None
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1 : j], j + 1
    return None


def _unwrap_text(s: str) -> str:
    pattern = re.compile(r"\\(" + "|".join(_TEXT_CMDS) + r")(?![A-Za-z])\s*")
    for _ in range(40):
        m = pattern.search(s)
        if not m:
            return s
        group = _read_braced(s, m.end())
        if group is None:
            s = s[: m.start()] + " " + s[m.end() :]
            continue
        content, end = group
        c = content.strip()
        if re.fullmatch(r"[A-Za-z]", c):
            rep = f" {c} "
        elif c in _FUNC_WORDS:
            rep = f" \\{c} "
        else:
            rep = f" ; {content} ; "
        s = s[: m.start()] + rep + s[end:]
    return s


def _prose_parens(m: re.Match[str]) -> str:
    return " ; " + m.group(1) + " ; "


def prepare(text: str) -> str:
    """Normalized text: Unicode math -> LaTeX commands, \\text{} unwrapped, noise removed."""
    s = repair_escapes(text or "")
    s = _POINTS.sub(" ; ", s)
    for k, v in _UNICODE_TEX.items():
        s = s.replace(k, v)
    s = _CIRCLED_RE.sub(" ; ", s)
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac").replace("\\cfrac", "\\frac")
    s = s.replace("\\dbinom", "\\binom").replace("\\tbinom", "\\binom")
    s = s.replace("\\\\", " ; ").replace("&", " ")
    s = _unwrap_text(s)
    s = re.sub(r"\\(?:left|right|bigl|bigr|Bigl|Bigr|big|Big)(?![A-Za-z])\s*\.?", " ", s)
    s = re.sub(r"\\(?:displaystyle|textstyle|limits|nolimits|mathop)(?![A-Za-z])", " ", s)
    s = re.sub(r"\\(?:quad|qquad)(?![A-Za-z])", " ; ", s)
    s = re.sub(r"\\[,;:! ]", " ", s)
    s = s.replace("~", " ")
    s = re.sub(r"(?<=\d)\s*\\?%", " /100 ", s)  # 95\% = 0.95
    s = re.sub(r"\\(?:therefore|because|Rightarrow|Longrightarrow|implies|iff)(?![A-Za-z])", " ; ", s)
    s = re.sub(r"(?<![\\A-Za-z])(" + "|".join(_FUNC_WORDS) + r")(?![A-Za-z])", r" \\\1 ", s)
    s = s.replace("->", " \\to ")
    s = re.sub(r"(?<![A-Za-z0-9_{}])(\d+)\s*([CPH])\s*(\d+)(?![0-9])", r"{}_{\1}\2_{\3}", s)  # 5C2
    # sequence names: {a_n}, \{a_n\}
    s = re.sub(r"\\?\{\s*[A-Za-z]\s*_\s*\{?\s*n\s*\}?\s*\\?\}", " ; ", s)
    # parenthesized prose and conditions: "(단, a는 상수이다.)", "(where ...)", "(t >= 0)"
    s = re.sub(rf"\(([^()]*[{_CJK}][^()]*)\)", _prose_parens, s)
    s = re.sub(r"\(((?:\s*(?:where|for|assume|given|if|with|note)\b)[^()]*)\)", _prose_parens, s, flags=re.I)
    s = re.sub(r"\(([^()]*(?:\\(?:le|ge|leq|geq|ne|neq|lt|gt)(?![A-Za-z])|[<>=])[^()]*)\)", _prose_parens, s)
    return s


# ---------------------------------------------------------------------------------------
# Segments: math runs between prose, with the prose around them
# ---------------------------------------------------------------------------------------


@dataclass
class Segment:
    tex: str
    before: str
    after: str


def _split_top(s: str, seps: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in s:
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth = max(0, depth - 1)
        if ch in seps and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def segments(prepared: str) -> list[Segment]:
    pieces: list[tuple[bool, str]] = []
    pos = 0
    for m in _PROSE.finditer(prepared):
        if m.start() > pos:
            pieces.append((False, prepared[pos : m.start()]))
        pieces.append((True, m.group(0)))
        pos = m.end()
    if pos < len(prepared):
        pieces.append((False, prepared[pos:]))
    merged: list[tuple[bool, str]] = []
    for is_prose, t in pieces:
        if not is_prose and not re.search(r"[0-9A-Za-z\\]", t):
            is_prose = True
        if merged and merged[-1][0] == is_prose:
            merged[-1] = (is_prose, merged[-1][1] + t)
        else:
            merged.append((is_prose, t))
    out: list[Segment] = []
    for idx, (is_prose, t) in enumerate(merged):
        if is_prose:
            continue
        # "$f'(2)$의 값은?": math delimiters are not prose words
        before = (merged[idx - 1][1] if idx > 0 else "").replace("$", " ").rstrip()
        after = (merged[idx + 1][1] if idx + 1 < len(merged) else "").replace("$", " ").lstrip()
        parts = [p.strip(" .") for p in _split_top(t, ",;")]
        parts = [p for p in parts if p]
        for j, p in enumerate(parts):
            out.append(Segment(p, before if j == 0 else ",", after if j == len(parts) - 1 else ","))
    return out


# ---------------------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------------------

_REL_TOKENS = {
    "=": "=",
    "<": "<",
    ">": ">",
    "<=": "<=",
    ">=": ">=",
    "!=": "!=",
    "\\le": "<=",
    "\\leq": "<=",
    "\\leqq": "<=",
    "\\leqslant": "<=",
    "\\ge": ">=",
    "\\geq": ">=",
    "\\geqq": ">=",
    "\\geqslant": ">=",
    "\\lt": "<",
    "\\gt": ">",
    "\\ne": "!=",
    "\\neq": "!=",
    "\\approx": "~",
    "\\fallingdotseq": "~",
    "\\simeq": "~",
}


def tokenize(s: str) -> list[str]:
    toks: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c == "\\":
            m = re.match(r"\\([A-Za-z]+)", s[i:])
            if m:
                toks.append("\\" + m.group(1))
                i += m.end()
                continue
            nxt = s[i + 1] if i + 1 < n else ""
            if nxt and nxt in "{}":
                toks.append("(" if nxt == "{" else ")")
            elif nxt == "|":
                toks.append("|")
            else:
                raise _Err(f"escape \\{nxt}")  # never drop a character silently
            i += 2
            continue
        if c.isdigit() or (c == "." and i + 1 < n and s[i + 1].isdigit()):
            m = re.match(r"\d+(?:\.\d+)?|\.\d+", s[i:])
            assert m is not None
            toks.append(m.group(0))
            i += m.end()
            continue
        if c.isascii() and c.isalpha():
            toks.append(c)
            i += 1
            continue
        two = s[i : i + 2]
        if two in ("<=", ">=", "!="):
            toks.append(two)
            i += 2
            continue
        if c in "+-*/^_(){}[]|!',=<>":
            toks.append(c)
            i += 1
            continue
        raise _Err(f"character {c!r}")
    if len(toks) > MAX_TOKENS:
        raise _Err("too long")
    return toks


def split_relations(toks: list[str]) -> tuple[list[list[str]], list[str]]:
    """Top-level relation split: 'a = b < c' -> ([a, b, c], ['=', '<'])."""
    parts: list[list[str]] = [[]]
    ops: list[str] = []
    depth = 0
    for t in toks:
        if t in "({[":
            depth += 1
        elif t in ")}]":
            depth -= 1
        if depth == 0 and t in _REL_TOKENS:
            ops.append(_REL_TOKENS[t])
            parts.append([])
        else:
            parts[-1].append(t)
    return parts, ops


# ---------------------------------------------------------------------------------------
# Environment (definitions) and the expression parser
# ---------------------------------------------------------------------------------------


@dataclass
class Env:
    funcs: dict[str, tuple[sympy.Symbol, sympy.Expr]] = field(default_factory=dict)
    seqs: dict[str, tuple[sympy.Symbol, sympy.Expr]] = field(default_factory=dict)
    vectors: dict[str, sympy.Matrix] = field(default_factory=dict)
    points: dict[str, sympy.Matrix] = field(default_factory=dict)
    events: tuple[str, ...] = ()
    atoms: tuple[sympy.Symbol, ...] = ()
    rvs: dict[str, tuple[sympy.Expr, sympy.Expr]] = field(default_factory=dict)  # name -> (mean, variance)
    euler: bool = True  # "e" is Euler's number unless the problem names something e ("이심률을 e라 할 때")
    # base of a bare "log": 10 in Korea (상용로그) and the US; e in Japan (数学Ⅲ writes log x for ln x)
    log_base: Any = 10
    # a_{n+1} = f(n, a_n) (order 1) or a_{n+2} = f(n, a_n, a_{n+1}) (order 2): name -> (order, n, f, a)
    recurrences: dict[str, tuple[int, sympy.Symbol, sympy.Expr, Any]] = field(default_factory=dict)
    extra_eqs: list[sympy.Expr] = field(default_factory=list)  # model constraints (unit circle, angle)
    extra_ineqs: list[tuple[sympy.Expr, str, sympy.Expr]] = field(default_factory=list)
    # triangle ABC: vertex -> (length of the opposite side, cosine of the angle at the vertex)
    triangle: dict[str, tuple[sympy.Symbol, sympy.Symbol]] = field(default_factory=dict)

    def term(self, name: str, k: int) -> sympy.Expr:
        """k-th term of a recursively defined sequence, in terms of its first term(s) a_1 (, a_2)."""
        order, n, body, prev = self.recurrences[name]
        if not 1 <= k <= 60:
            raise _Err("term index")
        vals: dict[int, sympy.Expr] = {i: sym(f"{name}_{i}") for i in range(1, order + 1)}
        for m in range(1, k - order + 1):
            nxt = body.subs(n, m)
            nxt = nxt.subs({prev(m + j): vals[m + j] for j in range(order)})
            if nxt.has(prev):
                raise _Err("recurrence")
            nxt = sympy.expand(nxt)
            if sympy.count_ops(nxt) > 200:
                raise _Err("recurrence grows too fast")
            vals[m + order] = nxt
        return vals[k]

    def event_set(self, name: str) -> frozenset[int]:
        k = self.events.index(name)
        return frozenset(i for i in range(len(self.atoms)) if i >> k & 1)

    def prob(self, ev: frozenset[int]) -> sympy.Expr:
        return sympy.Add(*[self.atoms[i] for i in sorted(ev)])


_FUNCS: dict[str, Callable[[Any], Any]] = {
    "\\sin": sympy.sin,
    "\\cos": sympy.cos,
    "\\tan": sympy.tan,
    "\\sec": sympy.sec,
    "\\csc": sympy.csc,
    "\\cot": sympy.cot,
    "\\exp": sympy.exp,
}
_GREEK = {
    "\\theta": "theta",
    "\\alpha": "alpha",
    "\\beta": "beta",
    "\\gamma": "gamma",
    "\\omega": "omega",
    "\\phi": "phi",
    "\\varphi": "phi",
    "\\lambda": "lambda",
    "\\mu": "mu",
    "\\sigma": "sigma",
    "\\delta": "delta",
    "\\rho": "rho",
    "\\tau": "tau",
}
_BIG_OPS = ("\\lim", "\\sum", "\\int", "\\log", "\\ln") + tuple(_FUNCS)
_ATOM_CMDS = {
    "\\frac",
    "\\sqrt",
    "\\pi",
    "\\infty",
    "\\binom",
    "\\vec",
    "\\overrightarrow",
    "\\overline",
    "\\bar",
    "\\angle",
    *_BIG_OPS,
    *_GREEK,
}
_MUL = {"*", "\\times", "\\cdot"}
_DIV = {"/", "\\div"}
_FUNC_LETTERS = set("fghFGHpqsvuwxyk")


def _is_num(t: str | None) -> bool:
    return bool(t) and (t[0].isdigit() or t[0] == ".")  # type: ignore[index]


def _is_letter(t: str | None) -> bool:
    return t is not None and len(t) == 1 and t.isalpha()


def _int(v: Any) -> int:
    if isinstance(v, sympy.Matrix) or not getattr(v, "is_integer", False) or not v.is_number:
        raise _Err("integer expected")
    return int(v)


def _scalar(v: Any) -> sympy.Expr:
    if isinstance(v, sympy.MatrixBase):
        raise _Err("vector where a number was expected")
    if isinstance(v, (sympy.Tuple, tuple)):
        raise _Err("tuple")
    return sympy.sympify(v)


def _finite(v: sympy.Expr) -> bool:
    try:
        return not v.has(sympy.oo, -sympy.oo, sympy.zoo, sympy.nan) and v.is_finite is not False
    except Exception:
        return False


def _integrate(body: sympy.Expr, var: sympy.Symbol, lo: sympy.Expr, hi: sympy.Expr) -> sympy.Expr:
    """Definite integral; |g(x)| is split at the roots of g so SymPy integrates each piece."""
    if body.has(sympy.Abs) and lo.is_number and hi.is_number:
        cuts = {lo, hi}
        for a in body.atoms(sympy.Abs):
            arg = a.args[0]
            try:
                roots = sympy.solveset(arg, var, sympy.Interval(sympy.Min(lo, hi), sympy.Max(lo, hi)))
            except Exception as exc:
                raise _Err("abs roots") from exc
            if not isinstance(roots, sympy.FiniteSet):
                raise _Err("abs roots")
            cuts |= set(roots)
        pts = sorted(cuts, key=lambda p: float(p))
        total = sympy.Integer(0)
        for a, b in zip(pts, pts[1:], strict=False):
            mid = (a + b) / 2
            signs = {ab: ab.args[0] * sympy.sign(ab.args[0].subs(var, mid)) for ab in body.atoms(sympy.Abs)}
            total += sympy.integrate(body.xreplace(signs), (var, a, b))
        val = total if float(lo) <= float(hi) else -total
    else:
        val = sympy.integrate(body, (var, lo, hi))
    if val.has(sympy.Integral):
        raise _Err("integral not evaluated")
    return sympy.simplify(val)


class Parser:
    """Recursive-descent LaTeX math parser producing SymPy values (scalars or vectors)."""

    def __init__(self, toks: list[str], env: Env) -> None:
        self.t = list(toks)
        self.i = 0
        self.env = env
        self.abs_depth = 0

    # -- helpers --------------------------------------------------------------------
    def peek(self, k: int = 0) -> str | None:
        j = self.i + k
        return self.t[j] if j < len(self.t) else None

    def take(self) -> str:
        tok = self.peek()
        if tok is None:
            raise _Err("unexpected end")
        self.i += 1
        return tok

    def expect(self, tok: str) -> None:
        if self.take() != tok:
            raise _Err(f"expected {tok}")

    def done(self) -> bool:
        return self.i >= len(self.t)

    def full(self) -> Any:
        v = self.expr()
        if not self.done():
            raise _Err(f"trailing {self.peek()}")
        return v

    def starts_atom(self, tok: str | None) -> bool:
        if tok is None:
            return False
        if _is_num(tok) or _is_letter(tok):
            return True
        if tok == "|":
            return self.abs_depth == 0
        return tok in ("(", "{", "[") or tok in _ATOM_CMDS

    def group_tokens(self) -> list[str]:
        """Tokens of a {...} group, or the single next token."""
        if self.peek() == "{":
            self.take()
            depth = 1
            out: list[str] = []
            while True:
                tok = self.take()
                if tok == "{":
                    depth += 1
                elif tok == "}":
                    depth -= 1
                    if depth == 0:
                        return out
                out.append(tok)
        tok = self.take()
        if tok in ("-", "+"):
            return [tok, *self.group_tokens()]
        if _is_num(tok) and len(tok) > 1 and "." not in tok:
            self.t.insert(self.i, tok[1:])  # "\frac12": one character per argument
            return [tok[0]]
        return [tok]

    def sub(self, toks: list[str]) -> Any:
        p = Parser(toks, self.env)
        return p.full()

    def group(self) -> Any:
        return self.sub(self.group_tokens())

    # -- grammar --------------------------------------------------------------------
    def expr(self) -> Any:
        val = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()
            rhs = self.term()
            val = val + rhs if op == "+" else val - rhs
        return val

    def term(self) -> Any:
        val = self.factor()
        while True:
            tok = self.peek()
            if tok in _MUL:
                self.take()
                rhs = self.factor()
                val = self.mul(val, rhs, dot=tok == "\\cdot")
            elif tok in _DIV:
                self.take()
                rhs = _scalar(self.factor())
                if rhs == 0:
                    raise _Err("division by zero")
                val = val / rhs
            elif self.starts_atom(tok):
                val = self.mul(val, self.postfix())
            else:
                return val

    @staticmethod
    def mul(a: Any, b: Any, dot: bool = False) -> Any:
        va, vb = isinstance(a, sympy.MatrixBase), isinstance(b, sympy.MatrixBase)
        if va and vb:
            if not dot or a.shape != b.shape:
                raise _Err("vector product")
            return a.dot(b)
        return a * b

    def factor(self) -> Any:
        tok = self.peek()
        if tok == "-":
            self.take()
            return -self.factor()
        if tok == "+":
            self.take()
            return self.factor()
        return self.postfix()

    def postfix(self) -> Any:
        return self.postfix_ops(self.atom())

    def postfix_ops(self, val: Any) -> Any:
        while True:
            tok = self.peek()
            if tok == "^":
                self.take()
                if self.peek() == "\\circ":
                    self.take()
                    val = _scalar(val) * sympy.pi / 180
                    continue
                if self.peek() == "{" and self.peek(1) == "\\circ" and self.peek(2) == "}":
                    self.i += 3
                    val = _scalar(val) * sympy.pi / 180
                    continue
                exp = _scalar(self.sub(self.group_tokens()))
                val = _scalar(val) ** exp
            elif tok == "!":
                self.take()
                n = _int(_scalar(val))
                if n < 0 or n > 170:
                    raise _Err("factorial range")
                val = sympy.factorial(n)
            else:
                return val

    def atom(self) -> Any:
        tok = self.take()
        if _is_num(tok):
            return sympy.Rational(tok)
        if tok == "(":
            items = [self.expr()]
            while self.peek() == ",":
                self.take()
                items.append(self.expr())
            self.expect(")")
            if len(items) > 1:
                return sympy.Matrix([_scalar(v) for v in items])
            return items[0]
        if tok == "{":
            if self.peek() == "}" and self.peek(1) == "_":
                self.take()
                return self.counting()
            v = self.expr()
            self.expect("}")
            return v
        if tok == "_":
            self.i -= 1
            return self.counting()
        if tok == "[":
            return self.bracket_eval()
        if tok == "|":
            self.abs_depth += 1
            v = self.expr()
            self.abs_depth -= 1
            self.expect("|")
            if isinstance(v, sympy.MatrixBase):
                return sympy.sqrt(v.dot(v))
            return sympy.Abs(v)
        if tok == "\\frac":
            return self.frac()
        if tok == "\\sqrt":
            index = None
            if self.peek() == "[":
                self.take()
                idx_toks: list[str] = []
                while self.peek() != "]":
                    idx_toks.append(self.take())
                self.take()
                index = _int(_scalar(self.sub(idx_toks)))
            if self.peek() == "{":
                arg = _scalar(self.group())
            else:
                nxt = self.take()
                arg = _scalar(self.sub([nxt]))
            if index is None or index == 2:
                return sympy.sqrt(arg)
            if index % 2 == 1:
                return sympy.real_root(arg, index)
            return sympy.root(arg, index)
        if tok == "\\pi":
            return sympy.pi
        if tok == "\\infty":
            return sympy.oo
        if tok in _GREEK:
            if tok == "\\sigma" and self.peek() == "(" and self.env.rvs:
                return self.moment("sigma")
            return sym(_GREEK[tok])
        if tok == "\\binom":
            n = _int(_scalar(self.group()))
            r = _int(_scalar(self.group()))
            return sympy.binomial(n, r)
        if tok in _FUNCS:
            return self.func(_FUNCS[tok])
        if tok in ("\\log", "\\ln"):
            return self.log(tok)
        if tok == "\\lim":
            return self.limit()
        if tok == "\\sum":
            return self.summation()
        if tok == "\\int":
            return self.integral()
        if tok in ("\\vec", "\\overrightarrow"):
            name = "".join(self.group_tokens())
            return self.vector(name)
        if tok == "\\overline":
            name = "".join(self.group_tokens())
            if len(name) == 2 and all(c in self.env.points for c in name):
                d = self.env.points[name[1]] - self.env.points[name[0]]
                return sympy.sqrt(d.dot(d))
            tri = self.env.triangle
            if len(name) == 2 and name[0] != name[1] and all(c in tri for c in name):
                (third,) = set(tri) - set(name)
                return tri[third][0]  # side opposite the third vertex
            raise _Err("overline")
        if tok == "\\angle":
            if self.peek() == "{":
                name = "".join(self.group_tokens())
            else:
                letters: list[str] = []
                while len(letters) < 3 and _is_letter(self.peek()) and str(self.peek()).isupper():
                    letters.append(self.take())
                name = "".join(letters)
            if len(name) == 1 and name in self.env.triangle:
                return sympy.acos(self.env.triangle[name][1])
            if len(name) == 3 and set(name) == set(self.env.triangle):
                return sympy.acos(self.env.triangle[name[1]][1])  # ∠BAC: the angle at A
            raise _Err("angle")
        if _is_letter(tok):
            return self.letter(tok)
        raise _Err(f"token {tok}")

    def frac(self) -> Any:
        num = self.group_tokens()
        den = self.group_tokens()
        if num and num[0] == "d" and den and den[0] == "d" and len(den) == 2 and _is_letter(den[1]):
            if num != ["d"]:
                raise _Err("dy/dx")
            var = sym(den[1])
            return sympy.diff(_scalar(self.postfix()), var)
        n, d = self.sub(num), _scalar(self.sub(den))
        if d == 0:
            raise _Err("division by zero")
        return n / d

    def func_arg(self) -> sympy.Expr:
        """Argument of sin/log/...: a parenthesized group or the following monomial
        ("2x", "\\frac{\\pi}{3}")."""
        if self.peek() in ("(", "{"):
            return _scalar(self.postfix_ops(self.atom()))
        val = _scalar(self.postfix())
        while self.starts_atom(self.peek()) and self.peek() not in _BIG_OPS and self.peek() != "|":
            val = val * _scalar(self.postfix())
        return val

    def func(self, fn: Callable[[Any], Any]) -> sympy.Expr:
        power = None
        if self.peek() == "^":
            self.take()
            power = _scalar(self.sub(self.group_tokens()))
            if power == -1:
                raise _Err("inverse function")
        val = fn(self.func_arg())
        return val**power if power is not None else val

    def log(self, tok: str) -> sympy.Expr:
        base: sympy.Expr = sympy.E if tok == "\\ln" else sympy.sympify(self.env.log_base)
        if tok == "\\log" and self.peek() == "_":
            self.take()
            base = _scalar(self.sub(self.group_tokens()))
        power = None
        if self.peek() == "^":
            self.take()
            power = _scalar(self.sub(self.group_tokens()))
        arg = self.func_arg()
        val = sympy.log(arg, base)
        return val**power if power is not None else val

    def limit(self) -> sympy.Expr:
        self.expect("_")
        sub = self.group_tokens()
        if len(sub) < 3 or sub[1] not in ("\\to", "\\rightarrow", "\\longrightarrow"):
            raise _Err("limit subscript")
        var = sym(_GREEK.get(sub[0], sub[0])) if (_is_letter(sub[0]) or sub[0] in _GREEK) else None
        if var is None:
            raise _Err("limit variable")
        rest = sub[2:]
        direction = "+-"
        for tail, d in (
            (["^", "{", "+", "}"], "+"),
            (["^", "{", "-", "}"], "-"),
            (["^", "+"], "+"),
            (["^", "-"], "-"),
            (["+", "0"], "+"),
            (["-", "0"], "-"),
            (["+"], "+"),
            (["-"], "-"),
        ):
            if len(rest) > len(tail) and rest[-len(tail) :] == tail:
                if tail[0] in "+-" and len(tail) == 2 and len(rest) == 2:
                    continue  # "x -> -0"? treat "-0" as the point itself
                rest = rest[: -len(tail)]
                direction = d
                break
        target = _scalar(self.sub(rest))
        body = _scalar(self.term())
        if body.free_symbols - {var}:
            raise _Err("limit with parameters")
        if target in (sympy.oo, -sympy.oo):
            val = sympy.limit(body, var, target)
        else:
            try:
                val = sympy.limit(body, var, target, direction)
            except ValueError as exc:  # left and right limits differ
                raise _Err("limit does not exist") from exc
        if not _finite(val) or val.has(sympy.Limit):
            raise _Err("limit not finite")
        return val

    def summation(self) -> sympy.Expr:
        lo_toks: list[str] | None = None
        hi_toks: list[str] | None = None
        for _ in range(2):
            if self.peek() == "_":
                self.take()
                lo_toks = self.group_tokens()
            elif self.peek() == "^":
                self.take()
                hi_toks = self.group_tokens()
        if lo_toks is None or hi_toks is None or len(lo_toks) < 3 or lo_toks[1] != "=":
            raise _Err("sum bounds")
        var = sym(lo_toks[0]) if _is_letter(lo_toks[0]) else None
        if var is None:
            raise _Err("sum variable")
        lo = _int(_scalar(self.sub(lo_toks[2:])))
        hi = _scalar(self.sub(hi_toks))
        body = _scalar(self.term())
        if hi != sympy.oo and hi.is_number and _int(hi) - lo > 10000:
            raise _Err("sum too long")
        val = sympy.summation(body, (var, lo, hi))
        if val.has(sympy.Sum) or not _finite(val):
            raise _Err("sum not evaluated")
        return sympy.simplify(val)

    def integral(self) -> sympy.Expr:
        lo_toks: list[str] | None = None
        hi_toks: list[str] | None = None
        for _ in range(2):
            if self.peek() == "_":
                self.take()
                lo_toks = self.group_tokens()
            elif self.peek() == "^":
                self.take()
                hi_toks = self.group_tokens()
        if lo_toks is None or hi_toks is None:
            raise _Err("indefinite integral")
        depth = 0
        j = self.i
        while j < len(self.t) - 1:
            tok = self.t[j]
            if tok in "({[":
                depth += 1
            elif tok in ")}]":
                depth -= 1
                if depth < 0:
                    break
            elif depth == 0 and tok == "d" and (_is_letter(self.t[j + 1]) or self.t[j + 1] in _GREEK):
                break
            j += 1
        else:
            raise _Err("no differential")
        if depth != 0 or self.t[j] != "d":
            raise _Err("no differential")
        body_toks = self.t[self.i : j]
        dv = self.t[j + 1]
        var = sym(_GREEK.get(dv, dv))
        self.i = j + 2
        lo, hi = _scalar(self.sub(lo_toks)), _scalar(self.sub(hi_toks))
        body = _scalar(self.sub(body_toks)) if body_toks else sympy.Integer(1)
        if body.free_symbols - {var}:
            params = body.free_symbols - {var}
            if any(not p.is_real for p in params) or lo.free_symbols or hi.free_symbols:
                raise _Err("integral parameters")
        return _integrate(body, var, lo, hi)

    def counting(self) -> sympy.Expr:
        """{}_n C_r, _nP_r, _nH_r, _n\\Pi_r."""
        self.expect("_")
        n = _int(_scalar(self.sub(self.group_tokens())))
        kind = self.take()
        if kind not in ("C", "P", "H", "\\Pi"):
            raise _Err("counting symbol")
        self.expect("_")
        r = _int(_scalar(self.sub(self.group_tokens())))
        if n < 0 or r < 0:
            raise _Err("counting range")
        if kind == "C":
            if r > n:
                raise _Err("nCr range")
            return sympy.binomial(n, r)
        if kind == "P":
            if r > n:
                raise _Err("nPr range")
            return sympy.ff(n, r)
        if kind == "H":
            return sympy.binomial(n + r - 1, r)
        return sympy.Integer(n) ** r

    def bracket_eval(self) -> sympy.Expr:
        """[F(x)]_a^b = F(b) - F(a)."""
        inner = _scalar(self.expr())
        self.expect("]")
        lo_toks = hi_toks = None
        for _ in range(2):
            if self.peek() == "_":
                self.take()
                lo_toks = self.group_tokens()
            elif self.peek() == "^":
                self.take()
                hi_toks = self.group_tokens()
        if lo_toks is None or hi_toks is None or len(inner.free_symbols) != 1:
            raise _Err("bracket")
        (var,) = inner.free_symbols
        lo, hi = _scalar(self.sub(lo_toks)), _scalar(self.sub(hi_toks))
        return sympy.simplify(inner.subs(var, hi) - inner.subs(var, lo))

    def vector(self, name: str) -> sympy.Matrix:
        if name in self.env.vectors:
            return self.env.vectors[name]
        if len(name) == 2 and all(c in self.env.points or c == "O" for c in name):
            pts = self.env.points
            dim = next(iter(pts.values())).shape[0] if pts else 2
            zero = sympy.zeros(dim, 1)
            return pts.get(name[1], zero) - pts.get(name[0], zero)
        raise _Err("unknown vector")

    def primes(self) -> int:
        n = 0
        while True:
            if self.peek() == "'":
                self.take()
                n += 1
            elif self.peek() == "^" and self.peek(1) == "\\prime":
                self.i += 2
                n += 1
            elif self.peek() == "^" and self.peek(1) == "{" and self.peek(2) == "\\prime":
                self.i += 2
                while self.peek() == "\\prime":
                    self.take()
                    n += 1
                self.expect("}")
            else:
                return n

    def letter(self, tok: str) -> Any:
        env = self.env
        tri = env.triangle
        nxt = self.peek()
        primed = nxt == "'" or nxt == "^" and "\\prime" in (self.peek(1), self.peek(2))
        if tri and nxt not in ("(", "_") and not primed:
            if tok in tri:
                return sympy.acos(tri[tok][1])  # textbook convention: A is the angle at A
            if tok.upper() in tri and tok.islower() and tok not in env.funcs:
                return tri[tok.upper()][0]  # a is the side opposite A
        order = self.primes()
        if tok in env.funcs and self.peek() == "(":
            self.take()
            arg = _scalar(self.expr())
            self.expect(")")
            var, body = env.funcs[tok]
            f = sympy.diff(body, var, order) if order else body
            return f.subs(var, arg)
        if order:
            raise _Err("derivative of an unknown function")
        if tok == "P" and self.peek() == "_" and env.events:
            # Japanese notation P_A(B) = P(B|A)
            self.take()
            given = Parser(self.group_tokens(), env)
            cond = given.event_union()
            if not given.done() or self.peek() != "(":
                raise _Err("conditional probability")
            self.take()
            ev = self.event_union()
            self.expect(")")
            return env.prob(ev & cond) / env.prob(cond)
        if self.peek() == "_" and tok not in ("C", "P", "H"):
            self.take()
            sub_toks = self.group_tokens()
            if tok in env.recurrences:
                return env.term(tok, _int(_scalar(self.sub(sub_toks))))
            if tok in env.seqs:
                var, body = env.seqs[tok]
                k = _scalar(self.sub(sub_toks))
                return body.subs(var, k)
            k = _scalar(self.sub(sub_toks))
            if not k.is_Integer:
                raise _Err("term of an unknown sequence")
            return sym(f"{tok}_{int(k)}")
        if tok == "P" and self.peek() == "(" and env.events:
            return self.probability()
        if tok in ("E", "V") and self.peek() == "(" and env.rvs:
            return self.moment(tok)
        if self.peek() == "(" and tok in env.points:
            raise _Err("point")
        if tok in _FUNC_LETTERS and self.peek() == "(" and tok not in ("x", "y", "k", "s", "u", "w"):
            raise _Err("unknown function")
        if tok.isupper() and tok in env.vectors:
            return env.vectors[tok]  # the random variable inside E(...), V(...)
        if tok == "e" and env.euler:
            return sympy.E
        return sym(tok)

    # -- probability and statistics --------------------------------------------------
    def probability(self) -> sympy.Expr:
        self.expect("(")
        ev = self.event_union()
        cond = None
        if self.peek() in ("|", "\\mid"):
            self.take()
            cond = self.event_union()
        self.expect(")")
        if cond is None:
            return self.env.prob(ev)
        return self.env.prob(ev & cond) / self.env.prob(cond)

    def event_union(self) -> frozenset[int]:
        ev = self.event_inter()
        while self.peek() == "\\cup":
            self.take()
            ev = ev | self.event_inter()
        return ev

    def event_inter(self) -> frozenset[int]:
        ev = self.event_factor()
        while self.peek() == "\\cap":
            self.take()
            ev = ev & self.event_factor()
        return ev

    def event_factor(self) -> frozenset[int]:
        env = self.env
        everything = frozenset(range(len(env.atoms)))
        tok = self.take()
        if tok == "(":
            ev = self.event_union()
            self.expect(")")
        elif tok in ("\\overline", "\\bar"):
            inner = Parser(self.group_tokens(), env)
            ev = everything - inner.event_union()
            if not inner.done():
                raise _Err("event")
        elif tok in env.events:
            ev = env.event_set(tok)
        else:
            raise _Err("event")
        while True:
            if self.peek() == "^" and self.peek(1) in ("C", "c"):
                self.i += 2
                ev = everything - ev
            elif (
                self.peek() == "^"
                and self.peek(1) == "{"
                and self.peek(2) in ("C", "c")
                and self.peek(3) == "}"
            ):
                self.i += 4
                ev = everything - ev
            elif self.peek() == "'":
                self.take()
                ev = everything - ev
            else:
                return ev

    def moment(self, kind: str) -> sympy.Expr:
        self.expect("(")
        depth = 1
        inner: list[str] = []
        while True:
            tok = self.take()
            if tok == "(":
                depth += 1
            elif tok == ")":
                depth -= 1
                if depth == 0:
                    break
            inner.append(tok)
        names = [t for t in inner if t in self.env.rvs]
        if len(set(names)) != 1:
            raise _Err("random variable")
        name = names[0]
        mean, var = self.env.rvs[name]
        X = sympy.Dummy("X")
        sub_env = Env(vectors={name: X})  # the variable parses as a plain symbol
        expr = _scalar(Parser(inner, sub_env).full())
        poly = sympy.Poly(sympy.expand(expr), X)
        if poly.degree() > 2 or poly.free_symbols - {X}:
            raise _Err("moment")
        coeffs = dict(zip(range(poly.degree(), -1, -1), poly.all_coeffs(), strict=True))
        a2, a1, a0 = coeffs.get(2, 0), coeffs.get(1, 0), coeffs.get(0, 0)
        if kind == "E":
            return sympy.expand(a2 * (var + mean**2) + a1 * mean + a0)
        if a2 != 0:
            raise _Err("variance of a square")
        if kind == "V":
            return sympy.expand(a1**2 * var)
        return sympy.Abs(a1) * sympy.sqrt(var)


def parse_expr(tex: str, env: Env | None = None) -> Any:
    """One LaTeX expression (no relation, no prose) -> SymPy value; raises _Err."""
    return Parser(tokenize(prepare(tex)), env or Env()).full()


# ---------------------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------------------

# The expression a problem asks for: "...의 값은?", "...の値を求めよ", "Find the value of ...".
_TARGET_AFTER = re.compile(
    r"^\s*(?:의\s*(?:극한)?값(?!\s*(?:의|이|가))|[을를]\s*(?:계산|간단히|구하)"
    r"|の\s*(?:極限)?値(?!\s*(?:の|が))|を\s*(?:計算|簡単に|求め))"
)
_TARGET_BEFORE = re.compile(
    r"(?:value of|evaluate|compute|calculate|find|what is|simplify)\s*(?:the\s+(?:limit\s+|integral\s+)?)?$",
    re.IGNORECASE,
)
# Prose that is only an instruction ("다음 극한값을 구하시오.", "Evaluate.").
_INSTRUCTION = re.compile(
    r"다음|식|극한값|극한|값|정적분|을|를|의|은|는|구하시오|구하여라|구하라|계산하시오|계산하여라|계산하면|구하면|구해|주세요|줘|풀어|문제"
    r"|次|の|極限値|極限|値|定積分|を|は|求めよ|求めなさい|計算せよ|計算しなさい|式"
    r"|\b(?:evaluate|compute|calculate|find|the|value|of|limit|integral|sum|expression|what|is|please|solve)\b"
    r"|[\s?？。、.:：;,$]",
    re.IGNORECASE,
)
_ARITH_SEQ = re.compile(r"등차수열|等差数列|arithmetic (?:sequence|progression)", re.IGNORECASE)
_GEO_SEQ = re.compile(r"등비수열|等比数列|geometric (?:sequence|progression)", re.IGNORECASE)
_PARTIAL_SUM = re.compile(r"합|和|\bsum\b", re.IGNORECASE)
_BINOMIAL = re.compile(r"이항분포|二項分布|binomial", re.IGNORECASE)
_NORMAL = re.compile(r"정규분포|正規分布|normal distribution|normally", re.IGNORECASE)
_INDEPENDENT = re.compile(
    r"독립(?!\s*시행)(?!이\s*아|적이지)|独立(?!試行)(?!で(?:は)?ない)|(?<!not )independent(?! trials)",
    re.IGNORECASE,
)
_EXCLUSIVE = re.compile(r"배반|排反|mutually exclusive|disjoint", re.IGNORECASE)
_EXCLUSIVE_AB = re.compile(
    r"A\s*(?:와|과)\s*B\s*(?:는|가|은)?\s*서로\s*배반|AとBは(?:互いに)?排反|A and B are mutually exclusive"
)
_POSITIVE_RATIO = re.compile(r"공비가\s*양수|公比が正|common ratio is positive|positive common ratio", re.I)
_POSITIVE_TERMS = re.compile(r"모든\s*항이\s*양수|すべての項が正|all (?:of its )?terms are positive", re.I)
_NUMBER_TEX = r"(-?\s*[\d.]+|-?\s*\\frac\s*\{[^{}]*\}\s*\{[^{}]*\})"
_SEQ_GIVEN = {
    "first": re.compile(r"(?:첫째항|初項|first term)\s*(?:이|가|은|는|が|は|is)?\s*\$?" + _NUMBER_TEX),
    "diff": re.compile(r"(?:공차|公差|common difference)\s*(?:이|가|은|는|が|は|is)?\s*\$?" + _NUMBER_TEX),
    "ratio": re.compile(r"(?:공비|公比|common ratio)\s*(?:이|가|은|는|が|は|is)?\s*\$?" + _NUMBER_TEX),
}
_EXTREME = {
    "max_local": re.compile(r"극댓값|極大値|local maximum value", re.IGNORECASE),
    "min_local": re.compile(r"극솟값|極小値|local minimum value", re.IGNORECASE),
    "max": re.compile(r"(?<!극)최댓값|最大値|(?<!local )maximum value", re.IGNORECASE),
    "min": re.compile(r"(?<!극)최솟값|最小値|(?<!local )minimum value", re.IGNORECASE),
}
_EXTREME_SUM = re.compile(r"(?:값|値|values?)\s*(?:의|の)?\s*(?:합|和)|\bsum of the\b", re.IGNORECASE)
_AREA = re.compile(
    r"둘러싸인\s*(?:부분|도형|영역)의\s*넓이|囲まれた(?:部分|図形)の面積|area of the region", re.I
)
_X_AXIS = re.compile(r"x\s*축|x\s*軸|x-axis", re.IGNORECASE)
_Y_AXIS = re.compile(r"y\s*축|y\s*軸|y-axis", re.IGNORECASE)
_DISTANCE = re.compile(r"움직인\s*거리|動いた道のり|道のり|distance (?:travel+ed|covered)", re.IGNORECASE)
_DISPLACEMENT = re.compile(r"위치의\s*변화량|変位|displacement|change in position", re.IGNORECASE)
_VELOCITY = re.compile(r"속도|速度|velocity", re.IGNORECASE)
_POSITION = re.compile(r"위치|位置|position", re.IGNORECASE)
_SLOPE_AT = re.compile(
    r"미분계수|접선의\s*기울기|微分係数|接線の傾き|derivative (?:of .{1,40} )?at|slope of the tangent",
    re.IGNORECASE,
)
_KANA = re.compile(r"[぀-ヿ]")
_EXPANSION = re.compile(r"전개식|展開式|展開した|expansion", re.IGNORECASE)
_COEFF_AFTER = re.compile(r"^\s*(?:의\s*계수|の\s*係数)")
_COEFF_BEFORE = re.compile(r"coefficient of\s*(?:the\s+)?(?:term\s+)?$", re.IGNORECASE)
_CONSTANT_TERM = re.compile(r"상수항|定数項|constant term", re.IGNORECASE)
_BLOCK = re.compile(r"\\begin|\\cdots|\\ldots|\\dots|\\vdots|\\cases|\\lfloor|\\lceil")


@dataclass
class CsatResult:
    value: sympy.Expr
    env: Env
    how: str  # which reading produced the value ("value", "area", ...): logs and tests


@dataclass
class _Parsed:
    stem: str
    env: Env
    rels: list[tuple[sympy.Expr, str, sympy.Expr]]
    exprs: list[tuple[Segment, Any]]
    curves: list[sympy.Expr]
    verticals: list[sympy.Expr]  # "x = 2" (lines of an area, the point of a derivative)
    times: list[sympy.Expr]  # "t = 3"
    wants_dydx: bool = False  # the problem asks for dy/dx (implicit or parametric curve)


class _Skip(Exception):
    """A template recognised the problem but cannot read it: the whole analysis is None."""


def analyze(stem: str) -> CsatResult | None:
    """SymPy's value for a CSAT computation problem, or None when it is out of scope.

    Runs in a daemon thread with a time limit: SymPy can take very long on odd input."""
    ctx = contextvars.copy_context()
    box: list[CsatResult | None] = []

    def run() -> None:
        try:
            box.append(ctx.run(_analyze, stem))
        except Exception:
            box.append(None)

    worker = threading.Thread(target=run, daemon=True, name="csat-verify")
    worker.start()
    worker.join(TIMEOUT)
    return box[0] if box else None


def _analyze(stem: str) -> CsatResult | None:
    if not stem or len(stem) > 2000 or _BLOCK.search(stem):
        return None
    text = prepare(stem)
    segs = segments(text)
    if not segs:
        return None
    plain = stem.replace("$", "")  # prose regexes: "$x$축" -> "x축" ("$" still separates formulas in text)
    env = _template_env(plain, text)
    if _KANA.search(stem):
        env.log_base = sympy.E
    parsed = _read(segs, env, plain)
    if parsed is None:
        return None
    try:
        templates = (_coefficient, _area, _distance, _extreme, _slope_at, _segment_length, _conic, _counting)
        for template in templates:
            res = template(parsed)
            if res is not None:
                return res
    except _Skip:
        return None
    prose = " ".join(_PROSE.findall(text))
    target = _target(parsed, prose)
    if target is None:
        return None
    value = _solve(parsed, _scalar(target))
    return CsatResult(value, parsed.env, "value") if value is not None else None


def _seq_letter(text: str, exclude: str = "") -> str:
    letters = [c for c in re.findall(r"(?<![A-Za-z\\])([a-z])\s*_", text) if c not in exclude]
    return max(sorted(set(letters)), key=letters.count) if letters else "a"


def _template_env(stem: str, text: str) -> Env:
    """Unknown-constant models the prose announces: arithmetic / geometric sequences, events."""
    env = Env()
    arith, geo = bool(_ARITH_SEQ.search(stem)), bool(_GEO_SEQ.search(stem))
    if arith != geo:
        name = _seq_letter(text, "S")
        n = sympy.Symbol("n", integer=True)
        first = sympy.Dummy("first", real=True, positive=True) if _POSITIVE_TERMS.search(stem) else None
        first = first or sympy.Dummy("first", real=True)
        positive = _POSITIVE_RATIO.search(stem) or _POSITIVE_TERMS.search(stem)
        step = (
            sympy.Dummy("step", real=True, positive=True)
            if geo and positive
            else sympy.Dummy("step", real=True)
        )
        given: dict[str, sympy.Expr] = {}
        for key, rx in _SEQ_GIVEN.items():
            m = rx.search(stem)
            if m:
                with contextlib.suppress(_Err):
                    given[key] = _scalar(parse_expr(m.group(1)))
        a1: sympy.Expr = given.get("first", first)
        d: sympy.Expr = given.get("diff" if arith else "ratio", step)
        env.seqs[name] = (n, a1 + (n - 1) * d if arith else a1 * d ** (n - 1))
        if _PARTIAL_SUM.search(stem) and re.search(r"(?<![A-Za-z\\])S\s*_", text):
            total = n * (2 * a1 + (n - 1) * d) / 2 if arith else a1 * (d**n - 1) / (d - 1)
            env.seqs["S"] = (n, total)
    for name in sorted(set(re.findall(r"(?<![A-Za-z\\])[EV]\s*\(\s*[^()]*?([XYZ])", text))):
        # a random variable given only by its moments ("E(X) = 4, V(X) = 2"); B(n, p) / N(m, s^2) override
        env.rvs[name] = (sympy.Dummy("mean", real=True), sympy.Dummy("variance", nonnegative=True))
    prob_call = r"(?<![A-Za-z\\])P\s*(_\s*\{?\s*[A-Z]\s*\}?)?\s*\(([^()]*)\)"  # P(A), P_A(B)
    if re.search(prob_call, text) and not _BINOMIAL.search(stem) and not _NORMAL.search(stem):
        inside = [sub + " " + arg for sub, arg in re.findall(prob_call, text)]
        names = sorted(
            {c for part in inside for c in re.findall(r"(?<![A-Za-z\\])([A-Z])(?![A-Za-z])", part)}
            - {"C", "X", "Y", "Z"}
        )
        if 1 <= len(names) <= 3:
            env.events = tuple(names)
            env.atoms = tuple(sympy.Dummy(f"p{i}", nonnegative=True) for i in range(2 ** len(names)))
    _vector_model(stem, text, env)
    _triangle_model(stem, env)
    return env


_TRIANGLE = re.compile(
    r"(?:삼각형|三角形|triangle)\s*\$?\s*([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])", re.IGNORECASE
)
_CIRCUMRADIUS = re.compile(r"외접원|外接円|circumcircle|circumradius", re.IGNORECASE)


def _triangle_model(stem: str, env: Env) -> None:
    """Triangle ABC: sides a, b, c and the cosines of A, B, C tied by the three laws of cosines
    (they fix a triangle from any three independent measurements); angles are acos of the
    cosines, sines follow as sqrt(1 - cos^2) (positive inside a triangle)."""
    found = {m.groups() for m in _TRIANGLE.finditer(stem)}
    if len(found) != 1:
        return
    vertices = next(iter(found))
    if len(set(vertices)) != 3:
        return
    for v in vertices:
        env.triangle[v] = (sympy.Dummy(f"side_{v}", positive=True), sympy.Dummy(f"cos_{v}", real=True))
    for v in vertices:
        (side, cos_v), others = env.triangle[v], [env.triangle[o][0] for o in vertices if o != v]
        env.extra_eqs.append(side**2 - (others[0] ** 2 + others[1] ** 2 - 2 * others[0] * others[1] * cos_v))
        env.extra_ineqs += [(cos_v, "<", sympy.Integer(1)), (cos_v, ">", sympy.Integer(-1))]
    if _CIRCUMRADIUS.search(stem) and "R" not in vertices:
        side, cos_v = env.triangle[vertices[0]]
        env.extra_eqs.append(2 * sym("R") * sympy.sqrt(1 - cos_v**2) - side)  # law of sines: a = 2R sin A


_VEC_NAME = r"\\(?:vec|overrightarrow)\s*\{?\s*([a-z])\s*\}?"
_ANGLE = re.compile(
    r"이루는\s*각의\s*크기(?:가|는)\s*(.+?)\s*(?:일\s*때|이고|이다|이므로|,)"
    r"|なす角(?:の大きさ)?\s*(?:が|は)\s*(.+?)\s*(?:のとき|であり|で,|,|、)"
    r"|angle between (?:them|the (?:two )?vectors|\S+ and \S+) is\s*(.+?)(?:,|\.|$| and\b)",
    re.IGNORECASE,
)


def _vector_model(stem: str, text: str, env: Env) -> None:
    """Two plane vectors known only by lengths, angle and dot products: place them as
    a = (p, 0), b = (q cos φ, q sin φ). Every length or dot product built from a and b depends
    only on p, q and φ, so these coordinates lose nothing."""
    names = sorted(set(re.findall(_VEC_NAME, text)))
    defined = re.search(_VEC_NAME + r"\s*=\s*\(", text)
    if not 1 <= len(names) <= 2 or defined or re.search(r"수직|평행|垂直|平行|perpendicular|parallel", stem):
        return
    p = sympy.Dummy("len_a", positive=True)
    env.vectors[names[0]] = sympy.Matrix([p, 0])
    if len(names) == 2:
        q = sympy.Dummy("len_b", positive=True)
        c, s = sympy.Dummy("cos", real=True), sympy.Dummy("sin", real=True)
        env.vectors[names[1]] = sympy.Matrix([q * c, q * s])
        env.extra_eqs.append(c**2 + s**2 - 1)
        m = _ANGLE.search(stem)
        if m:
            try:
                angle = _scalar(parse_expr(next(g for g in m.groups() if g)))
            except _Err:
                return
            env.extra_eqs.append(c - sympy.cos(angle))


def _is_name(toks: list[str], env: Env) -> bool:
    """A mention rather than math: "f", "A", "a_n", "f(x)", "[0, 2]"."""
    if len(toks) == 1 and (_is_letter(toks[0]) or toks[0] in _GREEK):
        return True
    if len(toks) == 3 and _is_letter(toks[0]) and toks[1] == "_" and toks[2] in ("n", "k"):
        return True
    if toks and toks[0] == "[" and toks[-1] == "]" and "," in toks:
        return True  # an interval, read by the templates from the text
    return (
        len(toks) == 4
        and _is_letter(toks[0])
        and toks[1] == "("
        and _is_letter(toks[2])
        and toks[3] == ")"
        and (toks[0] in env.funcs or toks[0] in _FUNC_LETTERS)
    )


def _marked(seg: Segment) -> bool:
    return bool(_TARGET_AFTER.search(seg.after) or _TARGET_BEFORE.search(seg.before))


def _read(segs: list[Segment], env: Env, stem: str) -> _Parsed | None:
    """Definitions first (functions may use earlier ones), then relations and expressions."""
    tokens: list[list[str] | None] = []
    for seg in segs:
        try:
            tokens.append(tokenize(seg.tex))
        except _Err:
            if re.search(r"[0-9\\]", seg.tex):
                return None
            tokens.append(None)
    if any(toks == ["e"] for toks in tokens):
        env.euler = False  # "…을 e라 할 때": e names a quantity here
    used = [False] * len(segs)
    defined: set[str] = set()
    rv_name = "X"
    for _ in range(3):
        progress = False
        for idx, toks in enumerate(tokens):
            if toks is None or used[idx]:
                continue
            if len(toks) == 1 and toks[0] in ("X", "Y", "Z", "W"):
                rv_name = toks[0]
                continue
            try:
                kind = _definition(toks, env, stem, rv_name)
            except _Err:
                kind = None
            except Exception:
                return None
            if kind:
                if kind.startswith("func:"):
                    if kind in defined:
                        return None  # two formulas for one function: piecewise, not modelled
                    defined.add(kind)
                used[idx] = True
                progress = True
        if not progress:
            break
    parsed = _Parsed(stem, env, [], [], [], [], [])
    x, t = sym("x"), sym("t")
    for idx, toks in enumerate(tokens):
        if toks is None or used[idx]:
            continue
        seg = segs[idx]
        if _is_name(toks, env) and not (len(toks) == 1 and _marked(seg)):
            continue
        if toks == ["\\frac", "{", "d", "y", "}", "{", "d", "x", "}"]:
            parsed.wants_dydx = True  # "t = 2일 때 dy/dx의 값": the slope template reads it
            continue
        parts, ops = split_relations(toks)
        try:
            if not ops:
                parsed.exprs.append((seg, Parser(toks, env).full()))
                continue
            if "~" in ops or "!=" in ops:
                continue  # approximations and exclusions only remove solutions: ignoring them is safe
            if any(not p for p in parts):
                return None
            if ops == ["="] and parts[0] == ["y"]:
                parsed.curves.append(_scalar(Parser(parts[1], env).full()))
                continue
            vals = [_scalar(Parser(p, env).full()) for p in parts]
        except _Err:
            return None
        except Exception:
            return None
        if ops == ["="] and vals[0] == x and not vals[1].free_symbols:
            parsed.verticals.append(vals[1])
        if ops == ["="] and vals[0] == t and not vals[1].free_symbols:
            parsed.times.append(vals[1])
        for i, op in enumerate(ops):
            parsed.rels.append((vals[i], op, vals[i + 1]))
    return parsed


def _definition(toks: list[str], env: Env, stem: str, rv_name: str) -> str | None:
    """Registers a definition segment in env; returns its kind or None."""
    parts, ops = split_relations(toks)
    if not ops:
        if len(toks) >= 5 and toks[0] in ("B", "N") and toks[1] == "(" and toks[-1] == ")":
            is_b = toks[0] == "B" and _BINOMIAL.search(stem)
            is_n = toks[0] == "N" and _NORMAL.search(stem)
            if is_b or is_n:
                val = Parser(toks[1:], env).full()
                if not isinstance(val, sympy.MatrixBase) or val.shape != (2, 1):
                    raise _Err("distribution")
                a, b = val[0], val[1]
                env.rvs[rv_name] = (a * b, a * b * (1 - b)) if is_b else (a, b)
                return "rv"
        if (
            len(toks) >= 5
            and _is_letter(toks[0])
            and toks[0].isupper()
            and toks[1] == "("
            and toks[-1] == ")"
            and "," in toks
            and not env.events
        ):
            val = Parser(toks[1:], Env()).full()
            if isinstance(val, sympy.MatrixBase) and not val.free_symbols:
                env.points[toks[0]] = val
                return "point"
        return None
    if ops != ["="] or len(parts) != 2:
        return None
    lhs, rhs = parts
    # f(x) = ...
    if (
        len(lhs) == 4
        and _is_letter(lhs[0])
        and lhs[1] == "("
        and (_is_letter(lhs[2]) or lhs[2] in _GREEK)
        and lhs[3] == ")"
        and lhs[0] not in ("P", "E", "V", "B", "N")
        and lhs[2] in rhs
        and lhs[0] != lhs[2]
    ):
        var = sym(_GREEK.get(lhs[2], lhs[2]))
        body = _scalar(Parser(rhs, env).full())
        env.funcs[lhs[0]] = (var, body)
        return f"func:{lhs[0]}"
    # a_n = ..., S_n = ...
    if len(lhs) in (3, 5) and _is_letter(lhs[0]) and lhs[1] == "_":
        idx = lhs[2] if len(lhs) == 3 else (lhs[3] if lhs[2] == "{" and lhs[4] == "}" else "")
        from_template = lhs[0] in env.seqs and env.seqs[lhs[0]][1].atoms(sympy.Dummy)
        if idx in ("n", "k") and idx in rhs and (lhs[0] not in env.seqs or from_template):
            n = sympy.Symbol("n", integer=True)
            body = _scalar(Parser(rhs, env).full()).subs(sym(idx), n)
            if lhs[0] == "S" and _PARTIAL_SUM.search(stem):
                name = _seq_letter(stem, "S")
                env.seqs["S"] = (n, body)
                env.seqs[name] = (n, _from_partial_sums(body, n))
                return "seq"
            env.seqs[lhs[0]] = (n, body)
            return "seq"
    # a_{n+1} = f(n, a_n), a_{n+2} = f(n, a_n, a_{n+1})
    m = re.fullmatch(r"([a-z]) _ \{ ([nk]) \+ ([12]) \}", " ".join(lhs))
    if m and m.group(1) not in env.seqs and m.group(1) not in env.recurrences:
        name, idx, order = m.group(1), m.group(2), int(m.group(3))
        n = sympy.Symbol("n", integer=True)
        prev = sympy.Function(f"_prev_{name}")
        env.seqs[name] = (n, prev(n))  # a_n, a_{n+1} parse as prev(n), prev(n + 1) for a moment
        try:
            body = _scalar(Parser(rhs, env).full()).subs(sym(idx), n)
        finally:
            del env.seqs[name]
        if not body.has(prev):
            return None
        env.recurrences[name] = (order, n, body, prev)
        return "recurrence"
    # \sum_{k=1}^{n} a_k = g(n)
    if lhs and lhs[0] == "\\sum":
        m = re.fullmatch(
            r"\\sum _ \{ ([a-z]) = 1 \} \^ (?:\{ )?([a-z])(?: \})? ([a-z]) _ (?:\{ )?\1(?: \})?",
            " ".join(lhs),
        )
        if m and m.group(2) in rhs:
            n = sympy.Symbol("n", integer=True)
            total = _scalar(Parser(rhs, env).full()).subs(sym(m.group(2)), n)
            env.seqs[m.group(3)] = (n, _from_partial_sums(total, n))
            return "seq"
    # \vec{a} = (1, 2)
    if len(lhs) >= 2 and lhs[0] in ("\\vec", "\\overrightarrow"):
        p = Parser(lhs[1:], env)
        name = "".join(p.group_tokens())
        if p.done():
            val = Parser(rhs, env).full()
            if isinstance(val, sympy.MatrixBase):
                env.vectors[name] = val
                return "vector"
    return None


def _from_partial_sums(total: sympy.Expr, n: sympy.Symbol) -> sympy.Expr:
    """a_n from S_n: a_1 = S_1, a_n = S_n - S_{n-1} (n >= 2)."""
    return sympy.Piecewise(
        (total.subs(n, 1), sympy.Eq(n, 1)), (sympy.expand(total - total.subs(n, n - 1)), True)
    )


_LIST_BEFORE = re.compile(r"(?:와|과|및|と|および|\band|^\s*[,、])\s*$", re.IGNORECASE)


def _target(parsed: _Parsed, prose: str) -> Any:
    marked_segs = [(seg, val) for seg, val in parsed.exprs if _marked(seg)]
    if any(_LIST_BEFORE.search(seg.before) for seg, _ in marked_segs):
        return None  # "a, b의 값", "a와 b의 값": the answer is a pair
    marked = [val for _, val in marked_segs]
    if marked:
        return marked[-1] if all(_same(marked[-1], v) for v in marked) else None
    if len(parsed.exprs) == 1 and not _INSTRUCTION.sub("", prose).strip():
        return parsed.exprs[0][1]
    return None


def _same(a: Any, b: Any) -> bool:
    try:
        return bool(sympy.simplify(_scalar(a) - _scalar(b)) == 0)
    except Exception:
        return False


def _const(v: Any) -> sympy.Expr | None:
    """A finite real constant (exact), or None."""
    try:
        v = _scalar(v)
        if (
            v.free_symbols
            or not _finite(v)
            or v.has(sympy.Limit, sympy.Integral, sympy.Sum, sympy.Derivative)
        ):
            return None
        c = complex(sympy.N(v, 30))
        if abs(c.imag) > 1e-12 * max(1.0, abs(c.real)):
            return None
        return sympy.nsimplify(v) if v.is_Float else v
    except Exception:
        return None


def _num(v: sympy.Expr) -> float | None:
    try:
        c = complex(sympy.N(v, 30))
    except Exception:
        return None
    return c.real if abs(c.imag) <= 1e-12 * max(1.0, abs(c.real)) else None


def _holds(rel: tuple[sympy.Expr, str, sympy.Expr], sol: dict[Any, Any]) -> bool | None:
    lhs, op, rhs = rel
    a, b = _num(lhs.subs(sol)), _num(rhs.subs(sol))
    if a is None or b is None:
        return None
    eps = 1e-12
    checks = {"<": a < b - eps, "<=": a <= b + eps, ">": a > b + eps, ">=": a >= b - eps}
    return checks.get(op)


def _solve(parsed: _Parsed, target: sympy.Expr) -> sympy.Expr | None:
    """The target's value, unique over every solution of the stated equations."""
    env = parsed.env
    eqs = [sympy.expand(lhs - rhs) for lhs, op, rhs in parsed.rels if op == "="]
    eqs = [e for e in eqs if e != 0]
    ineqs = [r for r in parsed.rels if r[1] != "="] + env.extra_ineqs
    # model constraints (vectors, triangle) that touch the problem's symbols, transitively
    involved = set(target.free_symbols).union(*(q.free_symbols for q in eqs))
    pending = list(env.extra_eqs)
    while True:
        take = [e for e in pending if e.free_symbols & involved]
        if not take:
            break
        for e in take:
            pending.remove(e)
            eqs.append(e)
            involved |= e.free_symbols
    if env.atoms:
        eqs.append(sympy.Add(*env.atoms) - 1)
        if _EXCLUSIVE.search(parsed.stem):
            if not _EXCLUSIVE_AB.search(parsed.stem) or len(env.events) != 2:
                return None
            eqs.append(env.prob(env.event_set("A") & env.event_set("B")))
        if _INDEPENDENT.search(parsed.stem):
            if len(env.events) != 2:
                return None
            a, b = env.event_set(env.events[0]), env.event_set(env.events[1])
            eqs.append(env.prob(a & b) - env.prob(a) * env.prob(b))
    if any(not e.free_symbols for e in eqs):
        return None  # a contradiction such as 3 = 5: something was misread
    unknowns: set[sympy.Symbol] = set(target.free_symbols)
    for e in eqs:
        unknowns |= e.free_symbols
    if not unknowns:
        return _const(target)
    if not eqs or len(unknowns) > MAX_UNKNOWNS + len(env.atoms) + 2 * len(env.triangle) + 1:
        return None
    sols = _solutions(eqs, sorted(unknowns, key=str), ineqs, env)
    values: list[sympy.Expr] = []
    for sol in sols:
        v = _const(sympy.simplify(target.subs(sol)))
        if v is None:
            return None
        if not any(numbers_equal(v, u) for u in values):
            values.append(v)
    return values[0] if len(values) == 1 else None


def _trig_linear(e: sympy.Expr, u: sympy.Symbol) -> bool:
    """u appears only inside sin/cos/tan of (integer)*u + constant: 2π-periodic in u."""
    if not e.has(u):
        return True
    funcs = [f for f in e.atoms(sympy.Function) if f.has(u)]
    if not funcs or any(f.func not in (sympy.sin, sympy.cos, sympy.tan) for f in funcs):
        return False
    for f in funcs:
        coeff = sympy.expand(f.args[0]).coeff(u)
        if not coeff.is_Integer or sympy.expand(f.args[0] - coeff * u).has(u):
            return False
    dummy = e.subs({f: sympy.Dummy() for f in funcs})
    return not dummy.has(u)


def _solutions(
    eqs: list[sympy.Expr],
    unknowns: list[sympy.Symbol],
    ineqs: list[tuple[sympy.Expr, str, sympy.Expr]],
    env: Env,
) -> list[dict[Any, Any]]:
    if len(unknowns) == 1:
        return _solutions_1d(eqs, unknowns[0], ineqs)
    if any(e.atoms(sympy.sin, sympy.cos, sympy.tan) for e in eqs):
        return []  # sympy.solve returns principal values only: uniqueness could be false
    try:
        raw = sympy.solve(eqs, unknowns, dict=True)
    except Exception:
        return []
    out = []
    for sol in raw:
        if any(v.is_number and _num(v) is None for v in sol.values()):
            continue  # complex
        if env.atoms and any(a in sol and sol[a].is_number and _num(sol[a]) < -1e-12 for a in env.atoms):  # type: ignore[operator]
            continue
        if any(_holds(r, sol) is False for r in ineqs):
            continue
        out.append(sol)
    return out


def _solutions_1d(
    eqs: list[sympy.Expr], u: sympy.Symbol, ineqs: list[tuple[sympy.Expr, str, sympy.Expr]]
) -> list[dict[Any, Any]]:
    cond: sympy.Set | None = None
    for lhs, op, rhs in ineqs:
        if (lhs - rhs).free_symbols == {u}:
            rel = {"<": sympy.Lt, "<=": sympy.Le, ">": sympy.Gt, ">=": sympy.Ge}[op](lhs, rhs)
            try:
                s = sympy.solve_univariate_inequality(rel, u, relational=False)
            except Exception:
                return []
            cond = s if cond is None else sympy.Intersection(cond, s)
    periodic = all(_trig_linear(e, u) for e in eqs) and any(e.atoms(sympy.Function) for e in eqs)
    if cond is not None:
        domain: sympy.Set = cond
    elif periodic:
        domain = sympy.Interval.Ropen(0, 2 * sympy.pi)
    else:
        domain = sympy.S.Reals
    result: sympy.Set = domain
    for e in eqs:
        try:
            result = sympy.Intersection(result, sympy.solveset(e, u, domain))
        except Exception:
            return []
    if not isinstance(result, sympy.FiniteSet) and not periodic:
        result = _solve_fallback(eqs, u, domain)  # log equations: solveset returns a ConditionSet
    if not isinstance(result, sympy.FiniteSet) or not 0 < len(result) <= 8:
        return []
    return [{u: v} for v in result]


def _solve_fallback(eqs: list[sympy.Expr], u: sympy.Symbol, domain: sympy.Set) -> sympy.Set:
    """sympy.solve candidates that really satisfy every equation with real values (log domains)."""
    try:
        cands = sympy.solve(eqs[0], u)
    except Exception:
        return sympy.S.EmptySet
    good = []
    for c in cands:
        cv = _num(c)
        if cv is None or not bool(domain.contains(c)):
            continue
        vals = [_num(e.subs(u, c)) for e in eqs]
        if all(v is not None and abs(v) < 1e-9 for v in vals):
            good.append(c)
    return sympy.FiniteSet(*good) if good else sympy.S.EmptySet


# ---------------------------------------------------------------------------------------
# Templates: extrema, enclosed area, distance travelled, derivative at a point
# ---------------------------------------------------------------------------------------


def _single_function(parsed: _Parsed) -> tuple[str, sympy.Symbol, sympy.Expr] | None:
    """The one explicitly given function (no unknown constants)."""
    funcs = parsed.env.funcs
    if len(funcs) == 1:
        name, (var, body) = next(iter(funcs.items()))
        if body.free_symbols <= {var}:
            return name, var, body
        return None
    if not funcs and len(parsed.curves) == 1 and parsed.curves[0].free_symbols <= {sym("x")}:
        return "y", sym("x"), parsed.curves[0]
    return None


# "넓이를 S라 할 때", "面積を S とする", "let S be the area": the prose names the template's value.
_NAMED = re.compile(
    r"(?:넓이|거리|극댓값|극솟값|최댓값|최솟값|계수|상수항|미분계수|기울기|길이)\s*(?:을|를)\s*\$?\s*([A-Za-z])\s*\$?\s*(?:이)?라"
    r"|(?:面積|道のり|極大値|極小値|最大値|最小値|係数|定数項|微分係数|傾き|長さ)\s*を\s*\$?\s*([A-Za-z])\s*\$?\s*と"
    r"|\blet\s+\$?([A-Za-z])\$?\s+be\s+the\s+(?:area|distance|local|maximum|minimum|coefficient|constant|slope|length)",
    re.IGNORECASE,
)


def _template_result(parsed: _Parsed, value: Any, how: str) -> CsatResult:
    """The template's value, or the asked expression that uses it by name ("넓이를 S라 할 때 6S의 값")."""
    const = _const(value)
    if const is None:
        raise _Skip
    marked = [v for seg, v in parsed.exprs if _marked(seg)]
    if not marked:
        return CsatResult(const, parsed.env, how)
    names = {next(g for g in m.groups() if g) for m in _NAMED.finditer(parsed.stem)}
    if len(marked) != 1 or len(names) != 1:
        raise _Skip
    target, name = _scalar(marked[0]), sym(names.pop())
    if target.free_symbols != {name}:
        raise _Skip
    result = _const(target.subs(name, const))
    if result is None:
        raise _Skip
    return CsatResult(result, parsed.env, how)


def _extreme(parsed: _Parsed) -> CsatResult | None:
    stem = parsed.stem
    kinds = [k for k, rx in _EXTREME.items() if rx.search(stem)]
    if not kinds:
        return None
    fn = _single_function(parsed)
    if fn is None or parsed.rels and not _interval_rels_only(parsed):
        raise _Skip
    _, var, body = fn
    if len(kinds) == 2 and not _EXTREME_SUM.search(stem) or len(kinds) > 2:
        raise _Skip
    d1 = sympy.diff(body, var)
    crit = sympy.solveset(d1, var, sympy.S.Reals)
    if not isinstance(crit, sympy.FiniteSet):
        raise _Skip
    found: list[sympy.Expr] = []
    for kind in kinds:
        if kind in ("max_local", "min_local"):
            vals = []
            for c in crit:
                eps = sympy.Rational(1, 10**6)
                left, right = _num(d1.subs(var, c - eps)), _num(d1.subs(var, c + eps))
                if left is None or right is None:
                    raise _Skip
                if kind == "max_local" and left > 0 > right or kind == "min_local" and left < 0 < right:
                    vals.append(sympy.simplify(body.subs(var, c)))
            if len(vals) != 1:
                raise _Skip
            found.append(vals[0])
        else:
            interval = _interval(parsed, var)
            if interval is None:
                raise _Skip
            lo, hi = interval
            pts = [lo, hi] + [c for c in crit if lo <= c <= hi]
            vals = [sympy.simplify(body.subs(var, p)) for p in pts]
            nums = [_num(v) for v in vals]
            if any(n is None for n in nums):
                raise _Skip
            pick = max if kind == "max" else min
            found.append(vals[nums.index(pick(nums))])  # type: ignore[type-var]
    return _template_result(parsed, sympy.simplify(sympy.Add(*found)), "extreme")


def _interval_rels_only(parsed: _Parsed) -> bool:
    return all(op in ("<=", "<") for _, op, _ in parsed.rels)


def _interval(parsed: _Parsed, var: sympy.Symbol) -> tuple[sympy.Expr, sympy.Expr] | None:
    m = re.search(r"\[\s*([^\[\],]+?)\s*,\s*([^\[\],]+?)\s*\]", prepare(parsed.stem))
    if m:
        try:
            lo, hi = _scalar(parse_expr(m.group(1))), _scalar(parse_expr(m.group(2)))
        except _Err:
            return None
        return (lo, hi) if lo.is_number and hi.is_number and lo < hi else None
    lows = [r[0] for r in parsed.rels if r[1] == "<=" and r[2] == var and r[0].is_number]
    highs = [r[2] for r in parsed.rels if r[1] == "<=" and r[0] == var and r[2].is_number]
    if len(lows) == 1 and len(highs) == 1 and lows[0] < highs[0]:
        return lows[0], highs[0]
    return None


def _area(parsed: _Parsed) -> CsatResult | None:
    if not _AREA.search(parsed.stem):
        return None
    x = sym("x")
    if parsed.env.funcs and not parsed.curves:
        raise _Skip
    curves: list[sympy.Expr] = []
    for c in parsed.curves:
        if not any(_same(c, d) for d in curves):
            curves.append(c)
    if _X_AXIS.search(parsed.stem):
        curves.append(sympy.Integer(0))
    verticals = list(parsed.verticals) + ([sympy.Integer(0)] if _Y_AXIS.search(parsed.stem) else [])
    if len(curves) != 2 or any(c.free_symbols - {x} for c in curves):
        raise _Skip
    diff = sympy.expand(curves[0] - curves[1])
    if len(verticals) == 2:
        lo, hi = sorted(verticals, key=lambda v: float(v))
    else:
        roots = sympy.solveset(diff, x, sympy.S.Reals)
        if not isinstance(roots, sympy.FiniteSet):
            raise _Skip
        pts = sorted(roots, key=lambda v: float(v))
        if not verticals and len(pts) >= 2:
            lo, hi = pts[0], pts[-1]  # between the outermost intersections
        elif len(verticals) == 1 and len(pts) == 1 and not numbers_equal(pts[0], verticals[0]):
            lo, hi = sorted([pts[0], verticals[0]], key=lambda v: float(v))  # y = ln x, x-axis, x = e
        else:
            raise _Skip
    try:
        value = _integrate(sympy.Abs(diff), x, lo, hi)
    except _Err as exc:
        raise _Skip from exc
    return _template_result(parsed, value, "area")


def _distance(parsed: _Parsed) -> CsatResult | None:
    stem = parsed.stem
    moved, disp = bool(_DISTANCE.search(stem)), bool(_DISPLACEMENT.search(stem))
    if not (moved or disp):
        return None
    fn = _single_function(parsed)
    if fn is None or len(parsed.times) != 2 or moved == disp:
        raise _Skip
    name, var, body = fn
    if name == "v" or (_VELOCITY.search(stem) and name != "x"):
        velocity = body
    elif name == "x" or (_POSITION.search(stem) and name != "v"):
        velocity = sympy.diff(body, var)
    else:
        raise _Skip
    lo, hi = sorted(parsed.times, key=lambda v: float(v))
    try:
        value = _integrate(sympy.Abs(velocity) if moved else velocity, var, lo, hi)
    except _Err as exc:
        raise _Skip from exc
    return _template_result(parsed, value, "distance")


def _coefficient(parsed: _Parsed) -> CsatResult | None:
    """Coefficient of x^k (or the constant term) in the expansion of (...)^n."""
    stem = parsed.stem
    if not _EXPANSION.search(stem):
        return None
    const = bool(_CONSTANT_TERM.search(stem))
    monos = [
        v for seg, v in parsed.exprs if _COEFF_AFTER.search(seg.after) or _COEFF_BEFORE.search(seg.before)
    ]
    bases = [
        v
        for seg, v in parsed.exprs
        if not (_COEFF_AFTER.search(seg.after) or _COEFF_BEFORE.search(seg.before) or _marked(seg))
        and not isinstance(v, sympy.MatrixBase)
        and _scalar(v).free_symbols
    ]
    wanted_ok = not monos if const else len(monos) == 1
    if len(bases) != 1 or parsed.rels or not wanted_ok:
        raise _Skip
    expanded = sympy.expand(_scalar(bases[0]))
    mono = sympy.Integer(1) if const else _scalar(monos[0])
    coeff, rest = mono.as_coeff_Mul()
    if coeff != 1 or rest.free_symbols - expanded.free_symbols or sympy.count_ops(expanded) > 400:
        raise _Skip
    terms = expanded.as_coefficients_dict()
    return _template_result(parsed, terms.get(rest, sympy.Integer(0)), "coefficient")


def _slope_at(parsed: _Parsed) -> CsatResult | None:
    """dy/dx at a point: y = f(x), a parametric curve (x(t), y(t)) or an implicit curve F(x, y) = 0."""
    if not (_SLOPE_AT.search(parsed.stem) or parsed.wants_dydx):
        return None
    x, y, t = sym("x"), sym("y"), sym("t")
    points = [v for _, v in parsed.exprs if isinstance(v, sympy.MatrixBase) and v.shape == (2, 1)]
    x_of_t = [r[2] for r in parsed.rels if r[1] == "=" and r[0] == x and r[2].free_symbols == {t}]
    y_of_t = [c for c in parsed.curves if c.free_symbols == {t}]
    fn = _single_function(parsed)
    if x_of_t or y_of_t:
        # x = f(t), y = g(t), "t = 2일 때": dy/dx = g'(t) / f'(t)
        if len(x_of_t) != 1 or len(y_of_t) != 1 or len(parsed.times) != 1 or len(parsed.rels) != 2 or points:
            raise _Skip
        at = parsed.times[0]
        dx = sympy.diff(x_of_t[0], t).subs(t, at)
        if dx == 0:
            raise _Skip
        value = sympy.diff(y_of_t[0], t).subs(t, at) / dx
    elif fn is not None:
        if len(parsed.verticals) + len(points) != 1 or len(parsed.rels) != len(parsed.verticals):
            raise _Skip
        _, var, body = fn
        at = parsed.verticals[0] if parsed.verticals else points[0][0]
        if points and not numbers_equal(body.subs(var, at), points[0][1]):
            raise _Skip  # the point is not on the curve: misread
        value = sympy.diff(body, var).subs(var, at)
    else:
        # implicit curve "x^2 + xy + y^2 = 7 위의 점 (1, 2)": dy/dx = -F_x / F_y
        implicit = [
            lhs - rhs for lhs, op, rhs in parsed.rels if op == "=" and (lhs - rhs).free_symbols == {x, y}
        ]
        if len(implicit) != 1 or len(parsed.rels) != 1 or len(points) != 1 or parsed.curves:
            raise _Skip
        at_pt = {x: points[0][0], y: points[0][1]}
        curve = implicit[0]
        fy = sympy.diff(curve, y).subs(at_pt)
        if not numbers_equal(curve.subs(at_pt), sympy.Integer(0)) or fy == 0:
            raise _Skip
        value = -sympy.diff(curve, x).subs(at_pt) / fy
    return _template_result(parsed, value, "slope")


_CONIC_ASKS = {
    "foci": re.compile(
        r"초점\s*사이의\s*거리|焦点間の距離|2つの焦点の間の距離|distance between the (?:two )?foci",
        re.I,
    ),
    "major": re.compile(r"장축의\s*길이|長軸の長さ|length of the major axis", re.I),
    "minor": re.compile(r"단축의\s*길이|短軸の長さ|length of the minor axis", re.I),
    "transverse": re.compile(r"주축의\s*길이|主軸の長さ|length of the transverse axis", re.I),
    "asymptote": re.compile(
        r"점근선.{0,30}기울기가\s*양수|漸近線.{0,30}傾きが正|asymptote with (?:a )?positive slope", re.I
    ),
    "focus_x": re.compile(r"초점의\s*x\s*좌표|焦点の\s*x\s*座標|x-coordinate of the focus", re.I),
}


def _conic(parsed: _Parsed) -> CsatResult | None:
    """Foci distance, axis lengths, asymptote slope and parabola focus of a conic in standard form."""
    asks = [k for k, rx in _CONIC_ASKS.items() if rx.search(parsed.stem)]
    if not asks:
        return None
    x, y = sym("x"), sym("y")
    conics = [
        sympy.expand(lhs - rhs)
        for lhs, op, rhs in parsed.rels
        if op == "=" and (lhs - rhs).free_symbols == {x, y}
    ]
    if len(asks) != 1 or len(conics) != 1 or len(parsed.rels) != 1:
        raise _Skip
    try:
        poly = sympy.Poly(conics[0], x, y)
    except sympy.PolynomialError as exc:
        raise _Skip from exc
    coeff = {m: poly.coeff_monomial(m) for m in (x**2, y**2, x * y, x, y, 1)}
    ask = asks[0]
    if ask == "focus_x":
        # y^2 = 4px: y^2 - 4px = 0
        if coeff[x**2] or coeff[x * y] or coeff[y] or coeff[1] or not coeff[y**2] or not coeff[x]:
            raise _Skip
        return _template_result(parsed, -coeff[x] / coeff[y**2] / 4, "conic")
    if coeff[x * y] or coeff[x] or coeff[y] or not coeff[x**2] or not coeff[y**2] or not coeff[1]:
        raise _Skip  # only centred conics A x^2 + B y^2 = C
    a_coef, b_coef, c = coeff[x**2], coeff[y**2], -coeff[1]
    if a_coef * b_coef > 0 and c * a_coef > 0:  # ellipse
        p2, q2 = c / a_coef, c / b_coef  # semi-axes squared along x and y
        values = {
            "foci": 2 * sympy.sqrt(abs(p2 - q2)),
            "major": 2 * sympy.sqrt(sympy.Max(p2, q2)),
            "minor": 2 * sympy.sqrt(sympy.Min(p2, q2)),
        }
    elif a_coef * b_coef < 0:  # hyperbola
        p2, q2 = abs(c / a_coef), abs(c / b_coef)
        values = {
            "foci": 2 * sympy.sqrt(p2 + q2),
            "transverse": 2 * sympy.sqrt(p2 if c * a_coef > 0 else q2),
            "asymptote": sympy.sqrt(-a_coef / b_coef),
        }
    else:
        raise _Skip
    if ask not in values:
        raise _Skip
    return _template_result(parsed, values[ask], "conic")


_COUNT_INTEGERS = re.compile(
    r"(정수|자연수)\s*([a-z])\s*의\s*개수|(整数|自然数)\s*([a-z])\s*の個数"
    r"|number of (integers|natural numbers|positive integers)\s*([a-z])",
    re.IGNORECASE,
)
_ROOTS = re.compile(
    r"(?:모든\s*)?(?:서로\s*다른\s*)?(?:실근|해|근|(?:실수\s*)?[a-z]\s*의\s*값)\s*의\s*(합|곱|개수)"
    r"|(?:すべての\s*)?(?:異なる\s*)?(?:実数解|解|(?:実数\s*)?[a-z]\s*の値)\s*の\s*(和|積|個数)"
    r"|\b(sum|product|number) of (?:all )?(?:the )?(?:distinct )?(?:real )?"
    r"(?:solutions|roots|values of [a-z])",
    re.IGNORECASE,
)
# Prose conditions that restrict a solution set: a sum or a count would change without them.
_RESTRICTING = re.compile(
    r"양수|음수|양의|음의|유리수|무리수|이상|이하|초과|미만|보다\s*(?:크|작)|짝수|홀수|소수|배수|약수|열린구간|중근"
    r"|正の|負の|以上|以下|より大きい|より小さい|未満|偶数|奇数|素数|倍数|約数"
    r"|\bpositive\b|\bnegative\b|greater|less than|at least|at most|\beven\b|\bodd\b|prime|multiple",
    re.IGNORECASE,
)


def _solution_set(parsed: _Parsed, u: sympy.Symbol, need_equation: bool) -> sympy.Set:
    """Every real u satisfying the stated relations (and a closed interval named in the prose)."""
    domain: sympy.Set = sympy.S.Reals
    interval = _interval(parsed, u) if re.search(r"구간|区間|interval", parsed.stem) else None
    if interval is not None:
        domain = sympy.Interval(*interval)
    elif re.search(r"구간|区間|interval", parsed.stem):
        raise _Skip
    eqs = [lhs - rhs for lhs, op, rhs in parsed.rels if op == "="]
    if need_equation and not eqs:
        raise _Skip
    for lhs, op, rhs in parsed.rels:
        if op == "=":
            continue
        rel = {"<": sympy.Lt, "<=": sympy.Le, ">": sympy.Gt, ">=": sympy.Ge}[op](lhs, rhs)
        domain = sympy.Intersection(domain, sympy.solve_univariate_inequality(rel, u, relational=False))
    periodic = eqs and all(_trig_linear(e, u) for e in eqs) and any(e.atoms(sympy.Function) for e in eqs)
    if periodic and domain == sympy.S.Reals:
        raise _Skip  # infinitely many solutions unless an interval is given
    result: sympy.Set = domain
    for e in eqs:
        result = sympy.Intersection(result, sympy.solveset(e, u, domain))
    if eqs and not isinstance(result, sympy.FiniteSet):
        result = _solve_fallback(eqs, u, domain) if not periodic else result
    return result


def _counting(parsed: _Parsed) -> CsatResult | None:
    """ "…을 만족시키는 정수 x의 개수", "모든 실근의 합 / 곱 / 개수": one variable, every
    condition written in math."""
    m_int = _COUNT_INTEGERS.search(parsed.stem)
    m_roots = None if m_int else _ROOTS.search(parsed.stem)
    if not (m_int or m_roots):
        return None
    if _RESTRICTING.search(parsed.stem) or not parsed.rels:
        raise _Skip
    free: set[Any] = set()
    for lhs, _, rhs in parsed.rels:
        free |= (lhs - rhs).free_symbols
    if len(free) != 1:
        raise _Skip
    u = free.pop()
    marked = [v for seg, v in parsed.exprs if _marked(seg)]
    if marked:
        raise _Skip
    if m_int:
        groups = [g for g in m_int.groups() if g]
        if sym(groups[1]) != u:
            raise _Skip
        s = _solution_set(parsed, u, need_equation=False)
        if re.search(r"자연수|自然数|natural|positive integer", groups[0], re.I):
            s = sympy.Intersection(s, sympy.Interval(1, sympy.oo))
        lo, hi = s.inf, s.sup
        if not (lo.is_finite and hi.is_finite) or hi - lo > 100000:
            raise _Skip
        count = 0
        for i in range(int(sympy.ceiling(lo)), int(sympy.floor(hi)) + 1):
            inside = s.contains(i)
            if inside not in (sympy.true, sympy.false):
                raise _Skip
            count += inside == sympy.true
        return _template_result(parsed, sympy.Integer(count), "count")
    assert m_roots is not None
    kind = next(g for g in m_roots.groups() if g).lower()
    roots = _solution_set(parsed, u, need_equation=True)
    if not isinstance(roots, sympy.FiniteSet) or not 0 < len(roots) <= 20:
        raise _Skip
    if kind in ("합", "和", "sum"):
        value = sympy.Add(*roots)
    elif kind in ("곱", "積", "product"):
        value = sympy.Mul(*roots)
    else:
        value = sympy.Integer(len(roots))
    return _template_result(parsed, sympy.simplify(value), "roots")


_SEGMENT = re.compile(
    r"선분\s*\$?\s*([A-Z])\s*([A-Z])\s*\$?\s*의\s*길이|線分\s*\$?\s*([A-Z])\s*([A-Z])\s*\$?\s*の長さ"
    r"|length of (?:the )?(?:line )?segment\s*\$?\s*([A-Z])\s*([A-Z])\$?",
    re.IGNORECASE,
)
_BETWEEN = re.compile(r"사이의\s*거리|間の距離|distance between", re.IGNORECASE)


def _segment_length(parsed: _Parsed) -> CsatResult | None:
    """ "선분 AB의 길이" / "두 점 A, B 사이의 거리" for points given by coordinates."""
    pts = parsed.env.points
    m = _SEGMENT.search(parsed.stem)
    if m:
        a, b = [g for g in m.groups() if g]
    elif _BETWEEN.search(parsed.stem) and len(pts) == 2:
        a, b = sorted(pts)
    else:
        return None
    if a not in pts or b not in pts or pts[a].shape != pts[b].shape or parsed.rels:
        raise _Skip
    d = pts[b] - pts[a]
    return _template_result(parsed, sympy.sqrt(d.dot(d)), "length")


# ---------------------------------------------------------------------------------------
# Answers, choices and board lines
# ---------------------------------------------------------------------------------------


def value_of(text: str, env: Env | None = None) -> sympy.Expr | None:
    """The single constant an answer or a choice states ("12", "\\frac{3}{2}", "f'(2) = 12", "e^2 - 1")."""
    env = env or Env()
    try:
        segs = segments(prepare(text))
    except Exception:
        return None
    values: list[sympy.Expr] = []
    for seg in segs:
        try:
            parts, ops = split_relations(tokenize(seg.tex))
            if any(op not in ("=", "~") for op in ops) or not parts[-1]:
                continue
            v = _const(Parser(parts[-1], env).full())
        except Exception:
            continue
        if v is not None:
            values.append(v)
    if not values or any(not numbers_equal(values[0], v) for v in values[1:]):
        return None
    return values[0]


def line_error(env: Env, write: str) -> str | None:
    """Error for a board line whose numeric equalities are false ("2^3 = 6"); None otherwise.

    Only constant = constant pairs are judged; anything with a variable or notation we
    cannot read is skipped."""
    try:
        segs = segments(prepare(write))
    except Exception:
        return None
    for seg in segs:
        try:
            toks = tokenize(seg.tex)
        except _Err:
            continue
        parts, ops = split_relations(toks)
        if not ops or any(op != "=" for op in ops):
            continue
        vals: list[sympy.Expr | None] = []
        for p in parts:
            try:
                vals.append(_const(Parser(p, env).full()) if p else None)
            except Exception:
                vals.append(None)
        for i in range(len(ops)):
            a, b = vals[i], vals[i + 1]
            if a is None or b is None:
                continue
            decimals = [len(d) for d in re.findall(r"\d\.(\d+)", " ".join(parts[i] + parts[i + 1]))]
            tol = 0.5 * 10 ** (-max(decimals)) if decimals else None
            if not numbers_equal(a, b, tol):
                return f"계산이 맞지 않아요 ({sympy.latex(a)} \\neq {sympy.latex(b)})."
    return None


def line_errors(env: Env, write: str) -> str | None:
    """line_error with a time limit (a board line may contain a slow limit or integral)."""
    ctx = contextvars.copy_context()
    box: list[str | None] = []

    def run() -> None:
        try:
            box.append(ctx.run(line_error, env, write))
        except Exception:
            box.append(None)

    worker = threading.Thread(target=run, daemon=True, name="csat-line")
    worker.start()
    worker.join(TIMEOUT / 2)
    return box[0] if box else None
