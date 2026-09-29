"""Accuracy / latency evaluation of the real solve pipeline on eval/problems.py.

    uv run python -m eval.run_eval [--tier lite|standard|pro|max] [--images] [--limit N] [--ids L01,F02]
                                   [--set default|csat-math|csat-hard]

Text mode sends `problem_text`; --images renders each problem to a PNG (PIL) and sends
`image_base64`, exercising Qwen2.5-VL (pro/standard) or RapidOCR + pix2tex (lite).
--set csat-math runs the CSAT (수능) math problems of eval/problems_csat_math.py (Korean;
--lang only switches the prompt language) and reports accuracy per subject; --set csat-hard
runs the killer / 준킬러 4점 problems of eval/problems_csat_hard.py the same way.
Writes eval/results/<timestamp>-<tier>-<mode>[-<set>].json and prints a summary.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import statistics
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import sympy
from sympy.parsing.sympy_parser import parse_expr

from eval.problems import PROBLEMS, EvalProblem

RESULTS_DIR = Path(__file__).with_name("results")


def _symbols(p: EvalProblem) -> dict[str, sympy.Symbol]:
    return {name: sympy.Symbol(name, real=True) for name in p.answer}


def check_ground_truth(p: EvalProblem) -> None:
    """Solves the plain-SymPy restatement independently and compares with the stored answer."""
    syms = _symbols(p)
    eqs = []
    for eq in p.equations:
        lhs, rhs = eq.split("=")
        eqs.append(sympy.Eq(parse_expr(lhs, local_dict=syms), parse_expr(rhs, local_dict=syms)))
    sols = sympy.solve(eqs, list(syms.values()), dict=True)
    got = {name: sorted({sympy.nsimplify(s[sym]) for s in sols}, key=float) for name, sym in syms.items()}
    want = {name: sorted({sympy.Rational(v) for v in vals}, key=float) for name, vals in p.answer.items()}
    if got != want:
        raise AssertionError(f"{p.id}: ground truth {want} but SymPy says {got}")


def gt_text(p: EvalProblem) -> str:
    if len(p.answer) == 1:
        name, vals = next(iter(p.answer.items()))
        return " 또는 ".join(f"{name} = {v}" for v in vals)
    return ", ".join(f"{n} = {vals[0]}" for n, vals in p.answer.items())


def judge(final_answer: str, p: EvalProblem) -> bool:
    """True when the pipeline's final answer states exactly the ground-truth solution."""
    from studymate.verify import parse_answer
    from studymate.verify.latex import numbers_equal, sym

    ans = parse_answer(final_answer)
    if ans is None:
        return False
    for name, vals in p.answer.items():
        given = ans.assignments.get(sym(name))
        if given is None and len(p.answer) == 1 and not ans.assignments:
            given = ans.values
        if not given:
            return False
        want = [sympy.Rational(v) for v in vals]
        uniq: list[sympy.Expr] = []
        for g in given:
            if not any(numbers_equal(g, u) for u in uniq):
                uniq.append(g)
        if len(uniq) != len(want) or not all(any(numbers_equal(w, g) for g in uniq) for w in want):
            return False
    return True


# Instruction phrases of the (Korean) problem set in Japanese and English; the math stays.
_PHRASES: dict[str, tuple[str, str]] = {
    "다음 방정식을 푸시오.": ("次の方程式を解きなさい。", "Solve the equation."),
    "다음 일차방정식의 해를 구하시오.": ("次の一次方程式を解きなさい。", "Solve the linear equation."),
    "다음 이차방정식을 푸시오.": ("次の二次方程式を解きなさい。", "Solve the quadratic equation."),
    "다음 연립방정식을 푸시오.": ("次の連立方程式を解きなさい。", "Solve the system of equations."),
    "을 만족하는 x의 값을 구하시오.": (
        " を満たす x の値を求めなさい。",
        " Find the value of x that satisfies it.",
    ),
    "의 해를 구하시오.": (" の解を求めなさい。", " Find the solution."),
    "연립방정식": ("連立方程式", "The system"),
    "방정식": ("方程式", "The equation"),
}


def localize_problem(text: str, lang: str) -> str:
    if lang == "ko":
        return text
    idx = 0 if lang == "ja" else 1
    for ko, alt in _PHRASES.items():  # longest phrases first (dict order above)
        text = text.replace(ko, alt[idx])
    return text


