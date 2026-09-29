from __future__ import annotations

import pytest

from studymate.verify import analyze_problem, answers_equivalent, parse_answer, verify_answer, verify_solution
from studymate.verify.latex import parse_math, sym, to_plain

x, y, a = sym("x"), sym("y"), sym("a")


@pytest.mark.parametrize(
    ("latex", "expected"),
    [
        (r"\frac{x}{2} + 3", x / 2 + 3),
        (r"\dfrac{2x-1}{3}", (2 * x - 1) / 3),
        (r"3(x-2)", 3 * x - 6),
        (r"x(x+1)", x * (x + 1)),
        (r"0.5x - 1.2", x / 2 - 6 / 5),
        (r"2 \times 3 \div 4", 6 / 4),
        (r"x^{2} - 5x + 6", x**2 - 5 * x + 6),
        (r"\sqrt{12}", 2 * 3**0.5),
        (r"\sqrt 12", 2 * 3**0.5),
        ("x² − 1", x**2 - 1),
        (r"\left( x + 1 \right)", x + 1),
        (r"-\frac{1}{2}", -0.5),
    ],
)
def test_parse_math(latex: str, expected: object) -> None:
    plain = to_plain(latex)
    assert plain is not None
    got = parse_math(plain)
    assert got is not None
    import sympy

    assert (
        abs(complex(sympy.N(got - sympy.nsimplify(expected), 20)).real) < 1e-9
        if not got.free_symbols
        else sympy.simplify(got - sympy.nsimplify(expected)) == 0
    )


@pytest.mark.parametrize(
    "bad",
    [
        "__import__('os')",
        "x" * 500,
        r"\unknowncmd{x}",
        "2**99999",
        "import os",
        "lambda: 1",
        "",
        "(((",
        "x_1",
    ],
)
def test_parse_math_rejects_garbage(bad: str) -> None:
    plain = to_plain(bad)
    assert plain is None or parse_math(plain) is None


CORRECT = [
    ("다음 방정식을 푸시오. 2x + 3 = 7", ["2x = 4", "x = 2"], "x = 2"),
    (r"\frac{x}{2} + 3 = 7", [r"\frac{x}{2} = 4", "x = 8"], "x = 8"),
    (r"\text{방정식 } 3(x-2) = 2x + 5 \text{의 해를 구하시오.}", ["3x - 6 = 2x + 5", "x = 11"], "x = 11"),
    ("0.3x - 1.2 = 0.5x + 0.4", ["3x - 12 = 5x + 4", "-2x = 16", "x = -8"], "x = -8"),
    ("x^2 - 5x + 6 = 0", ["(x-2)(x-3) = 0", "x = 2", "x = 3"], r"x = 2 \text{ 또는 } x = 3"),
    ("x^2 - 5x + 6 = 0", ["(x-2)(x-3) = 0"], "x = 2, 3"),
    (
        r"\begin{cases} x + y = 5 \\ x - y = 1 \end{cases}",
        ["2x = 6", "x = 3", "3 + y = 5", "y = 2"],
        "x = 3, y = 2",
    ),
    ("연립방정식 x + y = 5, x - y = 1을 푸시오", ["2x = 6"], "(x, y) = (3, 2)"),
    ("연립방정식 2x + y = 7, x - y = 2", [], r"x = 3 \text{이고 } y = 1"),
    ("2x - 1 > 5", ["2x > 6", "x > 3"], "x > 3"),
    (r"-2x + 1 \le 7", [r"-2x \le 6", r"x \ge -3"], r"x \ge -3"),
    (r"-1 < 2x + 1 \le 5", [r"-2 < 2x \le 4"], r"-1 < x \le 2"),
    (r"3 + 4 \times 2 \text{를 계산하시오}", ["= 3 + 8", "= 11"], "11"),
    (r"(-3)^2 - 4 \div 2 \text{의 값을 구하시오}", ["9 - 2 = 7"], "7"),
    ("x = 2일 때, 3x + 1의 값을 구하시오.", [r"3 \times 2 + 1 = 7"], "7"),
    ("x = 2가 방정식 ax + 3 = 7의 해일 때, 상수 a의 값을 구하시오.", ["2a + 3 = 7", "a = 2"], "a = 2"),
    ("x^2 = 2", [], r"x = \pm \sqrt{2}"),
    ("x^2 + 1 = 0", [], "해가 없다"),
    ("2(x+1) = 2x + 2", [], "해가 무수히 많다"),
    ("2(x + 3) - x 를 간단히 하시오", ["= 2x + 6 - x", "= x + 6"], "x + 6"),
    ("2x + y = 5를 y에 대하여 푸시오", [], "y = -2x + 5"),
    (r"\frac{x-1}{2} = \frac{x+2}{3}", ["3(x-1) = 2(x+2)", "3x - 3 = 2x + 4", "x = 7"], "x = 7"),
    ("$5x - 4 = 3x + 8$", [r"\text{이항하면 } 5x - 3x = 8 + 4", "2x = 12", r"\therefore x = 6"], "x=6"),
    ("x - 7 = -3", ["x = -3 + 7 = 4"], "x = 4입니다."),
    ("3x = 2", [], r"x = \frac{2}{3}"),
    ("3x = 2", [], r"x \approx 0.67"),
    ("① 2x = 4를 푸시오", [], "x = 2"),
]


