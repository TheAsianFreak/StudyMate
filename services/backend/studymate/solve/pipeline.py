"""Solve pipeline: problem -> LLM solution script -> SymPy verification loop.

confidence:
- "high"   SymPy parsed the problem and verified every board line and the final answer
- "medium" SymPy cannot read the problem, but an independent re-solve (fresh context,
           different seed) reached the same final answer
- "low"    anything else; the script is still returned with verified=False
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from studymate.errors import UserFacingError
from studymate.i18n import tr
from studymate.protocol.backend import ScriptStep, SolveScript
from studymate.solve import curriculum, prompts
from studymate.solve.safety import filter_steps, is_unsafe
from studymate.solve.schema import (
    RESOLVE_SCHEMA,
    THINK_SCHEMA,
    lesson_steps,
    solve_line_indices,
    solve_schema,
)
from studymate.verify import (
    VerifyResult,
    analyze_problem,
    answers_equivalent,
    format_expected,
    verify_solution,
)
from studymate.verify.answer import choice_indices
from studymate.verify.latex import repair_escapes, to_plain
from studymate.verify.problem import ParsedProblem
from studymate.vision import Problem, board_latex, guess_subject, read_problem

if TYPE_CHECKING:
    from studymate.services import Services

log = logging.getLogger(__name__)

Stage = Literal["ocr", "solving", "verifying", "retry", "voicing"]
ProgressFn = Callable[[Stage, int | None, str | None], Awaitable[None]]
Confidence = Literal["high", "medium", "low"]

SEED_BASE = 1000
RESOLVE_SEED_BASE = 7000
THINK_SEED = 70_000


@dataclass
class Candidate:
    problem_latex: str
    steps: list[ScriptStep]
    final_answer: str
    raw: dict[str, Any]
    check: VerifyResult | None = None
    support: int = 0  # re-solves that agreed with its answer (-1: the lesson contradicts it)


def is_multiple_choice(problem_text: str) -> bool:
    return len(set(re.findall(r"[①②③④⑤]", problem_text))) >= 3


def lesson_inconsistency(cand: Candidate) -> str | None:
    """Why a multiple-choice answer can't be shown: "multiple" options answered or "none".

    (Comparing the answer with the options the board marks ○/× was tried and dropped: the
    model uses the marks both for "this statement is true" and "this is the answer", so it
    flagged many correct lessons on "적절하지 않은 것" and <보기> combination items.)"""
    picked = choice_indices(cand.final_answer)
    if len(picked) > 1:
        return "multiple"
    return None if picked else "none"


def _votes(answer: str, resolves: list[str], problem_text: str) -> tuple[int, int]:
    """(re-solves agreeing with `answer`, re-solves disagreeing)."""
    support = sum(answers_equivalent(answer, r, problem_text) for r in resolves)
    return support, len(resolves) - support


def _majority(resolves: list[str], problem_text: str) -> str | None:
    """The re-solve answer most re-solves share, when it is a strict majority."""
    best: str | None = None
    best_n = 0
    for r in resolves:
        n = sum(answers_equivalent(r, o, problem_text) for o in resolves)
        if n > best_n:
            best, best_n = r, n
    return best if best_n * 2 > len(resolves) else None


@dataclass
class SolveOutcome:
    script: SolveScript
    problem: Problem
    attempts: int
    first_attempt_ok: bool
    flagged: bool = False
    resolve_answers: list[str] = field(default_factory=list)
    attempt_log: list[dict[str, Any]] = field(default_factory=list)


async def _noop(stage: Stage, attempt: int | None, detail: str | None) -> None:
    return None


def text_problem(text: str, subject_hint: str | None = None) -> Problem:
    text = text.strip()
    return Problem(text, board_latex(text), guess_subject(text, subject_hint), "text")


async def generate_candidate(
    services: Services, messages: list[dict[str, Any]], attempt: int, *, analysis: bool = False
) -> Candidate:
    cfg = services.settings.solve
    raw = await services.llm.chat_json(
        messages,
        solve_schema(analysis=analysis),
        name="solve_script",
        temperature=min(0.9, cfg.temperature + 0.25 * (attempt - 1)),
        max_tokens=cfg.max_tokens + (cfg.analysis_max_tokens if analysis else 0),
        sampling=_dry(cfg) if analysis else None,
        seed=SEED_BASE + attempt,
    )
    steps = lesson_steps(raw)
    final = repair_escapes(str(raw.get("final_answer", ""))).replace("$", "").strip()
    if not steps or not final:
        raise UserFacingError("llm_bad_output", "모델 출력이 올바르지 않습니다.")
    return Candidate(repair_escapes(str(raw.get("problem_latex", ""))).strip(), steps, final, raw)


def unsolved_unknowns(parsed: ParsedProblem | None, writes: list[str | None]) -> list[str]:
    """Unknowns of a system whose value no working line states ("y = 1"), in order.

    The board must show every unknown being found before the check (a model sometimes
    works the last one out inside the check line instead).
    """
    if parsed is None or parsed.kind != "equation" or len(parsed.answer_symbols) < 2:
        return []
    found: set[str] = set()
    for w in writes:
        plain = to_plain(w or "") or ""
        for part in plain.split(","):
            m = re.fullmatch(r"\s*([A-Za-z])\s*=\s*([^A-Za-z=<>]+)", part)
            if m:
                found.add(m.group(1))
    return [s.name for s in parsed.answer_symbols if s.name not in found]


def no_problem_error() -> UserFacingError:
    return UserFacingError(
        "no_problem",
        tr(
            "풀 문제를 찾지 못했어요. 질문이나 지시문까지 함께 잘라 주세요.",
            "解く問題が見つかりませんでした。問いや指示の文まで一緒に切り取ってください。",
            "I couldn't find a question to solve. Please include the question or instructions too.",
        ),
    )


# One letter equal to one number ("x = 3", "$y=-2.5$"): an answer, not a problem.
_BARE_ANSWER = re.compile(r"^\s*\$*\s*[A-Za-z]\s*=\s*[-+]?\d+(?:\.\d+)?\s*\$*\s*[.。]?\s*$")


async def classify_unit(services: Services, problem_text: str) -> curriculum.Unit:
    """Curriculum unit of the problem (JSON-constrained), so the explanation follows the textbook.
    Two steps: the subject, then a unit of that subject (a biology item never lands in a math
    unit)."""
    user = {"role": "user", "content": prompts.resolve_user(problem_text)}
    try:
        out = await services.llm.chat_json(
            [{"role": "system", "content": curriculum.subject_prompt()}, user],
            curriculum.subject_schema(),
            name="subject",
            temperature=0.0,
            max_tokens=32,
        )
    except UserFacingError as exc:
        log.warning("subject classification failed: %s", exc.code)
        return curriculum.unit(None)
    if out.get("has_task") is False:
        # A lesson on nothing makes the model repeat "there is no problem here" in every line.
        raise no_problem_error()
    subject = str(out.get("subject", "math"))
    if subject not in curriculum.SUBJECTS:
        subject = "math"
    if subject == "other":
        return curriculum.unit("etc_general")
    try:
        out = await services.llm.chat_json(
            [{"role": "system", "content": curriculum.classifier_prompt(subject)}, user],
            curriculum.classifier_schema(subject),
            name="unit",
            temperature=0.0,
            max_tokens=40,
        )
    except UserFacingError as exc:
        log.warning("unit classification failed: %s", exc.code)
        return curriculum.unit(None)
    return curriculum.unit(str(out.get("unit_id", "")))


def _dry(cfg: Any) -> dict[str, Any]:
    return {
        "dry_multiplier": cfg.dry_multiplier,
        "dry_allowed_length": cfg.dry_allowed_length,
        "dry_penalty_last_n": cfg.dry_penalty_last_n,
    }


async def resolve_answer(
    services: Services, problem_text: str, attempt: int, hint: str | None = None
) -> str | None:
    """Independent re-solve in a fresh context (different prompt and seed): final answer only.
    `hint` is the unit's key idea, so the re-solve doesn't trip on a formula the lesson knows."""
    system = prompts.resolve_system()
    if hint:
        system += "\n\n" + tr("참고 개념", "参考になる考え方", "Key idea") + f": {hint}"
    try:
        out = await services.llm.chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompts.resolve_user(problem_text)},
            ],
            RESOLVE_SCHEMA,
            name="resolve",
            temperature=services.settings.solve.resolve_temperature,
            max_tokens=services.settings.solve.max_tokens,
            seed=RESOLVE_SEED_BASE + attempt,
        )
    except UserFacingError as exc:
        log.warning("re-solve failed: %s", exc.code)
        return None
    answer = str(out.get("final_answer", "")).strip()
    return answer or None


@dataclass
class Worked:
    """The reasoning pass's solution: the lesson is written along it."""

    outline: str
    answer: str


