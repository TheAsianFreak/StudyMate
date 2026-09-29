from __future__ import annotations

import pytest

from studymate.protocol.backend import Mark, ScriptStep
from studymate.solve.safety import REFUSAL_SAY, filter_steps, is_unsafe, safety_prompt


@pytest.mark.parametrize(
    "text",
    [
        "이번 선거에서는 꼭 2번을 찍으세요.",
        "국민의힘을 지지합니다.",
        "더불어민주당은 최악이에요.",
        "대통령은 탄핵해야 해요.",
        "하나님을 믿으세요. 그래야 구원받아요.",
        "불교는 가짜 종교예요.",
        "교회에 다니세요!",
        "외국인들은 다 없어져야 해요.",
        "여자는 수학을 못해서 열등해요.",
        "이 씨 발 문제 뭐야",
        "너 진짜 병신이구나",
        r"\text{짱깨}",
    ],
)
def test_unsafe_texts_are_flagged(text: str) -> None:
    assert is_unsafe(text)


@pytest.mark.parametrize(
    "text",
    [
        "양변에 2를 곱해요. 그러면 x는 8이에요!",
        "시발점에서 출발한 기차의 속력을 구해 봐요.",
        "정의에 따라 계산하면 돼요.",
        "고려 시대에는 불교를 믿었어요.",
        "삼권분립에서 정부는 법을 집행하는 역할을 해요.",
        "불이 꺼져도 계속 공부할 거예요?",
        "좋은 질문이에요! 함수의 정의부터 볼까요?",
        "민주주의의 기본 원리는 국민 주권이에요.",
        "x = 2 \\text{ 또는 } x = 3",
        "",
    ],
)
def test_study_texts_pass(text: str) -> None:
    assert not is_unsafe(text)


def test_filter_steps_replaces_offending_steps_once() -> None:
    steps = [
        ScriptStep(say="먼저 식을 정리해요.", write="2x = 4"),
        ScriptStep(say="그런데 국민의힘을 지지합니다."),
        ScriptStep(say="교회에 다니세요!"),
        ScriptStep(say="답은 x는 2예요.", write="x = 2", mark=Mark(type="circle", target="x = 2")),
    ]
    out, flagged = filter_steps(steps)
    assert flagged
    assert [s.say for s in out] == ["먼저 식을 정리해요.", REFUSAL_SAY, "답은 x는 2예요."]
    assert out[1].write is None


def test_filter_checks_write_and_mark() -> None:
    out, flagged = filter_steps([ScriptStep(say="이걸 보세요.", write=r"\text{대통령 탄핵해야 해요}")])
    assert flagged and out[0].say == REFUSAL_SAY
    out, flagged = filter_steps(
        [ScriptStep(say="좋아요.", write="x", mark=Mark(type="arrow", target="병신"))]
    )
    assert flagged


def test_filter_never_returns_empty() -> None:
    out, flagged = filter_steps([])
    assert len(out) == 1 and not flagged


def test_prompt_clause_mentions_politics_and_religion() -> None:
    assert "정치" in safety_prompt() and "종교" in safety_prompt() and "공격" in safety_prompt()
