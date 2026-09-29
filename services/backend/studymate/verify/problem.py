"""Understands a problem statement well enough for SymPy to solve it.

Supported (middle-school scope): linear / fractional / decimal equations, systems of
equations, simple polynomial equations, linear inequalities (also chained and systems),
arithmetic expressions and "simplify" expressions, "x = 2일 때 2x+1의 값" substitutions
and "x = 2가 해일 때 상수 a의 값" parameter problems. High-school / CSAT notation (limits,
integrals, sums, logs, trig, nCr, sequences, probability ...) goes to verify/csat.py and
yields a "value" problem. Multiple-choice problems (① ~ ⑤) keep their choices so an
answer "③" is compared by the value of choice 3. Anything else returns None so the
caller falls back to re-solve agreement instead of reporting a false failure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

import sympy

from studymate.i18n import tr
from studymate.verify import csat
from studymate.verify.latex import (
    HANGUL,
    has_english_words,
    has_relation,
    is_constant,
    numbers_equal,
    parse_math,
    split_relation_chain,
    split_top,
    strip_hangul,
    sym,
    to_plain,
)

Kind = Literal["equation", "inequality", "expression", "simplify", "value"]

# Question types this analyzer does not model; verifying them would produce false failures.
_UNSUPPORTED = re.compile(
    r"개수|자연수|정수|합을|합은|합이|곱을|곱은|최댓값|최솟값|최대|최소|넓이|둘레|부피|나이|속력|몇|확률|좌표"
    r"|기울기|그래프|함수|비율|평균|몫|나머지|약수|배수|소수(?!로)|근삿값|반올림|어림|단위|%|퍼센트|거리|시간"
    r"|個数|自然数|整数|和を|和は|積を|積は|最大|最小|面積|周の長さ|体積|年齢|速さ|いくつ|何個|何人|確率|座標"
    r"|傾き|グラフ|関数|割合|平均|商|余り|約数|倍数|素数|近似値|四捨五入|単位|パーセント|距離|時間"
    r"|\bhow many\b|\bnumber of\b|\bnatural numbers?\b|\bintegers?\b|\bsum\b|\bproduct\b|\bmaxim|\bminim|\barea\b"
    r"|\bperimeter\b|\bvolume\b|\bage\b|\bspeed\b|\bprobability\b|\bcoordinates?\b|\bslope\b|\bgraph\b|\bfunction\b"
    r"|\bratio\b|\baverage\b|\bmean\b|\bquotient\b|\bremainder\b|\bfactors? of\b|\bdivisors?\b|\bmultiples?\b|\bprimes?\b"
    r"|\bapproximat|\bround\b|\bunits?\b|\bpercent\b|\bdistance\b|\btime\b",
    re.IGNORECASE,
)
_CALC_WORDS = re.compile(
    r"계산|간단히|정리|값을\s*구|값은|값이|나타내|전개|구하시오|구하여라|구해"
    r"|計算|簡単に|整理|値を求め|値は|の値|表しなさい|表せ|展開|求めなさい|求めよ"
    r"|\bcalculate\b|\bcompute\b|\bsimplify\b|\bevaluate\b|\bvalue of\b|\bexpand\b|\bwhat is\b|\bfind\b",
    re.IGNORECASE,
)
_ENUM = re.compile(
    r"(?m)^\s*(?:\(\d{1,2}\)|\d{1,2}[.)](?!\d)|(?:문제|問題|問|Problem|Question|Q)\s*\d+\s*[.:)]?)\s*"
)
_CIRCLED = re.compile(r"[①-⑳❶-❿]")
_JUNK = re.compile(r"[^0-9A-Za-z+\-*/().,<>=!±≈ ;]")
_TARGET = re.compile(
    r"([0-9A-Za-z+\-*/()., ]+?)\s*(?:의\s*값|の値)|\bvalue of\s+([0-9A-Za-z+\-*/(). ]+?)(?:\s+(?:when|if|for|given)\b|[?.,]|$)",
    re.IGNORECASE,
)
_SOLVE_FOR = re.compile(
    r"([A-Za-z])\s*에\s*(?:대하여|대해|관하여)\s*(?:풀|푸|정리|나타)|([A-Za-z])\s*について\s*(?:解|整理|表)"
    r"|\bsolve for\s+([A-Za-z])\b",
    re.IGNORECASE,
)
_OPS = {"=", "<", "<=", ">", ">="}
MAX_OPS = 80


@dataclass
class Relation:
    lhs: sympy.Expr
    op: str
    rhs: sympy.Expr

    def as_sympy(self) -> sympy.Basic:
        return {
            "=": sympy.Eq,
            "<": sympy.Lt,
            "<=": sympy.Le,
            ">": sympy.Gt,
            ">=": sympy.Ge,
        }[self.op](self.lhs, self.rhs, evaluate=False)

    @property
    def free_symbols(self) -> set[sympy.Symbol]:
        return set(self.lhs.free_symbols | self.rhs.free_symbols)


@dataclass
class ParsedProblem:
    kind: Kind
    variables: tuple[sympy.Symbol, ...]
    relations: list[Relation] = field(default_factory=list)
    expr: sympy.Expr | None = None
    targets: tuple[sympy.Symbol, ...] = ()
    target_expr: sympy.Expr | None = None
    solutions: list[dict[sympy.Symbol, sympy.Expr]] = field(default_factory=list)
    identity: bool = False
    solution_set: sympy.Set | None = None
    value: sympy.Expr | None = None
    choices: list[str] = field(default_factory=list)  # multiple-choice options ① ~ ⑤, as written
    answer_choice: int | None = None  # 1-based option that holds SymPy's answer
    context: Any = None  # csat.Env: definitions (f(x) = ..., a_n = ...) for reading answers and lines

    @property
    def answer_symbols(self) -> tuple[sympy.Symbol, ...]:
        return self.targets or self.variables


def parse_relations(segment: str) -> list[Relation] | None:
    """'a = b <= c' (plain) -> relations between consecutive parts; None if any part fails."""
    parts, ops = split_relation_chain(segment)
    if not ops or any(op not in _OPS for op in ops):
        return None
    exprs = []
    for part in parts:
        e = parse_math(part.strip(" ."))
        if e is None:
            return None
        exprs.append(e)
    return [Relation(exprs[i], ops[i], exprs[i + 1]) for i in range(len(ops))]


def math_segments(text: str) -> list[str]:
    """Math-only segments of a mixed Korean/LaTeX text, in reading order."""
    text = _CIRCLED.sub(" ; ", text)
    text = _ENUM.sub(" ", text)
    plain = to_plain(text)
    if plain is None:
        return []
    plain = strip_hangul(plain)
    plain = _JUNK.sub(" ; ", plain)
    out: list[str] = []
    for run in split_top(plain, ";"):
        for seg in split_top(run, ","):
            seg = seg.strip(" .")
            if seg and re.search(r"[0-9A-Za-z]", seg):
                out.append(seg)
    return out


def _has_operator(seg: str) -> bool:
    body = seg.lstrip(" +-(")
    return bool(re.search(r"[+\-*/]", body)) or bool(re.search(r"\d\s*\(|\)\s*\(|\d[A-Za-z]", body))


def _targets(
    text: str, variables: tuple[sympy.Symbol, ...]
) -> tuple[tuple[sympy.Symbol, ...], sympy.Expr | None]:
    plain = to_plain(text) or ""
    m = _SOLVE_FOR.search(plain)
    if m:
        s = sym(next(g for g in m.groups() if g))
        return ((s,) if s in variables else ()), None
    for m in _TARGET.finditer(plain):
        capture = next((g for g in m.groups() if g), "").strip(" ,.")
        if not capture:
            continue
        names = [c.strip() for c in capture.split(",")]
        if all(re.fullmatch(r"[A-Za-z]", n) for n in names):
            syms = tuple(sym(n) for n in names)
            if all(s in variables for s in syms):
                return syms, None
            continue
        expr = parse_math(capture)
        if expr is not None and expr.free_symbols and expr.free_symbols <= set(variables):
            if isinstance(expr, sympy.Symbol):
                return (expr,), None
            return (), expr
    return (), None


def _complex(expr: sympy.Expr) -> bool:
    try:
        if sympy.count_ops(expr) > MAX_OPS:
            return True
        for s in expr.free_symbols:
            poly = sympy.Poly(expr, s) if expr.is_polynomial(s) else None
            if poly is not None and poly.degree() > 4:
                return True
    except Exception:
        return True
    return False


def _solve_equations(problem: ParsedProblem) -> ParsedProblem | None:
    eqs = [sympy.expand(r.lhs - r.rhs) for r in problem.relations]
    variables = problem.variables
    if not variables or any(_complex(e) for e in eqs):
        return None
    nonzero = [e for e in eqs if e != 0]
    if not nonzero:
        problem.identity = True
        return problem
    if any(is_constant(e) for e in nonzero):
        problem.solutions = []  # contradiction such as 0 = 5
        return problem
    unknowns = list(variables)
    if problem.targets and len(nonzero) < len(variables):
        unknowns = list(problem.targets)  # "y에 대하여 풀어라": parametric answer
    try:
        sols = sympy.solve(nonzero, unknowns, dict=True)
    except Exception:
        return None
    if len(unknowns) == len(variables):
        for sol in sols:
            if any(v.free_symbols for v in sol.values()) or len(sol) < len(unknowns):
                return None  # underdetermined: infinitely many solutions
    real_sols = [
        {k: sympy.nsimplify(v) if v.is_Float else v for k, v in sol.items()}
        for sol in sols
        if all(v.is_real is not False for v in sol.values())
    ]
    problem.solutions = real_sols
    if len(variables) == 1 and not problem.target_expr:
        x = variables[0]
        problem.solution_set = sympy.FiniteSet(*[s[x] for s in real_sols if x in s])
    return problem


def _solve_inequalities(problem: ParsedProblem) -> ParsedProblem | None:
    if len(problem.variables) != 1:
        return None
    x = problem.variables[0]
    result: sympy.Set = sympy.S.Reals
    try:
        for rel in problem.relations:
            if _complex(rel.lhs - rel.rhs):
                return None
            if rel.op == "=":
                return None
            s = sympy.solve_univariate_inequality(rel.as_sympy(), x, relational=False)
            result = sympy.Intersection(result, s)
    except Exception:
        return None
    problem.solution_set = result
    return problem


def analyze_problem(text: str) -> ParsedProblem | None:
    """ParsedProblem with SymPy's solution, or None when the problem is outside scope."""
    try:
        return _analyze(text)
    except Exception:  # never let odd input crash the caller
        return None


