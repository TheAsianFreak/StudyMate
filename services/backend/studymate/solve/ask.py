"""Q&A and casual conversation with the character (voice or typed, multi-turn).

mode "question": study answer, may write LaTeX lines, optionally grounded with retrieved
document chunks; a message that is itself a solvable math problem goes through the
verified solve pipeline instead. mode "chat": 1-3 short spoken lines, no board writing.
When the client omits the mode it is classified with a schema-constrained LLM call.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Literal

from studymate.errors import UserFacingError
from studymate.i18n import tr
from studymate.protocol.backend import AskRequest, ChatTurn, ScriptStep
from studymate.solve import prompts
from studymate.solve.grounding import format_chunks, retrieve_safe
from studymate.solve.memory import SolvedProblem
from studymate.solve.safety import filter_steps, is_unsafe_request, refusal_step, safety_prompt
from studymate.solve.schema import ANALYSIS_MAX, steps_schema, to_steps
from studymate.verify import analyze_problem, answers_equivalent, verify_answer

if TYPE_CHECKING:
    from studymate.services import Services

log = logging.getLogger(__name__)

Mode = Literal["question", "chat"]

CLASSIFY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"mode": {"enum": ["question", "chat"]}},
    "required": ["mode"],
    "additionalProperties": False,
}
QUESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"steps": steps_schema(1, 4, write=True, mark=False)},
    "required": ["steps"],
    "additionalProperties": False,
}
CHAT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"steps": steps_schema(1, 3, write=False)},
    "required": ["steps"],
    "additionalProperties": False,
}


def classify_system() -> str:
    return tr(
        "학생이 선생님 캐릭터에게 한 말을 분류해요.\n"
        "- question: 공부 내용에 대한 질문이나 요청 (개념 설명, 문제 풀이, 과목 지식, 단어 뜻, 숙제 도움)\n"
        "- chat: 인사, 잡담, 기분, 응원 요청, 공부 습관·계획 이야기, 대답이나 맞장구",
        "生徒が先生キャラクターに言ったことを分類します。\n"
        "- question: 勉強の内容についての質問やお願い（考え方の説明、問題の解き方、教科の知識、言葉の意味、宿題の手伝い）\n"
        "- chat: あいさつ、雑談、気分、応援してほしい、勉強の習慣や計画の話、返事やあいづち",
        "Classify what the student said to the teacher character.\n"
        "- question: a question or request about study content (explaining a concept, solving a problem, "
        "subject knowledge, word meanings, homework help)\n"
        "- chat: greetings, small talk, feelings, asking for encouragement, study habits or plans, replies "
        "or acknowledgements",
    )


def question_system() -> str:
    rules = tr(
        """지금 할 일: 학생의 공부 질문에 말로 짧게 답해요.
- steps는 1~4개. say는 소리 내어 읽기 좋은 짧은 문장 1~2개예요.
- say에는 LaTeX나 =, √, ², /, ± 같은 기호를 쓰지 말고 말로 읽어요 (예: "b 제곱 빼기 4ac").
- 칠판에 쓰면 도움이 될 때만 write에 LaTeX 한 줄을 써요. 수식은 그대로 쓰고, \\text{...}는 한국어 단어에만 써요.
- 쓸 게 없으면 write는 빈 문자열이에요.
- 참고 자료가 주어지면 질문과 관련 있을 때만 그 내용을 바탕으로 답해요. 모르는 것은 솔직하게 모른다고 말해요.
- 숫자나 계산은 정확히 확인하고 말해요.
- 학생이 정답지·해설의 답을 알려주거나 틀렸다고 하면 고집하지 말고 다시 확인해요. 정답지가 틀렸다고 단정하지 않아요.
- 이전 대화가 있으면 그 흐름을 이어서 답해요.""",
        """今やること: 生徒の勉強の質問に、声で短く答えます。
- steps は1〜4個。say は読み上げやすい短い文1〜2つです。
- say には LaTeX や =, √, ², /, ± のような記号を使わず、言葉で読みます（例: 「b の2乗ひく4ac」）。
- 黒板に書くと役に立つときだけ、write に LaTeX を1行書きます。数式はそのまま書き、\\text{...} は日本語の言葉にだけ使います。
- 書くことがなければ write は空文字列です。
- 参考資料があるときは、質問に関係する場合だけその内容をもとに答えます。わからないことは正直にわからないと言います。
- 数字や計算は正確に確かめてから言います。
- 生徒が解答・解説の答えを教えてくれたり、まちがいだと言ったりしたら、意地を張らずに確かめ直します。解答がまちがっていると決めつけません。
- 前の会話があれば、その流れに続けて答えます。""",
        """Task: answer the student's study question out loud, briefly.
