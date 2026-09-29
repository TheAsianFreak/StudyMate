"""Quiz generation (SPEC 7.2): generate -> independent re-solve -> answers agree -> SymPy.

Every item is generated with a JSON schema, re-solved in a fresh context with a
different prompt and seed, and (for math that SymPy can read) verified. Items that do
not pass within `quiz.max_attempts` are dropped, so the client only receives items with
confidence "high" (SymPy verified) or "medium" (re-solve agreement only).
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any, Literal

import studymate.learning.store as store
from studymate.i18n import tr
from studymate.protocol.backend import GenerateQuiz, QuizItem, QuizSource, Solution
from studymate.solve import prompts
from studymate.solve.grounding import format_chunks, retrieve_safe
from studymate.solve.safety import filter_steps, is_unsafe, safety_prompt
from studymate.solve.schema import answer_schema, steps_schema, to_steps
from studymate.verify import analyze_problem, answers_equivalent, normalize_text, verify_answer
from studymate.verify.latex import repair_escapes

if TYPE_CHECKING:
    from studymate.rag.retrieve import RetrievedChunk
    from studymate.services import Services

log = logging.getLogger(__name__)

Kind = Literal["multiple_choice", "short_answer"]
ProgressFn = Callable[[int, int], Awaitable[None]]


def difficulty(level: str) -> str:
    if level == "easy":
        return tr(
            "쉬움 (기본 개념을 확인하는 문제)",
            "やさしい（基本の考え方を確かめる問題）",
            "easy (checks a basic concept)",
        )
    if level == "hard":
        return tr(
            "어려움 (여러 단계를 거치는 응용 문제)",
            "むずかしい（いくつもの段階がある応用問題）",
            "hard (multi-step application)",
        )
    return tr("보통 (교과서 예제 수준)", "ふつう（教科書の例題レベル）", "normal (textbook example level)")


EXCERPT_CHARS = 200
GEN_SEED = 20_000
RESOLVE_SEED = 40_000


def item_schema(kind: Kind) -> dict[str, Any]:
    props: dict[str, Any] = {
        "question_latex": {"type": "string", "minLength": 5, "maxLength": 400},
        "solution_steps": steps_schema(2, 5, mark=False),
        "answer": {"type": "string", "minLength": 1, "maxLength": 60},  # short key; no explanations
    }
    required = ["question_latex", "solution_steps", "answer"]
    if kind == "multiple_choice":
        props["distractors"] = {
            "type": "array",
            "items": {"type": "string", "minLength": 1, "maxLength": 80},
            "minItems": 3,
            "maxItems": 3,
        }
        required.append("distractors")
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


RESOLVE_SA_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"work": {"type": "string", "maxLength": 900}, "final_answer": answer_schema()},
    "required": ["work", "final_answer"],
    "additionalProperties": False,
}
RESOLVE_MC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"work": {"type": "string", "maxLength": 900}, "choice": {"enum": [1, 2, 3, 4]}},
    "required": ["work", "choice"],
    "additionalProperties": False,
}


def gen_system() -> str:
    rules = tr(
        """너는 학생을 위해 복습 문제를 만드는 선생님이에요. 문제를 한 개 만들어요.
- question_latex: 문제 문장. 한국어 문장은 그대로 쓰고 수식은 LaTeX로 써요 ($ 없이). 답이 하나로 정해지는 문제만 만들어요.
- 수학 문제는 계산하면 답이 정확히 하나 나오는 문제로 만들어요 (예: 방정식, 계산, 식의 값).
- solution_steps: 2~5단계 풀이. say는 소리 내어 읽을 짧은 문장, write는 칠판에 쓸 LaTeX 한 줄 (없으면 빈 문자열).
- answer: 정답만 짧게 (수, 식, 또는 한두 단어). 설명은 쓰지 않아요. 계산으로 꼭 확인해요.
- distractors가 있으면: 정답과 다른, 학생이 흔히 하는 실수에서 나오는 그럴듯한 오답 3개. 정답과 같은 값은 안 돼요.
- 참고 자료가 주어지면 그 내용에 근거해서 문제를 만들고, 자료에 없는 내용은 묻지 않아요.
- 이미 낸 문제와 겹치지 않게, 유형이나 수를 바꿔서 다양하게 만들어요.""",
        """あなたは生徒のために復習問題を作る先生です。問題を1つ作ります。
