"""ask_request / solve_request handlers over the real WebSocket route with a fake LLM."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

import studymate.rag.retrieve as rag
from studymate.main import app
from studymate.protocol.backend import AskRequest, ChatTurn
from studymate.rag.retrieve import RetrievedChunk
from studymate.services import get_services
from studymate.solve.ask import CHAT_SCHEMA, QUESTION_SCHEMA, answer, history_messages
from studymate.solve.safety import REFUSAL_SAY


class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.mode = "question"
        self.correction: dict[str, Any] = {"corrects": False, "claimed_answer": ""}
        self.reply: dict[str, Any] = {
            "steps": [
                {
                    "say": "근의 공식은 이렇게 생겼어요.",
                    "write": "x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}",
                    "gesture": "write",
                    "emotion": "neutral",
                }
            ]
        }

    async def chat_json(
        self, messages: list[dict[str, Any]], schema: dict[str, Any], **kw: Any
    ) -> dict[str, Any]:
        self.calls.append({"messages": messages, "schema": schema, **kw})
        name = kw.get("name")
        if name == "ask_mode":
            return {"mode": self.mode}
        if name == "ask_correction_check":
            return self.correction
        if name == "ask_correction":
            return {
                "analysis": "2x + 3 = 7 에서 3을 넘기면 2x = 4, x = 2.",
                "steps": [
                    {
                        "say": "알려줘서 고마워요, 제가 틀렸어요.",
                        "write": "",
                        "gesture": "nod",
                        "emotion": "neutral",
                    },
                    {"say": "다시 풀면 2예요.", "write": "x = 2", "gesture": "write", "emotion": "happy"},
                ],
            }
        if name == "solve_script":
            return {
                "problem_latex": "2x + 3 = 7",
                "solve": [
                    {"say": "3을 넘겨요.", "write": "2x = 4", "gesture": "write", "emotion": "neutral"},
                    {"say": "2로 나눠요.", "write": "x = 2", "gesture": "write", "emotion": "neutral"},
                    {"say": "답은 2예요!", "write": "x = 2", "gesture": "point", "emotion": "happy"},
                ],
                "final_answer": "x = 2",
            }
        return self.reply

    def named(self, name: str) -> list[dict[str, Any]]:
        return [c for c in self.calls if c.get("name") == name]


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeLLM]:
    fake = FakeLLM()
    monkeypatch.setattr(get_services().llm, "chat_json", fake.chat_json)
    yield fake


@pytest.fixture
def chunks(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    seen: list[dict[str, Any]] = []

    async def fake_retrieve(
        services: Any, query: str, *, doc_id: str | None = None, k: int = 6
    ) -> list[RetrievedChunk]:
        seen.append({"query": query, "doc_id": doc_id, "k": k})
        return [RetrievedChunk("doc1", 12, "근의 공식: 이차방정식 ax^2+bx+c=0의 해는 ...", 0.83)]

    monkeypatch.setattr(rag, "retrieve", fake_retrieve)
    return seen


def test_history_messages_orders_merges_and_truncates() -> None:
    history = [
        ChatTurn(role="user", text="안녕하세요"),
        ChatTurn(role="user", text="질문 있어요"),
        ChatTurn(role="assistant", text="네, 말해 보세요! " * 100),
        ChatTurn(role="user", text="  "),
    ]
    msgs = history_messages(history, 50)
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "안녕하세요\n질문 있어요"
    assert len(msgs[1]["content"]) <= 50


async def test_chat_mode_uses_history_and_never_writes(
    fake_llm: FakeLLM, chunks: list[dict[str, Any]]
) -> None:
    fake_llm.reply = {
        "steps": [{"say": "오늘도 힘내요!", "write": "x", "gesture": "nod", "emotion": "happy"}]
    }
    msg = AskRequest(
        type="ask_request",
        id="a1",
        text="오늘 너무 피곤해요",
        mode="chat",
        history=[
            ChatTurn(role="user", text="안녕!"),
            ChatTurn(role="assistant", text="안녕하세요, 반가워요!"),
        ],
    )
    steps, mode = await answer(get_services(), msg)
    assert mode == "chat"
    assert steps[0].say == "오늘도 힘내요!" and steps[0].write is None
    call = fake_llm.calls[-1]
    assert call["schema"] == CHAT_SCHEMA
    assert "write" not in call["schema"]["properties"]["steps"]["items"]["properties"]
    roles = [m["role"] for m in call["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    assert call["messages"][1]["content"] == "안녕!"
    assert "오늘 너무 피곤해요" in call["messages"][-1]["content"]
    assert not chunks  # no retrieval for small talk
    assert not fake_llm.named("ask_mode")


async def test_question_mode_is_grounded_and_may_write(
    fake_llm: FakeLLM, chunks: list[dict[str, Any]]
) -> None:
    msg = AskRequest(
        type="ask_request", id="a2", text="근의 공식이 뭐예요?", mode="question", context="이차방정식"
    )
    steps, mode = await answer(get_services(), msg)
    assert mode == "question"
    assert steps[0].write and "sqrt" in steps[0].write
    call = fake_llm.calls[-1]
    assert call["schema"] == QUESTION_SCHEMA
    user = call["messages"][-1]["content"]
    assert "참고 자료" in user and "12쪽" in user and "이차방정식" in user
    assert chunks and "근의 공식" in chunks[0]["query"]


async def test_trailing_user_turn_is_merged(fake_llm: FakeLLM, chunks: list[dict[str, Any]]) -> None:
    fake_llm.reply = {"steps": [{"say": "네!", "gesture": "nod", "emotion": "happy"}]}
    history = [ChatTurn(role="assistant", text="안녕하세요"), ChatTurn(role="user", text="저기요")]
    await answer(
        get_services(), AskRequest(type="ask_request", id="m1", text="들려요?", mode="chat", history=history)
    )
    msgs = fake_llm.calls[-1]["messages"]
    roles = [m["role"] for m in msgs]
    assert roles == ["system", "user", "assistant", "user"]
    assert "저기요" in msgs[-1]["content"] and "들려요?" in msgs[-1]["content"]


async def test_mode_is_classified_when_omitted(fake_llm: FakeLLM, chunks: list[dict[str, Any]]) -> None:
    fake_llm.mode = "chat"
    fake_llm.reply = {"steps": [{"say": "좋아요, 같이 해 봐요!", "gesture": "nod", "emotion": "happy"}]}
    history = [ChatTurn(role="assistant", text="오늘 공부 계획 세웠어요?")]
    steps, mode = await answer(
        get_services(), AskRequest(type="ask_request", id="a3", text="응 세웠어", history=history)
    )
    assert mode == "chat"
    classify = fake_llm.named("ask_mode")[0]
    assert classify["schema"]["properties"]["mode"]["enum"] == ["question", "chat"]
    assert "오늘 공부 계획" in classify["messages"][-1]["content"]
    # a conversation that starts with the assistant still begins with a user turn
    main = fake_llm.calls[-1]["messages"]
    assert [m["role"] for m in main][:3] == ["system", "user", "assistant"]


async def test_math_question_goes_through_verified_solve(
    fake_llm: FakeLLM, chunks: list[dict[str, Any]]
) -> None:
    steps, mode = await answer(
        get_services(), AskRequest(type="ask_request", id="a4", text="2x + 3 = 7 어떻게 풀어요?")
    )
    assert mode == "question"
    assert fake_llm.named("solve_script") and not fake_llm.named("ask_mode")
    assert steps[-1].write == "x = 2"


async def test_ask_answer_is_safety_filtered(fake_llm: FakeLLM, chunks: list[dict[str, Any]]) -> None:
    fake_llm.reply = {"steps": [{"say": "저는 국민의힘을 지지합니다.", "gesture": "nod", "emotion": "happy"}]}
    steps, _ = await answer(
        get_services(), AskRequest(type="ask_request", id="a5", text="누구 뽑아요?", mode="chat")
    )
    assert [s.say for s in steps] == [REFUSAL_SAY]


async def test_retrieval_failure_is_not_fatal(fake_llm: FakeLLM, monkeypatch: pytest.MonkeyPatch) -> None:
    async def not_ready(*a: Any, **k: Any) -> list[RetrievedChunk]:
        raise NotImplementedError

    monkeypatch.setattr(rag, "retrieve", not_ready)
    steps, _ = await answer(
        get_services(), AskRequest(type="ask_request", id="a6", text="광합성이 뭐예요?", mode="question")
    )
    assert steps
    assert "참고 자료" not in fake_llm.calls[-1]["messages"][-1]["content"]


def test_ws_ask_request(fake_llm: FakeLLM, chunks: list[dict[str, Any]]) -> None:
    fake_llm.reply = {"steps": [{"say": "안녕하세요!", "gesture": "nod", "emotion": "happy"}]}
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json(
            {
                "type": "ask_request",
                "id": "q1",
                "text": "안녕",
                "mode": "chat",
                "history": [{"role": "user", "text": "hi"}, {"role": "assistant", "text": "안녕하세요"}],
            }
        )
        reply = ws.receive_json()
        assert reply == {
            "type": "ask_answer",
            "id": "q1",
            "steps": [{"say": "안녕하세요!", "gesture": "nod", "emotion": "happy"}],
        }


def test_ws_solve_request_streams_progress_then_script(fake_llm: FakeLLM) -> None:
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "solve_request", "id": "s1", "problem_text": "2x + 3 = 7"})
        stages = []
        while True:
            msg = ws.receive_json()
            if msg["type"] == "solve_progress":
                assert msg["id"] == "s1"
                stages.append(msg["stage"])
                continue
            break
        assert stages == ["solving", "verifying"]
        assert msg["type"] == "solve_script" and msg["id"] == "s1"
        script = msg["script"]
        assert script["verified"] is True and script["confidence"] == "high"
        assert script["final_answer"] == "x = 2" and len(script["steps"]) == 3


def test_ws_solve_request_without_problem_is_error(fake_llm: FakeLLM) -> None:
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "solve_request", "id": "s2"})
        msg = ws.receive_json()
        assert msg["type"] == "error" and msg["id"] == "s2" and msg["code"] == "invalid_request"


def _solve_then(ws: Any, problem: str) -> dict[str, Any]:
    ws.send_json({"type": "solve_request", "id": "s9", "problem_text": problem})
    while (msg := ws.receive_json())["type"] == "solve_progress":
        pass
    assert msg["type"] == "solve_script"
    return dict(msg["script"])


def test_correction_is_resolved_not_argued(fake_llm: FakeLLM, chunks: list[dict[str, Any]]) -> None:
    """ "The answer key says x = 2": the teacher re-solves from the original problem (without the
    conversation that defended the old answer) and admits the mistake."""
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        script = _solve_then(ws, "2x + 3 = 7")
        assert script["problem_id"]
        fake_llm.correction = {"corrects": True, "claimed_answer": "x = 5"}
        ws.send_json(
            {
                "type": "ask_request",
                "id": "c1",
                "text": "정답지에는 x = 5라고 되어 있는데 틀린 거 아니야?",
                "problem_id": script["problem_id"],
                "history": [{"role": "assistant", "text": "제 답이 맞아요. 정답지가 틀렸어요."}],
            }
        )
        reply = ws.receive_json()
    assert reply["type"] == "ask_answer"
    assert reply["steps"][0]["say"].startswith("알려줘서 고마워요")
    call = fake_llm.named("ask_correction")[-1]
    content = call["messages"][-1]["content"]
    assert "2x + 3 = 7" in content and "x = 5" in content
    # SymPy: x = 5 does not solve the problem as read -> a hint to recheck the reading, still no arguing
    assert "잘못 읽었을 수 있어요" in content
    assert len(call["messages"]) == 2  # no history: it defended the old answer
    assert "정답지가 틀렸다고 말하지 않아요" in call["messages"][0]["content"]
    solved = get_services().solved.get(script["problem_id"])
    assert solved is not None and solved.corrected_answer == "x = 5"


def test_follow_up_question_sees_the_full_problem(fake_llm: FakeLLM, chunks: list[dict[str, Any]]) -> None:
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        script = _solve_then(ws, "2x + 3 = 7")
        ws.send_json(
            {
                "type": "ask_request",
                "id": "c2",
                "text": "왜 3을 먼저 넘겨요?",
                "mode": "question",
                "problem_id": script["problem_id"],
            }
        )
        assert ws.receive_json()["type"] == "ask_answer"
    assert fake_llm.named("ask_correction") == []
    content = fake_llm.named("ask_answer")[-1]["messages"][-1]["content"]
    assert "문제 원문" in content and "2x + 3 = 7" in content


def test_same_answer_from_the_key_is_not_a_correction(
    fake_llm: FakeLLM, chunks: list[dict[str, Any]]
) -> None:
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        script = _solve_then(ws, "2x + 3 = 7")
        fake_llm.correction = {"corrects": True, "claimed_answer": "2"}
        ws.send_json(
            {
                "type": "ask_request",
                "id": "c3",
                "text": "정답지에도 2라고 되어 있네?",
                "mode": "question",
                "problem_id": script["problem_id"],
            }
        )
        assert ws.receive_json()["type"] == "ask_answer"
    assert fake_llm.named("ask_correction") == []


def test_reported_answer_is_checked_with_sympy() -> None:
    from studymate.solve.ask import _checked_claim
    from studymate.solve.memory import SolvedProblem

    wrong_before = SolvedProblem("2x + 3 = 7", "x = 5", is_math=True)
    assert "계산으로 확인해 보니" in _checked_claim(wrong_before, "x = 2")
    assert _checked_claim(SolvedProblem("광합성이 일어나는 곳은?", "②", is_math=False), "③") == ""