- 1 to 4 steps. Each say is one or two short sentences that read well aloud.
- In say, don't use LaTeX or symbols like =, √, ², /, ±; read them in words (e.g. "b squared minus 4 a c").
- Only when writing on the board helps, put one line of LaTeX in write. Keep formulas as they are; use \\text{...} only for words.
- If there is nothing to write, write is an empty string.
- If reference material is given, use it only when it is relevant to the question. If you don't know, say so honestly.
- Double-check numbers and calculations before saying them.
- If the student gives the answer from an answer key or says you are wrong, don't insist: check again. Never claim the answer key is wrong.
- If there was an earlier conversation, continue from it.""",
    )
    return f"{prompts.persona()}\n\n{rules}\n\n{safety_prompt()}"


CORRECTION_CHECK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "corrects": {"type": "boolean"},
        "claimed_answer": {"type": "string", "maxLength": 60},
    },
    "required": ["corrects", "claimed_answer"],
    "additionalProperties": False,
}
CORRECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        # hidden scratch work: re-solve toward the reported answer before the lesson
        "analysis": {"type": "string", "minLength": 20, "maxLength": ANALYSIS_MAX},
        "steps": steps_schema(2, 6, write=True, mark=False),
    },
    "required": ["analysis", "steps"],
    "additionalProperties": False,
}


def correction_check_system() -> str:
    return tr(
        "선생님이 문제를 풀고 답을 말했어요. 학생의 말을 보고 판단해요.\n"
        "- corrects: 학생이 선생님의 답이 틀렸다고 하거나, 다른 답(정답지·해설·교과서·자기 풀이)을 정답이라고 "
        "말하면 true. 풀이 방법을 묻거나 이해가 안 된다는 말, 다른 질문은 false.\n"
        "- claimed_answer: 학생이 정답이라고 말한 답을 그대로 (예: '③', '4', 'x = 2'). 말하지 않았으면 빈 문자열.",
        "先生が問題を解いて答えを言いました。生徒の言葉を見て判断します。\n"
        "- corrects: 生徒が先生の答えはまちがいだと言ったり、別の答え（解答・解説・教科書・自分の解き方）を"
        "正解だと言ったりしていれば true。解き方の質問、わからないという言葉、別の質問は false。\n"
        "- claimed_answer: 生徒が正解だと言った答えをそのまま（例: 「③」「4」「x = 2」）。言っていなければ空文字列。",
        "The teacher solved a problem and gave an answer. Judge the student's message.\n"
        "- corrects: true if the student says the teacher's answer is wrong, or gives a different answer "
        "(from an answer key, a solution manual, the textbook or their own work) as the correct one. "
        "Questions about the method, saying they don't understand, or other questions are false.\n"
        "- claimed_answer: the answer the student says is correct, as written (e.g. '③', '4', 'x = 2'); "
        "empty if they didn't give one.",
    )


def correction_system() -> str:
    rules = tr(
        """지금 할 일: 학생이 선생님(너)의 답이 틀렸다고 알려줬어요.
- 고집하지 않아요. 먼저 알려줘서 고맙다고 하고 다시 풀어요. 정답지·해설·교과서의 정답은 믿을 수 있는 기준이에요. 정답지가 틀렸다고 말하지 않아요.
- analysis: 문제 원문을 처음부터 다시 꼼꼼히 풀어요. 학생이 알려준 정답이 있으면 그 답이 왜 맞는지, 앞의 풀이가 어디서 틀렸는지(놓친 조건, 계산 실수, 보기 판단 실수) 찾아요. 짧은 평문으로, 같은 말을 되풀이하지 않아요.
- steps: 2~6개. 틀린 곳 인정 → 바른 풀이의 핵심 → 정답 확인 순서예요. say는 소리 내어 읽을 짧은 문장, write는 칠판에 쓸 LaTeX 한 줄 (한국어는 \\text{...}), 쓸 게 없으면 빈 문자열.
- 끝까지 다시 풀어도 학생이 알려준 답이 나오지 않으면, 내가 문제를 잘못 읽었을 수 있다고 솔직하게 말하고 어떤 조건이나 숫자를 확인하면 좋을지 물어요. 이때도 정답지가 틀렸다고 하지 않아요.""",
        """今やること: 生徒が、先生（あなた）の答えはまちがいだと教えてくれました。