- question_latex: 問題文。日本語の文はそのまま書き、数式は LaTeX で書きます（$ なし）。答えが1つに決まる問題だけを作ります。
- 数学の問題は、計算すると答えがちょうど1つになる問題にします（例: 方程式、計算、式の値）。
- solution_steps: 2〜5段階の解き方。say は読み上げる短い文、write は黒板に書く LaTeX 1行（なければ空文字列）。
- answer: 正解だけを短く（数、式、または1〜2語）。説明は書きません。必ず計算で確かめます。
- distractors があるとき: 正解とは違う、生徒がよくするまちがいから出てくる、それらしい誤答を3つ。正解と同じ値はだめです。
- 参考資料があるときはその内容にもとづいて問題を作り、資料にないことは聞きません。
- もう出した問題と重ならないように、型や数を変えていろいろ作ります。""",
        """You are a teacher making review questions for a student. Make one question.
- question_latex: the question text. Write English sentences as they are and math in LaTeX (no $). Only questions with a single definite answer.
- A math question must have exactly one answer when calculated (e.g. an equation, a calculation, the value of an expression).
- solution_steps: a 2-5 step solution. say is a short sentence to read aloud; write is one line of LaTeX for the board (empty string if none).
- answer: only the answer, short (a number, an expression, or one or two words). No explanations. Always verify by calculating.
- If distractors are asked for: 3 plausible wrong answers that come from common student mistakes. None may equal the correct answer.
- If reference material is given, base the question on it and don't ask about anything it doesn't cover.
- Vary the type and the numbers so the question doesn't overlap with questions already asked.""",
    )
    return f"{rules}\n\n{prompts.answer_format()}\n\n{safety_prompt()}"


def resolve_system() -> str:
    head = tr(
        "너는 문제를 정확하게 푸는 검산 담당이에요. work에 핵심 계산 과정을 짧게 적고 답을 골라요.",
        "あなたは問題を正確に解く検算係です。work に大事な計算の過程を短く書き、答えを選びます。",
        "You double-check questions by solving them exactly. Write the key working briefly in work and pick the answer.",
    )
    return f"{head}\n\n{prompts.answer_format()}"


@dataclass
class _Draft:
    question: str
    answer: str
    steps: Any
    choices: list[str] | None


def is_math(subject: str, question: str) -> bool:
    return (
        bool(
            re.search(
                r"수학|math|산수|대수|기하|数学|算数|代数|幾何|algebra|geometry|arithmetic", subject, re.I
            )
        )
        or analyze_problem(question) is not None
    )


def _gen_user(req: GenerateQuiz, kind: Kind, chunk: RetrievedChunk | None, avoid: list[str]) -> str:
    lines = [tr("과목", "教科", "Subject") + f": {req.subject}"]
    if req.unit:
        lines.append(tr("단원", "単元", "Unit") + f": {req.unit}")
    lines.append(tr("난이도", "難易度", "Difficulty") + f": {difficulty(req.difficulty)}")
    if kind == "multiple_choice":
        form = tr(
            "4지선다 객관식 (정답 1개 + 오답 3개)",
            "4択問題（正解1つ + 誤答3つ）",
            "multiple choice, 4 options (1 correct + 3 wrong)",
        )
    else:
        form = tr("단답형", "記述（短答）", "short answer")
    lines.append(tr("문제 형식", "問題の形式", "Question type") + f": {form}")
    if chunk is not None:
        lines.append(
            "\n" + tr("참고 자료", "参考資料", "Reference material") + f":\n{format_chunks([chunk])}"
        )
    if avoid:
        done = tr("이미 낸 문제", "もう出した問題", "Questions already asked")
        lines.append(f"\n{done}:\n" + "\n".join(f"- {q}" for q in avoid[-AVOID_SHOWN:]))
    return "\n".join(lines)


AVOID_SHOWN = 12
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _plain(question: str) -> str:
    """Question text without LaTeX commands, spacing and punctuation, for comparison."""
    text = re.sub(r"\\[A-Za-z]+", " ", question)
    return re.sub(r"[\s{}$\\^_()\[\].,:;?!。、？！：]", "", text).lower()