@dataclass(frozen=True)
class EvalSet:
    """A problem set with its own ground-truth check, judge and categories."""

    name: str
    problems: list[Any]
    validate: Callable[[], None]
    judge: Callable[[str, Any], bool]
    gt_text: Callable[[Any], str]
    category: Callable[[Any], str]
    localize: Callable[[str, str], str]


def _default_set() -> EvalSet:
    def validate() -> None:
        for p in PROBLEMS:
            check_ground_truth(p)

    return EvalSet("default", PROBLEMS, validate, judge, gt_text, lambda p: p.category, localize_problem)


def _csat_math_set() -> EvalSet:
    from eval import problems_csat_math as cm

    # Korean problems in every run; --lang switches the prompt and lesson language only
    return EvalSet(
        "csat-math",
        cm.PROBLEMS,
        cm.validate_problems,
        cm.judge,
        cm.gt_text,
        lambda p: p.subject,
        lambda s, _: s,
    )


def _csat_hard_set() -> EvalSet:
    from eval import problems_csat_hard as ch

    # Korean problems in every run; --lang switches the prompt and lesson language only
    return EvalSet(
        "csat-hard",
        ch.PROBLEMS,
        ch.validate_problems,
        ch.judge,
        ch.gt_text,
        lambda p: p.subject,
        lambda s, _: s,
    )


SETS: dict[str, Callable[[], EvalSet]] = {
    "default": _default_set,
    "csat-math": _csat_math_set,
    "csat-hard": _csat_hard_set,
}


def _category_detail(rows: list[dict[str, Any]], cats: list[str]) -> dict[str, dict[str, Any]]:
    """Per category: accuracy, first-attempt accuracy and the confidence distribution."""
    out: dict[str, dict[str, Any]] = {}
    for c in cats:
        rs = [r for r in rows if r["category"] == c]
        out[c] = {
            "correct": f"{sum(r['correct'] for r in rs)}/{len(rs)}",
            "first_attempt": f"{sum(r['first_attempt_correct'] for r in rs)}/{len(rs)}",
            "confidence": {k: sum(r.get("confidence") == k for r in rs) for k in ("high", "medium", "low")},
            "wrong_but_high": sum(r.get("confidence") == "high" and not r["correct"] for r in rs),
        }
    return out