@pytest.mark.parametrize(("problem", "writes", "answer"), CORRECT)
def test_correct_solutions_verify(problem: str, writes: list[str], answer: str) -> None:
    r = verify_solution(problem, writes, answer)
    assert r.parsed, r.detail
    assert r.verified, r.detail


WRONG_ANSWER = [
    ("2x + 3 = 7", "x = 5"),
    ("x^2 - 5x + 6 = 0", "x = 2"),  # incomplete
    ("x^2 - 5x + 6 = 0", "x = 2, 4"),
    ("연립방정식 x + y = 5, x - y = 1", "x = 3"),  # missing y
    ("연립방정식 x + y = 5, x - y = 1", "x = 2, y = 3"),
    ("2x - 1 > 5", "x < 3"),
    ("2x - 1 > 5", "x = 3"),
    (r"3 + 4 \times 2 \text{를 계산하시오}", "14"),
    ("x^2 + 1 = 0", "x = 1"),
    ("3x = 2", "x = 0.67"),  # not exact and not marked approximate
    ("2x + 3 = 7", "모르겠어요"),
]


@pytest.mark.parametrize(("problem", "answer"), WRONG_ANSWER)
def test_wrong_answers_fail(problem: str, answer: str) -> None:
    r = verify_answer(problem, answer)
    assert r.parsed
    assert not r.verified
    assert r.answer_ok is False
    assert r.detail


WRONG_STEP = [
    ("2x + 3 = 7", ["2x = 10", "x = 2"], "x = 2"),
    ("2x - 1 > 5", ["2x > 6", "x < 3"], "x > 3"),
    (r"-2x + 1 \le 7", [r"-2x \le 6", r"x \le -3"], r"x \ge -3"),
    (r"3 + 4 \times 2 \text{를 계산하시오}", ["= 7 \\times 2 = 14"], "11"),
    ("연립방정식 x + y = 5, x - y = 1", ["2y = 6"], "x = 3, y = 2"),
    ("x^2 - 5x + 6 = 0", ["(x-2)(x-4) = 0"], "x = 2, 3"),
    ("x = 2일 때, 3x + 1의 값", [r"3 \times 2 + 1 = 8"], "7"),
]


@pytest.mark.parametrize(("problem", "writes", "answer"), WRONG_STEP)
def test_wrong_steps_fail(problem: str, writes: list[str], answer: str) -> None:
    r = verify_solution(problem, writes, answer)
    assert r.parsed
    assert not r.verified
    assert r.step_errors
    assert "1번째 줄" in r.step_errors[0] or "2번째 줄" in r.step_errors[0]


