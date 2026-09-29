"""Quiz generation (generate -> independent re-solve -> agree -> SymPy) with a fake LLM."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

import studymate.learning.store as store
import studymate.rag.retrieve as rag
from studymate.config import get_settings
from studymate.main import app
from studymate.protocol.backend import GenerateQuiz, QuizItem
from studymate.quiz.generate import generate_quiz, item_schema
from studymate.rag.retrieve import RetrievedChunk
from studymate.services import get_services

Handler = Callable[[str, list[dict[str, Any]], dict[str, Any]], dict[str, Any]]

STEPS = [
    {"say": "5를 넘겨요.", "write": "2x = 16", "gesture": "write", "emotion": "neutral"},
    {"say": "2로 나눠요.", "write": "x = 8", "gesture": "write", "emotion": "happy"},
]


class FakeLLM:
    def __init__(self, handler: Handler) -> None:
        self.handler = handler
        self.calls: list[dict[str, Any]] = []

    async def chat_json(
        self, messages: list[dict[str, Any]], schema: dict[str, Any], **kw: Any
    ) -> dict[str, Any]:
        self.calls.append({"messages": messages, "schema": schema, **kw})
        return self.handler(kw.get("name", ""), messages, schema)

    def named(self, name: str) -> list[dict[str, Any]]:
        return [c for c in self.calls if c.get("name") == name]


def services_with(handler: Handler) -> Any:
    return SimpleNamespace(settings=get_settings(), llm=FakeLLM(handler))


# Different questions with the same answer (x = 8), in turn: a quiz never repeats a question.
QUESTIONS = [
    "2x - 5 = 11 일 때 x의 값은?",
    "3x - 4 = 20 일 때 x의 값은?",
    "x + 5 = 13 일 때 x의 값은?",
    "4x = 32 일 때 x의 값은?",
    "x - 3 = 5 일 때 x의 값은?",
    "5x = 40 일 때 x의 값은?",
]
_asked = iter(range(10**6))


def math_item(answer: str = "8", distractors: list[str] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "question_latex": QUESTIONS[next(_asked) % len(QUESTIONS)],
        "solution_steps": STEPS,
        "answer": answer,
    }
    if distractors is not None:
        out["distractors"] = distractors
    return out


def pick_correct(messages: list[dict[str, Any]], answer: str) -> dict[str, Any]:
    listed = messages[-1]["content"].split("보기:\n")[1].splitlines()
    for line in listed:
        num, _, text = line.partition(") ")
        if text == answer:
            return {"work": "...", "choice": int(num)}
    raise AssertionError("answer not among choices")


@pytest.fixture(autouse=True)
def no_rag_no_store(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"saved": [], "queries": [], "recent": []}

    async def fake_retrieve(
        services: Any, query: str, *, doc_id: str | None = None, k: int = 6
    ) -> list[RetrievedChunk]:
        state["queries"].append((query, doc_id, k))
        if doc_id == "doc1":
            return [
                RetrievedChunk("doc1", 12, "일차방정식의 풀이: 이항을 이용해 x의 값을 구한다. " * 20, 0.9)
            ]
        return []

    def fake_save(services: Any, items: list[QuizItem]) -> None:
        state["saved"].extend(items)

    monkeypatch.setattr(rag, "retrieve", fake_retrieve)
    monkeypatch.setattr(store, "save_quiz_items", fake_save)
    monkeypatch.setattr(store, "recent_questions", lambda services, subject, unit, limit=30: state["recent"])
    return state


def req(**kw: Any) -> GenerateQuiz:
    base = {
        "type": "generate_quiz",
        "id": "g1",
        "subject": "수학",
        "unit": "일차방정식",
        "difficulty": "normal",
        "count": 2,
    }
    base.update(kw)
    return GenerateQuiz(**base)


async def test_math_items_are_verified_high(no_rag_no_store: dict[str, Any]) -> None:
    def handler(name: str, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        if name == "quiz_item":
            mc = "distractors" in schema["properties"]
            return math_item("8", ["3", "-8", "16"] if mc else None)
        if "choice" in schema["properties"]:
            return pick_correct(messages, "8")
        return {"work": "2x=16", "final_answer": "x = 8"}

    services = services_with(handler)
    done: list[tuple[int, int]] = []

    async def progress(d: int, t: int) -> None:
        done.append((d, t))

    items = await generate_quiz(services, req(source_doc_id="doc1"), progress)
    assert len(items) == 2 and done == [(1, 2), (2, 2)]
    mc, sa = items
    assert mc.choices is not None and len(mc.choices) == 4 and mc.answer in mc.choices
    assert sa.choices is None
    assert all(i.confidence == "high" for i in items)
    assert mc.item_id != sa.item_id and len(mc.item_id) == 36
    assert mc.source is not None and mc.source.doc_id == "doc1" and mc.source.page == 12
    assert mc.source.excerpt and len(mc.source.excerpt) <= 200
    assert no_rag_no_store["saved"] == items
    assert no_rag_no_store["queries"][0][1] == "doc1"
    # re-solve runs in a fresh context: system + one user message, and never sees the answer key
    for call in services.llm.named("quiz_resolve"):
        assert len(call["messages"]) == 2
        assert "solution" not in call["messages"][1]["content"]
    # the second item is told what was already asked
    assert "이미 낸 문제" in services.llm.named("quiz_item")[1]["messages"][1]["content"]


async def test_short_answer_wrong_then_right() -> None:
    answers = iter(["9", "8"])

    def handler(name: str, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        if name == "quiz_item":
            return math_item(next(answers))
        return {"work": "", "final_answer": "9" if len(services.llm.named("quiz_item")) == 1 else "x = 8"}

    services = services_with(handler)
    from studymate.quiz import generate as gen

    item = await gen.generate_item(services, req(count=1), "short_answer", 0, None, [])
    assert item is not None and item.answer == "8" and item.confidence == "high"
    assert len(services.llm.named("quiz_item")) == 2  # first draft rejected by SymPy despite agreement


async def test_disagreement_drops_item_after_max_attempts() -> None:
    def handler(name: str, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        if name == "quiz_item":
            return {
                "question_latex": "광합성이 일어나는 세포 소기관은?",
                "solution_steps": STEPS[:2],
                "answer": "엽록체",
            }
        return {"work": "", "final_answer": "미토콘드리아"}

    services = services_with(handler)
    items = await generate_quiz(services, req(subject="과학", unit=None, count=2), None)
    assert items == []
    # two slots per item asked for, plus two spare ones: bounded, not endless
    assert len(services.llm.named("quiz_item")) == (2 + 2) * get_settings().quiz.max_attempts


async def test_non_math_agreement_is_medium() -> None:
    def handler(name: str, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        if name == "quiz_item":
            return {
                "question_latex": "광합성이 일어나는 세포 소기관은?",
                "solution_steps": STEPS[:2],
                "answer": "엽록체",
            }
        return {"work": "", "final_answer": "엽록체입니다."}

    services = services_with(handler)
    from studymate.quiz import generate as gen

    item = await gen.generate_item(services, req(subject="과학"), "short_answer", 1, None, [])
    assert item is not None and item.confidence == "medium"


async def test_multiple_choice_with_two_correct_choices_is_rejected() -> None:
    def handler(name: str, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        if name == "quiz_item":
            return math_item("8", ["x = 8", "3", "5"])
        return pick_correct(messages, "8")

    services = services_with(handler)
    from studymate.quiz import generate as gen

    assert await gen.generate_item(services, req(), "multiple_choice", 0, None, []) is None


async def test_unsafe_question_is_rejected() -> None:
    def handler(name: str, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        if name == "quiz_item":
            return {
                "question_latex": "이번 선거에서 누구를 찍어야 할까요? 국민의힘을 지지합니다",
                "solution_steps": STEPS,
                "answer": "2번",
            }
        return {"work": "", "final_answer": "2번"}

    services = services_with(handler)
    from studymate.quiz import generate as gen

    assert await gen.generate_item(services, req(subject="사회"), "short_answer", 0, None, []) is None


def test_item_schema_shapes() -> None:
    mc, sa = item_schema("multiple_choice"), item_schema("short_answer")
    assert mc["properties"]["distractors"]["minItems"] == 3 == mc["properties"]["distractors"]["maxItems"]
    assert "distractors" not in sa["properties"]
    assert mc["required"][-1] == "distractors" and sa["required"] == [
        "question_latex",
        "solution_steps",
        "answer",
    ]


def test_ws_generate_quiz(monkeypatch: pytest.MonkeyPatch, no_rag_no_store: dict[str, Any]) -> None:
    def handler(name: str, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        if name == "quiz_item":
            return math_item("8", ["3", "-8", "16"] if "distractors" in schema["properties"] else None)
        if "choice" in schema["properties"]:
            return pick_correct(messages, "8")
        return {"work": "", "final_answer": "8"}

    fake = FakeLLM(handler)
    monkeypatch.setattr(get_services().llm, "chat_json", fake.chat_json)
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json(
            {"type": "generate_quiz", "id": "g9", "subject": "수학", "difficulty": "easy", "count": 2}
        )
        progress = []
        while True:
            msg = ws.receive_json()
            if msg["type"] != "quiz_progress":
                break
            progress.append((msg["done"], msg["total"]))
        assert progress == [(0, 2), (1, 2), (2, 2)]
        assert msg["type"] == "quiz_items" and msg["id"] == "g9" and len(msg["items"]) == 2
        assert {i["confidence"] for i in msg["items"]} == {"high"}
        assert len(no_rag_no_store["saved"]) == 2


def test_is_repeat() -> None:
    from studymate.quiz.generate import is_repeat

    earlier = [r"2x - 5 = 11 일 때 x의 값은?", r"\text{광합성이 일어나는 세포 소기관은?}"]
    assert is_repeat("2x-5=11일 때 x의 값은?", earlier)  # spacing only
    assert is_repeat("2x - 5 = 11 일 때, x의 값을 구하시오.", earlier)  # reworded, same numbers
    assert is_repeat("광합성이 일어나는 세포 소기관은?", earlier)  # \text{} wrapper only
    assert not is_repeat("2x - 7 = 11 일 때 x의 값은?", earlier)  # other numbers: a new question
    assert not is_repeat("세포 호흡이 일어나는 세포 소기관은?", earlier)


def drafting(questions: list[str], disagree_first: int = 0) -> Handler:
    """Fake model: proposes `questions` in order (answer 8, options when asked); the first
    `disagree_first` re-solves disagree."""
    drafts = iter(questions)
    resolves = iter(range(10**6))

    def handler(name: str, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        if name == "quiz_item":
            out = {"question_latex": next(drafts), "solution_steps": STEPS, "answer": "8"}
            if "distractors" in schema["properties"]:
                out["distractors"] = ["3", "-8", "16"]
            return out
        if next(resolves) < disagree_first:
            return {
                "work": "",
                "final_answer": "7",
                "choice": 1 if "choice" in schema["properties"] else None,
            }
        if "choice" in schema["properties"]:
            return pick_correct(messages, "8")
        return {"work": "", "final_answer": "8"}

    return handler


async def test_same_question_again_is_replaced_and_count_is_kept() -> None:
    """The model keeps proposing one question: only one copy is kept, the rest are replaced
    by new questions, and the quiz still has the number asked for."""
    services = services_with(drafting([QUESTIONS[0]] * 3 + QUESTIONS[1:]))
    items = await generate_quiz(services, req(count=3), None)
    questions = [i.question_latex for i in items]
    assert len(items) == 3 and len(set(questions)) == 3


async def test_failed_items_are_replaced_until_the_count() -> None:
    services = services_with(drafting(QUESTIONS * 3, disagree_first=4))
    items = await generate_quiz(services, req(count=2), None)
    assert len(items) == 2


async def test_recent_questions_are_not_asked_again(no_rag_no_store: dict[str, Any]) -> None:
    no_rag_no_store["recent"] = [QUESTIONS[0]]
    services = services_with(drafting([QUESTIONS[0], QUESTIONS[1]]))
    items = await generate_quiz(services, req(count=1), None)
    assert [i.question_latex for i in items] == [QUESTIONS[1]]
    assert QUESTIONS[0] in services.llm.named("quiz_item")[0]["messages"][1]["content"]


async def test_each_quiz_uses_new_seeds() -> None:
    def handler(name: str, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        if name == "quiz_item":
            return math_item("8", ["3", "-8", "16"] if "distractors" in schema["properties"] else None)
        if "choice" in schema["properties"]:
            return pick_correct(messages, "8")
        return {"work": "", "final_answer": "8"}

    first, second = services_with(handler), services_with(handler)
    await generate_quiz(first, req(count=1), None)
    await generate_quiz(second, req(count=1), None)
    seed = lambda s: s.llm.named("quiz_item")[0]["seed"]  # noqa: E731
    assert seed(first) != seed(second)
