"""The CSAT (non-math) evaluation set is well-formed, and the runner reads option answers."""

from __future__ import annotations

from collections import Counter

import pytest

from eval.problems_csat import (
    INLINE_OPTION_SUBTYPES,
    MARKS,
    PROBLEMS,
    SUBJECT_AREA,
    SUBTYPES,
    CsatProblem,
    option_lines,
    validate_problems,
)
from eval.run_csat import judge, predicted_choice
from studymate.verify.answer import answers_equivalent


def test_set_validates() -> None:
    validate_problems(PROBLEMS)


def test_ids_unique() -> None:
    assert len({p.id for p in PROBLEMS}) == len(PROBLEMS)


@pytest.mark.parametrize("p", PROBLEMS, ids=lambda p: p.id)
def test_item_labels_and_answer(p: CsatProblem) -> None:
    assert p.subject in SUBJECT_AREA
    assert p.subtype in SUBTYPES[p.subject]
    assert p.answer in MARKS
    assert p.answer in p.text
    assert p.rationale.strip()
    if p.subtype in INLINE_OPTION_SUBTYPES:
        assert [p.text.count(m) for m in MARKS] == [1] * 5
        assert [p.text.find(m) for m in MARKS] == sorted(p.text.find(m) for m in MARKS)
    else:
        opts = option_lines(p.text)
        assert [o[:1] for o in opts] == list(MARKS)
        assert all(o[1:].strip() for o in opts)
        assert len({o[1:].strip() for o in opts}) == 5  # no duplicated option


def test_coverage() -> None:
    assert 70 <= len(PROBLEMS) <= 90
    per_subject = Counter(p.subject for p in PROBLEMS)
    for subject, area in SUBJECT_AREA.items():
        need = {"사회탐구": 2, "과학탐구": 3}.get(area, 5)
        assert per_subject[subject] >= need, subject
    korean = {p.subtype for p in PROBLEMS if p.subject == "국어"}
    assert {"독서-인문", "독서-사회", "독서-과학", "독서-기술", "화법과 작문", "언어와 매체"} <= korean
    assert {"문학-현대시", "문학-고전시가", "문학-현대소설", "문학-고전소설"} <= korean
    assert sum(len(p.text) >= 800 for p in PROBLEMS if p.subject == "국어") >= 4  # long passages
    # the answers are spread over the five positions
    assert min(Counter(p.answer for p in PROBLEMS).values()) >= len(PROBLEMS) // 8


def test_judge_accepts_option_forms() -> None:
    for final in ("③", "③ 이성계", "3번", "정답은 ③번입니다."):
        assert answers_equivalent(final, "③"), final
    assert not answers_equivalent("②", "③")


def _item(pid: str) -> CsatProblem:
    return next(p for p in PROBLEMS if p.id == pid)


def test_predicted_choice_reads_numbers_and_option_text() -> None:
    ph02 = _item("PH02")  # options ㄱ / ㄷ / ㄱ, ㄴ / ㄴ, ㄷ / ㄱ, ㄴ, ㄷ
    assert predicted_choice("③ ㄱ, ㄴ", ph02) == 3
    assert predicted_choice("ㄱ, ㄴ", ph02) == 3
    assert predicted_choice("ㄱ,ㄴ,ㄷ", ph02) == 5
    assert predicted_choice("3", ph02) == 3
    assert predicted_choice("잘 모르겠어요", ph02) is None
    en13 = _item("EN13")
    assert predicted_choice("(B)-(A)-(C)", en13) == 2
    hi03 = _item("HI03")
    assert predicted_choice("전국의 서원을 정리하여 47개소만 남겼다", hi03) == 1


def test_judge_rejects_several_options() -> None:
    le01 = _item("LE01")  # key ②
    assert judge("②", le01)["correct"]
    assert judge("② 을은 형벌을 정할 때 범죄 예방 효과를 고려해야 한다고 본다.", le01)["correct"]
    for final in ("②, ③", "②④", "2번과 3번"):
        verdict = judge(final, le01)
        assert verdict["multiple_options"] and not verdict["correct"] and not verdict["correct_lenient"], (
            final
        )
    ph02 = _item("PH02")  # key ③ = ㄱ, ㄴ
    assert judge("ㄱ, ㄴ", ph02) == {
        "predicted": 3,
        "multiple_options": False,
        "correct": False,  # not an option number: counted only as lenient
        "correct_lenient": True,
    }