def thinks(services: Services, unit: curriculum.Unit) -> bool:
    """Whether a problem of `unit` gets a reasoning pass first (solve.think, GPU only)."""
    mode = services.settings.solve.think
    if mode == "off" or not getattr(services.llama, "on_gpu", False):
        return False
    return curriculum.is_advanced(unit) and (mode == "all" or unit.is_math)


async def think_solve(services: Services, problem_text: str, guide: str) -> Worked | None:
    """Solves in thinking mode: thousands of reasoning tokens, then an outline and the answer.
    Hard problems (case analysis, hidden conditions) need this; the quick one-shot lesson
    misses conditions the reasoning catches."""
    cfg = services.settings.solve
    try:
        out = await services.llm.chat_json(
            [
                {"role": "system", "content": prompts.think_system(guide)},
                {"role": "user", "content": prompts.resolve_user(problem_text)},
            ],
            THINK_SCHEMA,
            name="think",
            temperature=cfg.think_temperature,
            max_tokens=cfg.think_max_tokens,
            seed=THINK_SEED,
            sampling={"top_p": 0.95, "top_k": 20},
            think=True,
        )
    except UserFacingError as exc:
        log.warning("reasoning pass failed: %s", exc.code)
        return None
    answer = repair_escapes(str(out.get("final_answer", ""))).replace("$", "").strip()
    outline = repair_escapes(str(out.get("outline", ""))).strip()
    return Worked(outline, answer) if answer else None


