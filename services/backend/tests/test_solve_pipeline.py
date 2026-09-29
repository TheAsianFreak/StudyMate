"""Solve pipeline with a fake LLM (no llama-server)."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from studymate.config import get_settings
from studymate.solve import pipeline
from studymate.solve.pipeline import solve
from studymate.solve.safety import REFUSAL_SAY
from studymate.vision import Problem

Handler = Callable[[str, list[dict[str, Any]], int], dict[str, Any]]


class FakeLLM:
    def __init__(self, handler: Handler) -> None:
        self.handler = handler
        self.calls: list[dict[str, Any]] = []
        self.unit_calls = 0
        self.subject = "math"
        self.has_task = True
        self.unit_id = "m1_linear_equation"

    async def chat_json(
        self, messages: list[dict[str, Any]], schema: dict[str, Any], **kw: Any
    ) -> dict[str, Any]:
        if kw.get("name") == "subject":
            return {"has_task": self.has_task, "subject": self.subject}
        if kw.get("name") == "unit":
            # curriculum classification: answered here so handlers only see solve/resolve calls
            self.unit_calls += 1
            return {"unit_id": self.unit_id}
        self.calls.append({"messages": messages, "schema": schema, **kw})
        return self.handler(kw.get("name", ""), messages, len(self.calls))

    def named(self, name: str) -> list[dict[str, Any]]:
        return [c for c in self.calls if c.get("name") == name]


def make_services(handler: Handler, *, vision: bool = False) -> Any:
    return SimpleNamespace(
        settings=get_settings(),
        llm=FakeLLM(handler),
        llama=SimpleNamespace(available=lambda role: vision),
    )


def script(answer: str, writes: list[str], latex: str = "") -> dict[str, Any]:
    steps = [
        {"say": f"{i}번째 단계예요.", "write": w, "gesture": "write", "emotion": "neutral"}
        for i, w in enumerate(writes)
    ]
    return {"problem_latex": latex, "solve": steps, "final_answer": answer}


class Progress:
    def __init__(self) -> None:
        self.events: list[tuple[str, int | None, str | None]] = []

    async def __call__(self, stage: str, attempt: int | None, detail: str | None) -> None:
        self.events.append((stage, attempt, detail))


async def test_verified_first_attempt_is_high() -> None:
    services = make_services(lambda name, m, n: script("x = 2", ["2x = 4", "x = 2", "x = 2"], "2x + 3 = 7"))
    progress = Progress()
    out = await solve(services, problem_text="다음 방정식을 푸시오. 2x + 3 = 7", progress=progress)
    assert out.script.verified and out.script.confidence == "high"
    assert out.attempts == 1 and out.first_attempt_ok
    assert out.script.final_answer == "x = 2"
    assert out.script.problem_latex == "2x + 3 = 7"
    assert [e[0] for e in progress.events] == ["solving", "verifying"]
    call = services.llm.calls[0]
    assert call["schema"]["required"] == [
        "problem_latex",
        "intro",
        "concept",
        "solve",
        "check",
        "summary",
        "final_answer",
    ]
    assert "안전 규칙" in call["messages"][0]["content"]


async def test_wrong_answer_is_retried_with_feedback() -> None:
    answers = iter(
        [script("x = 5", ["2x = 10", "x = 5", "x = 5"]), script("x = 2", ["2x = 4", "x = 2", "x = 2"])]
    )
    services = make_services(lambda name, m, n: next(answers))
    progress = Progress()
    out = await solve(services, problem_text="2x + 3 = 7", progress=progress)
    assert out.script.confidence == "high" and out.attempts == 2 and not out.first_attempt_ok
    stages = [e[0] for e in progress.events]
    assert stages == ["solving", "verifying", "retry", "verifying"]
    retry = progress.events[2]
    assert retry[1] == 2 and retry[2] and "틀렸" in retry[2]
    second = services.llm.calls[1]["messages"]
    # fresh context (no copy of the wrong answer), feedback with line numbers + SymPy's answer and hint
    assert [m["role"] for m in second] == ["system", "user"]
    feedback = second[-1]["content"]
    assert "2x + 3 = 7" in feedback and "x = 2" in feedback and "2x = 4" in feedback
    assert "1, 2, 3번째 줄" in feedback and "2x = 10" not in feedback
    assert services.llm.calls[0]["seed"] != services.llm.calls[1]["seed"]
    assert services.llm.calls[1]["temperature"] > services.llm.calls[0]["temperature"]


async def test_all_attempts_fail_returns_low_but_prefers_correct_answer() -> None:
    bad_steps = script("x = 2", ["2x = 10", "x = 2", "x = 2"])  # right answer, wrong line
    wrong = script("x = 7", ["2x = 14", "x = 7", "x = 7"])
    answers = iter([wrong, bad_steps, wrong])
    services = make_services(lambda name, m, n: next(answers))
    out = await solve(services, problem_text="2x + 3 = 7")
    assert out.attempts == get_settings().solve.max_attempts == 3
    assert not out.script.verified and out.script.confidence == "low"
    assert out.script.final_answer == "x = 2"


async def test_unparseable_problem_uses_resolve_agreement() -> None:
    def handler(name: str, messages: list[dict[str, Any]], n: int) -> dict[str, Any]:
        if name == "resolve":
            assert len(messages) == 2  # fresh context: system + problem only
            return {"work": "2(x+3)=14", "final_answer": "4"}
        return script("x = 4", ["2(x + 3) = 14", "x + 3 = 7", "x = 4"], "2(x + 3) = 14")

    services = make_services(handler)
    out = await solve(services, problem_text="어떤 수에 3을 더한 수의 2배는 14이다. 어떤 수를 구하시오.")
    assert out.script.confidence == "medium" and not out.script.verified
    assert out.script.problem_latex == "2(x + 3) = 14"
    resolve = services.llm.named("resolve")[0]
    assert resolve["seed"] != services.llm.named("solve_script")[0]["seed"]


async def test_unparseable_problem_disagreement_is_low() -> None:
    def handler(name: str, messages: list[dict[str, Any]], n: int) -> dict[str, Any]:
        if name == "resolve":
            return {"work": "...", "final_answer": "엽록체"}
        return {
            "problem_latex": "",
            "solve": script("", ["", "", ""])["solve"],
            "final_answer": "미토콘드리아",
        }

    services = make_services(handler)
    progress = Progress()
    out = await solve(services, problem_text="광합성이 일어나는 세포 소기관은?", progress=progress)
    assert out.script.confidence == "low"
    assert len(services.llm.named("solve_script")) == 3
    assert ("retry", 2, "검산 답과 달라서 다시 풀어요.") in progress.events


async def test_unsafe_output_is_replaced() -> None:
    raw = script("x = 2", ["2x = 4", "x = 2", "x = 2"])
    raw["solve"][1]["say"] = "그런데 이번 선거에서는 꼭 2번을 찍으세요."
    services = make_services(lambda name, m, n: raw)
    out = await solve(services, problem_text="2x + 3 = 7")
    says = [s.say for s in out.script.steps]
    assert REFUSAL_SAY in says and not any("선거" in s for s in says)
    assert out.script.confidence == "low" and not out.script.verified


async def test_image_problem_goes_through_ocr_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_read(services: Any, png: str) -> Problem:
        assert png == "UE5H"
        return Problem("다음 방정식을 푸시오.\n\\frac{x}{2} + 3 = 7", "\\frac{x}{2} + 3 = 7", "수학", "ocr")

    monkeypatch.setattr(pipeline, "read_problem", fake_read)
    services = make_services(
        lambda name, m, n: script("x = 8", ["\\frac{x}{2} = 4", "x = 8", "x = 8"], "ignored")
    )
    progress = Progress()
    out = await solve(services, image_base64="UE5H", progress=progress)
    assert progress.events[0] == ("ocr", None, None)
    assert out.script.confidence == "high"
    assert out.script.problem_latex == "\\frac{x}{2} + 3 = 7"  # from the reader, not the LLM
    assert "\\frac{x}{2} + 3 = 7" in services.llm.calls[0]["messages"][1]["content"]


async def test_missing_input_is_user_error() -> None:
    from studymate.errors import UserFacingError

    services = make_services(lambda name, m, n: {})
    with pytest.raises(UserFacingError):
        await solve(services, problem_text="   ")


async def test_marks_outside_write_are_dropped() -> None:
    raw = script("x = 2", ["2x = 4", "x = 2", "x = 2"])
    raw["solve"][0]["mark"] = {"type": "circle", "target": "4"}
    raw["solve"][1]["mark"] = {"type": "underline", "target": "y"}
    services = make_services(lambda name, m, n: raw)
    out = await solve(services, problem_text="2x + 3 = 7")
    assert out.script.steps[0].mark is not None and out.script.steps[0].mark.target == "4"
    assert out.script.steps[1].mark is None


async def test_uncertain_ocr_read_is_never_high(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_read(services: Any, png: str) -> Problem:
        return Problem("2x + 3 = 7", "2x + 3 = 7", "수학", "ocr", uncertain=True)

    monkeypatch.setattr(pipeline, "read_problem", fake_read)
    services = make_services(lambda name, m, n: script("x = 2", ["2x = 4", "x = 2", "x = 2"]))
    out = await solve(services, image_base64="UE5H")
    assert out.script.verified and out.script.confidence == "medium"


def test_to_steps_cleans_tts_and_katex_output() -> None:
    from studymate.solve.schema import to_steps

    steps = to_steps(
        [
            {
                "say": "좋아요! 😊 같이 해 봐요 ✨",
                "write": r"\text{\textit{x} = \frac{-\textit{b}}{2\textit{a}}}",
            },
            {"say": "판별식이에요.", "write": r"\text{판별식} = b^2 - 4ac"},
            {"say": "   ", "write": "x = 1"},
            {"say": "끝!", "write": "$x = 2$", "gesture": "fly", "emotion": "angry"},
        ]
    )
    assert [s.say for s in steps] == ["좋아요! 같이 해 봐요", "판별식이에요.", "끝!"]
    assert steps[0].write == r"x = \frac{-b}{2a}"
    assert steps[1].write == r"\text{판별식} = b^2 - 4ac"
    assert steps[2].write == "x = 2" and steps[2].gesture is None and steps[2].emotion is None


def test_prose_answers_are_not_compared_by_sympy() -> None:
    from studymate.verify import answers_equivalent

    assert not answers_equivalent("이산화탄소(CO₂)와 물(H₂O)이에요", "산소(O₂)와 물(H₂O)")
    assert answers_equivalent("x = 8입니다", "8")


def test_bare_korean_in_write_is_wrapped_for_katex() -> None:
    from studymate.solve.schema import to_steps

    steps = to_steps(
        [
            {"say": "a", "write": "이산화탄소"},
            {"say": "b", "write": r"\text{판별식} = b^2 - 4ac"},
            {"say": "c", "write": "x = 2 또는 x = 3"},
        ]
    )
    assert [s.write for s in steps] == [
        r"\text{이산화탄소}",
        r"\text{판별식} = b^2 - 4ac",
        r"x = 2 \text{ 또는 }x = 3",
    ]


async def test_roles_unit_and_only_solve_lines_are_verified() -> None:
    """Concept/check/summary lines are not equivalent forms of the problem and must not fail it."""

    def line(
        say: str, write: str, note: str, gesture: str = "write", emotion: str = "neutral"
    ) -> dict[str, Any]:
        return {"say": say, "write": write, "note": note, "gesture": gesture, "emotion": emotion}

    raw = {
        "problem_latex": "2x + 3 = 7",
        "intro": line("일차방정식이에요.", "2x + 3 = 7", ""),
        "concept": line("이항을 떠올려요.", r"a = b \Rightarrow a + c = b + c", "등식의 성질"),
        "solve": [
            line("3을 이항해요.", "2x = 7 - 3", "3 이항"),
            line("정리해요.", "2x = 4", "정리"),
            line("2로 나눠요.", "x = 2", "양변 ÷ 2", emotion="happy"),
        ],
        "check": line("대입해 봐요.", r"2 \times 2 + 3 = 7", "검산", "point", "happy"),
        "summary": line("이항, 정리, 나누기!", r"\text{이항 → 정리 → 나누기}", "", "nod", "happy"),
        "final_answer": "x = 2",
    }
    services = make_services(lambda name, m, n: raw)
    out = await solve(services, problem_text="2x + 3 = 7 을 푸시오.")
    assert out.script.verified and out.script.confidence == "high"
    assert out.script.unit == "중1 · 일차방정식"
    assert [s.role for s in out.script.steps] == [
        "intro",
        "concept",
        "solve",
        "solve",
        "solve",
        "check",
        "summary",
    ]
    assert out.script.steps[2].note == "3 이항"
    assert services.llm.unit_calls == 1
    system = services.llm.named("solve_script")[0]["messages"][0]["content"]
    assert "중1 · 일차방정식" in system and "이항" in system


def test_unsolved_unknowns_in_working_lines() -> None:
    from studymate.solve.pipeline import unsolved_unknowns
    from studymate.verify import analyze_problem

    parsed = analyze_problem("다음 연립방정식을 푸시오. $2x + y = 7$, $x - y = 2$")
    assert unsolved_unknowns(parsed, ["3x = 9", "x = 3"]) == ["y"]
    assert unsolved_unknowns(parsed, ["3x = 9", "x = 3", "3 - y = 2", "y = 1"]) == []
    assert unsolved_unknowns(parsed, ["x = 3, y = 1"]) == []
    assert unsolved_unknowns(analyze_problem("2x + 3 = 7"), ["x = 2"]) == []


async def test_unsolved_unknown_triggers_one_retry_and_falls_back() -> None:
    def line(say: str, write: str) -> dict[str, Any]:
        return {"say": say, "write": write, "note": "", "gesture": "write", "emotion": "neutral"}

    short = {
        "problem_latex": "2x + y = 7, x - y = 2",
        "solve": [line("더해요.", "3x = 9"), line("나눠요.", "x = 3")],
        "final_answer": "x = 3, y = 1",
    }
    services = make_services(lambda name, m, n: short)
    out = await solve(services, problem_text="다음 연립방정식을 푸시오. $2x + y = 7$, $x - y = 2$")
    # every attempt leaves y unsolved: the first verified script is kept, still "high"
    assert out.script.verified and out.script.confidence == "high"
    retries = services.llm.named("solve_script")
    assert len(retries) >= 2 and "y" in retries[1]["messages"][1]["content"]


async def test_non_math_subject_uses_evidence_lesson_and_agreement() -> None:
    def line(say: str, write: str, note: str = "") -> dict[str, Any]:
        return {"say": say, "write": write, "note": note, "gesture": "write", "emotion": "neutral"}

    lesson = {
        "analysis": "① 틀림 ② 틀림 ③ 3문단 근거로 맞음 ④ 틀림 ⑤ 틀림. 정답 ③.",
        "problem_latex": r"\text{빈칸 추론}",
        "intro": line("빈칸 추론 문제예요.", r"\text{빈칸에 들어갈 말}"),
        "concept": line("빈칸은 주제와 이어져요.", r"\text{빈칸 = 주제의 재진술}"),
        "solve": [
            line("3문단이 근거예요.", r"\text{3문단: cooperation}", "근거"),
            line("③이 맞아요.", "③", "③ ○"),
        ],
        "check": line("다시 확인해요.", "③", "확인"),
        "summary": line("재진술을 찾아요.", r"\text{재진술 찾기}"),
        "final_answer": "③",
    }

    def handler(name: str, messages: list[dict[str, Any]], n: int) -> dict[str, Any]:
        return {"work": "...", "final_answer": "③ cooperation"} if name == "resolve" else lesson

    services = make_services(handler)
    services.llm.subject, services.llm.unit_id = "english", "eng_blank"
    out = await solve(services, problem_text="다음 빈칸에 들어갈 말로 가장 적절한 것은? ① a ② b ③ c ④ d ⑤ e")
    assert out.script.confidence == "medium" and not out.script.verified
    assert out.script.final_answer == "③" and out.script.unit == "수능 영어 · 빈칸 추론"
    call = services.llm.named("solve_script")[0]
    assert call["schema"]["required"][0] == "analysis"
    assert "선택지" in call["messages"][0]["content"] and "analysis" in call["messages"][0]["content"]
    # the hidden scratch work never reaches the board or speech
    assert all("정답 ③" not in (s.say + (s.write or "")) for s in out.script.steps)


def test_english_sentence_on_board_is_wrapped_as_text() -> None:
    from studymate.solve.schema import lesson_steps

    steps = lesson_steps({"solve": [{"say": "봐요.", "write": "people tend to cooperate", "note": ""}]})
    assert steps[0].write == r"\text{people tend to cooperate}"
    assert lesson_steps({"solve": [{"say": "봐요.", "write": "x = 2", "note": ""}]})[0].write == "x = 2"


async def test_text_without_a_question_gets_no_lesson() -> None:
    """A capture of an answer or a heading: no lesson that repeats "there is no problem"."""
    from studymate.errors import UserFacingError

    services = make_services(lambda name, m, n: pytest.fail("no lesson for a non-problem"))
    services.llm.has_task = False
    with pytest.raises(UserFacingError) as exc:
        await solve(services, problem_text="제3장 이차방정식")
    assert exc.value.code == "no_problem"
    services.llm.has_task = True
    # nothing to read, or a bare answer: rejected before any model call
    for stray in ("③", "?", "-", "x = 3", "$y=-2.5$", "a = 7."):
        with pytest.raises(UserFacingError) as exc:
            await solve(services, problem_text=stray)
        assert exc.value.code == "no_problem"
    assert services.llm.unit_calls == 0


def _math_lesson(answer: str) -> dict[str, Any]:
    def line(say: str, write: str) -> dict[str, Any]:
        return {"say": say, "write": write, "note": "", "gesture": "write", "emotion": "neutral"}

    return {
        "analysis": "극값을 구해 n의 범위를 정한다.",
        "problem_latex": r"x^3 - 3x^2 - 9x + n = 0",
        "intro": line("실근의 개수 문제예요.", r"x^3 - 3x^2 - 9x + n = 0"),
        "concept": line("극값의 부호를 봐요.", r"f(-1)f(3) < 0"),
        "solve": [line("범위를 구해요.", r"-5 < n < 27")],
        "check": line("자연수만 세요.", r"n = 1, \dots, 26"),
        "summary": line("극값으로 개수를 정해요.", r"\text{극값의 부호}"),
        "final_answer": answer,
    }


HARD = "자연수 n에 대하여 방정식 x^3 - 3x^2 - 9x + n = 0의 서로 다른 실근의 개수가 3이 되도록 하는 자연수 n의 개수를 구하시오."


async def test_hard_math_gets_a_reasoning_pass_first() -> None:
    """A CSAT-level unit on a GPU: the model reasons (thinking mode) before the lesson, the
    lesson is written along that solution, and its answer is a vote."""

    def handler(name: str, messages: list[dict[str, Any]], n: int) -> dict[str, Any]:
        if name == "think":
            return {"outline": r"f(x) = x^3-3x^2-9x, f(-1)=5, f(3)=-27", "final_answer": "26"}
        if name == "resolve":
            return {"work": "...", "final_answer": "26"}
        return _math_lesson("26")

    services = make_services(handler)
    services.llama.on_gpu = True
    services.llm.unit_id = "s2_derivative_use"
    out = await solve(services, problem_text=HARD)
    think = services.llm.named("think")
    assert len(think) == 1 and think[0]["think"] is True
    lesson = services.llm.named("solve_script")[0]["messages"][1]["content"]
    assert "f(-1)=5" in lesson and "26" in lesson  # the lesson follows the reasoning pass
    assert out.script.final_answer == "26" and out.script.confidence == "medium"
    assert out.attempt_log[0]["think"] == "26"


async def test_reasoning_answer_is_kept_when_quick_resolves_disagree() -> None:
    def handler(name: str, messages: list[dict[str, Any]], n: int) -> dict[str, Any]:
        if name == "think":
            return {"outline": "극값 f(-1)=5, f(3)=-27", "final_answer": "26"}
        if name == "resolve":
            return {"work": "...", "final_answer": "5"}  # the quick re-solve misses the condition
        return _math_lesson("26")

    services = make_services(handler)
    services.llama.on_gpu = True
    services.llm.unit_id = "s2_derivative_use"
    out = await solve(services, problem_text=HARD)
    assert out.script.final_answer == "26" and out.script.confidence == "low"
    assert len(services.llm.named("solve_script")) == 1  # no retry toward the quick answer


async def test_no_reasoning_pass_on_cpu_or_for_basic_units() -> None:
    def handler(name: str, messages: list[dict[str, Any]], n: int) -> dict[str, Any]:
        if name == "resolve":
            return {"work": "...", "final_answer": "26"}
        return _math_lesson("26")

    cpu = make_services(handler)  # llama without on_gpu: CPU
    cpu.llm.unit_id = "s2_derivative_use"
    await solve(cpu, problem_text=HARD)
    assert cpu.llm.named("think") == []
    basic = make_services(handler)
    basic.llama.on_gpu = True  # middle-school unit: fast path
    await solve(basic, problem_text="2x + 3 = 7")
    assert basic.llm.named("think") == []