- 意地を張りません。まず教えてくれたお礼を言って、解き直します。解答・解説・教科書の正解は信頼できる基準です。解答がまちがっているとは言いません。
- analysis: 問題文を最初からていねいに解き直します。生徒が教えてくれた正解があれば、なぜそれが正しいのか、前の解き方のどこでまちがえたのか（見落とした条件、計算ミス、選択肢の判断ミス）を見つけます。短い平文で、同じことをくり返しません。
- steps: 2〜6個。まちがいを認める → 正しい解き方の要点 → 正解の確認、の順です。say は読み上げる短い文、write は黒板に書く LaTeX 1行（日本語は \\text{...}）、書くことがなければ空文字列。
- 最後まで解き直しても生徒が教えてくれた答えにならないときは、問題を読みまちがえたかもしれないと正直に言い、どの条件や数を確かめるとよいかを聞きます。このときも解答がまちがっているとは言いません。""",
        """Task: the student told you (the teacher) that your answer is wrong.
- Don't insist. First thank them, then solve it again. The answer from an answer key, solution manual or textbook is a reliable reference; never say the answer key is wrong.
- analysis: re-solve the original problem carefully from the start. If the student gave the correct answer, work out why it is right and where the earlier solution went wrong (a missed condition, an arithmetic slip, a misjudged option). Short plain text, no repetition.
- steps: 2 to 6, in order: admit the mistake -> the key of the right solution -> confirm the answer. say is a short sentence to read aloud; write is one line of LaTeX for the board (words in \\text{...}), or an empty string.
- If even a careful re-solve doesn't reach the student's answer, say honestly that you may have misread the problem and ask which condition or number to check. Even then, never say the answer key is wrong.""",
    )
    return f"{prompts.persona()}\n\n{rules}\n\n{safety_prompt()}"


def chat_system() -> str:
    rules = tr(
        """지금 할 일: 학생과 가볍게 이야기해요 (인사, 기분, 응원, 공부 습관이나 계획 이야기).
- steps는 1~3개. say는 짧고 자연스러운 말 한두 문장이에요.
- 칠판에는 쓰지 않아요.
- 학생의 말에 공감하고 따뜻하게 격려해요. 자연스럽게 공부로 이어지면 좋아요.
- 이전 대화가 있으면 그 흐름을 이어서 말해요.""",
        """今やること: 生徒と気軽におしゃべりします（あいさつ、気分、応援、勉強の習慣や計画の話）。
- steps は1〜3個。say は短く自然な1〜2文です。
- 黒板には書きません。
- 生徒の言葉に共感して、あたたかく励まします。自然に勉強の話につながるといいですね。
- 前の会話があれば、その流れに続けて話します。""",
        """Task: chat casually with the student (greetings, feelings, encouragement, study habits or plans).