def _analyze(text: str) -> ParsedProblem | None:
    if not text or len(text) > 2000:
        return None
    stem, choices = csat.split_choices(text)
    problem: ParsedProblem | None
    if csat.looks_csat(stem):
        res = csat.analyze(stem)
        if res is None:
            return None
        problem = ParsedProblem("value", (), value=res.value, context=res.env)
    else:
        problem = _analyze_basic(stem)
        if problem is None:
            return None
    problem.choices = choices
    return _consistent(problem, text)


def _consistent(problem: ParsedProblem, text: str) -> ParsedProblem | None:
    """Sanity checks that catch a misread problem before it can fail a correct solution:
    SymPy's answer must be exactly one of the choices, and a CSAT short answer ("[3점]"
    without choices) is an integer from 0 to 999."""
    if problem.choices:
        from studymate.verify.check import check_answer  # check imports this module

        hits = [i for i, c in enumerate(problem.choices, 1) if _choice_matches(problem, c, check_answer)]
        if len(hits) != 1:
            return None
        problem.answer_choice = hits[0]
        return problem
    if csat.has_point_marker(text) and problem.kind in ("value", "expression"):
        v = problem.value
        if v is None or not (v.is_Integer and 0 <= int(v) <= 999):
            return None
    return problem


def _choice_matches(problem: ParsedProblem, choice: str, check: Any) -> bool:
    if problem.kind == "value":
        v = csat.value_of(choice, problem.context)
        return v is not None and problem.value is not None and numbers_equal(problem.value, v)
    try:
        ok, _ = check(problem, choice, use_choices=False)
        return bool(ok)
    except Exception:
        return False


