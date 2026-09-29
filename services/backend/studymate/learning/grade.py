"""Answer grading for quiz items.

Rules (in order):
1. Text normalisation: Unicode NFKC (fullwidth -> ASCII), superscripts -> `^`, math
   symbols (−, ×, ÷, √, π, ≤ ...) -> ASCII, a small LaTeX subset -> plain math,
   "정답은"/"답:" prefixes and "입니다"/"이다" endings removed, whitespace/case ignored.
2. Multiple choice: the user's answer is mapped to a choice by an explicit index ("②",
   "2번", "(2)", "2)"), by the choice text or value ("0.5" matches "\\frac{1}{2}"), and
   finally by a bare index ("2", "B"). Correct iff it is the key's choice.
3. O/X answers accept 참/거짓, 맞다/틀리다, true/false, ○/× ...
4. Math: both sides are parsed with SymPy (whitelisted tokens only, never raw eval of
   arbitrary names) and compared numerically/symbolically: "x=8" == "8", "1/2" == "0.5",
   "2(x+1)" == "2x+2", "y=2x+1" == "2x+1=y", "x>3" == "3<x", "x=±2" == "x=2, x=-2"
   (order-free), "(1, 2)" is an ordered pair. Units must agree when both sides have one
   ("8cm" == "8", "8cm" != "8m"). A decimal with >= 2 places that correctly rounds an
   irrational or non-terminating key is accepted ("1.41" for "\\sqrt{2}").
5. Otherwise the normalised strings must match. Parse errors never raise.
"""

from __future__ import annotations

import logging
import random
import re
import unicodedata
import warnings
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from studymate.protocol.backend import QuizItem

log = logging.getLogger(__name__)

_MAX_LEN = 300
_REL_TOL = 1e-9
_MAX_EXPONENT = 1000
_TRIALS = 6

# --- index designators ------------------------------------------------------------

_CIRCLED: dict[str, int] = {}
for _base, _count in ((0x2460, 20), (0x2474, 20), (0x2776, 10), (0x2780, 10), (0x278A, 10)):
    for _i in range(_count):
        _CIRCLED[chr(_base + _i)] = _i + 1

_EXPLICIT_INDEX = re.compile(
    r"[(\[]\s*(\d{1,2})\s*[)\]]|(\d{1,2})\s*(?:번째|번|番目|番)(?:\s*(?:선택지|보기|の選択肢))?|(\d{1,2})\)"
    r"|(?:option|choice|number|no\.)\s*(\d{1,2})\b",
    re.IGNORECASE,
)
_LOOSE_NUMBER = re.compile(r"(\d{1,2})\.?")
_LOOSE_LETTER = re.compile(r"[(\[]?([A-Za-z])[)\].]?")
_CHOICE_LABEL = re.compile(
    r"^(?:[\u2460-\u2473\u2474-\u2487\u2776-\u277f\u2780-\u2789\u278a-\u2793]|\(?\d{1,2}[.)]|\(?[A-Ea-e][.)])\s*"
)

# --- normalisation ------------------------------------------------------------------

_PREFIX = re.compile(
    r"^(?:(?:정답|답)\s*(?:은|는|이)?\s*[:：=]\s*|(?:정답|답)\s*(?:은|는)\s+|정답\s+"
    r"|(?:正解|答え|答)\s*(?:は)?\s*[:：=]?\s*"
    r"|(?:the\s+)?(?:answer|ans)\s*(?:is\s+|[:=]\s*))",
    re.IGNORECASE,
)
_SUFFIX = re.compile(r"\s*(?:입니다|이에요|예요|이다|です|である|だ)?\s*[.。!！]*$")
_REMARK = re.compile(r"[(（][^()（）]*[가-힣぀-ヿ一-鿿][^()（）]*[)）]")  # "(중근)", "（重解）"
_SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
_SUPERSCRIPT_RUN = re.compile("[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+")
_SUBSCRIPT = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUBSCRIPT_RUN = re.compile("[₀₁₂₃₄₅₆₇₈₉]+")
_SYMBOLS = {
    "\u2044": "/",
    "\u2212": "-",
    "\u2013": "-",
    "\u2014": "-",
    "×": "*",
    "·": "*",
    "∙": "*",
    "⋅": "*",
    "÷": "/",
    "≤": "<=",
    "≦": "<=",
    "≥": ">=",
    "≧": ">=",
    "≠": "!=",
    "√": "sqrt",
    "π": "pi",
    "∞": "oo",
    "∓": "±",  # treated like ± for alternatives
}
_UNIT_CHARS = {"㎡": "m^2", "㎠": "cm^2", "㎤": "cm^3", "㎥": "m^3", "㎢": "km^2", "℃": "°C"}
_LATEX_WORDS = {
    "cdot": "*",
    "times": "*",
    "div": "/",
    "pm": "±",
    "mp": "±",
    "le": "<=",
    "leq": "<=",
    "leqslant": "<=",
    "ge": ">=",
    "geq": ">=",
    "geqslant": ">=",
    "ne": "!=",
    "neq": "!=",
    "lt": "<",
    "gt": ">",
    "pi": "pi",
    "infty": "oo",
    "sin": "sin",
    "cos": "cos",
    "tan": "tan",
    "log": "log",
    "ln": "ln",
    "exp": "exp",
    "therefore": "",
    "circ": "°",
    "degree": "°",
    "%": "%",
}
_LATEX_SPACING = re.compile(r"\\(?:displaystyle|left|right|bigg|Bigg|big|Big|quad|qquad|[,;:! ])")
_LATEX_TEXT = re.compile(r"\\(?:text|mathrm|mathbf|mathit|operatorname|textrm|textbf|mbox)\s*\{([^{}]*)\}")

