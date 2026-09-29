"""SymPy verification of CSAT (수능) math: 수학Ⅰ·Ⅱ, 확률과 통계, 미적분, 기하 computations."""

from __future__ import annotations

import pytest
import sympy

from studymate.i18n import use_lang
from studymate.verify import analyze_problem, answers_equivalent, format_expected, verify_solution
from studymate.verify.csat import Env, line_error, looks_csat, parse_expr, split_choices, value_of


def _value(problem: str) -> sympy.Expr | None:
    p = analyze_problem(problem)
    return None if p is None else p.value


def test_e_as_a_name() -> None:
    # "이심률을 e라 할 때": e is a quantity, not Euler's number
    p = analyze_problem(r"함수 f(x) = x^2에 대하여 f'(e)를 e라 할 때 \lim_{x \to 1} (x + e)의 값은?")
    assert p is None or p.value is None or p.value.free_symbols


@pytest.mark.parametrize(
    ("latex", "expected"),
    [
        (r"\log_2 12 - \log_2 3", 2),
        (r"\log_{3}{27} + \log 100", 5),
        (r"\ln e^3", 3),
        (r"\log_2 3 \times \log_3 8", 3),
        (r"\sin\frac{\pi}{6} + \cos\frac{2}{3}\pi + \tan\frac{\pi}{4}", 1),
        (r"\sin 30^\circ \times \cos 60°", sympy.Rational(1, 4)),
        (r"\sin^2\frac{\pi}{3}", sympy.Rational(3, 4)),
        (r"{}_{5}\mathrm{C}_{2} + {}_4P_2 + {}_3H_2 + 4!", 52),
        (r"_{3}\Pi_{2}", 9),
        (r"\binom{6}{3}", 20),
        ("5C2", 10),
        (r"\sqrt[3]{-8} \times 4^{\frac{1}{2}}", -4),
        (r"\frac12 + \sqrt 9", sympy.Rational(7, 2)),
        (r"\lim_{x\to 2}\frac{x^2-4}{x-2}", 4),
        (r"\lim_{x \to \infty}\frac{3x^2+1}{x^2-2x}", 3),
        (r"\lim_{x\to 0+}\frac{|x|}{x}", 1),
        (r"\lim_{x\to 1^-}\frac{|x-1|}{x-1}", -1),
        (r"\lim_{x \to 1-0}\frac{|x-1|}{x-1}", -1),
        (r"\lim_{n\to\infty}(\sqrt{n^2+4n} - n)", 2),
        (r"\lim_{x\to 0}\frac{e^{2x}-1}{x}", 2),
        (r"\lim_{x\to 0}\frac{\sin 3x}{x}", 3),
        (r"\int_0^2 (3x^2 - 2x + 1)\,dx", 6),
        (r"\int_{-1}^{1} (x^3 + 3x^2) dx", 2),
        (r"\int_0^3 |x - 1| dx", sympy.Rational(5, 2)),
        (r"\int_1^e \frac{1}{x} dx + \int_0^{\pi} \sin x dx", 3),
        (r"\int_0^1 x e^x dx", 1),
        (r"\left[x^3 - x^2\right]_1^2", 4),
        (r"\sum_{k=1}^{10}(2k+1)", 120),
        (r"\sum_{k=1}^{5} k^2", 55),
        (r"\sum_{n=1}^{\infty} \left(\frac{1}{3}\right)^n", sympy.Rational(1, 2)),
        (r"\frac{d}{dx}(x^3 + 2x)", None),  # still has x: not a constant
    ],
)
def test_parse_expr(latex: str, expected: object) -> None:
    got = parse_expr(latex)
    if expected is None:
        assert got.free_symbols
        return
    assert sympy.N(got - expected) == 0 or abs(complex(sympy.N(got - expected))) < 1e-12