def is_repeat(question: str, earlier: list[str]) -> bool:
    """The same question as one already asked: identical text, or nearly the same wording
    with the same numbers. The same kind of question with other numbers is a new question."""
    plain = _plain(question)
    numbers = _NUMBER.findall(question)
    for old in earlier:
        other = _plain(old)
        if plain == other:
            return True
        if numbers == _NUMBER.findall(old) and SequenceMatcher(None, plain, other).ratio() >= REPEAT_RATIO:
            return True
    return False


REPEAT_RATIO = 0.8


def _mc_user(question: str, choices: list[str]) -> str:
    listed = "\n".join(f"{i}) {c}" for i, c in enumerate(choices, 1))
    return tr(
        f"문제:\n{question}\n\n보기:\n{listed}\n\n정답 보기의 번호를 고르세요.",
        f"問題:\n{question}\n\n選択肢:\n{listed}\n\n正解の選択肢の番号を選んでください。",
        f"Question:\n{question}\n\nOptions:\n{listed}\n\nPick the number of the correct option.",
    )


async def _resolve(services: Services, draft: _Draft, seed: int) -> str | None:
    """Independent re-solve in a fresh context; returns the re-solver's answer text."""
    cfg = services.settings
    try:
        if draft.choices:
            out = await services.llm.chat_json(
                [
                    {"role": "system", "content": resolve_system()},
                    {"role": "user", "content": _mc_user(draft.question, draft.choices)},
                ],
                RESOLVE_MC_SCHEMA,
                name="quiz_resolve",
                temperature=cfg.solve.resolve_temperature,
                max_tokens=cfg.quiz.max_tokens,
                seed=seed,
            )
            choice = out.get("choice")
            return (
                draft.choices[choice - 1]
                if isinstance(choice, int) and 1 <= choice <= len(draft.choices)
                else None
            )
        out = await services.llm.chat_json(
            [
                {"role": "system", "content": resolve_system()},
                {"role": "user", "content": prompts.resolve_user(draft.question)},
            ],
            RESOLVE_SA_SCHEMA,
            name="quiz_resolve",
            temperature=cfg.solve.resolve_temperature,
            max_tokens=cfg.quiz.max_tokens,
            seed=seed,
        )
        return str(out.get("final_answer", "")).strip() or None
    except Exception as exc:
        log.warning("quiz re-solve failed: %s", exc)
        return None


def _sympy_check(draft: _Draft) -> tuple[bool, bool, str]:
    """(parsed, ok, detail): the answer is verified and no distractor is also correct."""
    check = verify_answer(draft.question, draft.answer)
    if not check.parsed:
        return False, False, check.detail
    if not check.verified:
        return True, False, f"answer {draft.answer!r}: {check.detail}"
    also_right = [
        c for c in (draft.choices or []) if c != draft.answer and verify_answer(draft.question, c).verified
    ]
    if also_right:
        return True, False, f"distractor also correct: {also_right}"
    return True, True, ""


def _draft(raw: dict[str, Any], kind: Kind, rng: random.Random) -> tuple[_Draft | None, str]:
    question = repair_escapes(str(raw.get("question_latex", ""))).strip()
    answer = repair_escapes(str(raw.get("answer", ""))).strip()
    if not question or not answer:
        return None, "empty"
    choices = None
    if kind == "multiple_choice":
        distractors = [repair_escapes(str(d)).strip() for d in raw.get("distractors") or [] if str(d).strip()]
        if len(distractors) != 3:
            return None, "distractors"
        options = [answer, *distractors]
        keys = {normalize_text(o) for o in options}
        if len(keys) != 4 or any(answers_equivalent(d, answer) for d in distractors):
            return None, "duplicate choices"
        rng.shuffle(options)
        choices = options
    texts = [question, answer, *(choices or [])]
    if any(is_unsafe(t) for t in texts):
        return None, "unsafe"
    return _Draft(question, answer, raw.get("solution_steps"), choices), ""