def _analyze_basic(text: str) -> ParsedProblem | None:
    if _UNSUPPORTED.search(text):
        return None
    segments = math_segments(text)
    if not segments:
        return None
    relations: list[Relation] = []
    expressions: list[tuple[str, sympy.Expr]] = []
    for seg in segments:
        if has_relation(seg):
            rels = parse_relations(seg)
            if rels is None:
                return None
            relations.extend(rels)
        else:
            e = parse_math(seg)
            if e is not None and _has_operator(seg):
                expressions.append((seg, e))

    if relations:
        free: set[sympy.Symbol] = set()
        for r in relations:
            free |= r.free_symbols
        variables = tuple(sorted(free, key=lambda s: s.name))
        if not variables:
            return None
        ops = {r.op for r in relations}
        targets, target_expr = _targets(text, variables)
        if ops == {"="}:
            problem = ParsedProblem(
                "equation", variables, relations, targets=targets, target_expr=target_expr
            )
            return _solve_equations(problem)
        if "=" in ops:
            # "x = 2일 때" + inequality, or similar mixes: not modelled
            return None
        problem = ParsedProblem("inequality", variables, relations, targets=targets)
        return _solve_inequalities(problem)

    if not expressions:
        return None
    if (HANGUL.search(text) or has_english_words(to_plain(text) or "")) and not _CALC_WORDS.search(text):
        return None  # probably a word problem that merely contains numbers
    seg, expr = max(expressions, key=lambda p: len(p[0]))
    if _complex(expr):
        return None
    free_vars = tuple(sorted(expr.free_symbols, key=lambda s: s.name))
    if not free_vars:
        return ParsedProblem("expression", (), expr=expr, value=sympy.nsimplify(sympy.simplify(expr)))
    return ParsedProblem("simplify", free_vars, expr=expr, value=sympy.expand(expr))