- 1 to 3 steps. Each say is one or two short, natural sentences.
- Don't write on the board.
- Empathize with the student and encourage them warmly. It's nice if the talk leads back to studying naturally.
- If there was an earlier conversation, continue from it.""",
    )
    return f"{prompts.persona()}\n\n{rules}\n\n{safety_prompt()}"


def history_messages(history: list[ChatTurn] | None, max_chars: int) -> list[dict[str, Any]]:
    """Prior turns (oldest first) as chat messages; consecutive same-role turns are merged."""
    out: list[dict[str, Any]] = []
    for turn in (history or [])[-20:]:
        text = turn.text.strip()[:max_chars]
        if not text:
            continue
        if out and out[-1]["role"] == turn.role:
            out[-1]["content"] += "\n" + text
        else:
            out.append({"role": turn.role, "content": text})
    return out


async def classify(services: Services, msg: AskRequest) -> Mode:
    recent = history_messages(msg.history, 200)[-2:]
    student, teacher = tr("학생", "生徒", "Student"), tr("선생님", "先生", "Teacher")
    context = "\n".join(f"{student if m['role'] == 'user' else teacher}: {m['content']}" for m in recent)
    earlier = tr("이전 대화", "前の会話", "Earlier conversation")
    said = tr("학생이 한 말", "生徒が言ったこと", "What the student said")
    user = (f"{earlier}:\n{context}\n\n" if context else "") + f"{said}: {msg.text}"
    try:
        out = await services.llm.chat_json(
            [{"role": "system", "content": classify_system()}, {"role": "user", "content": user}],
            CLASSIFY_SCHEMA,
            name="ask_mode",
            temperature=0.0,
            max_tokens=16,
            seed=0,
        )
    except Exception:
        log.warning("mode classification failed; treating as question", exc_info=True)
        return "question"
    return "chat" if out.get("mode") == "chat" else "question"


async def _solve_steps(services: Services, text: str) -> list[ScriptStep]:
    from studymate.solve.pipeline import solve

    outcome = await solve(services, problem_text=text)
    steps = list(outcome.script.steps)
    if not outcome.script.verified and outcome.script.confidence == "low":
        steps.append(
            ScriptStep(
                say=tr(
                    "이 풀이는 검산을 통과하지 못했어요. 한 번 더 확인해 보는 게 좋겠어요.",
                    "この解き方は検算を通りませんでした。もう一度確かめてみてくださいね。",
                    "This solution didn't pass the check. It's worth double-checking it.",
                ),
                gesture="idle",
                emotion="neutral",
            )
        )
    return steps


def _user_content(msg: AskRequest, chunks_text: str, solved: SolvedProblem | None = None) -> str:
    parts = []
    if chunks_text:
        parts.append(tr("참고 자료", "参考資料", "Reference material") + f":\n{chunks_text}")
    if solved is not None:
        parts.append(tr("문제 원문", "問題文", "The problem") + f":\n{solved.text[:PROBLEM_CHARS]}")
        if solved.corrected_answer:
            # the lesson summary below still carries the old, wrong answer
            key = tr(
                "정답 (학생이 알려준 정답지 기준)",
                "正解（生徒が教えてくれた解答）",
                "Answer (from the student's answer key)",
            )
            parts.append(f"{key}: {solved.corrected_answer}")
    if msg.context and msg.context.strip() and not (solved and solved.corrected_answer):
        topic = tr("지금 보고 있는 문제나 주제", "今見ている問題や話題", "The problem or topic on screen")
        parts.append(f"{topic}: {msg.context.strip()[:800]}")
    parts.append(tr("학생", "生徒", "Student") + f": {msg.text.strip()}")
    return "\n\n".join(parts)


PROBLEM_CHARS = 6000  # a whole CSAT reading passage


async def check_correction(services: Services, msg: AskRequest, solved: SolvedProblem) -> tuple[bool, str]:
    """Whether the student says the teacher's answer is wrong, and the answer they give."""
    user = (
        tr("선생님의 답", "先生の答え", "The teacher's answer")
        + f": {solved.answer}\n"
        + tr("학생의 말", "生徒の言葉", "What the student said")
        + f": {msg.text.strip()}"
    )
    try:
        out = await services.llm.chat_json(
            [{"role": "system", "content": correction_check_system()}, {"role": "user", "content": user}],
            CORRECTION_CHECK_SCHEMA,
            name="ask_correction_check",
            temperature=0.0,
            max_tokens=48,
            seed=0,
        )
    except UserFacingError:
        return False, ""
    return out.get("corrects") is True, str(out.get("claimed_answer", "")).strip()


def _checked_claim(solved: SolvedProblem, claimed: str) -> str:
    """What SymPy says about the student's answer, for the re-solve prompt ("" if it can't tell)."""
    if not solved.is_math or not claimed:
        return ""
    check = verify_answer(solved.text, claimed)
    if check.verified:
        return tr(
            "계산으로 확인해 보니 학생이 알려준 답이 맞아요.",
            "計算で確かめると、生徒が教えてくれた答えが正しいです。",
            "A calculation check confirms the student's answer is correct.",
        )
    if check.parsed:
        return tr(
            "문제를 읽은 그대로 계산하면 학생이 알려준 답이 나오지 않아요. 문제의 숫자나 조건을 잘못 읽었을 수 있어요.",
            "読み取った問題のとおりに計算すると、生徒が教えてくれた答えになりません。問題の数や条件を読みまちがえたかもしれません。",
            "Computed from the problem as it was read, the student's answer does not come out. "
            "A number or condition of the problem may have been misread.",
        )
    return ""


