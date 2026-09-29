"""Checks a solution script (board lines + final answer) against SymPy's own solution."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

import sympy

from studymate.verify import csat
from studymate.verify.answer import choice_index, parse_answer, sets_equal, value_lists_equal
from studymate.verify.latex import (
    exprs_equal,
    has_relation,
    numbers_equal,
    parse_math,
    split_relation_chain,
    split_top,
    strip_hangul,
    to_plain,
)
from studymate.verify.problem import ParsedProblem, analyze_problem, format_expected, solution_hint

log = logging.getLogger(__name__)

_JUNK = re.compile(r"[^0-9A-Za-z+\-*/().,<>=!±≈ ;]")
_INEQ = {"<", "<=", ">", ">="}
_REL = {"<": sympy.Lt, "<=": sympy.Le, ">": sympy.Gt, ">=": sympy.Ge}


@dataclass
class VerifyResult:
    verified: bool
    parsed: bool  # SymPy understood the problem
    detail: str  # Korean reason (fed back to the LLM on retry)
    answer_ok: bool | None = None
    expected: str | None = None  # SymPy's answer, LaTeX-ish
    step_errors: list[str] = field(default_factory=list)
    bad_lines: list[int] = field(default_factory=list)  # 1-based indices of wrong board lines
    hint: str | None = None  # SymPy-derived next step for a retry prompt


def _ltx(e: sympy.Basic) -> str:
    try:
        return str(sympy.latex(e))
    except Exception:
        return str(e)


def _approx_tol(text: str) -> float | None:
    if not re.search(r"≈|≒|\\approx|\\fallingdotseq|약\s*\d|約\s*\d|\babout\b|\bapprox", text):
        return None
    ds = [len(m) for m in re.findall(r"\d\.(\d+)", text)]
    return 0.5 * 10 ** (-max(ds)) if ds else 0.5


def check_answer(problem: ParsedProblem, text: str, *, use_choices: bool = True) -> tuple[bool, str]:
    wrong = f"최종 답 '{text}'이(가) 틀렸어요."
    if use_choices and problem.choices:
        idx = choice_index(text)
        if idx is not None:
            # "③" (or "③ 12") on a multiple-choice problem: the option number is the answer
            if not 1 <= idx <= len(problem.choices):
                return False, wrong
            if problem.answer_choice is not None:
                return idx == problem.answer_choice, "" if idx == problem.answer_choice else wrong
            text = problem.choices[idx - 1]
    if problem.kind == "value":
        if problem.value is None:
            return False, wrong
        given = csat.value_of(text, problem.context)
        if given is None:
            return (
                False,
                f"최종 답 '{text}'을(를) 수로 읽을 수 없어요. '12'나 '\\frac{{3}}{{2}}'처럼 써 주세요.",
            )
        ok = numbers_equal(problem.value, given, _approx_tol(text))
        return ok, "" if ok else wrong
    ans = parse_answer(text)
    if ans is None:
        return False, f"최종 답 '{text}'을(를) 수식으로 읽을 수 없어요. 'x = 3'처럼 써 주세요."
    tol = ans.tol

    if problem.kind in ("expression", "simplify"):
        candidates = list(ans.values) + [v for vals in ans.assignments.values() for v in vals]
        if not candidates or problem.value is None:
            return False, wrong
        given = candidates[-1]
        if problem.kind == "expression":
            ok = not given.free_symbols and numbers_equal(problem.value, given, tol)
        else:
            ok = exprs_equal(problem.value, given)
        return ok, "" if ok else wrong

    if problem.kind == "inequality":
        if ans.solution_set is None or problem.solution_set is None:
            return False, f"부등식의 답은 'x > 3'처럼 범위로 써야 해요. ('{text}')"
        ok = sets_equal(problem.solution_set, ans.solution_set)
        return ok, "" if ok else wrong

    # equations
    sols = problem.solutions
    if problem.identity:
        return ans.all_reals, "" if ans.all_reals else wrong
    if not sols:
        return ans.no_solution, "" if ans.no_solution else wrong
    if ans.no_solution or ans.all_reals:
        return False, wrong

    if problem.target_expr is not None:
        expected = [sympy.simplify(problem.target_expr.subs(s)) for s in sols]
        given = list(ans.values)
        for key, vals in ans.assignments.items():
            if exprs_equal(key, problem.target_expr):
                given.extend(vals)
        ok = bool(given) and value_lists_equal(expected, given, tol)
        return ok, "" if ok else wrong

    syms = problem.answer_symbols
    if len(syms) == 1:
        x = syms[0]
        given = list(ans.assignments.get(x, []))
        if not given and not ans.assignments:
            given = list(ans.values)
        expected = [s[x] for s in sols if x in s]
        ok = bool(given) and value_lists_equal(expected, given, tol)
    else:
        if any(len(ans.assignments.get(v, [])) != 1 for v in syms):
            return False, f"모든 미지수의 값을 써 주세요 ({', '.join(v.name for v in syms)}). ('{text}')"
        given_map = {v: ans.assignments[v][0] for v in syms}
        ok = len(sols) == 1 and all(
            v in sols[0] and numbers_equal(sols[0][v], given_map[v], tol) for v in syms
        )
    if ok:
        # values given for other unknowns must be consistent too
        for key, vals in ans.assignments.items():
            other = isinstance(key, sympy.Symbol) and key in problem.variables and key not in syms
            if other and not all(any(key in s and numbers_equal(s[key], v, tol) for s in sols) for v in vals):
                ok = False
    return ok, "" if ok else wrong


def _check_equality(problem: ParsedProblem, a: sympy.Expr, b: sympy.Expr) -> str | None:
    free = a.free_symbols | b.free_symbols
    if not free:
        if numbers_equal(a, b):
            return None
        return f"계산이 맞지 않아요 ({_ltx(a)} \\neq {_ltx(b)})."
    if not free <= set(problem.variables):
        return None  # unknown symbols (substitution variable etc.): cannot judge
    if problem.kind == "simplify":
        return None if exprs_equal(a, b) else "식을 정리한 결과가 원래 식과 같지 않아요."
    if problem.kind != "equation" or problem.identity or not problem.solutions:
        return None
    if exprs_equal(a, b):
        return None  # identity such as an expansion
    diff = a - b
    if len(problem.variables) == 1 and problem.solution_set is not None:
        x = problem.variables[0]
        try:
            step_set = sympy.solveset(diff, x, domain=sympy.S.Reals)
        except Exception:
            return None
        if not isinstance(step_set, sympy.FiniteSet):
            return None if step_set != sympy.S.EmptySet else "이 식은 해가 없어서 원래 식과 맞지 않아요."
        sol_set = problem.solution_set
        if len(step_set) > 0 and (step_set.is_subset(sol_set) or sol_set.is_subset(step_set)):
            return None
        return "원래 식과 해가 달라지는 식이에요."
    for sol in problem.solutions:
        if not free <= set(sol):
            return None
        try:
            if numbers_equal(diff.subs(sol), sympy.Integer(0)):
                return None
        except Exception:
            return None
    return "원래 식의 해를 넣으면 성립하지 않는 식이에요."


def _check_inequality(problem: ParsedProblem, exprs: list[sympy.Expr], ops: list[str]) -> str | None:
    if problem.kind != "inequality" or problem.solution_set is None or len(problem.variables) != 1:
        return None
    x = problem.variables[0]
    free: set[sympy.Basic] = set()
    for e in exprs:
        free |= e.free_symbols
    if free != {x}:
        return None
    try:
        step: sympy.Set = sympy.S.Reals
        for i, op in enumerate(ops):
            rel = _REL[op](exprs[i], exprs[i + 1])
            step = sympy.Intersection(step, sympy.solve_univariate_inequality(rel, x, relational=False))
    except Exception:
        return None
    sol = problem.solution_set
    if len(problem.relations) == 1:
        ok = sets_equal(sol, step)
    else:
        try:
            ok = bool(sol.is_subset(step))
        except Exception:
            return None
    return None if ok else "부등식의 해가 원래 문제와 달라졌어요. 부등호 방향을 확인해 주세요."


def check_write(problem: ParsedProblem, write: str) -> str | None:
    """Error message for one board line, or None when it is fine or not checkable."""
    if problem.kind == "value":
        # CSAT notation: only constant = constant equalities are judged ("\log_2 8 = 3")
        return csat.line_errors(problem.context or csat.Env(), write)
    plain = to_plain(write)
    if plain is None:
        return None
    plain = _JUNK.sub(" ; ", strip_hangul(plain, " ; "))
    for seg in split_top(plain, ",;"):
        seg = seg.strip(" .")
        if not has_relation(seg):
            continue
        parts, ops = split_relation_chain(seg)
        if any(op in ("!=", "≈") for op in ops):
            continue
        if parts and not parts[-1]:
            parts, ops = parts[:-1], ops[:-1]
        exprs: list[sympy.Expr] = []
        if parts and not parts[0]:
            if problem.kind in ("expression", "simplify") and problem.expr is not None:
                exprs.append(problem.expr)
            else:
                ops = ops[1:]
            parts = parts[1:]
        parsed = [parse_math(p) for p in parts]
        if not ops or any(e is None for e in parsed):
            continue
        exprs.extend(e for e in parsed if e is not None)
        if len(exprs) != len(ops) + 1:
            continue
        if all(op == "=" for op in ops):
            for i in range(len(ops)):
                err = _check_equality(problem, exprs[i], exprs[i + 1])
                if err:
                    return err
        elif all(op in _INEQ for op in ops):
            err = _check_inequality(problem, exprs, ops)
            if err:
                return err
    return None


def check_steps(problem: ParsedProblem, writes: Sequence[str | None]) -> list[str]:
    return [msg for _, msg in _step_errors(problem, writes)]


def _step_errors(problem: ParsedProblem, writes: Sequence[str | None]) -> list[tuple[int, str]]:
    errors = []
    for i, w in enumerate(writes, 1):
        if not w or not w.strip():
            continue
        try:
            err = check_write(problem, w)
        except Exception:
            log.debug("step check crashed on %r", w, exc_info=True)
            err = None
        if err:
            errors.append((i, f"{i}번째 줄 '{w}': {err}"))
    return errors


def verify_solution(problem_text: str, writes: Sequence[str | None], final_answer: str) -> VerifyResult:
    """Verifies board lines and the final answer against SymPy. Never raises."""
    try:
        problem = analyze_problem(problem_text)
        if problem is None:
            return VerifyResult(False, False, "SymPy가 이 문제를 해석하지 못했어요.")
        expected = format_expected(problem)
        answer_ok, answer_err = check_answer(problem, final_answer)
        errors = _step_errors(problem, writes)
        step_errors = [msg for _, msg in errors]
        if answer_ok and not step_errors:
            return VerifyResult(True, True, "SymPy 검산 통과", True, expected)
        reasons = ([answer_err] if not answer_ok else []) + step_errors[:2]
        return VerifyResult(
            False,
            True,
            " ".join(reasons),
            answer_ok,
            expected,
            step_errors,
            [i for i, _ in errors],
            solution_hint(problem),
        )
    except Exception:
        log.exception("verification crashed")
        return VerifyResult(False, False, "검산 중 오류가 발생했어요.")


def verify_answer(problem_text: str, final_answer: str) -> VerifyResult:
    return verify_solution(problem_text, [], final_answer)
