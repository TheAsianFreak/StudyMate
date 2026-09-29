"""The CSAT math eval set: ground truth recomputed independently, judge behaviour."""

from __future__ import annotations

from eval.problems_csat_math import PROBLEMS, SUBJECTS, correct_choice, gt_text, judge, validate_problems


def test_problems_are_valid() -> None:
    validate_problems()
    assert len(PROBLEMS) >= 40
    assert {p.subject for p in PROBLEMS} == set(SUBJECTS)
    assert any(p.multiple_choice for p in PROBLEMS) and any(not p.multiple_choice for p in PROBLEMS)


def test_judge() -> None:
    mc = next(p for p in PROBLEMS if p.id == "M2-01")  # ④ 4
    assert correct_choice(mc) == 4 and gt_text(mc) == "④ (4)"
    for good in ["④", "④ 4", "4", "정답: ④"]:
        assert judge(good, mc), good
    for bad in ["③", "3", "⑤ 4"]:
        assert not judge(bad, mc), bad
    short = next(p for p in PROBLEMS if p.id == "CA-04")  # ⑤ 3e
    assert judge("3e", short) and judge("⑤", short) and not judge("e^3", short)