_OX_TRUE = {
    "o", "○", "◯", "〇", "⭕", "참", "맞다", "맞음", "맞아요", "true", "yes", "correct", "right", "예", "네",
    "正しい", "正", "はい", "まる", "マル",
}  # fmt: skip
_OX_FALSE = {
    "x", "×", "✕", "✗", "❌", "거짓", "틀리다", "틀림", "틀려요", "false", "no", "incorrect", "wrong",
    "아니오", "아니요", "間違い", "まちがい", "誤り", "誤", "いいえ", "ばつ", "バツ",
}  # fmt: skip

_UNIT = re.compile(
    r"^(?P<value>.*?)\s*(?P<unit>km/h|m/s|cm\^\(?[23]\)?|m\^\(?[23]\)?|mm|cm|km|kg|mg|ml|mL|°C|°|%|퍼센트|パーセント"
    r"|개월|시간|번째|마리|kcal|cal|cc|[mgLl]|도|개|명|원|번|배|살|장|권|대|쪽|분|초|일|년|주|회|점|cm"
    r"|か月|時間|番目|ページ|個|人|円|回|本|枚|歳|才|倍|度|分|秒|日|年|週|点|匹|冊|台)$"
)
_ALT_SEPARATOR = re.compile(
    r"\s*(?:,|;|、|\s또는\s|\s혹은\s|\sor\s|\sand\s|\s및\s|\s그리고\s|\s이고\s|\s*または\s*|\s*もしくは\s*|\s*および\s*)\s*"
)
_THOUSANDS = re.compile(r"(?<![\d.,])\d{1,3}(?:,\d{3})+(?![\d,])")
_RELATION = re.compile(r"(<=|>=|!=|=|<|>)")
_LONE_SYMBOL = re.compile(r"[A-Za-z](?:_\d+)?")
_IDENT = re.compile(r"[A-Za-z]+(?:_\d+)?")
_FUNCS = ("sqrt", "sin", "cos", "tan", "log", "ln", "exp", "abs", "pi", "oo")


def _light(text: str) -> str:
    """Whitespace, answer prefixes and polite endings only (keeps ①/② etc.)."""
    text = " ".join(text.split())
    text = _PREFIX.sub("", text)
    return _SUFFIX.sub("", text).strip()


def normalize(text: str) -> str:
    text = _light(text)
    text = _SUPERSCRIPT_RUN.sub(lambda m: "^(" + m.group(0).translate(_SUPERSCRIPT) + ")", text)
    text = _SUBSCRIPT_RUN.sub(lambda m: "_" + m.group(0).translate(_SUBSCRIPT), text)
    for src, dst in _UNIT_CHARS.items():
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKC", text)
    for src, dst in _SYMBOLS.items():
        text = text.replace(src, dst)
    if "\\" in text or "$" in text or "{" in text:
        text = latex_to_plain(text)
    text = text.replace("==", "=").replace("=<", "<=").replace("=>", ">=")
    text = _REMARK.sub("", text)
    return _light(text)


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text).lower().rstrip(".。")


