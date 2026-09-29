"""LaTeX / plain-text math -> SymPy.

Problems, board lines and answers arrive as a mix of LaTeX, Unicode math and Korean text
(from the LLM or OCR). `to_plain` rewrites the math into a Python-like string that
`parse_math` feeds to SymPy's parser with implicit multiplication. Everything here is
defensive: unparseable input yields None, never an exception.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Any

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    rationalize,
    standard_transformations,
)

# Natural-language script inside a problem or answer: Korean (Hangul) and Japanese (kana,
# kanji). Named HANGUL for history; it marks "prose, not math" for every CJK language.
_CJK = r"\uac00-\ud7a3\u3131-\u318e\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f"
HANGUL = re.compile(f"[{_CJK}]")
HANGUL_RUN = re.compile(f"[{_CJK}]+")

# English words in a problem or answer ("Solve", "x = 2 or x = 3", "no solution"). Function
# and Greek-letter names that to_plain produces are kept; so are single letters (variables)
# and two-letter products ("ab") except common short words.
_KEEP_WORDS = (
    "sqrt|root|sin|cos|tan|log|ln|exp|pi|abs|Abs"
    "|alpha|beta|gamma|delta|epsilon|theta|lambda|sigma|omega|phi|psi"
)
_EN_WORD = re.compile(
    rf"(?<![A-Za-z0-9_])(?:(?!(?:{_KEEP_WORDS})(?![A-Za-z]))[A-Za-z]{{3,}}|(?i:is|of|if|in|to|by|an|at|or|as|be|it|so|we|on|no))(?![A-Za-z0-9_])"
)

_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor, rationalize)
_FUNCS = {"sqrt", "root", "Abs", "pi"}
_SAFE_CHARS = re.compile(r"^[0-9A-Za-z+\-*/().,<>=!± ]*$")
_IDENT = re.compile(r"[A-Za-z_]+")
MAX_LEN = 400

# Commands that carry no math meaning on their own.
_DROP_COMMANDS = (
    "displaystyle",
    "textstyle",
    "left",
    "right",
    "big",
    "Big",
    "bigl",
    "bigr",
    "Bigl",
    "Bigr",
    "limits",
    "nolimits",
    "mathord",
    "boxed",
    "circ",
    "degree",
)
_TEXT_COMMANDS = (
    "text",
    "textrm",
    "textbf",
    "textit",
    "mathrm",
    "mathbf",
    "mathit",
    "mbox",
    "operatorname",
    "boxed",
)
_SEPARATORS = (
    "therefore",
    "because",
    "Rightarrow",
    "rightarrow",
    "Longrightarrow",
    "implies",
    "iff",
    "to",
    "Leftrightarrow",
    "Longleftrightarrow",
)
_SUPERSCRIPTS = {"²": "^2", "³": "^3", "¹": "^1", "⁴": "^4", "⁰": "^0"}
_UNICODE = {
    "−": "-",
    "–": "-",
    "—": "-",
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
    "＝": "=",
    "，": ",",
    "：": ":",
    "√": "\\sqrt ",
    "π": "\\pi ",
    "∴": ";",
    "→": ";",
    "⇒": ";",
    "⟹": ";",
    "≈": "≈",
    "≒": "≈",
    "（": "(",
    "）": ")",
    "｛": "{",
    "｝": "}",
    "［": "[",
    "］": "]",
}


def sym(name: str) -> sympy.Symbol:
    """The one Symbol used for a variable name everywhere (real-valued)."""
    return _sym(name)


@lru_cache(maxsize=128)
def _sym(name: str) -> sympy.Symbol:
    return sympy.Symbol(name, real=True)


def _root(x: Any, n: Any) -> Any:
    """n-th root; the real root for an odd n (\\sqrt[3]{-8} = -2 in school math, not a complex root)."""
    if getattr(n, "is_Integer", False) and int(n) % 2 == 1:
        return sympy.real_root(x, n)
    return sympy.root(x, n)


def _local_dict() -> dict[str, Any]:
    names = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    d: dict[str, Any] = {c: sym(c) for c in names}
    d.update(pi=sympy.pi, sqrt=sympy.sqrt, root=_root, Abs=sympy.Abs)
    return d


_LOCALS = _local_dict()


def _read_group(s: str, i: int) -> tuple[str, int] | None:
    """Reads a `{...}` group or a single token starting at s[i]; returns (content, next index)."""
    while i < len(s) and s[i] == " ":
        i += 1
    if i >= len(s):
        return None
    if s[i] == "{":
        depth = 0
        for j in range(i, len(s)):
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
                if depth == 0:
                    return s[i + 1 : j], j + 1
        return None
    if s[i] == "\\":
        m = re.match(r"\\[A-Za-z]+", s[i:])
        if m:
            return m.group(0), i + len(m.group(0))
    return s[i], i + 1


def unwrap_text(s: str) -> str:
    """`\\text{...}` and friends -> their content (Korean kept)."""
    pattern = re.compile(r"\\(" + "|".join(_TEXT_COMMANDS) + r")\s*(?=\{)")
    for _ in range(20):
        m = pattern.search(s)
        if not m:
            break
        group = _read_group(s, m.end())
        if group is None:
            s = s[: m.start()] + s[m.end() :]
            continue
        content, end = group
        s = s[: m.start()] + " " + content + " " + s[end:]
    return s


def _replace_command_with_args(s: str, name: str, nargs: int, fmt: str) -> str | None:
    """Rewrites `\\name{a}{b}` using fmt.format(*args), innermost-safe via repeated passes."""
    token = "\\" + name
    for _ in range(50):
        idx = _find_command(s, token)
        if idx < 0:
            return s
        i = idx + len(token)
        args = []
        for _k in range(nargs):
            group = _read_group(s, i)
            if group is None:
                return None
            args.append(group[0])
            i = group[1]
        s = s[:idx] + fmt.format(*args) + s[i:]
    return s


def _find_command(s: str, token: str) -> int:
    """Index of `token` not followed by another letter (so `\\frac` does not match `\\fracx`)."""
    start = 0
    while True:
        idx = s.find(token, start)
        if idx < 0:
            return -1
        end = idx + len(token)
        if end >= len(s) or not s[end].isalpha():
            return idx
        start = end


def _convert_sqrt(s: str) -> str | None:
    for _ in range(30):
        idx = _find_command(s, "\\sqrt")
        if idx < 0:
            return s
        i = idx + len("\\sqrt")
        while i < len(s) and s[i] == " ":
            i += 1
        index = None
        if i < len(s) and s[i] == "[":
            close = s.find("]", i)
            if close < 0:
                return None
            index = s[i + 1 : close]
            i = close + 1
        group = _read_group(s, i)
        if group is None:
            return None
        arg, end = group
        # `\sqrt 12` style: take the whole number, not only its first digit
        if not s[i:].lstrip().startswith("{"):
            m = re.match(r"\s*(\d+(?:\.\d+)?)", s[i:])
            if m:
                arg, end = m.group(1), i + m.end()
        rep = f"root(({arg}),({index}))" if index else f"sqrt(({arg}))"
        s = s[:idx] + rep + s[end:]
    return s


# An LLM writing "\frac" inside a JSON string without doubling the backslash produces the
# JSON escape \f (form feed) + "rac". Same for \t(imes), \b(egin), \r(ight), \n(eq).
_ESCAPE_REPAIRS = [
    (re.compile("\x0c"), "\\\\f"),
    (re.compile("\x08"), "\\\\b"),
    (re.compile("\r(?=[A-Za-z])"), "\\\\r"),
    (re.compile("\t(?=[A-Za-z])"), "\\\\t"),
    (re.compile("\n(?=(?:eq|e(?![a-z])|ot|abla|u(?![a-z])|ewline|i(?![a-z])|leq|geq|mid))"), "\\\\n"),
]


def repair_escapes(s: str) -> str:
    """Restores LaTeX commands that were swallowed as JSON control-character escapes."""
    for pattern, rep in _ESCAPE_REPAIRS:
        s = pattern.sub(rep, s)
    return s


def normalize_unicode(s: str) -> str:
    for k, v in _SUPERSCRIPTS.items():
        s = s.replace(k, v)
    for k, v in _UNICODE.items():
        s = s.replace(k, v)
    return unicodedata.normalize("NFKC", s)


def to_plain(s: str) -> str | None:
    """LaTeX-ish text -> plain math string (Korean left in place). None when it cannot convert."""
    if not s:
        return ""
    s = normalize_unicode(repair_escapes(s))
    # line breaks and math delimiters separate formulas ("$x+y=5$\n$x-y=1$" is two equations)
    s = s.replace("$", " ; ").replace("\n", " ; ")
    s = s.replace("\\(", " ").replace("\\)", " ").replace("\\[", " ").replace("\\]", " ")
    s = re.sub(r"\\begin\{array\}\s*\{[^{}]*\}", " ; ", s)  # column spec: \begin{array}{cl}
    s = re.sub(r"\\begin\{[a-z*]+\}|\\end\{[a-z*]+\}", ";", s)
    s = s.replace("\\\\", " ; ").replace("&", " ")
    s = unwrap_text(s)
    s = s.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac").replace("\\cfrac", "\\frac")
    s = re.sub(r"\^\s*\{?\s*\\circ\s*\}?|°", "", s)
    s = re.sub(r"\\[,;:! ]", " ", s)
    s = s.replace("~", " ")
    s = re.sub(r"\\(?:le|leq|leqslant)(?![A-Za-z])", "<=", s)
    s = re.sub(r"\\(?:ge|geq|geqslant)(?![A-Za-z])", ">=", s)
    s = re.sub(r"\\(?:neq|ne)(?![A-Za-z])", "!=", s)
    s = re.sub(r"\\lt(?![A-Za-z])", "<", s)
    s = re.sub(r"\\gt(?![A-Za-z])", ">", s)
    s = re.sub(r"\\(?:cdot|times|ast)(?![A-Za-z])", "*", s)
    s = re.sub(r"\\div(?![A-Za-z])", "/", s)
    s = re.sub(r"\\(?:approx|simeq|fallingdotseq)(?![A-Za-z])", "≈", s)
    s = re.sub(r"\\pm(?![A-Za-z])", "±", s)
    s = re.sub(r"\\pi(?![A-Za-z])", " pi ", s)
    s = re.sub(r"\\[lr]vert(?![A-Za-z])|\\mid(?![A-Za-z])", "|", s)
    s = s.replace("\\{", "(").replace("\\}", ")").replace("\\%", "%")
    s = re.sub(r"\\(?:quad|qquad)(?![A-Za-z])", " , ", s)
    s = re.sub(r"\\(?:" + "|".join(_SEPARATORS) + r")(?![A-Za-z])", " ; ", s)
    s = re.sub(r"\\(" + "|".join(_DROP_COMMANDS) + r")(?![A-Za-z])", " ", s)
    frac = _replace_command_with_args(s, "frac", 2, "(({0})/({1}))")
    if frac is None:
        return None
    s = _convert_sqrt(frac)  # type: ignore[assignment]
    if s is None:
        return None
    if re.search(r"\\[A-Za-z]+", s):
        return None  # unknown command
    s = s.replace("{", "(").replace("}", ")").replace("[", "(").replace("]", ")")
    s = _convert_abs(s)
    s = s.replace("^", "**")
    s = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", s)  # thousands separators: 1,000
    return re.sub(r"\s+", " ", s).strip()


def _convert_abs(s: str) -> str:
    for _ in range(10):
        m = re.search(r"\|([^|]+)\|", s)
        if not m:
            break
        s = s[: m.start()] + f"Abs({m.group(1)})" + s[m.end() :]
    return s.replace("|", " ")


def _safe(s: str) -> bool:
    if len(s) > MAX_LEN or not _SAFE_CHARS.match(s):
        return False
    for ident in _IDENT.findall(s):
        if ident in _FUNCS:
            continue
        if "_" in ident or len(ident) > 3:
            return False
    if re.search(r"\d{16,}", s):
        return False
    for m in re.finditer(r"\*\*\s*\(?\s*(\d+)", s):
        if int(m.group(1)) > 60:
            return False
    return s.count("(") == s.count(")")


def parse_math(s: str) -> sympy.Expr | None:
    """Plain math string (output of `to_plain`, no relation) -> SymPy expression."""
    s = s.strip()
    if not s or not _safe(s) or any(op in s for op in ("=", "<", ">", "±", "!")):
        return None
    if len(split_top(s, ",")) > 1:
        return None  # a list, not one expression (commas inside root(a, n) are fine)
    s = re.sub(r"(?<=\d)\s+(?=\d)", "", s)  # "1 000" -> "1000"
    if re.search(r"\d\.(?!\d)", s):
        s = re.sub(r"(\d)\.(?!\d)", r"\1", s)  # trailing period after a number
    try:
        expr = parse_expr(s, local_dict=_LOCALS, transformations=_TRANSFORMS, evaluate=True)
    except Exception:  # SyntaxError, TokenError, TypeError, ... from arbitrary input
        return None
    if not isinstance(expr, sympy.Expr):
        return None
    if expr.has(sympy.zoo, sympy.nan, sympy.oo, -sympy.oo):
        return None
    if any(isinstance(f, sympy.core.function.AppliedUndef) for f in expr.atoms(sympy.Function)):
        return None
    return expr


def strip_hangul(s: str, repl: str = " ; ") -> str:
    """Replaces prose with a separator: Korean/Japanese runs, parenthesised remarks
    ("(\uc911\uadfc)", "\uff08\u91cd\u89e3\uff09", "(double root)") and English words ("Solve", "or")."""
    s = re.sub(rf"\([^()]*[{_CJK}][^()]*\)|\(\s*[A-Za-z]{{3,}}(?:\s+[A-Za-z]+)*\s*\)", repl, s)
    s = HANGUL_RUN.sub(repl, s)
    return _EN_WORD.sub(repl, s)


def has_english_words(s: str) -> bool:
    return bool(_EN_WORD.search(s))


def split_top(s: str, seps: str = ",;") -> list[str]:
    """Splits on separator characters outside parentheses."""
    parts: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch in seps and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


_REL = re.compile(r"(<=|>=|!=|==|=|<|>|≈)")


def split_relation_chain(s: str) -> tuple[list[str], list[str]]:
    """'a = b < c' -> (['a', 'b', 'c'], ['=', '<'])."""
    tokens = _REL.split(s)
    parts = [t.strip() for t in tokens[0::2]]
    ops = ["=" if t == "==" else t for t in tokens[1::2]]
    return parts, ops


def has_relation(s: str) -> bool:
    return bool(_REL.search(s))


def is_constant(expr: sympy.Expr) -> bool:
    return not expr.free_symbols


def numbers_equal(a: sympy.Expr, b: sympy.Expr, tol: float | None = None) -> bool:
    """Exact equality for constants (numeric fallback), with optional tolerance."""
    try:
        diff = a - b
        if tol is not None:
            return abs(complex(sympy.N(diff, 30))) <= tol
        if diff == 0:
            return True
        if diff.free_symbols:
            return exprs_equal(a, b)
        return abs(complex(sympy.N(diff, 30))) < 1e-12
    except Exception:
        return False


def exprs_equal(a: sympy.Expr, b: sympy.Expr) -> bool:
    """Symbolic equality of two expressions (identical as functions)."""
    try:
        diff = sympy.expand(a - b)
        if diff == 0:
            return True
        return bool(sympy.simplify(diff) == 0)
    except Exception:
        return False
