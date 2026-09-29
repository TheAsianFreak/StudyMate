"""Accuracy / latency evaluation of the solve pipeline on non-math CSAT (수능) items.

    uv run python -m eval.run_csat [--tier lite|standard|pro|max] [--subjects 국어,사회탐구,화학Ⅰ]
                                   [--ids KO01,EN03] [--limit N] [--lang ko|ja|en] [--hint]
    uv run python -m eval.run_csat --rescore eval/results/<file>.json   # re-judge, no model

Each item of eval/problems_csat.py is sent as `problem_text` (the items are Korean; --lang only
switches the prompt language). The final answer is judged with `answers_equivalent`, which maps
"③", "3번", "③ 이성계" to the option number; an answer naming several options ("②, ③") is
wrong. `correct_lenient` additionally accepts an answer that states an option's text instead of
its number ("ㄱ, ㄴ", a bare "3"), to tell answer-format failures from wrong reasoning.
--hint passes the item's subject as `subject_hint`.

Writes eval/results/<timestamp>-<tier>-csat.json (rewritten after every item, so a partial run
keeps its rows) with each item's lesson steps, and prints a summary.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import statistics
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from eval.problems_csat import MARKS, PROBLEMS, SUBJECT_AREA, CsatProblem, option_lines, validate_problems

RESULTS_DIR = Path(__file__).with_name("results")
CONFIDENCES = ("high", "medium", "low")

_NON_WORD = re.compile(r"[^0-9A-Za-z가-힣ㄱ-ㅎ]")
_BARE_NUMBER = re.compile(r"\s*([1-5])\s*[.번]?\s*")
_NUMBERED = re.compile(r"(?<!\d)([1-5])\s*번")


def _norm(s: str) -> str:
    return _NON_WORD.sub("", s).lower()


def predicted_choice(final_answer: str, p: CsatProblem) -> int | None:
    """Option number the final answer names ("③", "3번"), else a bare "3", else the one option
    whose text it states ("ㄱ, ㄴ", "(B) - (A) - (C)", a quoted statement)."""
    from studymate.verify.answer import choice_index

    idx = choice_index(final_answer)
    if idx is not None:
        return idx
    m = _BARE_NUMBER.fullmatch(final_answer or "")
    if m:
        return int(m.group(1))
    got = _norm(final_answer or "")
    if not got:
        return None
    opts = [_norm(o[1:]) for o in option_lines(p.text)]
    exact = [i for i, o in enumerate(opts, 1) if o == got]
    if len(exact) == 1:
        return exact[0]
    quoted = [i for i, o in enumerate(opts, 1) if len(o) >= 8 and o in got]
    return quoted[0] if len(quoted) == 1 else None


def named_options(final_answer: str) -> set[int]:
    """Every option number the final answer names: "②, ③" -> {2, 3}."""
    text = final_answer or ""
    return {MARKS.index(c) + 1 for c in text if c in MARKS} | {int(n) for n in _NUMBERED.findall(text)}


def judge(final_answer: str, p: CsatProblem) -> dict[str, Any]:
    """`answers_equivalent` against the key; an answer naming several options ("②, ③") is wrong
    (choice_index alone would read only its first option)."""
    from studymate.verify.answer import answers_equivalent

    multiple = len(named_options(final_answer)) > 1
    predicted = None if multiple else predicted_choice(final_answer, p)
    return {
        "predicted": predicted,
        "multiple_options": multiple,
        "correct": not multiple and answers_equivalent(final_answer, p.answer),
        "correct_lenient": predicted == p.choice,
    }


def select(args: argparse.Namespace) -> list[CsatProblem]:
    problems = PROBLEMS
    if args.subjects:
        wanted = {s.strip() for s in args.subjects.split(",") if s.strip()}
        unknown = wanted - set(SUBJECT_AREA) - set(SUBJECT_AREA.values())
        if unknown:
            raise SystemExit(f"unknown subjects/areas: {sorted(unknown)}")
        problems = [p for p in problems if p.subject in wanted or p.area in wanted]
    if args.ids:
        ids = {i.strip() for i in args.ids.split(",")}
        problems = [p for p in problems if p.id in ids]
    if args.limit:
        problems = problems[: args.limit]
    return problems


def _ratio(flags: list[bool]) -> str:
    return f"{sum(flags)}/{len(flags)} ({sum(flags) / len(flags):.0%})" if flags else "0/0"


def _group(rows: list[dict[str, Any]], key: Callable[[dict[str, Any]], str]) -> dict[str, str]:
    groups: dict[str, list[bool]] = {}
    for r in rows:
        groups.setdefault(key(r), []).append(bool(r["correct"]))
    return {k: _ratio(v) for k, v in groups.items()}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    secs = [r["seconds"] for r in rows]
    predicted = [r.get("predicted") for r in rows]
    return {
        "total": n,
        "correct": sum(r["correct"] for r in rows),
        "accuracy": round(sum(r["correct"] for r in rows) / n, 3) if n else 0.0,
        "correct_lenient": sum(r["correct_lenient"] for r in rows),
        "first_attempt_correct": sum(r["first_attempt_correct"] for r in rows),
        "multiple_options": sum(bool(r.get("multiple_options")) for r in rows),
        "no_option_named": sum(
            r.get("predicted") is None and not r.get("multiple_options") and "error" not in r for r in rows
        ),
        "predicted_choices": {str(c): predicted.count(c) for c in (1, 2, 3, 4, 5, None)},
        "confidence": {c: sum(r.get("confidence") == c for r in rows) for c in CONFIDENCES},
        "accuracy_by_confidence": {
            c: _ratio([r["correct"] for r in rows if r.get("confidence") == c]) for c in CONFIDENCES
        },
        "errors": sum("error" in r for r in rows),
        "avg_steps": round(statistics.mean(len(r.get("steps", [])) for r in rows), 1) if rows else 0.0,
        "avg_seconds": round(statistics.mean(secs), 2) if secs else 0.0,
        "avg_seconds_after_warmup": round(statistics.mean(secs[1:]), 2) if len(secs) > 1 else None,
        "median_seconds": round(statistics.median(secs), 2) if secs else 0.0,
        "by_area": _group(rows, lambda r: r["area"]),
        "by_subject": _group(rows, lambda r: r["subject"]),
        "by_subtype": _group(rows, lambda r: f"{r['subject']}/{r['subtype']}"),
    }


def _write(out: Path, info: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    report = {"info": info, "summary": summarize(rows), "results": rows}
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


async def run(args: argparse.Namespace, problems: Iterable[CsatProblem], out: Path) -> dict[str, Any]:
    from studymate import i18n
    from studymate.services import get_services
    from studymate.solve.pipeline import solve

    i18n.set_lang(args.lang)
    services = get_services()
    info: dict[str, Any] = {
        "set": "csat",
        "tier": services.tier,
        "mode": "text",
        "lang": args.lang,
        "subject_hint": bool(args.hint),
        "chat_model": services.llama.model_for("chat"),
        "started": datetime.now().isoformat(timespec="seconds"),
    }
    print(f"tier={info['tier']} chat={info['chat_model']} lang={args.lang} hint={args.hint}", flush=True)
    rows: list[dict[str, Any]] = []
    try:
        for p in problems:
            t0 = time.perf_counter()
            row: dict[str, Any] = {
                "id": p.id,
                "area": p.area,
                "subject": p.subject,
                "subtype": p.subtype,
                "expected": p.answer,
                "rationale": p.rationale,
                "problem": p.text,
            }
            try:
                outcome = await solve(
                    services, problem_text=p.text, subject_hint=p.subject if args.hint else None
                )
                s = outcome.script
                first = next(
                    (a["final_answer"] for a in outcome.attempt_log if a.get("final_answer")), s.final_answer
                )
                row.update(
                    final_answer=s.final_answer,
                    **judge(s.final_answer, p),
                    first_attempt_correct=judge(first, p)["correct"],
                    confidence=s.confidence,
                    verified=s.verified,
                    attempts=outcome.attempts,
                    flagged=outcome.flagged,
                    detected_subject=outcome.problem.subject,
                    unit=s.unit,
                    resolve_answers=outcome.resolve_answers,
                    problem_latex=s.problem_latex,
                    steps=[st.model_dump(exclude_none=True) for st in s.steps],
                    attempt_log=outcome.attempt_log,
                )
            except Exception as exc:  # keep going; count as wrong
                row.update(
                    predicted=None,
                    multiple_options=False,
                    correct=False,
                    correct_lenient=False,
                    first_attempt_correct=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            row["seconds"] = round(time.perf_counter() - t0, 2)
            rows.append(row)
            _write(out, info, rows)
            mark = "OK " if row["correct"] else ("FMT" if row["correct_lenient"] else "BAD")
            answer = row.get("final_answer", row.get("error"))
            print(
                f"{mark} {p.id} {p.subject}/{p.subtype} {row['seconds']:6.1f}s conf={row.get('confidence')}"
                f" att={row.get('attempts')} unit={row.get('unit')!r} expected={p.answer} got={answer!r}",
                flush=True,
            )
    finally:
        services.shutdown()
    info["finished"] = datetime.now().isoformat(timespec="seconds")
    _write(out, info, rows)
    return {"info": info, "summary": summarize(rows), "results": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="StudyMate CSAT (non-math) evaluation")
    parser.add_argument("--tier", choices=["lite", "standard", "pro", "max"])
    parser.add_argument("--subjects", help="comma-separated subjects or areas (국어, 사회탐구, 화학Ⅰ, ...)")
    parser.add_argument("--ids", help="comma-separated item ids")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--lang", choices=["ko", "ja", "en"], default="ko", help="prompt language")
    parser.add_argument("--hint", action="store_true", help="pass the item's subject as subject_hint")
    parser.add_argument("--rescore", metavar="RESULTS_JSON", help="re-judge a saved run without the model")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    validate_problems(PROBLEMS)
    if args.rescore:
        out = Path(args.rescore)
        print_summary(rescore(out), out)
        return 0

    if args.tier:
        os.environ["STUDYMATE_TIER"] = args.tier
    os.environ.setdefault("STUDYMATE_DATA_DIR", tempfile.mkdtemp(prefix="studymate-eval-"))
    problems = select(args)
    print(f"CSAT set valid: {len(PROBLEMS)} items; running {len(problems)}", flush=True)

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = ("" if args.lang == "ko" else f"-{args.lang}") + ("-hint" if args.hint else "")
    out = RESULTS_DIR / f"{stamp}-{args.tier or 'auto'}-csat{suffix}.json"
    print_summary(asyncio.run(run(args, problems, out)), out)
    return 0


def rescore(path: Path) -> dict[str, Any]:
    """Re-judges a saved results file with the current answer key and judge, and rewrites it."""
    report: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    by_id = {p.id: p for p in PROBLEMS}
    for row in report["results"]:
        p = by_id.get(row["id"])
        if p is None or "final_answer" not in row:
            continue
        row["expected"] = p.answer
        row.update(judge(row["final_answer"], p))
        log = row.get("attempt_log") or []
        row["first_attempt_correct"] = judge(
            next((a["final_answer"] for a in log if a.get("final_answer")), row["final_answer"]), p
        )["correct"]
    report["summary"] = summarize(report["results"])
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def print_summary(report: dict[str, Any], out: Path) -> None:
    s = report["summary"]
    total = s["total"]
    print(
        f"\naccuracy {s['correct']}/{total} ({s['accuracy']:.0%}), lenient {s['correct_lenient']}/{total},"
        f" first attempt {s['first_attempt_correct']}/{total}, several options named {s['multiple_options']},"
        f" no option named {s['no_option_named']}, errors {s['errors']}"
    )
    print(f"confidence {s['confidence']}; accuracy by confidence {s['accuracy_by_confidence']}")
    print(
        f"avg {s['avg_seconds']}s/item (after warm-up {s['avg_seconds_after_warmup']}s), median"
        f" {s['median_seconds']}s, avg {s['avg_steps']} steps; predicted choices {s['predicted_choices']}"
    )
    for title, key in (("area", "by_area"), ("subject", "by_subject"), ("subtype", "by_subtype")):
        print(f"\nby {title}:")
        for name, ratio in s[key].items():
            print(f"  {name:<24} {ratio}")
    print(f"\nresults: {out}")


if __name__ == "__main__":
    raise SystemExit(main())