def latex_to_plain(text: str) -> str:
    """Converts the LaTeX subset that shows up in answers into plain math text."""
    text = text.replace("$", "").replace("\\[", "").replace("\\]", "").replace("\\(", "(").replace("\\)", ")")
    text = _LATEX_TEXT.sub(r"\1", text)
    text = re.sub(r"\^\s*\{?\s*\\circ\s*\}?", "°", text)
    text = _LATEX_SPACING.sub(" ", text)
    text = _convert_commands(text)
    text = text.replace("\\{", "(").replace("\\}", ")").replace("{", "(").replace("}", ")")
    return " ".join(text.split())


def _latex_arg(s: str, i: int) -> tuple[str, int]:
    while i < len(s) and s[i] == " ":
        i += 1
    if i >= len(s):
        return "", i
    if s[i] == "{":
        depth = 0
        for j in range(i, len(s)):
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
                if depth == 0:
                    return s[i + 1 : j], j + 1
        return s[i + 1 :], len(s)
    if s[i] == "\\":
        m = re.match(r"\\[A-Za-z]+", s[i:])
        if m:
            return m.group(0), i + len(m.group(0))
    return s[i], i + 1


def _convert_commands(s: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] != "\\":
            out.append(s[i])
            i += 1
            continue
        m = re.match(r"\\([A-Za-z]+|%)", s[i:])
        if not m:
            i += 1
            continue
        word = m.group(1)
        i += len(m.group(0))
        if word in ("frac", "dfrac", "tfrac", "cfrac"):
            num, i = _latex_arg(s, i)
            den, i = _latex_arg(s, i)
            out.append(f"(({_convert_commands(num)})/({_convert_commands(den)}))")
        elif word == "sqrt":
            index = None
            j = i
            while j < len(s) and s[j] == " ":
                j += 1
            if j < len(s) and s[j] == "[":
                end = s.find("]", j)
                if end > j:
                    index, i = s[j + 1 : end], end + 1
            arg, i = _latex_arg(s, i)
            body = _convert_commands(arg)
            out.append(f"sqrt({body})" if index is None else f"(({body})^(1/({_convert_commands(index)})))")
        elif word in _LATEX_WORDS:
            out.append(
                f" {_LATEX_WORDS[word]} "
                if word.isalpha() and _LATEX_WORDS[word].isalpha()
                else _LATEX_WORDS[word]
            )
        else:
            out.append("\\" + word)  # unknown command: leaves the text unparseable on purpose
    return "".join(out)


def _ox(text: str) -> str | None:
    key = compact(_light(unicodedata.normalize("NFKC", text)))
    if key in _OX_TRUE:
        return "O"
    if key in _OX_FALSE:
        return "X"
    return None


# --- SymPy parsing ------------------------------------------------------------------


@lru_cache(maxsize=1)
def _parser() -> tuple[Any, dict[str, Any], dict[str, Any], tuple[Any, ...]]:
    import string

    import sympy
    from sympy.parsing.sympy_parser import (
        convert_xor,
        implicit_application,
        implicit_multiplication,
        parse_expr,
        standard_transformations,
    )

    local: dict[str, Any] = {c: sympy.Symbol(c) for c in string.ascii_letters}
    local.update(
        sqrt=sympy.sqrt,
        sin=sympy.sin,
        cos=sympy.cos,
        tan=sympy.tan,
        log=sympy.log,
        ln=sympy.log,
        exp=sympy.exp,
        abs=sympy.Abs,
        pi=sympy.pi,
        oo=sympy.oo,
    )
    # parse_expr's default namespace ("from sympy import *"); only whitelisted names reach it
    global_dict: dict[str, Any] = {name: getattr(sympy, name) for name in sympy.__all__}
    transformations = (*standard_transformations, implicit_multiplication, implicit_application, convert_xor)
    return parse_expr, local, global_dict, transformations


def _safe_identifiers(text: str) -> str | None:
    """Keeps single-letter symbols and known functions; splits other words into products
    ("ab" -> "a*b", "sinx" -> "sin x"). Returns None for tokens outside the whitelist."""
    if re.search(r"[^0-9A-Za-z_+\-*/^().,\s]", text) or "__" in text:
        return None

    def repl(m: re.Match[str]) -> str:
        word = m.group(0)
        # a trailing space keeps "sqrt2" / "x2" from becoming one Python name
        tail = " " if m.end() < len(text) and text[m.end()].isdigit() else ""
        if word in _FUNCS or _LONE_SYMBOL.fullmatch(word):
            return word + tail
        for fn in sorted(_FUNCS, key=len, reverse=True):
            if word.startswith(fn) and word[len(fn) :].isalpha():
                return f"{fn} " + "*".join(word[len(fn) :]) + tail
        if word.isalpha():
            return "*".join(word) + tail
        return "\x00"

    out = _IDENT.sub(repl, text)
    return None if "\x00" in out or re.search(r"\d_|_(?!\d)", out) else out


