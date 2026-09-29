from __future__ import annotations

import time

import pytest

from studymate.learning.grade import choice_index, display_answer, equivalent, grade
from studymate.protocol.backend import QuizItem, Solution


def item(answer: str, choices: list[str] | None = None) -> QuizItem:
    return QuizItem(
        item_id="q_test",
        subject="수학",
        difficulty="normal",
        question_latex="?",
        choices=choices,
        answer=answer,
        solution=Solution(steps=[]),
        confidence="high",
    )


@pytest.mark.parametrize(
    ("user", "key", "expected"),
    [
        # variable prefix / plain value
        ("8", "x=8", True),
        ("x = 8", "8", True),
        ("x=8", "x = 8", True),
        ("8 = x", "x=8", True),
        ("9", "x=8", False),
        # fractions / decimals / LaTeX
        ("1/2", "0.5", True),
        ("0.5", r"\frac{1}{2}", True),
        (r"\dfrac{1}{2}", "1/2", True),
        (r"$\frac{3}{4}$", "0.75", True),
        (r"\frac{1}{2}", "½", True),
        ("-1/2", r"-\frac{1}{2}", True),
        ("−3", "-3", True),
        # fullwidth / whitespace
        ("２x＋２", "2(x+1)", True),
        ("  8  ", "8", True),
        # algebra
        ("2x+2", "2(x+1)", True),
        ("x²+2x+1", "(x+1)^2", True),
        ("x^2+2x+1", r"(x+1)^{2}", True),
        ("x^2+2x", "(x+1)^2", False),
        ("2x", "2y", False),
        ("abc", "a*b*c", True),
        ("3π", r"3\pi", True),
        (r"\sin x", "sin(x)", True),
        # roots
        ("√2", r"\sqrt{2}", True),
        ("2√2", r"\sqrt{8}", True),
        (r"\sqrt[3]{8}", "2", True),
        # equations / inequalities
        ("y=2x+1", "2x+1=y", True),
        ("2x-y+1=0", "y=2x+1", True),
        ("4x-2y+2=0", "y=2x+1", True),
        ("x>3", "3<x", True),
        ("x ≥ 3", "3 ≤ x", True),
        (r"x \geq 3", "x>=3", True),
        ("x>3", "x>=3", False),
        ("x<3", "x>3", False),
        ("2x>6", "x>3", True),
        ("-x>-3", "x>3", False),
        ("1<x<3", "3>x>1", True),
        # several solutions
        ("x=2, x=-2", "x=±2", True),
        ("-2, 2", r"x = \pm 2", True),
        ("x=2 또는 x=3", "x=3, 2", True),
        ("x=2", "x=±2", False),
        ("x = 1 ± √2", "1+sqrt(2), 1-sqrt(2)", True),
        ("x=2, y=3", "y=3, x=2", True),
        ("x=3, y=2", "x=2, y=3", False),
        ("x=2(중근)", "x=2", True),
        # ordered pairs
        ("(1, 2)", "(1,2)", True),
        ("(1, 2)", "(2, 1)", False),
        # units
        ("8cm", "8", True),
        ("8 cm", "8cm", True),
        ("8m", "8cm", False),
        ("8개", "8", True),
        ("12㎠", "12cm²", True),
        ("90°", r"90^\circ", True),
        ("50%", "50", True),
        ("1,000", "1000", True),
        ("1,000원", "1000원", True),
        # Korean phrasing
        ("정답은 8입니다.", "8", True),
        ("답: 8", "8", True),
        ("광합성", "광합성", True),
        ("광 합성", "광합성", True),
        ("엽록체", "광합성", False),
        ("답변", "변", False),
        # rounding: accepted only for irrational / non-terminating keys with >= 2 places
        ("1.41", r"\sqrt{2}", True),
        ("1.414", r"\sqrt{2}", True),
        ("1.4", r"\sqrt{2}", False),
        ("1.42", r"\sqrt{2}", False),
        ("0.33", "1/3", True),
        ("3.14", r"\pi", True),
        ("2.46", "2.456", False),
        # O/X
        ("O", "참", True),
        ("맞다", "O", True),
        ("X", "O", False),
        ("틀림", "X", True),
        ("true", "O", True),
        # garbage never raises
        ("", "8", False),
        ("8", "", False),
        ("2^(10^10)", "1", False),
        ('__import__("os").system("x")', "1", False),
        ("((((", "1", False),
        (r"\frac{1}{", "1", False),
        ("x=", "x=8", False),
        ("=", "=", True),
        (r"\unknown{3}", "3", False),
        ("1/0", "1", False),
    ],
)
def test_equivalent(user: str, key: str, expected: bool) -> None:
    assert equivalent(user, key) is expected


def test_equivalent_is_fast_on_hostile_input() -> None:
    start = time.perf_counter()
    for text in ["9^9^9^9", "x^100000", "2^(10^10)", "(" * 200 + "1" + ")" * 200, "1" * 400, "10^1000!"]:
        equivalent(text, "1")
    assert time.perf_counter() - start < 3.0


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("8", 2),
        ("③", 2),
        ("3번", 2),
        ("(3)", 2),
        ("3)", 2),
        ("정답은 3번", 2),
        ("C", 2),
        ("c)", 2),
        ("x=8", 2),
        ("8.0", 2),
        ("3", 2),  # "3" is not a choice text -> index
        ("6", 0),
        ("②", 1),
        ("10", None),
        ("", None),
    ],
)
def test_choice_index(answer: str, expected: int | None) -> None:
    assert choice_index(answer, ["6", "7", "8", "9"]) == expected


def test_choice_value_beats_index() -> None:
    # "2" is a choice text here, so it means the value 2 (choice ①), not choice ②.
    assert choice_index("2", ["2", "4", "6", "8"]) == 0
    assert choice_index("②", ["2", "4", "6", "8"]) == 1


def test_choice_math_equivalence_and_labels() -> None:
    assert choice_index("0.5", [r"\frac{1}{3}", r"\frac{1}{2}"]) == 1
    assert choice_index("① 1/3", ["1/3", "1/2"]) == 0
    assert choice_index("1/2", ["① 1/3", "② 1/2"]) == 1


def test_grade_multiple_choice() -> None:
    q = item("8", ["6", "7", "8", "9"])
    for ok in ["8", "③", "3번", "C", "x = 8", "3"]:
        assert grade(q, ok), ok
    for wrong in ["7", "②", "2", "B", "", "  ", "잘 모르겠어요"]:
        assert not grade(q, wrong), wrong
    # key stored as an index
    assert grade(item("③", ["6", "7", "8", "9"]), "8")
    assert grade(item("3", ["6", "7", "8", "9"]), "8")
    assert display_answer(item("③", ["6", "7", "8", "9"])) == "8"
    assert display_answer(item("x=8")) == "x=8"


def test_grade_free_form() -> None:
    q = item("x = 8")
    assert grade(q, "8")
    assert grade(q, "x=8")
    assert not grade(q, "x=-8")