def _problem_latex(problem: Problem, cand: Candidate) -> str:
    if problem.source != "text":
        return problem.latex
    original = analyze_problem(problem.text)
    if original is None:
        return cand.problem_latex or problem.latex
    restated = analyze_problem(cand.problem_latex) if cand.problem_latex else None
    if restated is not None and format_expected(restated) == format_expected(original):
        return cand.problem_latex
    return problem.latex


def _finish(
    problem: Problem, cand: Candidate, verified: bool, confidence: Confidence, unit: curriculum.Unit
) -> tuple[SolveScript, bool]:
    steps, flagged = filter_steps(cand.steps)
    final = cand.final_answer
    if is_unsafe(final):
        final, flagged = tr("답변할 수 없어요", "お答えできません", "I can't answer that"), True
    latex = _problem_latex(problem, cand)
    if is_unsafe(latex):
        latex, flagged = "", True
    if problem.uncertain and confidence == "high":
        # SymPy verified the problem *as read*; the two OCR engines disagreed on how it reads
        confidence = "medium"
    script = SolveScript(
        problem_latex=latex or problem.latex,
        final_answer=final,
        verified=verified and not flagged,
        confidence=confidence if not flagged else "low",
        steps=steps,
        unit=None if curriculum.is_general(unit) else unit.label,
        subject=unit.subject,  # type: ignore[arg-type]  # one of curriculum.SUBJECTS
    )
    return script, flagged


