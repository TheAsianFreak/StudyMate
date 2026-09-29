"""Parsing and comparing final answers ("x = 2 또는 x = 3", "(x, y) = (1, 2)", "x > 3", "14")."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sympy

from studymate.verify.latex import (
    HANGUL,
    exprs_equal,
    numbers_equal,
    parse_math,
    split_relation_chain,
    split_top,
    strip_hangul,
    sym,
    to_plain,
)

_NO_SOLUTION = re.compile(
    r"해가\s*없|해는\s*없|해\s*없음|불능|존재하지\s*않"
    r"|解なし|解はない|解がない|解は存在しない|解が存在しない|解を持たない|解をもたない|不能"
    r"|\bno (?:real )?solutions?\b|\bhas no solutions?\b|\bnone\b",
    re.IGNORECASE,
)
_ALL_REALS = re.compile(
    r"무수히|모든\s*실수|모든\s*수|부정(?!확)|항등식|무한히\s*많"
    r"|すべての(?:実数|数)|全ての(?:実数|数)|無数|不定|恒等式"
    r"|\binfinitely many\b|\ball real numbers\b|\bevery real number\b|\bany real number\b|\ball numbers\b|\bidentity\b",
    re.IGNORECASE,
)
_UNION = re.compile(r"또는|혹은|または|もしくは|\bor\b", re.IGNORECASE)
_TUPLE = re.compile(r"^\(\s*([A-Za-z](?:\s*,\s*[A-Za-z])+)\s*\)\s*=\s*\((.+)\)$")
_JUNK = re.compile(r"[^0-9A-Za-z+\-*/().,<>=!±≈ ;]")


@dataclass
class Answer:
    assignments: dict[sympy.Expr, list[sympy.Expr]] = field(default_factory=dict)
    values: list[sympy.Expr] = field(default_factory=list)
    solution_set: sympy.Set | None = None
    no_solution: bool = False
    all_reals: bool = False
    tol: float | None = None

    @property
    def empty(self) -> bool:
        return not (self.assignments or self.values or self.solution_set is not None) and not (
            self.no_solution or self.all_reals
        )


def _values(text: str) -> list[sympy.Expr] | None:
    text = text.strip(" .")
    if "±" in text:
        head, _, tail = text.partition("±")
        b = parse_math(tail)
        if b is None:
            return None
        if not head.strip():
            return [b, -b]
        a = parse_math(head)
        return None if a is None else [a + b, a - b]
    v = parse_math(text)
    return None if v is None else [v]


def _add(ans: Answer, key: sympy.Expr, vals: list[sympy.Expr]) -> None:
    """Adds values for a variable, skipping repeats ("x = 2, ..., x = 2")."""
    have = ans.assignments.setdefault(key, [])
    for v in vals:
        if not any(numbers_equal(v, h) for h in have):
            have.append(v)


def _decimals(text: str) -> int:
    ds = [len(m) for m in re.findall(r"\d\.(\d+)", text)]
    return max(ds) if ds else 0


def parse_answer(text: str) -> Answer | None:
    """Structured answer, or None when nothing in it could be parsed."""
    try:
        return _parse(text)
    except Exception:
        return None


def _parse(text: str) -> Answer | None:
    ans = Answer()
    if not text or len(text) > 500:
        return None
    ans.no_solution = bool(_NO_SOLUTION.search(text))
    ans.all_reals = bool(_ALL_REALS.search(text))
    union = bool(_UNION.search(text))
    plain = to_plain(text)
    if plain is None:
        return ans if (ans.no_solution or ans.all_reals) else None
    if "≈" in plain:
        ans.tol = 0.5 * 10 ** (-_decimals(plain)) if _decimals(plain) else 0.5
        plain = plain.replace("≈", "=")
    plain = _JUNK.sub(" , ", strip_hangul(plain, " , ")).strip(" ,.;")

    m = _TUPLE.match(plain)
    if m:
        names = [n.strip() for n in m.group(1).split(",")]
        raw_vals = split_top(m.group(2), ",")
        if len(raw_vals) == len(names):
            for n, v in zip(names, raw_vals, strict=True):
                pv = parse_math(v)
                if pv is None:
                    return None
                ans.assignments[sym(n)] = [pv]
            return ans

    last_key: sympy.Expr | None = None
    sets: list[sympy.Set] = []
    for seg in split_top(plain, ",;"):
        seg = seg.strip(" .")
        if not seg:
            continue
        parts, ops = split_relation_chain(seg)
        if not ops:
            vals = _values(seg)
            if vals is None:
                continue
            if last_key is not None:
                _add(ans, last_key, vals)
            else:
                ans.values.extend(vals)
            continue
        if all(op == "=" for op in ops):
            if not parts[0]:  # "= 14"
                vals = _values(parts[-1])
                if vals:
                    ans.values.extend(vals)
                continue
            lhs = parse_math(parts[0])
            rhs_vals = _values(parts[-1])
            if lhs is None or rhs_vals is None:
                # "8 = x" style
                rhs = parse_math(parts[-1])
                lhs_vals = _values(parts[0])
                if isinstance(rhs, sympy.Symbol) and lhs_vals:
                    _add(ans, rhs, lhs_vals)
                    last_key = rhs
                continue
            if not isinstance(lhs, sympy.Symbol) and isinstance(parse_math(parts[-1]), sympy.Symbol):
                key = parse_math(parts[-1])
                assert key is not None
                _add(ans, key, [lhs])
                last_key = key
                continue
            _add(ans, lhs, rhs_vals)
            last_key = lhs
            continue
        if any(op in ("!=",) for op in ops):
            continue
        s = _inequality_set(parts, ops)
        if s is not None:
            sets.append(s)
    if sets:
        result = sets[0]
        for s in sets[1:]:
            result = sympy.Union(result, s) if union else sympy.Intersection(result, s)
        ans.solution_set = result
    if ans.empty:
        return None
    return ans


def _inequality_set(parts: list[str], ops: list[str]) -> sympy.Set | None:
    exprs = [parse_math(p) for p in parts]
    if any(e is None for e in exprs):
        return None
    free: set[sympy.Basic] = set()
    for e in exprs:
        assert e is not None
        free |= e.free_symbols
    if len(free) != 1:
        return None
    x = free.pop()
    result: sympy.Set = sympy.S.Reals
    rel = {"<": sympy.Lt, "<=": sympy.Le, ">": sympy.Gt, ">=": sympy.Ge, "=": sympy.Eq}
    for i, op in enumerate(ops):
        s = sympy.solve_univariate_inequality(rel[op](exprs[i], exprs[i + 1]), x, relational=False)
        result = sympy.Intersection(result, s)
    return result


def sets_equal(a: sympy.Set, b: sympy.Set) -> bool:
    try:
        if a == b:
            return True
        return bool(sympy.Complement(a, b) == sympy.S.EmptySet and sympy.Complement(b, a) == sympy.S.EmptySet)
    except Exception:
        return False


def value_lists_equal(expected: list[sympy.Expr], given: list[sympy.Expr], tol: float | None = None) -> bool:
    """Same multiset of values ignoring order and duplicates."""
    exp_u: list[sympy.Expr] = []
    for v in expected:
        if not any(numbers_equal(v, u) for u in exp_u):
            exp_u.append(v)
    giv_u: list[sympy.Expr] = []
    for v in given:
        if not any(numbers_equal(v, u) for u in giv_u):
            giv_u.append(v)
    if len(exp_u) != len(giv_u):
        return False
    return all(any(_eq(e, g, tol) for g in giv_u) for e in exp_u)


def _eq(a: sympy.Expr, b: sympy.Expr, tol: float | None) -> bool:
    if a.free_symbols or b.free_symbols:
        return exprs_equal(a, b)
    return numbers_equal(a, b, tol)


def normalize_text(text: str) -> str:
    """Loose string form for answers SymPy cannot read (non-math subjects)."""
    t = text.lower()
    t = re.sub(r"\\text\{([^}]*)\}", r"\1", t)
    t = re.sub(r"[\s$\\{}.,!?'\"“”‘’()\[\]。、（）「」]", "", t)
    t = re.sub(r"(입니다|이다|예요|이에요|요|임|다|です|である|だ)$", "", t)
    t = re.sub(r"^(?:the|a|an)(?=[a-z])", "", t) if t.isascii() else t
    return t


# Words that may appear in a math answer ("x = 2 또는 x = 3", "解なし", "x = 2 or x = 3").
_ANSWER_WORDS = re.compile(
    r"또는|혹은|이고|그리고|이며|이므로|입니다|이에요|예요|이다|이요|해가|해는|없다|없음|없습니다|없어요|무수히|많다|많음"
    r"|모든|실수|부정|불능|항등식|존재하지|않|정답|답|은|는|와|과|요|다|중근"
    r"|または|もしくは|かつ|および|解なし|解はない|解がない|解は|解が|解を持たない|解をもたない|存在しない|無数|すべての|全ての"
    r"|実数|不定|恒等式|重解|答え|です|である|のとき|とき|ない|数|は|が|の|と|に"
)
_EN_ANSWER_WORDS = re.compile(
    r"\b(?:or|and|so|the|answer|answers|is|are|solution|solutions|no|real|none|all|numbers?|every|any|infinitely"
    r"|many|identity|double|repeated|roots?|approximately|about|has|is)\b",
    re.IGNORECASE,
)
_EN_PROSE_WORD = re.compile(
    r"(?<![A-Za-z\\])(?!(?:sqrt|root|sin|cos|tan|log|ln|exp|pi|abs|frac|text|times|div|pm|le|ge|neq|infty|alpha|beta"
    r"|gamma|delta|theta|lambda|sigma|omega|phi|mathrm|cdot|left|right|dot|overline)(?![A-Za-z]))[A-Za-z]{3,}"
)


def is_prose(text: str) -> bool:
    """Answer made of words (non-math subjects: "미토콘드리아", "ミトコンドリア", "mitochondria"):
    SymPy must not compare it."""
    plain = re.sub(r"\\text\{([^}]*)\}", r"\1", text)
    rest = _ANSWER_WORDS.sub("", plain)
    if HANGUL.search(rest):
        return True
    return bool(_EN_PROSE_WORD.search(_EN_ANSWER_WORDS.sub("", rest)))


# Multiple-choice answers: "③", "③ 이성계", "3번", "(3)", "3)", "③番", "option 3", "choice 3".
_CIRCLED_DIGITS = {chr(0x2460 + i): i + 1 for i in range(20)} | {chr(0x2776 + i): i + 1 for i in range(10)}
_CHOICE = re.compile(
    r"^\s*(?:[(\[]\s*(\d{1,2})\s*[)\]]|(\d{1,2})\s*(?:번|番|\))|(?:option|choice|no\.)\s*(\d{1,2})\b)",
    re.IGNORECASE,
)


def choice_index(text: str) -> int | None:
    """The option number a multiple-choice answer names, or None."""
    t = re.sub(r"\\text\{([^}]*)\}", r"\1", text or "").strip().strip("$").strip()
    t = re.sub(
        r"^(?:정답|답|正解|答え|the answer is|answer)\s*(?:은|는|は)?\s*[:：]?\s*", "", t, flags=re.IGNORECASE
    )
    if t[:1] in _CIRCLED_DIGITS:
        return _CIRCLED_DIGITS[t[0]]
    m = _CHOICE.match(t)
    return int(next(g for g in m.groups() if g)) if m else None


def choice_indices(text: str) -> list[int]:
    """Every option an answer names, sorted ("②, ③" → [2, 3]). A 5지선다 answer names one."""
    t = re.sub(r"\\text\{([^}]*)\}", r"\1", text or "")
    found = {_CIRCLED_DIGITS[ch] for ch in t if ch in _CIRCLED_DIGITS}
    found |= {int(m.group(1)) for m in re.finditer(r"(?<!\d)(\d{1,2})\s*(?:번|番)", t)}
    return sorted(found)


def answers_equivalent(a: str, b: str, problem_text: str | None = None) -> bool:
    """True when two final answers mean the same thing (choice number, SymPy, then loose text).

    With the problem text, a choice number of a multiple-choice problem ("③") stands for
    that option, so "③" and "12" agree when option ③ is 12."""
    ia, ib = choice_indices(a), choice_indices(b)
    if (len(ia) > 1 or len(ib) > 1) and ia and ib:
        return ia == ib  # "②, ③" is not "②"
    ca, cb = choice_index(a), choice_index(b)
    if ca is not None and cb is not None:
        return ca == cb
    if problem_text and (ca is not None or cb is not None):
        from studymate.verify.csat import split_choices

        _, choices = split_choices(problem_text)
        if ca is not None and 1 <= ca <= len(choices):
            a = choices[ca - 1]
        if cb is not None and 1 <= cb <= len(choices):
            b = choices[cb - 1]
    if normalize_text(a) == normalize_text(b):
        return True
    if is_prose(a) or is_prose(b):
        return False  # "CO₂" would otherwise parse as 2*C*O
    same = _values_equal(a, b)
    if same is not None:
        return same
    pa, pb = parse_answer(a), parse_answer(b)
    if pa is None or pb is None:
        return False
    try:
        return _structured_equal(pa, pb)
    except Exception:
        return False


def _values_equal(a: str, b: str) -> bool | None:
    """High-school notation plain SymPy parsing cannot read ("\\ln 2", "\\log_2 8", "{}_5C_2", "e^2");
    None when neither answer uses it or either is not a single number."""
    from studymate.verify.csat import looks_csat, value_of

    if not (looks_csat(a) or looks_csat(b) or re.search(r"(?<![A-Za-z\\])e(?![A-Za-z])", a + b)):
        return None
    va, vb = value_of(a), value_of(b)
    if va is None or vb is None:
        return None
    return numbers_equal(va, vb)


def _structured_equal(a: Answer, b: Answer) -> bool:
    if a.no_solution != b.no_solution or a.all_reals != b.all_reals:
        return False
    if (a.solution_set is None) != (b.solution_set is None):
        return False
    if (
        a.solution_set is not None
        and b.solution_set is not None
        and not sets_equal(a.solution_set, b.solution_set)
    ):
        return False
    tol = a.tol or b.tol
    a_vals = dict(a.assignments)
    b_vals = dict(b.assignments)
    # a bare value on one side matches a single assignment on the other ("8" vs "x = 8")
    if a.values and not a_vals and len(b_vals) == 1 and not b.values:
        a_vals = {next(iter(b_vals)): list(a.values)}
    elif b.values and not b_vals and len(a_vals) == 1 and not a.values:
        b_vals = {next(iter(a_vals)): list(b.values)}
    elif not value_lists_equal(a.values, b.values, tol):
        return False
    if set(a_vals) != set(b_vals):
        return False
    return all(value_lists_equal(a_vals[k], b_vals[k], tol) for k in a_vals)