VALUES = [
    (r"\lim_{x\to 2}\frac{x^2-4}{x-2}의 값은?", 4),
    (r"함수 f(x) = x^3 - 2x^2 + 3x - 1에 대하여 f'(2)의 값은? [3점]", 7),
    (r"함수 f(x) = x^2 + ax + 3에 대하여 f'(1) = 5일 때, 상수 a의 값은?", 3),
    (r"함수 f(x) = x^3 + 1에 대하여 \lim_{h\to 0}\frac{f(1+2h)-f(1)}{h}의 값은?", 6),
    (r"함수 f(x) = e^{2x}에 대하여 f'(0)의 값은?", 2),
    (r"f(x) = 2x^3 - x에 대하여 \int_{-1}^{1} f(x) dx의 값", 0),
    (r"\int_0^2 (3x^2 - 2x + 1)dx의 값은?", 6),
    (r"다음 극한값을 구하시오. \lim_{x\to 3}\frac{x^2-9}{x-3}", 6),
    (r"\sum_{k=1}^{10}(2k+1)의 값은?", 120),
    (r"등차수열 \{a_n\}에 대하여 a_3 = 8, a_6 = 17일 때 a_{10}의 값은?", 29),
    (r"첫째항이 3이고 공차가 2인 등차수열 \{a_n\}에 대하여 a_{10}의 값은?", 21),
    (r"등비수열 \{a_n\}에 대하여 a_2 = 6, a_5 = 48일 때, a_4의 값은?", 24),
    (r"공비가 양수인 등비수열 \{a_n\}에 대하여 a_2 = 4, a_4 = 16일 때, a_5의 값은?", 32),
    (r"수열 \{a_n\}의 첫째항부터 제n항까지의 합 S_n이 S_n = n^2 + 2n일 때, a_{10}의 값은?", 21),
    (r"\sum_{k=1}^{n} a_k = n^2 + 3n일 때 a_5의 값은?", 12),
    (r"수열 a_n = 2n - 1에 대하여 \sum_{k=1}^{10} a_k의 값은?", 100),
    (
        r"\sin\theta = \frac{3}{5}이고 \frac{\pi}{2} < \theta < \pi일 때, \cos\theta의 값은?",
        sympy.Rational(-4, 5),
    ),
    (r"\tan\theta = 2일 때 \frac{\sin\theta + \cos\theta}{\sin\theta - \cos\theta}의 값은?", 3),
    (r"2^{x} = 8일 때 x의 값은?", 3),
    (r"\log_2(x+1) = 3을 만족시키는 x의 값은?", 7),
    (
        r"두 사건 A, B에 대하여 P(A) = \frac{1}{3}, P(B) = \frac{1}{2}, P(A \cup B) = \frac{2}{3}일 때, "
        r"P(A \cap B)의 값은?",
        sympy.Rational(1, 6),
    ),
    (
        r"두 사건 A, B는 서로 독립이고 P(A) = \frac{1}{3}, P(A \cup B) = \frac{1}{2}일 때, P(B)의 값은?",
        sympy.Rational(1, 4),
    ),
    (r"두 사건 A, B에 대하여 P(A) = 0.4, P(B|A) = 0.5일 때 P(A \cap B)의 값은?", sympy.Rational(1, 5)),
    (
        r"두 사건 A, B에 대하여 P(A^C) = 0.7, P(A \cap B^C) = 0.1일 때 P(A \cap B)의 값은?",
        sympy.Rational(1, 5),
    ),
    (r"확률변수 X가 이항분포 B(20, \frac{1}{4})를 따를 때, V(4X+1)의 값은?", 60),
    (r"확률변수 X가 이항분포 B(n, \frac{1}{3})을 따르고 E(X) = 4일 때, V(X)의 값은?", sympy.Rational(8, 3)),
    (r"확률변수 X가 정규분포 N(50, 4^2)을 따를 때, E(2X) + \sigma(X)의 값은?", 104),
    (r"함수 f(x) = x^3 - 3x + 2의 극댓값은?", 4),
    (r"함수 f(x) = x^3 - 3x^2 + 5의 극댓값과 극솟값의 합은?", 6),
    (r"닫힌구간 [0, 3]에서 함수 f(x) = x^3 - 3x^2 + 1의 최솟값은?", -3),
    (r"-1 \le x \le 2에서 함수 f(x) = x^2 - 2x + 3의 최댓값은?", 6),
    (r"곡선 y = x^2 - 4x + 3과 x축으로 둘러싸인 부분의 넓이는?", sympy.Rational(4, 3)),
    (r"두 곡선 y = x^2, y = 2x로 둘러싸인 부분의 넓이는?", sympy.Rational(4, 3)),
    (r"곡선 y = x^2 - 1과 x축 및 두 직선 x = 0, x = 2로 둘러싸인 부분의 넓이는?", 2),
    (
        r"수직선 위를 움직이는 점 P의 시각 t (t \ge 0)에서의 속도 v(t)가 v(t) = t^2 - 4t + 3일 때, "
        r"시각 t = 0에서 t = 4까지 점 P가 움직인 거리는?",
        4,
    ),
    (r"함수 f(x) = x^2 - 2x의 x = 3에서의 미분계수는?", 4),
    (r"곡선 y = x^3 - x 위의 점 (1, 0)에서의 접선의 기울기는?", 2),
    (r"두 벡터 \vec{a} = (2, 1), \vec{b} = (1, -3)에 대하여 \vec{a} \cdot \vec{b}의 값은?", -1),
    (r"두 벡터 \vec{a} = (2, 1), \vec{b} = (1, -3)에 대하여 |\vec{a} + 2\vec{b}|^2의 값은?", 41),
    (r"두 점 A(1, 2, 3), B(3, -1, 9)에 대하여 |\overrightarrow{AB}|의 값은?", 7),
    (r"\sqrt[3]{27} \times 9^{\frac{1}{2}}의 값은?", 9),
    (r"\log_2 x + \log_2 (x-2) = 3을 만족시키는 x의 값은?", 4),
    (r"\sin\theta + \cos\theta = \frac{1}{2}일 때, \sin\theta\cos\theta의 값은?", sympy.Rational(-3, 8)),
    (r"확률변수 X에 대하여 E(X) = 4, V(X) = 2일 때, V(3X - 1) + E(2X)의 값은?", 26),
    (r"f(x) = x^3 + ax^2 + bx에서 f'(1) = 0, f'(3) = 0일 때, a + b의 값은?", 3),
    (r"(x+2)^5의 전개식에서 x^3의 계수는?", 40),
    (r"\left(x + \frac{2}{x}\right)^6의 전개식에서 상수항은?", 160),
    (r"(2x - y)^4의 전개식에서 x^2y^2의 계수는?", 24),
    (r"\lim_{n\to\infty}\frac{2^{n+1}+3^{n}}{3^{n+1}-2^{n}}의 값은?", sympy.Rational(1, 3)),
    (r"함수 f(x) = x e^{x}에 대하여 f''(0)의 값은?", 2),
    (r"\int_1^{e} \ln x \, dx의 값은?", 1),
    # recursions, parametric / implicit slopes, named template values, lengths from coordinates
    (
        r"수열 \{a_n\}이 a_1 = 2이고 모든 자연수 n에 대하여 a_{n+1} = a_n + 3을 만족시킬 때, a_{10}의 값은?",
        29,
    ),
    (r"a_1 = 1, a_2 = 1, a_{n+2} = a_{n+1} + a_n일 때 a_8의 값은?", 21),
    (r"a_1 = 3, a_{n+1} = 2a_n - n일 때 a_4의 값은?", 13),  # 3, 5, 8, 13
    (
        r"매개변수 t로 나타낸 곡선 x = t^2 + 1, y = t^3 - 2t에서 t = 2일 때, \frac{dy}{dx}의 값은?",
        sympy.Rational(5, 2),
    ),
    (r"곡선 x^2 + xy + y^2 = 7 위의 점 (1, 2)에서의 접선의 기울기는?", sympy.Rational(-4, 5)),
    (r"곡선 y = x^2 - 4x와 직선 y = x로 둘러싸인 부분의 넓이를 S라 할 때, 6S의 값은?", 125),
    (r"곡선 $y = \ln x$와 $x$축 및 직선 $x = e$로 둘러싸인 부분의 넓이를 $S$라 할 때, $10S$의 값은?", 10),
    (r"곡선 y = e^x와 x축, y축 및 직선 x = 1로 둘러싸인 부분의 넓이는?", sympy.E - 1),
    (r"함수 f(x) = x^3 - 3x의 극댓값을 M이라 할 때, M^2 + 1의 값은?", 5),
    (r"좌표공간의 두 점 A(1, -2, 3), B(4, 2, 3)에 대하여 선분 AB의 길이는?", 5),
    (r"두 점 A(1, 2, 3), B(3, -1, 9) 사이의 거리는?", 7),
    # plane vectors known by lengths, angle and dot products
    (
        r"두 벡터 $\vec{a}$, $\vec{b}$에 대하여 $|\vec{a}| = 2$, $|\vec{b}| = 3$이고 "
        r"두 벡터가 이루는 각의 크기가 $\frac{\pi}{3}$일 때, $|2\vec{a} - \vec{b}|^2$의 값은?",
        13,
    ),
    (
        r"|\vec{a}| = 1, |\vec{b}| = 2, \vec{a} \cdot \vec{b} = 1일 때 |\vec{a} + \vec{b}|의 값은?",
        sympy.sqrt(7),
    ),
    (r"|\vec{a}| = 3, |\vec{a} + \vec{b}| = 5, |\vec{b}| = 4일 때 \vec{a} \cdot \vec{b}의 값은?", 0),
    # triangles: laws of sines and cosines
    (
        r"삼각형 $ABC$에서 $\overline{AB} = 5$, $\overline{AC} = 8$, $\angle A = \frac{\pi}{3}$일 때, "
        r"$\overline{BC}^2$의 값을 구하시오. [3점]",
        49,
    ),
    (r"삼각형 ABC에서 a = 3, b = 5, C = 120°일 때, c의 값은?", 7),
    (r"삼각형 ABC에서 a = 6, A = 30°일 때, 삼각형 ABC의 외접원의 반지름의 길이 R의 값은?", 6),
    (r"삼각형 ABC에서 a = 7, b = 5, c = 3일 때, \cos A의 값은?", sympy.Rational(-1, 2)),
    # counting integer solutions, sums / products / numbers of roots
    (r"부등식 $\log_2(x - 1) \le 3$을 만족시키는 모든 정수 $x$의 개수를 구하시오. [3점]", 8),
    (r"부등식 x^2 - 3x - 4 < 0을 만족시키는 정수 x의 개수는?", 4),
    (r"부등식 \log_3 (x+1) < 2를 만족시키는 자연수 x의 개수는?", 7),
    ("부등식 2x - 1 < 7을 만족하는 자연수 x의 개수를 구하시오.", 3),
    (r"$0 \le x < 2\pi$일 때, 방정식 $2\cos x - 1 = 0$의 모든 해의 합은?", 2 * sympy.pi),
    (r"방정식 $4^x - 6 \cdot 2^x + 8 = 0$의 모든 실근의 합은?", 3),
    (r"방정식 x^3 - 2x^2 - 5x + 6 = 0의 모든 실근의 곱은?", -6),
    (r"방정식 x^2 - 2x - 3 = 0의 서로 다른 실근의 개수는?", 2),
    # conics in standard form
    (r"타원 \frac{x^2}{25} + \frac{y^2}{16} = 1의 두 초점 사이의 거리는?", 6),
    (r"타원 \frac{x^2}{9} + \frac{y^2}{25} = 1의 장축의 길이는?", 10),
    (r"쌍곡선 \frac{x^2}{9} - \frac{y^2}{16} = 1의 두 초점 사이의 거리는?", 10),
    (
        r"쌍곡선 \frac{x^2}{9} - \frac{y^2}{16} = 1의 점근선 중 기울기가 양수인 것의 기울기를 m이라 할 때, "
        r"12m의 값은?",
        16,
    ),
    (r"포물선 y^2 = 12x의 초점의 x좌표는?", 3),
]


