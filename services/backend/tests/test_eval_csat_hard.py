"""The hard CSAT math eval set: ground truth recomputed independently, judge behaviour."""

from __future__ import annotations

from collections import Counter

from eval.problems_csat_hard import (
    PROBLEMS,
    SUBJECT_COUNTS,
    SUBJECTS,
    correct_choice,
    gt_text,
    judge,
    validate_problems,
)


def test_problems_are_valid() -> None:
    validate_problems()  # every truth() equals the stored value, options hold the answer once
    assert len(PROBLEMS) == 20
    assert len({p.id for p in PROBLEMS}) == len(PROBLEMS)
    assert set(SUBJECT_COUNTS) == set(SUBJECTS)
    assert Counter(p.subject for p in PROBLEMS) == Counter(SUBJECT_COUNTS)
    mc = [p for p in PROBLEMS if p.multiple_choice]
    assert 6 <= len(mc) <= 12  # both 5지선다 and 단답형
    for p in PROBLEMS:
        assert "[4점]" in p.text and p.derivation.strip()
        if p.multiple_choice:
            assert len(p.choices) == 5 and correct_choice(p) is not None
        else:
            assert p.answer.is_Integer and 1 <= int(p.answer) <= 999


def test_judge() -> None:
    mc = next(p for p in PROBLEMS if p.id == "HPS-02")  # ③ 45/101
    assert correct_choice(mc) == 3 and gt_text(mc) == "③ (\\frac{45}{101})"
    for good in ["③", "③ \\frac{45}{101}", "\\frac{45}{101}", "정답: ③"]:
        assert judge(good, mc), good
    for bad in ["②", "\\frac{40}{101}", "⑤ \\frac{45}{101}"]:
        assert not judge(bad, mc), bad
    series = next(p for p in PROBLEMS if p.id == "HCA-02")  # ② 1/(2(e^pi - 1))
    assert judge("②", series) and judge("\\frac{1}{2(e^{\\pi} - 1)}", series)
    assert not judge("\\frac{1}{2(e^{\\pi} + 1)}", series)
    short = next(p for p in PROBLEMS if p.id == "HM1-01")
    assert gt_text(short) == "473" and judge("473", short) and not judge("474", short)


def test_registered_in_run_eval() -> None:
    from eval.run_eval import SETS

    s = SETS["csat-hard"]()
    assert s.name == "csat-hard" and s.problems is PROBLEMS
    assert s.category(PROBLEMS[0]) == PROBLEMS[0].subject
    assert s.localize("문제", "en") == "문제"  # Korean problems in every run
