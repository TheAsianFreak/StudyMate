# ruff: noqa: E501
"""Original CSAT (수능)-style math problems: 수학Ⅰ, 수학Ⅱ, 확률과 통계, 미적분, 기하.

Every problem was written for StudyMate (none is taken from KICE 수능/모의평가 or EBS
material). `text` is what a student would type or photograph (math in $...$), with the
score marker and, for 5지선다, the five options. 단답형 answers are integers from 0 to 999
as on the real exam.

`value` is the answer as a SymPy expression string and `truth` recomputes it independently
of the app's own LaTeX reader (plain SymPy, or the hand derivation written out), so a typo
in either is caught by `validate_problems` (run by eval/run_eval.py and the tests).
`derivation` says how the answer comes out, for whoever reviews a failure.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import sympy
from sympy import (
    E,
    Rational,
    binomial,
    cos,
    diff,
    exp,
    ff,
    integrate,
    limit,
    log,
    oo,
    pi,
    real_root,
    sqrt,
    summation,
)

MARKS = ("①", "②", "③", "④", "⑤")
SUBJECTS = ("수학Ⅰ", "수학Ⅱ", "확률과 통계", "미적분", "기하")

x, t, n, k = sympy.symbols("x t n k", real=True)


@dataclass(frozen=True)
class CsatMathProblem:
    id: str
    subject: str
    text: str
    value: str  # the answer as a SymPy expression ("Rational(5, 2)", "3*E")
    truth: Callable[[], Any]  # independent recomputation
    derivation: str
    choices: tuple[str, ...] = ()  # the five options of a 5지선다 problem (LaTeX, as in the text)

    @property
    def answer(self) -> sympy.Expr:
        return sympy.sympify(self.value)

    @property
    def multiple_choice(self) -> bool:
        return bool(self.choices)


def _mc(
    pid: str,
    subject: str,
    stem: str,
    points: int,
    options: tuple[str, ...],
    value: str,
    truth: Callable[[], Any],
    why: str,
) -> CsatMathProblem:
    opts = " ".join(
        f"{m} {o if o.startswith('$') else '$' + o + '$'}" for m, o in zip(MARKS, options, strict=True)
    )
    return CsatMathProblem(pid, subject, f"{stem} [{points}점]\n{opts}", value, truth, why, options)


def _short(
    pid: str, subject: str, stem: str, points: int, value: str, truth: Callable[[], Any], why: str
) -> CsatMathProblem:
    return CsatMathProblem(pid, subject, f"{stem} [{points}점]", value, truth, why)


def _normal_prob(a: float, b: float) -> float:
    """P(a <= Z <= b) for the standard normal distribution (second check of table problems)."""
    return float(sympy.N((sympy.erf(b / sympy.sqrt(2)) - sympy.erf(a / sympy.sqrt(2))) / 2))


PROBLEMS: list[CsatMathProblem] = [
    # ------------------------------------------------------------------ 수학Ⅰ
    _mc(
        "M1-01",
        "수학Ⅰ",
        "$\\sqrt[3]{54} \\times 2^{\\frac{2}{3}}$의 값은?",
        2,
        ("2", "4", "5", "6", "9"),
        "6",
        lambda: real_root(54, 3) * 2 ** Rational(2, 3),
        "54^(1/3) = 3·2^(1/3), times 2^(2/3) gives 3·2 = 6.",
    ),
    _mc(
        "M1-02",
        "수학Ⅰ",
        "$\\log_2 24 - \\log_2 3 + \\log_2 \\frac{1}{2}$의 값은?",
        2,
        ("1", "2", "3", "4", "5"),
        "2",
        lambda: log(24, 2) - log(3, 2) + log(Rational(1, 2), 2),
        "log2(24/3) = 3, plus log2(1/2) = -1.",
    ),
    _short(
        "M1-03",
        "수학Ⅰ",
        "부등식 $\\log_2(x - 1) \\le 3$을 만족시키는 모든 정수 $x$의 개수를 구하시오.",
        3,
        "8",
        lambda: sum(1 for i in range(-50, 50) if i - 1 > 0 and i - 1 <= 2**3),
        "Domain x > 1 and x - 1 <= 8: x = 2, ..., 9.",
    ),
    _mc(
        "M1-04",
        "수학Ⅰ",
        "$\\frac{\\pi}{2} < \\theta < \\pi$이고 $\\sin\\theta = \\frac{5}{13}$일 때, $\\tan\\theta$의 값은?",
        3,
        ("-\\frac{12}{5}", "-\\frac{5}{12}", "\\frac{5}{13}", "\\frac{5}{12}", "\\frac{12}{5}"),
        "Rational(-5, 12)",
        lambda: sympy.tan(pi - sympy.asin(Rational(5, 13))),
        "Second quadrant: cos = -12/13, tan = -5/12.",
    ),
    _short(
        "M1-05",
        "수학Ⅰ",
        "삼각형 $ABC$에서 $\\overline{AB} = 5$, $\\overline{AC} = 8$, $\\angle A = \\frac{\\pi}{3}$일 때, $\\overline{BC}^2$의 값을 구하시오.",
        3,
        "49",
        lambda: 5**2 + 8**2 - 2 * 5 * 8 * cos(pi / 3),
        "Law of cosines: 25 + 64 - 40 = 49.",
    ),
    _mc(
        "M1-06",
        "수학Ⅰ",
        "등차수열 $\\{a_n\\}$에 대하여 $a_2 = 7$, $a_6 = 19$일 때, $a_{11}$의 값은?",
        3,
        ("22", "25", "28", "31", "34"),
        "34",
        lambda: 4 + (11 - 1) * 3,
        "4d = 12 so d = 3, a_1 = 4, a_11 = 4 + 30.",
    ),
    _short(
        "M1-07",
        "수학Ⅰ",
        "$\\sum_{k=1}^{10}(k^2 - 2k)$의 값을 구하시오.",
        3,
        "275",
        lambda: sum(i * i - 2 * i for i in range(1, 11)),
        "385 - 2·55.",
    ),
    _short(
        "M1-08",
        "수학Ⅰ",
        "모든 항이 양수인 등비수열 $\\{a_n\\}$에 대하여 $a_1 a_3 = 16$, $a_3 + a_4 = 24$일 때, $a_5$의 값을 구하시오.",
        4,
        "32",
        lambda: 2 * 2**4,
        "a_1a_3 = a_2^2 = 16 so a_2 = 4; 4r + 4r^2 = 24 gives r = 2, a_1 = 2, a_5 = 32.",
    ),
    _mc(
        "M1-09",
        "수학Ⅰ",
        "수열 $\\{a_n\\}$이 $a_1 = 2$이고, 모든 자연수 $n$에 대하여 $a_{n+1} = 2a_n - 1$을 만족시킬 때, $a_6$의 값은?",
        3,
        ("31", "33", "63", "65", "129"),
        "33",
        lambda: _iterate(2, lambda a: 2 * a - 1, 5),
        "a_n = 2^(n-1) + 1: 2, 3, 5, 9, 17, 33.",
    ),
    # ------------------------------------------------------------------ 수학Ⅱ
    _mc(
        "M2-01",
        "수학Ⅱ",
        "$\\lim_{x \\to 3} \\frac{x^2 - 2x - 3}{x - 3}$의 값은?",
        2,
        ("1", "2", "3", "4", "5"),
        "4",
        lambda: limit((x**2 - 2 * x - 3) / (x - 3), x, 3),
        "(x - 3)(x + 1)/(x - 3) -> 4.",
    ),
    _mc(
        "M2-02",
        "수학Ⅱ",
        "함수 $f(x) = 2x^3 - 5x^2 + x - 4$에 대하여 $f'(2)$의 값은?",
        2,
        ("3", "5", "7", "9", "11"),
        "5",
        lambda: diff(2 * x**3 - 5 * x**2 + x - 4, x).subs(x, 2),
        "f'(x) = 6x^2 - 10x + 1, f'(2) = 24 - 20 + 1.",
    ),
    _short(
        "M2-03",
        "수학Ⅱ",
        "$\\int_{-1}^{2}(3x^2 + 2x - 1)\\,dx$의 값을 구하시오.",
        3,
        "9",
        lambda: integrate(3 * x**2 + 2 * x - 1, (x, -1, 2)),
        "[x^3 + x^2 - x] from -1 to 2 = 10 - 1.",
    ),
    _mc(
        "M2-04",
        "수학Ⅱ",
        "함수 $f(x) = x^3 - 6x^2 + 9x + 2$의 극솟값은?",
        3,
        ("2", "3", "4", "5", "6"),
        "2",
        lambda: (x**3 - 6 * x**2 + 9 * x + 2).subs(x, 3),
        "f'(x) = 3(x - 1)(x - 3): local min at x = 3, f(3) = 2 (6 is the local max).",
    ),
    _short(
        "M2-05",
        "수학Ⅱ",
        "곡선 $y = x^3 - 3x + 1$ 위의 점 $(2, 3)$에서의 접선이 점 $(a, 30)$을 지날 때, $a$의 값을 구하시오.",
        3,
        "5",
        lambda: sympy.solve(sympy.Eq(30, 9 * (x - 2) + 3), x)[0],
        "Slope f'(2) = 9, tangent y = 9x - 15; 30 = 9a - 15.",
    ),
    _mc(
        "M2-06",
        "수학Ⅱ",
        "두 상수 $a$, $b$에 대하여 $\\lim_{x \\to 1} \\frac{x^2 + ax + b}{x - 1} = 5$일 때, $a - b$의 값은?",
        3,
        ("3", "5", "7", "9", "11"),
        "7",
        lambda: _limit_constants(),
        "Numerator vanishes at 1: 1 + a + b = 0; the limit is 2 + a = 5, so a = 3, b = -4.",
    ),
    _short(
        "M2-07",
        "수학Ⅱ",
        "곡선 $y = x^2 - 4x$와 직선 $y = x$로 둘러싸인 부분의 넓이를 $S$라 할 때, $6S$의 값을 구하시오.",
        4,
        "125",
        lambda: 6 * integrate(x - (x**2 - 4 * x), (x, 0, 5)),
        "Intersections x = 0, 5; S = ∫(5x - x^2) = 125/6.",
    ),
    _mc(
        "M2-08",
        "수학Ⅱ",
        "수직선 위를 움직이는 점 P의 시각 $t$ $(t \\ge 0)$에서의 속도 $v(t)$가 $v(t) = 3t^2 - 12t + 9$일 때, 시각 $t = 0$에서 $t = 3$까지 점 P가 움직인 거리는?",
        3,
        ("0", "4", "6", "8", "12"),
        "8",
        lambda: integrate(3 * t**2 - 12 * t + 9, (t, 0, 1)) - integrate(3 * t**2 - 12 * t + 9, (t, 1, 3)),
        "v >= 0 on [0, 1], v <= 0 on [1, 3]: 4 + 4 (the displacement is 0).",
    ),
    _short(
        "M2-09",
        "수학Ⅱ",
        "함수 $f(x) = x^3 + ax^2 + bx + 1$이 $x = -1$에서 극댓값을 갖고 $x = 3$에서 극솟값을 가질 때, $f(-1)$의 값을 구하시오. (단, $a$, $b$는 상수이다.)",
        4,
        "6",
        lambda: (x**3 - 3 * x**2 - 9 * x + 1).subs(x, -1),
        "f'(x) = 3(x + 1)(x - 3) = 3x^2 - 6x - 9: a = -3, b = -9, f(-1) = -1 - 3 + 9 + 1.",
    ),
    # ------------------------------------------------------------------ 확률과 통계
    _mc(
        "PS-01",
        "확률과 통계",
        "${}_5\\mathrm{P}_2 + {}_5\\mathrm{C}_3$의 값은?",
        2,
        ("30", "35", "40", "45", "50"),
        "30",
        lambda: ff(5, 2) + binomial(5, 3),
        "20 + 10.",
    ),
    _short(
        "PS-02",
        "확률과 통계",
        "$\\left(x + \\frac{2}{x}\\right)^6$의 전개식에서 $x^2$의 계수를 구하시오.",
        3,
        "60",
        lambda: sympy.expand((x + 2 / x) ** 6).coeff(x, 2),
        "General term C(6, r)·2^r·x^(6-2r); r = 2 gives 15·4.",
    ),
    _mc(
        "PS-03",
        "확률과 통계",
        "두 사건 $A$, $B$에 대하여 $P(A) = \\frac{1}{2}$, $P(B) = \\frac{1}{3}$, $P(A \\cup B) = \\frac{2}{3}$일 때, $P(B|A)$의 값은?",
        3,
        ("\\frac{1}{2}", "\\frac{1}{3}", "\\frac{1}{4}", "\\frac{1}{5}", "\\frac{1}{6}"),
        "Rational(1, 3)",
        lambda: (Rational(1, 2) + Rational(1, 3) - Rational(2, 3)) / Rational(1, 2),
        "P(A ∩ B) = 1/6, divided by P(A) = 1/2.",
    ),
    _short(
        "PS-04",
        "확률과 통계",
        "방정식 $x + y + z = 7$을 만족시키는 음이 아닌 정수 $x$, $y$, $z$의 모든 순서쌍 $(x, y, z)$의 개수를 구하시오.",
        3,
        "36",
        lambda: sum(1 for a in range(8) for b in range(8) if 7 - a - b >= 0),
        "3H7 = 9C7 = 36 (counted directly as a check).",
    ),
    _mc(
        "PS-05",
        "확률과 통계",
        "흰 공 4개와 검은 공 3개가 들어 있는 주머니에서 임의로 3개의 공을 동시에 꺼낼 때, 꺼낸 공 중 흰 공이 2개일 확률은?",
        3,
        ("\\frac{2}{7}", "\\frac{12}{35}", "\\frac{3}{7}", "\\frac{18}{35}", "\\frac{4}{7}"),
        "Rational(18, 35)",
        lambda: binomial(4, 2) * binomial(3, 1) / binomial(7, 3),
        "4C2·3C1 / 7C3 = 18/35.",
    ),
    _short(
        "PS-06",
        "확률과 통계",
        "한 개의 주사위를 4번 던질 때, 3의 배수의 눈이 나오는 횟수가 2일 확률을 $p$라 하자. $81p$의 값을 구하시오.",
        3,
        "24",
        lambda: 81 * binomial(4, 2) * Rational(1, 3) ** 2 * Rational(2, 3) ** 2,
        "p = 4C2 (1/3)^2 (2/3)^2 = 24/81.",
    ),
    _mc(
        "PS-07",
        "확률과 통계",
        "확률변수 $X$가 이항분포 $B\\left(36, \\frac{1}{3}\\right)$을 따를 때, $V(3X - 2)$의 값은?",
        3,
        ("24", "32", "48", "64", "72"),
        "72",
        lambda: 9 * 36 * Rational(1, 3) * Rational(2, 3),
        "V(X) = 36·(1/3)·(2/3) = 8, V(3X - 2) = 9·8.",
    ),
    _mc(
        "PS-08",
        "확률과 통계",
        "확률변수 $X$가 정규분포 $N(50, 4^2)$을 따를 때, $P(46 \\le X \\le 58)$의 값을 표준정규분포표를 이용하여 구한 것은? "
        "(단, $Z$가 표준정규분포를 따르는 확률변수일 때, $P(0 \\le Z \\le 1) = 0.3413$, $P(0 \\le Z \\le 1.5) = 0.4332$, "
        "$P(0 \\le Z \\le 2) = 0.4772$로 계산한다.)",
        3,
        ("0.6826", "0.7745", "0.8185", "0.9104", "0.9544"),
        "Rational('0.8185')",
        lambda: Rational("0.3413") + Rational("0.4772"),
        "Z from -1 to 2: 0.3413 + 0.4772 (exact normal value 0.81859).",
    ),
    _short(
        "PS-09",
        "확률과 통계",
        "정규분포 $N(m, 12^2)$을 따르는 모집단에서 크기가 $36$인 표본을 임의추출하여 구한 표본평균을 이용하여, 모평균 $m$에 대한 신뢰도 $95\\%$의 신뢰구간을 구하였다. "
        "이 신뢰구간의 길이를 $l$이라 할 때, $100l$의 값을 구하시오. (단, $Z$가 표준정규분포를 따르는 확률변수일 때, $P(|Z| \\le 1.96) = 0.95$로 계산한다.)",
        4,
        "784",
        lambda: 100 * 2 * Rational("1.96") * 12 / sqrt(36),
        "l = 2·1.96·12/6 = 7.84.",
    ),
    # ------------------------------------------------------------------ 미적분
    _mc(
        "CA-01",
        "미적분",
        "$\\lim_{n \\to \\infty} \\frac{4n^2 + 3n}{2n^2 - 1}$의 값은?",
        2,
        ("1", "2", "3", "4", "6"),
        "2",
        lambda: limit((4 * n**2 + 3 * n) / (2 * n**2 - 1), n, oo),
        "Divide by n^2: 4/2.",
    ),
    _mc(
        "CA-02",
        "미적분",
        "$\\lim_{x \\to 0} \\frac{e^{3x} - 1}{\\ln(1 + 2x)}$의 값은?",
        2,
        ("\\frac{1}{2}", "\\frac{2}{3}", "1", "\\frac{3}{2}", "2"),
        "Rational(3, 2)",
        lambda: limit((exp(3 * x) - 1) / log(1 + 2 * x), x, 0),
        "(e^(3x) - 1)/(3x) · (2x)/ln(1 + 2x) · 3/2.",
    ),
    _short(
        "CA-03",
        "미적분",
        "$\\sum_{n=1}^{\\infty} \\frac{2^{n+1}}{3^n}$의 값을 구하시오.",
        3,
        "4",
        lambda: summation(2 ** (k + 1) / 3**k, (k, 1, oo)),
        "2·Σ(2/3)^n = 2·(2/3)/(1/3).",
    ),
    _mc(
        "CA-04",
        "미적분",
        "함수 $f(x) = x^2 e^x$에 대하여 $f'(1)$의 값은?",
        3,
        ("e", "\\frac{3}{2}e", "2e", "\\frac{5}{2}e", "3e"),
        "3*E",
        lambda: diff(x**2 * exp(x), x).subs(x, 1),
        "f'(x) = (2x + x^2)e^x.",
    ),
    _mc(
        "CA-05",
        "미적분",
        "매개변수 $t$로 나타낸 곡선 $x = t^2 + 1$, $y = t^3 - 2t$에서 $t = 2$일 때, $\\frac{dy}{dx}$의 값은?",
        3,
        ("2", "\\frac{5}{2}", "3", "\\frac{7}{2}", "4"),
        "Rational(5, 2)",
        lambda: (diff(t**3 - 2 * t, t) / diff(t**2 + 1, t)).subs(t, 2),
        "dy/dt = 3t^2 - 2 = 10, dx/dt = 2t = 4.",
    ),
    _short(
        "CA-06",
        "미적분",
        "$\\int_{1}^{e^3} \\frac{2\\ln x}{x}\\,dx$의 값을 구하시오.",
        3,
        "9",
        lambda: integrate(2 * log(x) / x, (x, 1, E**3)),
        "Substitute u = ln x: [(ln x)^2] from 1 to e^3 = 9.",
    ),
    _mc(
        "CA-07",
        "미적분",
        "곡선 $x^2 + xy + y^2 = 7$ 위의 점 $(1, 2)$에서의 접선의 기울기는?",
        3,
        ("-\\frac{4}{5}", "-\\frac{3}{5}", "-\\frac{2}{5}", "\\frac{2}{5}", "\\frac{4}{5}"),
        "Rational(-4, 5)",
        lambda: _implicit_slope(),
        "Implicit: 2x + y + xy' + 2yy' = 0, y' = -(2x + y)/(x + 2y) = -4/5.",
    ),
    _short(
        "CA-08",
        "미적분",
        "곡선 $y = \\ln x$와 $x$축 및 직선 $x = e$로 둘러싸인 부분의 넓이를 $S$라 할 때, $10S$의 값을 구하시오.",
        4,
        "10",
        lambda: 10 * integrate(log(x), (x, 1, E)),
        "By parts: [x ln x - x] from 1 to e = 1.",
    ),
    _mc(
        "CA-09",
        "미적분",
        "$\\sum_{n=1}^{\\infty} \\frac{1}{(2n - 1)(2n + 1)}$의 값은?",
        3,
        ("\\frac{1}{4}", "\\frac{1}{3}", "\\frac{1}{2}", "\\frac{2}{3}", "1"),
        "Rational(1, 2)",
        lambda: summation(1 / ((2 * k - 1) * (2 * k + 1)), (k, 1, oo)),
        "Telescoping: (1/2)(1/(2n-1) - 1/(2n+1)).",
    ),
    # ------------------------------------------------------------------ 기하
    _mc(
        "GE-01",
        "기하",
        "두 벡터 $\\vec{a} = (3, -1)$, $\\vec{b} = (2, 4)$에 대하여 $\\vec{a} \\cdot (\\vec{a} + \\vec{b})$의 값은?",
        2,
        ("6", "8", "10", "12", "14"),
        "12",
        lambda: sympy.Matrix([3, -1]).dot(sympy.Matrix([3, -1]) + sympy.Matrix([2, 4])),
        "|a|^2 = 10, a·b = 6 - 4 = 2.",
    ),
    _mc(
        "GE-02",
        "기하",
        "좌표공간의 두 점 $A(1, -2, 3)$, $B(4, 2, 3)$에 대하여 선분 $AB$의 길이는?",
        2,
        ("5", "\\sqrt{34}", "6", "\\sqrt{41}", "7"),
        "5",
        lambda: sqrt(3**2 + 4**2 + 0**2),
        "√(9 + 16 + 0).",
    ),
    _short(
        "GE-03",
        "기하",
        "포물선 $y^2 = 12x$ 위의 점 P와 이 포물선의 초점 F에 대하여 $\\overline{PF} = 10$일 때, 점 P의 $x$좌표를 구하시오.",
        3,
        "7",
        lambda: 10 - 3,
        "p = 3: PF = (distance to the directrix x = -3) = x + 3.",
    ),
    _mc(
        "GE-04",
        "기하",
        "타원 $\\frac{x^2}{25} + \\frac{y^2}{16} = 1$의 두 초점 사이의 거리는?",
        3,
        ("3", "4", "5", "6", "8"),
        "6",
        lambda: 2 * sqrt(25 - 16),
        "c^2 = 25 - 16 = 9.",
    ),
    _short(
        "GE-05",
        "기하",
        "쌍곡선 $\\frac{x^2}{9} - \\frac{y^2}{16} = 1$의 두 점근선 중 기울기가 양수인 직선의 기울기를 $m$이라 할 때, $12m$의 값을 구하시오.",
        3,
        "16",
        lambda: 12 * sqrt(16) / sqrt(9),
        "Asymptotes y = ±(4/3)x.",
    ),
    _mc(
        "GE-06",
        "기하",
        "두 벡터 $\\vec{a}$, $\\vec{b}$에 대하여 $|\\vec{a}| = 2$, $|\\vec{b}| = 3$이고 두 벡터가 이루는 각의 크기가 $\\frac{\\pi}{3}$일 때, $|2\\vec{a} - \\vec{b}|^2$의 값은?",
        3,
        ("7", "13", "19", "25", "37"),
        "13",
        lambda: 4 * 2**2 - 4 * (2 * 3 * cos(pi / 3)) + 3**2,
        "4|a|^2 - 4a·b + |b|^2 = 16 - 12 + 9.",
    ),
    _short(
        "GE-07",
        "기하",
        "두 평면 $\\alpha$, $\\beta$가 이루는 각의 크기가 $\\frac{\\pi}{3}$이다. 평면 $\\alpha$ 위에 있는 넓이가 $24$인 도형의 평면 $\\beta$ 위로의 정사영의 넓이를 구하시오.",
        3,
        "12",
        lambda: 24 * cos(pi / 3),
        "S cos θ = 24 · 1/2.",
    ),
    _mc(
        "GE-08",
        "기하",
        "좌표공간의 두 점 $A(1, 0, 5)$, $B(7, 3, -1)$에 대하여 선분 $AB$를 $2 : 1$로 내분하는 점의 좌표를 $(a, b, c)$라 할 때, $a + b + c$의 값은?",
        3,
        ("5", "6", "7", "8", "9"),
        "8",
        lambda: sum((2 * sympy.Matrix([7, 3, -1]) + sympy.Matrix([1, 0, 5])) / 3),
        "(2B + A)/3 = (5, 2, 1).",
    ),
]


def _iterate(a: int, step: Callable[[int], int], times: int) -> int:
    for _ in range(times):
        a = step(a)
    return a


def _limit_constants() -> sympy.Expr:
    """The numerator vanishes at x = 1 (b = -1 - a), then it is (x - 1)(x + 1 + a): limit 2 + a."""
    a = sympy.Symbol("a")
    quotient = sympy.cancel((x**2 + a * x - 1 - a) / (x - 1))
    a_val = sympy.solve(quotient.subs(x, 1) - 5, a)[0]
    b_val = -1 - a_val
    assert limit((x**2 + a_val * x + b_val) / (x - 1), x, 1) == 5
    return a_val - b_val


def _implicit_slope() -> sympy.Expr:
    y = sympy.Function("y")(x)
    dydx = sympy.solve(diff(x**2 + x * y + y**2 - 7, x), diff(y, x))[0]
    return dydx.subs(y, 2).subs(x, 1)


def correct_choice(p: CsatMathProblem) -> int | None:
    """1-based option holding the answer (read with the app's parser; validated to be unique)."""
    if not p.choices:
        return None
    from studymate.verify.csat import value_of
    from studymate.verify.latex import numbers_equal

    hits = [
        i for i, c in enumerate(p.choices, 1) if (v := value_of(c)) is not None and numbers_equal(v, p.answer)
    ]
    return hits[0] if len(hits) == 1 else None


def judge(final_answer: str, p: CsatMathProblem) -> bool:
    """A choice number is judged by the option; a value must equal the answer exactly."""
    from studymate.verify.answer import choice_index
    from studymate.verify.csat import value_of
    from studymate.verify.latex import numbers_equal

    if p.choices:
        idx = choice_index(final_answer)
        if idx is not None:
            return idx == correct_choice(p)
    v = value_of(final_answer)
    return v is not None and numbers_equal(v, p.answer)


def gt_text(p: CsatMathProblem) -> str:
    value = sympy.latex(p.answer)
    idx = correct_choice(p)
    return f"{MARKS[idx - 1]} ({value})" if idx else value


def validate_problems(problems: Iterable[CsatMathProblem] = PROBLEMS) -> None:
    """Independent recomputation equals the stored answer; options are unique; ids unique;
    단답형 answers are integers 0~999; every subject is present."""
    problems = list(problems)
    ids = Counter(p.id for p in problems)
    dup = [i for i, c in ids.items() if c > 1]
    if dup:
        raise AssertionError(f"duplicate ids {dup}")
    for p in problems:
        if p.subject not in SUBJECTS:
            raise AssertionError(f"{p.id}: unknown subject {p.subject}")
        got = sympy.nsimplify(sympy.sympify(p.truth()))
        if sympy.simplify(got - p.answer) != 0:
            raise AssertionError(f"{p.id}: stored answer {p.answer} but recomputed {got}")
        if p.choices:
            if len(p.choices) != 5 or correct_choice(p) is None:
                raise AssertionError(f"{p.id}: the answer must be exactly one of five options")
        elif not (p.answer.is_Integer and 0 <= int(p.answer) <= 999):
            raise AssertionError(f"{p.id}: 단답형 answers are integers from 0 to 999")
    if {p.subject for p in problems} != set(SUBJECTS) and len(problems) == len(PROBLEMS):
        raise AssertionError("every CSAT math subject needs problems")
    # the table problem also agrees with the exact normal distribution
    assert abs(_normal_prob(-1, 2) - 0.8185) < 1e-3