@lru_cache(maxsize=512)
def parse_math(text: str) -> Any | None:
    """SymPy expression for plain math text, or None if it is not safely parseable."""
    text = text.strip()
    if not text or len(text) > _MAX_LEN or re.search(r"\d{31,}", text) or text.count("^") > 6:
        return None
    safe = _safe_identifiers(text)
    if safe is None:
        return None
    parse_expr, local, global_dict, transformations = _parser()
    kwargs = {"local_dict": dict(local), "global_dict": global_dict, "transformations": transformations}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # SymPy deprecation noise on malformed input
            if not _bounded(parse_expr(safe, evaluate=False, **kwargs)):
                return None
            expr = parse_expr(safe, **kwargs)
    except Exception:  # SyntaxError, TokenError, TypeError, sympy errors ...
        return None
    import sympy

    if isinstance(expr, sympy.Tuple | sympy.Expr):
        return expr
    if isinstance(expr, tuple):
        return sympy.Tuple(*expr)
    return None


def _bounded(expr: Any) -> bool:
    """Rejects expressions whose exact evaluation would explode (2^(10^10) ...)."""
    import sympy

    if not isinstance(expr, sympy.Basic):
        return isinstance(expr, tuple) and all(_bounded(e) for e in expr)
    for node in sympy.preorder_traversal(expr):
        if isinstance(node, sympy.Pow) and not node.exp.free_symbols:
            try:
                value = complex(node.exp.evalf(15))
            except (TypeError, ValueError):
                return False
            if abs(value) > _MAX_EXPONENT:
                return False
    return True


# --- comparison ---------------------------------------------------------------------


@dataclass
class _Alt:
    parts: list[Any]
    ops: list[str] = field(default_factory=list)
    label: str | None = None
    unit: str | None = None
    raw: str = ""


def _split_unit(text: str) -> tuple[str, str | None]:
    m = _UNIT.match(text)
    if not m or not m.group("value").strip():
        return text, None
    value = m.group("value").strip()
    letters = re.sub(r"sqrt|pi", "", value)
    if re.search(r"[A-Za-z]", letters):  # "3m" is a unit, "3xm" is algebra
        return text, None
    unit = m.group("unit").replace("^(", "^").replace(")", "")
    return value, {"퍼센트": "%", "パーセント": "%", "l": "L", "mL": "ml"}.get(unit, unit)