@pytest.mark.parametrize(("problem", "expected"), VALUES)
def test_problem_values(problem: str, expected: object) -> None:
    p = analyze_problem(problem)
    assert p is not None, problem
    if p.kind == "value":
        assert p.value is not None
        assert abs(complex(sympy.N(p.value - sympy.nsimplify(expected)))) < 1e-12, (problem, p.value)  # type: ignore[arg-type]
    answer = sympy.latex(sympy.nsimplify(expected))  # type: ignore[arg-type]
    assert verify_solution(problem, [], answer).verified, (problem, answer)


@pytest.mark.parametrize(
    ("lang", "problem", "expected"),
    [
        ("ja", r"関数 f(x) = x^3 - 2x について、f'(2) の値を求めよ。", 10),
        ("ja", r"\lim_{x \to 2} \frac{x^2 - 4}{x - 2} を求めよ。", 4),
        ("ja", r"等差数列 \{a_n\} において a_2 = 5, a_5 = 14 のとき、a_{10} の値を求めよ。", 29),
        ("ja", r"\int_1^e \log x \, dx の値を求めよ。", 1),  # 数学Ⅲ: log x is the natural log
        (
            "ja",
            r"事象 A, B について P(A) = 0.4, P_A(B) = 0.5 のとき、P(A \cap B) の値を求めよ。",
            sympy.Rational(1, 5),
        ),
        ("en", r"Let f(x) = x^3 - 2x. Find f'(2).", 10),
        ("en", r"Evaluate \lim_{x \to 2} \frac{x^2-4}{x-2}.", 4),
        ("en", r"Find the value of a if f'(1) = 5, where f(x) = x^2 + ax + 3.", 3),
        ("en", r"Find the area of the region enclosed by y = x^2 and y = 2x.", sympy.Rational(4, 3)),
    ],
)
def test_problem_values_other_languages(lang: str, problem: str, expected: object) -> None:
    with use_lang(lang):  # type: ignore[arg-type]
        got = _value(problem)
    assert got is not None, problem
    assert abs(complex(sympy.N(got - sympy.nsimplify(expected)))) < 1e-12  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "problem",
    [
        # conditions only in prose / parameters the limit must determine
        r"\lim_{x \to 1}\frac{x^2 + ax + b}{x - 1} = 3일 때, a+b의 값은?",
        r"x^2 + ax + b = 0의 두 근이 1, 2일 때 a + b의 값은?",
        r"함수 f(x)가 다음 조건을 만족시킬 때, f(3)의 값은? (가) f(1) = 2 "
        r"(나) 모든 실수 x에 대하여 f'(x) = 2x",
        r"함수 f(x) = x^3 + ax의 극댓값이 2일 때, 상수 a의 값은?",
        # ambiguous without a prose condition (sign of the ratio, quadrant)
        r"\tan\theta = 2일 때 \sin\theta의 값은?",
        r"등비수열 \{a_n\}에 대하여 a_2 = 4, a_4 = 16일 때, a_5의 값은?",
        # piecewise, Gauss bracket, recursion, indefinite integral, tables
        r"f(x) = \begin{cases} x^2 & (x < 1) \\ 2x - 1 & (x \ge 1) \end{cases}일 때 "
        r"\lim_{x\to 1} f(x)의 값은?",
        r"[x]는 x보다 크지 않은 최대의 정수일 때 \lim_{x\to 1+}[x]의 값은?",
        r"a_1 = 1, a_{n+1} = \begin{cases} a_n + 3 & (a_n \text{이 홀수}) \\ "
        r"\frac{a_n}{2} & (a_n \text{이 짝수}) \end{cases}일 때 a_{10}의 값은?",
        r"수열 \{a_n\}이 모든 자연수 n에 대하여 a_{n+1} = 2a_n을 만족시킬 때 a_{10}의 값은?",  # no a_1
        r"\int (3x^2 + 1) dx",
        # limits that do not exist, word problems
        r"\lim_{x\to 0}\frac{|x|}{x}의 값은?",
        "주머니에 흰 공 3개, 검은 공 4개가 있다. 임의로 2개를 꺼낼 때 모두 흰 공일 확률은?",
        r"f(x) = x^2 (x \ge 0), f(x) = -x (x < 0)일 때 f(-2)의 값은?",
        # consistency checks: SymPy's value must be one of the choices; 단답형 answers are 0~999
        r"\lim_{x\to2} x^2 의 값은? ① 1 ② 2 ③ 3 ④ 5 ⑤ 6",
        r"\log_2 3의 값은? [3점]",
        r"두 사건 A, B가 서로 배반사건이 아니고 P(A) = 0.3일 때 P(B)의 값은?",
        # the answer is a pair; "x의 계수" of a simplified expression is not an expansion
        r"f(x) = x^3 + ax^2 + bx에서 f'(1) = 0, f'(3) = 0일 때, a, b의 값은?",
        "다음 식을 간단히 할 때 x의 계수를 구하시오. 3(x+2) - 2(x-1)",
        # triangles: two sides only, or a point the figure defines
        r"삼각형 ABC에서 a = 4, b = 5일 때 c의 값은?",
        r"그림과 같이 삼각형 ABC의 변 BC 위의 점 D에 대하여 \overline{AD} = 3일 때 \overline{BD}의 값은?",
        # sums and counts change with prose conditions (양의), need an interval, or a parameter
        r"양의 실수 x에 대하여 방정식 x^2 = 4의 모든 해의 합은?",
        r"방정식 \sin x = \frac{1}{2}의 모든 해의 합은?",
        r"x^2 + kx + 4 = 0이 중근을 가질 때 모든 실수 k의 값의 합은?",
        # vectors: underdetermined (no angle) or a prose condition we do not read (perpendicular)
        r"|\vec{a}| = 2, |\vec{b}| = 3일 때 |\vec{a} + \vec{b}|의 값은?",
        r"\vec{a}와 \vec{b}가 서로 수직이고 |\vec{a}| = 1, |\vec{b}| = 2일 때 |\vec{a} + \vec{b}|^2의 값은?",
    ],
)
def test_out_of_scope_problems_are_not_parsed(problem: str) -> None:
    assert analyze_problem(problem) is None
    r = verify_solution(problem, ["x = 1"], "1")
    assert not r.parsed and not r.verified