@pytest.mark.parametrize(
    "problem",
    [
        "어떤 수에 3을 더한 수의 2배는 14이다. 어떤 수를 구하시오.",
        "부등식 2x - 1 < 7을 만족하는 짝수인 자연수 x의 개수를 구하시오.",  # a prose condition (짝수)
        "광합성이 일어나는 장소는 어디인가?",
        "",
        "x + y = 5",  # underdetermined
        r"\int x dx",  # indefinite (definite integrals: test_verify_csat.py)
        "x^7 + x + 1 = 0",
    ],
)
def test_unsupported_problems_are_not_parsed(problem: str) -> None:
    r = verify_solution(problem, ["x = 1"], "x = 1")
    assert not r.parsed
    assert not r.verified


def test_text_and_unparseable_steps_are_skipped() -> None:
    r = verify_solution(
        "2x + 3 = 7",
        [
            r"\text{양변에서 3을 빼요}",
            "",
            r"2x = 4 \quad (\text{양변에서 } 3\text{을 빼요})",
            r"\frac{2x}{2} = \frac{4}{2}",
            "x = 2",
        ],
        "x = 2",
    )
    assert r.verified, r.detail


def test_json_swallowed_backslashes_are_repaired() -> None:
    from studymate.verify.latex import repair_escapes

    # "\frac" written with one backslash inside JSON decodes to form feed + "rac"
    assert repair_escapes("\x0crac{x}{2} + 3 = 7") == "\\frac{x}{2} + 3 = 7"
    assert repair_escapes("2\times 3") == "2\\times 3"
    assert repair_escapes("\x08egin{cases}") == "\\begin{cases}"
    assert repair_escapes("x \neq 2") == "x \\neq 2"
    assert repair_escapes("첫 줄\n둘째 줄") == "첫 줄\n둘째 줄"
    r = verify_solution("다음 방정식을 푸시오. \x0crac{3x - 2}{5} = 2", ["3x - 2 = 10", "x = 4"], "x = 4")
    assert r.verified, r.detail


def test_never_crashes_on_garbage() -> None:
    for junk in ["}}}{{{", "\\frac{", "=", "x = = 2", "\\sqrt[", "≤≥≠", "😀", "x" * 3000, "1/0 = x"]:
        r = verify_solution(junk, [junk], junk)
        assert isinstance(r.verified, bool)


def test_analyze_problem_kinds() -> None:
    assert analyze_problem("2x + 3 = 7").kind == "equation"  # type: ignore[union-attr]
    assert analyze_problem("2x + 3 < 7").kind == "inequality"  # type: ignore[union-attr]
    assert analyze_problem("3 + 4 계산").kind == "expression"  # type: ignore[union-attr]
    p = analyze_problem("x + y = 5, x - y = 1")
    assert p is not None and p.solutions == [{x: 3, y: 2}]


def test_parse_answer_forms() -> None:
    ans = parse_answer(r"x = 2 \text{ 또는 } x = 3")
    assert ans is not None and ans.assignments[x] == [2, 3]
    ans = parse_answer("(x, y) = (1, -2)")
    assert ans is not None and ans.assignments == {x: [1], y: [-2]}
    ans = parse_answer(r"x = 1 \pm \sqrt{2}")
    assert ans is not None and len(ans.assignments[x]) == 2
    ans = parse_answer("해가 없습니다")
    assert ans is not None and ans.no_solution


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        ("x = 8", "8", True),
        ("x = 8", "x=8입니다", True),
        (r"x = \frac{1}{2}", "x = 0.5", True),
        ("x = 2, 3", "x = 3 또는 x = 2", True),
        ("x = 3, y = 2", "(x, y) = (3, 2)", True),
        ("x > 3", "3 < x", True),
        ("x = 8", "x = 9", False),
        ("x > 3", "x >= 3", False),
        ("광합성", "광합성입니다.", True),
        ("엽록체", "미토콘드리아", False),
    ],
)
def test_answers_equivalent(a: str, b: str, same: bool) -> None:
    assert answers_equivalent(a, b) is same