async def generate_item(
    services: Services,
    req: GenerateQuiz,
    kind: Kind,
    index: int,
    chunk: RetrievedChunk | None,
    avoid: list[str],
    seed: int = 0,
) -> QuizItem | None:
    """One verified item, or None after `quiz.max_attempts`. `avoid`: questions already
    asked (this quiz and recent ones); a draft that repeats one is rejected. `seed` differs
    per quiz, so the same settings do not give the same questions every time."""
    cfg = services.settings.quiz
    rng = random.Random(seed + index * 7919 + len(avoid))
    messages = [
        {"role": "system", "content": gen_system()},
        {"role": "user", "content": _gen_user(req, kind, chunk, avoid)},
    ]
    for attempt in range(1, max(1, cfg.max_attempts) + 1):
        raw = await services.llm.chat_json(
            messages,
            item_schema(kind),
            name="quiz_item",
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            seed=seed + GEN_SEED + 100 * index + attempt,
        )
        draft, reason = _draft(raw, kind, rng)
        if draft is None:
            log.info("quiz item %d attempt %d rejected: %s", index, attempt, reason)
            continue
        if is_repeat(draft.question, avoid):
            log.info("quiz item %d attempt %d rejected: repeats an earlier question", index, attempt)
            continue
        other = await _resolve(services, draft, seed + RESOLVE_SEED + 100 * index + attempt)
        if other is None or not answers_equivalent(draft.answer, other):
            log.info(
                "quiz item %d attempt %d: re-solve disagrees (%r vs %r)", index, attempt, draft.answer, other
            )
            continue
        confidence: Literal["high", "medium"] = "medium"
        if await asyncio.to_thread(is_math, req.subject, draft.question):
            parsed, ok, detail = await asyncio.to_thread(_sympy_check, draft)
            if parsed:
                if not ok:
                    log.info("quiz item %d attempt %d rejected by SymPy: %s", index, attempt, detail)
                    continue
                confidence = "high"
        steps, flagged = filter_steps(to_steps(draft.steps))
        if flagged:
            continue
        source = None
        if chunk is not None:
            source = QuizSource(
                doc_id=chunk.doc_id, page=chunk.page, excerpt=" ".join(chunk.text.split())[:EXCERPT_CHARS]
            )
        return QuizItem(
            item_id=str(uuid.uuid4()),
            subject=req.subject,
            unit=req.unit,
            difficulty=req.difficulty,
            question_latex=draft.question,
            choices=draft.choices,
            answer=draft.answer,
            solution=Solution(steps=steps),
            confidence=confidence,
            source=source,
        )
    return None


async def _context(services: Services, req: GenerateQuiz) -> list[RetrievedChunk]:
    k = services.settings.quiz.retrieve_k
    query = " ".join(p for p in (req.subject, req.unit or "") if p).strip()
    if req.source_doc_id:
        return await retrieve_safe(services, query or req.subject, doc_id=req.source_doc_id, k=k)
    if req.unit:
        return await retrieve_safe(services, query, k=k)
    return []


async def generate_quiz(
    services: Services, req: GenerateQuiz, progress: ProgressFn | None = None
) -> list[QuizItem]:
    chunks = await _context(services, req)
    items: list[QuizItem] = []
    try:
        recent = await asyncio.to_thread(store.recent_questions, services, req.subject, req.unit)
    except Exception as exc:  # the quiz still works without the history
        log.warning("recent quiz questions unavailable: %s", exc)
        recent = []
    avoid = list(reversed(recent))  # oldest first: the prompt shows the newest
    seed = random.SystemRandom().randrange(1_000_000) * 1000
    # An item that fails verification is replaced by another one, so the quiz has the
    # number of questions asked for; the extra slots bound the time a hard topic can take.
    slots = req.count + max(2, req.count // 2)
    for i in range(slots):
        if len(items) >= req.count:
            break
        kind: Kind = "multiple_choice" if len(items) % 2 == 0 else "short_answer"
        chunk = chunks[i % len(chunks)] if chunks else None
        item = await generate_item(services, req, kind, i, chunk, avoid, seed)
        if item is not None:
            items.append(item)
            avoid.append(item.question_latex)
            if progress:
                await progress(len(items), req.count)
    if items:
        try:
            await asyncio.to_thread(store.save_quiz_items, services, items)
        except NotImplementedError:
            log.warning("save_quiz_items() not implemented yet; quiz items were not saved")
    return items