def format_expected(problem: ParsedProblem) -> str:
    """SymPy's answer as a LaTeX-ish string, used in retry feedback and logs ("③ (12)" for a
    multiple-choice problem)."""
    text = _format_expected(problem)
    if problem.answer_choice is not None:
        mark = chr(0x2460 + problem.answer_choice - 1)
        return f"{mark} ({text})" if text else mark
    return text


def _format_expected(problem: ParsedProblem) -> str:
    ltx = sympy.latex
    if problem.kind in ("expression", "simplify", "value"):
        return ltx(problem.value) if problem.value is not None else ""
    if problem.kind == "inequality":
        if problem.solution_set is None:
            return ""
        x = problem.variables[0]
        if problem.solution_set == sympy.S.EmptySet:
            return tr("해가 없다", "解なし", "no solution")
        if problem.solution_set == sympy.S.Reals:
            return tr("모든 실수", "すべての実数", "all real numbers")
        try:
            rel = problem.solution_set.as_relational(x)
            return str(ltx(rel)).replace("\\wedge", ",")
        except Exception:
            return str(problem.solution_set)
    if problem.identity:
        return tr("해가 무수히 많다", "解は無数にある", "infinitely many solutions")
    if not problem.solutions:
        return tr("해가 없다", "解なし", "no solution")
    union = tr(" 또는 ", " または ", " or ")
    if problem.target_expr is not None:
        vals = [sympy.simplify(problem.target_expr.subs(s)) for s in problem.solutions]
        return union.join(ltx(v) for v in vals)
    syms = problem.answer_symbols
    if len(syms) == 1:
        x = syms[0]
        vals = [s[x] for s in problem.solutions if x in s]
        return union.join(f"{ltx(x)} = {ltx(v)}" for v in vals)
    return union.join(", ".join(f"{ltx(v)} = {ltx(s[v])}" for v in syms if v in s) for s in problem.solutions)


def _denominators(expr: sympy.Expr) -> int:
    lcm = sympy.Integer(1)
    for r in expr.atoms(sympy.Rational):
        lcm = sympy.ilcm(lcm, r.q)
    return int(lcm)


def solution_hint(problem: ParsedProblem) -> str | None:
    """A correct intermediate line derived by SymPy, to steer a retry without quoting wrong lines."""
    try:
        if problem.kind != "equation" or not problem.relations:
            return None

        def ltx(e: sympy.Basic) -> str:
            out = sympy.latex(e).replace("\\left(", "(").replace("\\right)", ")")
            return re.sub(r"(?<=\d) (?=[a-z(])", "", re.sub(r"^- ", "-", out))

        if len(problem.relations) == 1 and len(problem.variables) == 1:
            rel = problem.relations[0]
            x = problem.variables[0]
            diff = sympy.expand(rel.lhs - rel.rhs)
            if not diff.is_polynomial(x):
                return None
            poly = sympy.Poly(diff, x)
            parts = []
            lcm = _denominators(rel.lhs) * 1
            lcm = int(sympy.ilcm(lcm, _denominators(rel.rhs)))
            if lcm > 1:
                lhs, rhs = sympy.expand(lcm * rel.lhs), sympy.expand(lcm * rel.rhs)
                parts.append(
                    tr(
                        f"양변에 {lcm}을(를) 곱하면 {ltx(lhs)} = {ltx(rhs)}",
                        f"両辺に{lcm}をかけると {ltx(lhs)} = {ltx(rhs)}",
                        f"multiplying both sides by {lcm} gives {ltx(lhs)} = {ltx(rhs)}",
                    )
                )
            if poly.degree() == 1:
                a, c = poly.all_coeffs()
                if lcm > 1:
                    a, c = a * lcm, c * lcm
                parts.append(
                    tr(
                        f"{x}항은 좌변, 상수항은 우변으로 이항하면 {ltx(a * x)} = {ltx(-c)}",
                        f"{x}の項を左辺、数の項を右辺に移項すると {ltx(a * x)} = {ltx(-c)}",
                        f"collecting the {x} terms on the left and the constants on the right gives "
                        f"{ltx(a * x)} = {ltx(-c)}",
                    )
                )
            elif poly.degree() == 2:
                factored = sympy.factor(diff)
                if factored != diff:
                    parts.append(
                        tr(
                            f"좌변으로 모아 인수분해하면 {ltx(factored)} = 0",
                            f"左辺にまとめて因数分解すると {ltx(factored)} = 0",
                            f"moving everything to the left and factoring gives {ltx(factored)} = 0",
                        )
                    )
            if not parts:
                return None
            return ", ".join(parts) + tr("이에요.", "です。", ".")
        return None
    except Exception:
        return None