def _top_level_split(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    buf = ""
    i = 0
    while i < len(text):
        ch = text[i]
        depth += ch in "([{"
        depth -= ch in ")]}"
        if depth == 0:
            m = _ALT_SEPARATOR.match(text, i)
            if m and m.end() > i:
                parts.append(buf)
                buf = ""
                i = m.end()
                continue
        buf += ch
        i += 1
    parts.append(buf)
    return [p.strip() for p in parts if p.strip()]


def _alternatives(text: str) -> list[_Alt] | None:
    text = _THOUSANDS.sub(lambda m: m.group(0).replace(",", ""), text)
    pieces = _top_level_split(text)
    expanded: list[str] = []
    for piece in pieces:
        if piece.count("±") == 1:
            expanded += [piece.replace("±", "+"), piece.replace("±", "-")]
        elif "±" in piece:
            return None
        else:
            expanded.append(piece)
    label: str | None = None
    alts: list[_Alt] = []
    for piece in expanded:
        alt = _parse_alt(piece)
        if alt is None:
            return None
        # "x = 2, 3" -> both values belong to x
        if alt.label:
            label = alt.label
        elif label and len(alt.parts) == 1:
            alt.label = label
        alts.append(alt)
    return alts


def _parse_alt(text: str) -> _Alt | None:
    tokens = _RELATION.split(text)
    sides = [t.strip() for t in tokens[0::2]]
    ops = tokens[1::2]
    if any(not s for s in sides):
        return None
    label = None
    if ops == ["="]:
        lone = [bool(_LONE_SYMBOL.fullmatch(s)) for s in sides]
        if lone[0] != lone[1]:
            label, value = (sides[0], sides[1]) if lone[0] else (sides[1], sides[0])
            sides, ops = [value], []
    if not ops:
        value, unit = _split_unit(sides[0])
        expr = parse_math(value)
        return None if expr is None else _Alt([expr], [], label, unit, value)
    exprs = [parse_math(s) for s in sides]
    if any(e is None for e in exprs):
        return None
    if all(op in (">", ">=") for op in ops):
        exprs.reverse()
        ops = [{">": "<", ">=": "<="}[op] for op in reversed(ops)]
    return _Alt(exprs, ops, None, None, text)


def _numeric(expr: Any, point: dict[Any, Any] | None = None) -> complex | None:
    try:
        value = expr.subs(point) if point else expr
        result = complex(value.evalf(30))
    except Exception:
        return None
    if result != result or abs(result) == float("inf"):  # NaN / inf
        return None
    return result


def _points(symbols: list[Any]) -> list[dict[Any, Any]]:
    import sympy

    rng = random.Random(20260925)
    return [{s: sympy.Float(rng.uniform(0.35, 2.9), 30) for s in symbols} for _ in range(_TRIALS)]


def _close(a: complex, b: complex) -> bool:
    return abs(a - b) <= _REL_TOL * max(1.0, abs(a), abs(b))


def _non_terminating(expr: Any) -> bool:
    """True for values that have no exact finite decimal (1/3, sqrt(2), pi)."""
    if getattr(expr, "is_Rational", False):
        q = int(expr.q)
        for p in (2, 5):
            while q % p == 0:
                q //= p
        return q != 1
    return getattr(expr, "is_rational", None) is False and getattr(expr, "is_real", None) is True


def _exprs_equal(user: Any, key: Any, user_raw: str = "") -> bool:
    import sympy

    if isinstance(user, sympy.Tuple) or isinstance(key, sympy.Tuple):
        return (
            isinstance(user, sympy.Tuple)
            and isinstance(key, sympy.Tuple)
            and len(user) == len(key)
            and all(_exprs_equal(u, k) for u, k in zip(user, key, strict=True))
        )
    try:
        diff = user - key
    except Exception:
        return False
    symbols = sorted(diff.free_symbols | getattr(key, "free_symbols", set()), key=str)
    if not symbols:
        u, k = _numeric(user), _numeric(key)
        if u is None or k is None:
            return False
        if _close(u, k):
            return True
        m = re.fullmatch(r"-?\d*\.(\d{2,})", user_raw.strip())
        if m and _non_terminating(key) and abs(k.imag) < 1e-12:
            places = len(m.group(1))
            return abs(u.real - k.real) <= 0.5 * 10.0**-places + 1e-12
        return False
    checked = 0
    for point in _points(symbols):
        u, k = _numeric(user, point), _numeric(key, point)
        if u is None or k is None:
            continue
        if not _close(u, k):
            return False
        checked += 1
    return checked >= 3


def _proportional(f: Any, g: Any, positive: bool) -> bool:
    """f = c*g for a constant c != 0 (c > 0 when `positive`)."""
    symbols = sorted(getattr(f, "free_symbols", set()) | getattr(g, "free_symbols", set()), key=str)
    ratio: complex | None = None
    checked = 0
    for point in _points(symbols) if symbols else [{}]:
        a, b = _numeric(f, point), _numeric(g, point)
        if a is None or b is None:
            continue
        if abs(a) < 1e-12 and abs(b) < 1e-12:
            continue
        if abs(b) < 1e-12 or abs(a) < 1e-12:
            return False
        r = a / b
        if ratio is None:
            ratio = r
        elif not _close(r, ratio):
            return False
        checked += 1
    if ratio is None or (symbols and checked < 3):
        return False
    return not positive or (abs(ratio.imag) < 1e-12 and ratio.real > 0)


def _as_equation(alt: _Alt) -> _Alt:
    """`x = 2y+1` stored as a labelled value -> the equation form, for equation-vs-equation checks."""
    if alt.label and len(alt.parts) == 1:
        import sympy

        return _Alt([sympy.Symbol(alt.label), alt.parts[0]], ["="], None, alt.unit, alt.raw)
    return alt


def _alts_equal(user: _Alt, key: _Alt) -> bool:
    if user.unit and key.unit and user.unit != key.unit:
        return False
    if len(user.parts) == 1 and len(key.parts) == 1:
        if user.label and key.label and user.label != key.label:
            return False
        return _exprs_equal(user.parts[0], key.parts[0], user.raw)
    if len(user.parts) != len(key.parts):
        user, key = _as_equation(user), _as_equation(key)
    if user.ops != key.ops or len(user.parts) != len(key.parts):
        return False
    if len(user.parts) == 2:
        positive = user.ops[0] not in ("=", "!=")
        return _proportional(user.parts[1] - user.parts[0], key.parts[1] - key.parts[0], positive)
    return all(_exprs_equal(u, k) for u, k in zip(user.parts, key.parts, strict=True))


def _math_equal(user: str, key: str) -> bool | None:
    alts_user, alts_key = _alternatives(user), _alternatives(key)
    if alts_user is None or alts_key is None:
        return None
    if len(alts_user) != len(alts_key):
        return False
    remaining = list(alts_key)
    for alt in alts_user:
        match = next((k for k in remaining if _alts_equal(alt, k)), None)
        if match is None:
            return False
        remaining.remove(match)
    return True


def equivalent(user: str, key: str) -> bool:
    """True if the user's free-form answer means the same as `key`. Never raises."""
    try:
        if len(user) > _MAX_LEN * 2 or len(key) > _MAX_LEN * 2:
            return compact(user) == compact(key)
        u, k = normalize(user), normalize(key)
        if not u or not k:
            return False
        if compact(u) == compact(k):
            return True
        ox_key = _ox(key)
        if ox_key is not None:
            return _ox(user) == ox_key
        result = _math_equal(u, k)
        if result is not None:
            return result
        return compact(_split_unit(u)[0]) == compact(_split_unit(k)[0]) and (
            _split_unit(u)[1] is None or _split_unit(k)[1] is None or _split_unit(u)[1] == _split_unit(k)[1]
        )
    except Exception:  # grading must never take the handler down
        log.exception("grading failed for %r vs %r", user, key)
        return compact(user) == compact(key)


# --- multiple choice ----------------------------------------------------------------


def _strip_label(choice: str) -> str:
    return _CHOICE_LABEL.sub("", choice.strip(), count=1) or choice


def _explicit_index(text: str) -> int | None:
    t = _light(text)
    if t and t[0] in _CIRCLED:
        return _CIRCLED[t[0]]
    t = unicodedata.normalize("NFKC", t)
    m = _EXPLICIT_INDEX.fullmatch(t)
    if m:
        return int(next(g for g in m.groups() if g))
    return None


def _loose_index(text: str) -> int | None:
    t = unicodedata.normalize("NFKC", _light(text))
    if m := _LOOSE_NUMBER.fullmatch(t):
        return int(m.group(1))
    if m := _LOOSE_LETTER.fullmatch(t):
        return ord(m.group(1).upper()) - ord("A") + 1
    return None


def choice_index(text: str, choices: list[str]) -> int | None:
    """0-based choice the text refers to, or None."""
    n = len(choices)
    idx = _explicit_index(text)
    if idx is not None and 1 <= idx <= n:
        return idx - 1
    labels = [_strip_label(c) for c in choices]
    wanted = compact(normalize(text))
    for i, choice in enumerate(labels):
        if wanted and compact(normalize(choice)) == wanted:
            return i
    for i, choice in enumerate(labels):
        if equivalent(text, choice):
            return i
    idx = _loose_index(text)
    if idx is not None and 1 <= idx <= n:
        return idx - 1
    return None


def grade(item: QuizItem, answer: str) -> bool:
    if not answer or not answer.strip():
        return False
    if item.choices:
        key_idx = choice_index(item.answer, item.choices)
        user_idx = choice_index(answer, item.choices)
        if key_idx is not None and user_idx is not None:
            return key_idx == user_idx
        if user_idx is not None:  # key not among the choices (bad item): compare values
            return equivalent(_strip_label(item.choices[user_idx]), item.answer)
    return equivalent(answer, item.answer)


def display_answer(item: QuizItem) -> str:
    """The correct answer for `quiz_graded`: the exact choice string for multiple choice
    (so the UI can highlight it even when the key was stored as an index), else the key."""
    if item.choices:
        idx = choice_index(item.answer, item.choices)
        if idx is not None:
            return item.choices[idx]
    return item.answer