def test_multiple_choice_answers() -> None:
    mc = r"\lim_{x\to 2}\frac{x^2-4}{x-2}의 값은? ① 1 ② 2 ③ 3 ④ 4 ⑤ 5"
    p = analyze_problem(mc)
    assert p is not None and p.answer_choice == 4
    assert format_expected(p) == "④ (4)"
    for good in ["④", "④ 4", "4", "4번", "(4)", "정답: ④"]:
        assert verify_solution(mc, [r"\lim_{x\to 2}(x+2) = 4"], good).verified, good
    for bad in ["③", "3", "⑤ 4"]:
        r = verify_solution(mc, [], bad)
        assert r.parsed and r.answer_ok is False, bad
    # middle-school kinds keep working with choices
    eq = "x^2 - 5x + 6 = 0의 해는? ① x=1 ② x=2 또는 x=3 ③ x=3 ④ x=-2 ⑤ x=6"
    assert verify_solution(eq, [], "②").verified
    assert not verify_solution(eq, [], "③").verified
    ex = r"\sqrt[3]{27} \times 9^{\frac{1}{2}}의 값은? ① 3 ② 6 ③ 9 ④ 12 ⑤ 15"
    assert verify_solution(ex, [], "③").verified


def test_split_choices() -> None:
    stem, choices = split_choices(r"값은? ① \frac{1}{2} ② 1 ③ \sqrt{2} ④ 2 ⑤ e")
    assert stem.strip() == "값은?"
    assert choices == [r"\frac{1}{2}", "1", r"\sqrt{2}", "2", "e"]
    # two circled labels are equation labels, not choices
    assert split_choices("① x + y = 5 ② x - y = 1")[1] == []


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("12", 12),
        ("12입니다", 12),
        (r"\frac{3}{2}", sympy.Rational(3, 2)),
        (r"2\sqrt{3}", 2 * sympy.sqrt(3)),
        ("e^2 - 1", sympy.E**2 - 1),
        (r"\ln 2", sympy.log(2)),
        (r"-\frac{4}{5}", sympy.Rational(-4, 5)),
        (r"\frac{\pi}{3}", sympy.pi / 3),
        ("a = 3", 3),
        ("0.25", sympy.Rational(1, 4)),
    ],
)
def test_value_of_answers(answer: str, expected: sympy.Expr) -> None:
    got = value_of(answer)
    assert got is not None and abs(complex(sympy.N(got - expected))) < 1e-12