async def run(args: argparse.Namespace, eval_set: EvalSet | None = None) -> dict[str, Any]:
    from studymate.services import get_services
    from studymate.solve.pipeline import solve

    eval_set = eval_set or _default_set()
    problems = eval_set.problems
    if args.ids:
        wanted = set(args.ids.split(","))
        problems = [p for p in problems if p.id in wanted]
    if args.limit:
        problems = problems[: args.limit]
    services = get_services()
    tier = services.tier
    info = {
        "tier": tier,
        "mode": "images" if args.images else "text",
        "chat_model": services.llama.model_for("chat"),
        "vision_model": services.llama.model_for("vision") if services.llama.available("vision") else None,
        "started": datetime.now().isoformat(timespec="seconds"),
    }
    print(
        f"tier={tier} mode={info['mode']} chat={info['chat_model']} vision={info['vision_model']}", flush=True
    )
    if args.images:
        from eval.render import render_png

    from studymate import i18n

    i18n.set_lang(args.lang)
    info["lang"] = args.lang
    info["set"] = eval_set.name
    judge_fn = eval_set.judge
    rows: list[dict[str, Any]] = []
    try:
        for p in problems:
            t0 = time.perf_counter()
            text = eval_set.localize(p.text, args.lang)
            row: dict[str, Any] = {
                "id": p.id,
                "category": eval_set.category(p),
                "problem": text,
                "ground_truth": eval_set.gt_text(p),
            }
            try:
                if args.images:
                    png = base64.b64encode(render_png(text)).decode("ascii")
                    outcome = await solve(services, image_base64=png)
                    row["read_text"] = outcome.problem.text
                else:
                    outcome = await solve(services, problem_text=text)
                s = outcome.script
                first = next(
                    (a["final_answer"] for a in outcome.attempt_log if a.get("final_answer")), s.final_answer
                )
                row.update(
                    final_answer=s.final_answer,
                    correct=judge_fn(s.final_answer, p),
                    first_attempt_correct=judge_fn(first, p),
                    unit=s.unit,
                    verified=s.verified,
                    confidence=s.confidence,
                    attempts=outcome.attempts,
                    steps=[st.model_dump(exclude_none=True) for st in s.steps],
                    problem_latex=s.problem_latex,
                    attempt_log=outcome.attempt_log,
                )
            except Exception as exc:  # keep going; count as wrong
                row.update(correct=False, first_attempt_correct=False, error=f"{type(exc).__name__}: {exc}")
            row["seconds"] = round(time.perf_counter() - t0, 2)
            rows.append(row)
            mark = "OK " if row["correct"] else "BAD"
            answer = row.get("final_answer", row.get("error"))
            conf, att = row.get("confidence"), row.get("attempts")
            print(f"{mark} {p.id} {row['seconds']:6.1f}s conf={conf} att={att} answer={answer!r}", flush=True)
    finally:
        services.shutdown()

    n = len(rows)
    secs = [r["seconds"] for r in rows]
    cats = list(dict.fromkeys(r["category"] for r in rows))
    by_cat = {c: [r["correct"] for r in rows if r["category"] == c] for c in cats}
    summary = {
        "total": n,
        "correct": sum(r["correct"] for r in rows),
        "accuracy": round(sum(r["correct"] for r in rows) / n, 3) if n else 0.0,
        "first_attempt_correct": sum(r["first_attempt_correct"] for r in rows),
        "verified_high": sum(r.get("confidence") == "high" for r in rows),
        "confidence": {c: sum(r.get("confidence") == c for r in rows) for c in ("high", "medium", "low")},
        "errors": sum("error" in r for r in rows),
        "avg_seconds": round(statistics.mean(secs), 2) if secs else 0.0,
        "avg_seconds_after_warmup": round(statistics.mean(secs[1:]), 2) if len(secs) > 1 else None,
        "median_seconds": round(statistics.median(secs), 2) if secs else 0.0,
        "by_category": {c: f"{sum(v)}/{len(v)}" for c, v in by_cat.items()},
        "by_category_detail": _category_detail(rows, cats),
    }
    return {"info": info, "summary": summary, "results": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="StudyMate solve-pipeline evaluation")
    parser.add_argument("--tier", choices=["lite", "standard", "pro", "max"])
    parser.add_argument("--images", action="store_true", help="render problems to PNG and go through OCR/VL")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", help="comma-separated problem ids")
    parser.add_argument(
        "--lang", choices=["ko", "ja", "en"], default="ko", help="language of prompts and problems"
    )
    parser.add_argument("--set", choices=sorted(SETS), default="default", help="problem set")
    args = parser.parse_args()

    if args.tier:
        os.environ["STUDYMATE_TIER"] = args.tier
    os.environ.setdefault("STUDYMATE_DATA_DIR", tempfile.mkdtemp(prefix="studymate-eval-"))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    eval_set = SETS[args.set]()
    eval_set.validate()
    print(
        f"ground truth verified by SymPy for {len(eval_set.problems)} problems ({eval_set.name})", flush=True
    )

    report = asyncio.run(run(args, eval_set))
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = ("" if args.lang == "ko" else f"-{args.lang}") + (
        "" if args.set == "default" else f"-{args.set}"
    )
    out = RESULTS_DIR / f"{stamp}-{report['info']['tier']}-{report['info']['mode']}{suffix}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    s = report["summary"]
    total, first = s["total"], s["first_attempt_correct"]
    print(
        f"\naccuracy {s['correct']}/{total} ({s['accuracy']:.0%}), first attempt {first}/{total},"
        f" SymPy-verified {s['verified_high']}, confidence {s['confidence']}, errors {s['errors']}"
    )
    print(
        f"avg {s['avg_seconds']}s/problem (after warm-up {s['avg_seconds_after_warmup']}s), median "
        f"{s['median_seconds']}s; by category {s['by_category']}"
    )
    for cat, d in s["by_category_detail"].items():
        print(
            f"  {cat}: {d['correct']} correct, first attempt {d['first_attempt']},"
            f" confidence {d['confidence']}, wrong-but-high {d['wrong_but_high']}"
        )
    print(f"results: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