async def correct(
    services: Services, msg: AskRequest, solved: SolvedProblem, claimed: str
) -> list[ScriptStep]:
    """Re-solves after the student reported the answer is wrong: admits and explains instead of
    arguing. Works from the original problem, without the conversation that defended the old answer."""
    cfg = services.settings.solve
    note = await asyncio.to_thread(_checked_claim, solved, claimed)
    parts = [
        tr("문제 원문", "問題文", "The problem") + f":\n{solved.text[:PROBLEM_CHARS]}",
        tr("앞서 선생님이 말한 답", "先生が前に言った答え", "The answer you gave before")
        + f": {solved.final_answer}",
        tr("학생의 말", "生徒の言葉", "What the student said") + f": {msg.text.strip()}",
    ]
    if claimed:
        parts.append(
            tr("학생이 알려준 정답", "生徒が教えてくれた正解", "The answer the student reports")
            + f": {claimed}"
        )
    if note:
        parts.append(note)
    out = await services.llm.chat_json(
        [{"role": "system", "content": correction_system()}, {"role": "user", "content": "\n\n".join(parts)}],
        CORRECTION_SCHEMA,
        name="ask_correction",
        temperature=0.2,
        max_tokens=cfg.max_tokens + cfg.analysis_max_tokens,
        sampling={
            "dry_multiplier": cfg.dry_multiplier,
            "dry_allowed_length": cfg.dry_allowed_length,
            "dry_penalty_last_n": cfg.dry_penalty_last_n,
        },
    )
    if claimed and msg.problem_id:
        services.solved.correct(msg.problem_id, claimed)
    return to_steps(out.get("steps"))


async def answer(services: Services, msg: AskRequest) -> tuple[list[ScriptStep], Mode]:
    """Steps to speak (and maybe write) in reply to the student's message."""
    cfg = services.settings.solve
    if is_unsafe_request(msg.text):
        # Refused before any model runs (sexual content; see solve/safety.py).
        return [refusal_step()], msg.mode or "chat"
    solved = services.solved.get(msg.problem_id)
    if solved is not None and msg.mode != "chat":
        corrects, claimed = await check_correction(services, msg, solved)
        # "the key says ⑤" when the answer was ⑤: a confirmation, not a correction
        if corrects and not (claimed and answers_equivalent(claimed, solved.answer, solved.text)):
            steps, _ = filter_steps(await correct(services, msg, solved, claimed))
            if steps:
                return steps, "question"
    solvable = await asyncio.to_thread(analyze_problem, msg.text) is not None
    mode: Mode = msg.mode or ("question" if solvable else await classify(services, msg))
    if mode == "question" and solvable:
        steps, _ = filter_steps(await _solve_steps(services, msg.text))
        return steps, mode

    chunks_text = ""
    if mode == "question":
        query = f"{msg.context or ''} {msg.text}".strip()
        chunks = await retrieve_safe(services, query, k=cfg.ask_retrieve_k)
        chunks_text = format_chunks(chunks)

    system = question_system() if mode == "question" else chat_system()
    schema = QUESTION_SCHEMA if mode == "question" else CHAT_SCHEMA
    messages = [{"role": "system", "content": system}]
    messages += history_messages(msg.history, cfg.ask_history_chars)
    current = _user_content(msg, chunks_text, solved if mode == "question" else None)
    if len(messages) > 1 and messages[-1]["role"] == "user":
        messages[-1]["content"] += "\n\n" + current  # unanswered previous turn: keep roles alternating
    else:
        messages.append({"role": "user", "content": current})
    if len(messages) > 1 and messages[1]["role"] == "assistant":
        start = tr("(대화 시작)", "（会話の始まり）", "(start of conversation)")
        messages.insert(1, {"role": "user", "content": start})
    out = await services.llm.chat_json(
        messages,
        schema,
        name="ask_answer",
        temperature=0.6 if mode == "chat" else 0.3,
        max_tokens=cfg.ask_max_tokens,
    )
    steps = to_steps(out.get("steps"))
    if mode == "chat":
        steps = [s.model_copy(update={"write": None, "mark": None}) for s in steps]
    if not steps:
        again = tr(
            "음, 다시 한 번 말해 줄래요?",
            "えっと、もう一回言ってくれますか？",
            "Hmm, could you say that again?",
        )
        steps = [ScriptStep(say=again, gesture="idle", emotion="neutral")]
    steps, _ = filter_steps(steps)
    return steps, mode