def test_value_answers_compare_with_expected() -> None:
    p = r"\int_0^{\frac{\pi}{3}} \cos x\,dx 의 값은?"
    assert verify_solution(p, [], r"\frac{\sqrt{3}}{2}").verified
    assert verify_solution(p, [], r"\frac{1}{2}\sqrt{3}").verified
    assert not verify_solution(p, [], r"\frac{1}{2}").verified
    q = r"\int_1^{e^2} \frac{1}{x} dx 의 값은?"
    assert verify_solution(q, [], "2").verified


def test_board_lines() -> None:
    p = r"함수 f(x) = x^3 - 2x^2 + 3x - 1에 대하여 f'(2)의 값은? [3점]"
    good = verify_solution(p, ["f'(x) = 3x^2 - 4x + 3", "f'(2) = 12 - 8 + 3 = 7"], "7")
    assert good.verified, good.detail
    bad = verify_solution(p, ["f'(x) = 3x^2 - 4x + 3", "f'(2) = 12 - 8 + 3 = 8"], "7")
    assert bad.parsed and not bad.verified and bad.bad_lines == [2]
    lim = r"\lim_{x\to 2}\frac{x^2-4}{x-2}의 값은?"
    r = verify_solution(
        lim,
        [
            r"\lim_{x\to 2}\frac{(x-2)(x+2)}{x-2}",
            r"= \lim_{x\to 2}(x+2)",
            r"= 2 + 2 = 4",
            r"\frac{0}{0} \text{ 꼴}",
        ],
        "4",
    )
    assert r.verified, r.detail