async def solve(
    services: Services,
    *,
    image_base64: str | None = None,
    problem_text: str | None = None,
    subject_hint: str | None = None,
    progress: ProgressFn | None = None,
) -> SolveOutcome:
    report = progress or _noop
    if image_base64:
        await report("ocr", None, None)
        problem = await read_problem(services, image_base64)
        if subject_hint:
            problem.subject = guess_subject(problem.text, subject_hint)
    elif problem_text and problem_text.strip():
        problem = text_problem(problem_text, subject_hint)
    else:
        raise UserFacingError("invalid_request", "문제 이미지나 문제 내용을 보내주세요.")

    if is_unsafe(problem.text):
        steps, _ = filter_steps([ScriptStep(say=problem.text)])
        script = SolveScript(problem_latex="", final_answer="", verified=False, confidence="low", steps=steps)
        return SolveOutcome(script, problem, 0, False, flagged=True)

    # a stray mark or symbol, or a bare answer such as "x = 3": nothing to solve
    if sum(ch.isalnum() for ch in problem.text) < 2 or _BARE_ANSWER.match(problem.text):
        raise no_problem_error()
    parsed = await asyncio.to_thread(analyze_problem, problem.text)
    max_attempts = max(1, services.settings.solve.max_attempts)
    unit = await classify_unit(services, problem.text)
    # Math: equation-style lesson, SymPy where it can read the problem. Other CSAT subjects:
    # evidence-style lesson (passage/data -> options -> answer), re-solve agreement only.
    # Harder problems first work it out in a hidden scratch field.
    analysis = curriculum.is_advanced(unit)
    guide = curriculum.teaching_guide(unit)
    if unit.is_math:
        system = prompts.solve_system(guide, analysis=analysis)
    else:
        system = prompts.evidence_system(guide)
        parsed = None
    base = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompts.solve_user(problem.text, problem.subject)},
    ]
    worked: Worked | None = None
    if thinks(services, unit):
        await report(
            "solving",
            1,
            tr(
                "어려운 문제라 먼저 차근차근 생각하고 있어요.",
                "難しい問題なので、まずじっくり考えています。",
                "A hard one, so I'm thinking it through first.",
            ),
        )
        worked = await think_solve(services, problem.text, guide)
        if worked is not None:
            extra = prompts.worked_user(worked.outline, worked.answer)
            base[1] = {"role": "user", "content": base[1]["content"] + "\n\n" + extra}
    messages = list(base)
    candidates: list[Candidate] = []
    resolve_answers: list[str] = []
    attempt_log: list[dict[str, Any]] = []
    first_ok = False
    verified_fallback: tuple[Candidate, int] | None = None

    choice = is_multiple_choice(problem.text)
    for attempt in range(1, max_attempts + 1):
        if attempt == 1:
            await report("solving", attempt, None)
        t0 = time.perf_counter()
        # Without SymPy the answer is checked by independent re-solves; they don't depend on
        # the lesson, so they run while it is written (llama-server serves requests in parallel).
        pending: asyncio.Future[list[str | None]] | None = None
        if parsed is None:
            n_new = 2 if attempt == 1 and choice else 1
            seeds = [attempt * 10 + k for k in range(n_new)]
            hint = unit.concept
            pending = asyncio.gather(*(resolve_answer(services, problem.text, s, hint) for s in seeds))
        try:
            cand = await generate_candidate(services, messages, attempt, analysis=analysis)
        except UserFacingError as exc:
            if pending is not None:
                resolve_answers.extend(a for a in await pending if a)
            # truncated / malformed JSON (e.g. a scratch field that looped): try again if we can
            if exc.code != "llm_bad_output" or attempt == max_attempts:
                if candidates:
                    break
                raise
            attempt_log.append({"attempt": attempt, "final_answer": "", "error": exc.code})
            continue
        candidates.append(cand)
        await report("verifying", attempt, None)
        entry: dict[str, Any] = {"attempt": attempt, "final_answer": cand.final_answer}

        if parsed is not None:
            # Only working lines must be equivalent to the problem (not concept/check/summary).
            line_steps = solve_line_indices(cand.steps)
            writes = [cand.steps[i].write for i in line_steps]
            check = await asyncio.to_thread(verify_solution, problem.text, writes, cand.final_answer)
            # report wrong lines by their step number in the script the model wrote
            check.bad_lines = [line_steps[n - 1] + 1 for n in check.bad_lines if 0 < n <= len(line_steps)]
            cand.check = check
            entry.update(
                verified=check.verified, detail=check.detail, seconds=round(time.perf_counter() - t0, 2)
            )
            attempt_log.append(entry)
            if check.verified:
                unsolved = unsolved_unknowns(parsed, writes)
                if unsolved and attempt < max_attempts:
                    # Correct, but the board never shows some unknown being found (e.g. y worked
                    # out inside the check line): ask once more, keep this one as the fallback.
                    verified_fallback = verified_fallback or (cand, attempt)
                    entry["unsolved"] = unsolved
                    await report("retry", attempt + 1, None)
                    feedback = prompts.unsolved_user(unsolved)
                    messages = [base[0], {"role": "user", "content": base[1]["content"] + "\n\n" + feedback}]
                    continue
                first_ok = attempt == 1 and not unsolved
                script, flagged = _finish(problem, cand, True, "high", unit)
                return SolveOutcome(script, problem, attempt, first_ok, flagged, resolve_answers, attempt_log)
            if verified_fallback is not None:
                fallback, at = verified_fallback
                script, flagged = _finish(problem, fallback, True, "high", unit)
                return SolveOutcome(script, problem, at, False, flagged, resolve_answers, attempt_log)
            if attempt < max_attempts:
                await report("retry", attempt + 1, check.detail)
                feedback = prompts.retry_user(check.answer_ok, check.bad_lines, check.expected, check.hint)
                # fresh context: with its wrong answer in view the model tends to copy it
                messages = [base[0], {"role": "user", "content": base[1]["content"] + "\n\n" + feedback}]
            continue

        # SymPy cannot read the problem: vote with independent re-solves. The lesson's answer
        # is shown as "medium" only when most re-solves agree with it (a multiple-choice
        # question gets two re-solves up front) and it names exactly one option.
        news = await pending if pending is not None else []
        resolve_answers.extend(a for a in news if a)
        issue = lesson_inconsistency(cand) if choice else None
        # the reasoning pass is an independent solve too (the lesson only saw its summary)
        votes = resolve_answers + ([worked.answer] if worked else [])
        support, against = _votes(cand.final_answer, votes, problem.text)
        cand.support = -1 if issue else support
        entry.update(
            resolve=[a for a in news if a],
            support=support,
            against=against,
            issue=issue,
            seconds=round(time.perf_counter() - t0, 2),
        )
        if worked is not None:
            entry["think"] = worked.answer
        attempt_log.append(entry)
        if issue is None and support > 0 and support > against:
            first_ok = attempt == 1
            script, flagged = _finish(problem, cand, False, "medium", unit)
            return SolveOutcome(script, problem, attempt, first_ok, flagged, resolve_answers, attempt_log)
        if (
            worked is not None
            and issue is None
            and answers_equivalent(cand.final_answer, worked.answer, problem.text)
        ):
            # Lesson and reasoning pass agree, the quick re-solves don't. On a hard problem the
            # reasoning pass is the stronger solver: keep its answer marked "check needed"
            # rather than retrying toward the quick answers.
            script, flagged = _finish(problem, cand, False, "low", unit)
            return SolveOutcome(script, problem, attempt, False, flagged, resolve_answers, attempt_log)
        if attempt < max_attempts:
            await report(
                "retry",
                attempt + 1,
                tr(
                    "검산 답과 달라서 다시 풀어요.",
                    "検算の答えと違うので、もう一度解きます。",
                    "The answer didn't match the check, solving again.",
                ),
            )
            if issue is not None:
                feedback = prompts.inconsistent_user(issue, cand.final_answer)
            else:
                likely = _majority(votes, problem.text)
                feedback = prompts.disagree_user(cand.final_answer, likely)
            messages = [base[0], {"role": "user", "content": base[1]["content"] + "\n\n" + feedback}]

    if verified_fallback is not None:
        fallback, at = verified_fallback
        script, flagged = _finish(problem, fallback, True, "high", unit)
        return SolveOutcome(script, problem, at, False, flagged, resolve_answers, attempt_log)
    # nothing verified: prefer a candidate whose final answer SymPy accepted, else the one
    # most re-solves agreed with
    best = next((c for c in candidates if c.check and c.check.answer_ok), None)
    if best is None:
        best = max(reversed(candidates), key=lambda c: c.support)
    script, flagged = _finish(problem, best, False, "low", unit)
    return SolveOutcome(script, problem, max_attempts, False, flagged, resolve_answers, attempt_log)