@pytest.mark.parametrize(
    ("line", "ok"),
    [
        (r"\log_2 8 = 3", True),
        (r"\log 2 = 0.3010", True),  # rounded decimals are compared to their precision
        (r"\sin 150^\circ = \sin 30^\circ = \frac{1}{2}", True),
        (r"{}_5C_2 \times {}_3C_1 = 10 \times 3 = 30", True),
        (r"\int_0^2 3x^2 dx = \left[x^3\right]_0^2 = 8", True),
        (r"\cos^2\theta = 1 - \sin^2\theta = 1 - \frac{9}{25} = \frac{16}{25}", True),
        (r"P(A \cap B) = P(A)P(B) = \frac{1}{6}", True),  # unknown notation: skipped
        (r"x = 2 \text{ 또는 } x = 3", True),
        (r"2^3 = 6", False),
        (r"\log_2 8 = 4", False),
        (r"\sin 30^\circ = \frac{\sqrt{3}}{2}", False),
        (r"{}_5C_2 = 20", False),
    ],
)
def test_line_error(line: str, ok: bool) -> None:
    assert (line_error(Env(), line) is None) is ok


def test_line_error_uses_problem_definitions() -> None:
    p = analyze_problem(
        r"확률변수 $X$가 이항분포 $B\left(36, \frac{1}{3}\right)$을 따를 때, $V(3X - 2)$의 값은?"
    )
    assert p is not None
    env = p.context
    for good in [
        r"V(X) = 36 \times \frac{1}{3} \times \frac{2}{3} = 8",
        r"V(3X-2) = 3^2 V(X) = 9 \times 8 = 72",
        r"E(X) = np = 12",
        r"P(|Z| \le 1.96) = 95\% = 0.95",
        r"\sqrt{3} = 1.7",  # rounded to the digits written
        r"a_{11} = a_1 + 10d = 4 + 30 = 34",
        r"\therefore 정답은 ②",
    ]:
        assert line_error(env, good) is None, good
    assert line_error(env, r"V(3X-2) = 3 V(X) = 24") is not None


def test_answers_equivalent_csat() -> None:
    mc = r"\lim_{x\to 2}\frac{x^2-4}{x-2}의 값은? ① 1 ② 2 ③ 3 ④ 4 ⑤ 5"
    assert answers_equivalent("④", "4", mc)
    assert not answers_equivalent("④", "3", mc)
    assert answers_equivalent(r"\ln 2", r"\log_e 2")
    assert answers_equivalent("{}_5C_2", "10")
    assert answers_equivalent("e^{2}", "e^2")
    assert not answers_equivalent(r"\ln 2", r"\ln 3")


def test_detection() -> None:
    assert looks_csat(r"\lim_{x\to 1} x")
    assert looks_csat("f'(2)의 값은?")
    assert looks_csat("등차수열 a_n")
    assert not looks_csat("2x + 3 = 7")
    assert not looks_csat("x = 2일 때, 3x + 1의 값을 구하시오.")
