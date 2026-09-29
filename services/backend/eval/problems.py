"""50 Korean middle-school equation problems with ground truth.

`text` is what a student would type or photograph (math in $...$ LaTeX, rendered for
the --images run). `equations` restate each problem in plain SymPy syntax so the ground
truth is checked by SymPy independently of the app's own LaTeX parser (see run_eval).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalProblem:
    id: str
    category: str
    text: str
    equations: tuple[str, ...]  # "lhs = rhs" in SymPy syntax
    answer: dict[str, tuple[str, ...]]  # variable -> all real solutions


def _p(
    pid: str, cat: str, text: str, eqs: tuple[str, ...], answer: dict[str, tuple[str, ...]]
) -> EvalProblem:
    return EvalProblem(pid, cat, text, eqs, answer)


SOLVE = "다음 방정식을 푸시오."
SOLVE_LINEAR = "다음 일차방정식의 해를 구하시오."
SOLVE_SYSTEM = "다음 연립방정식을 푸시오."
SOLVE_QUAD = "다음 이차방정식을 푸시오."

PROBLEMS: list[EvalProblem] = [
    # linear
    _p("L01", "linear", f"{SOLVE}\n$2x + 3 = 7$", ("2*x + 3 = 7",), {"x": ("2",)}),
    _p("L02", "linear", f"{SOLVE_LINEAR}\n$5x - 4 = 3x + 8$", ("5*x - 4 = 3*x + 8",), {"x": ("6",)}),
    _p("L03", "linear", f"{SOLVE}\n$7 - 2x = x + 1$", ("7 - 2*x = x + 1",), {"x": ("2",)}),
    _p("L04", "linear", "방정식 $4x + 9 = -3$의 해를 구하시오.", ("4*x + 9 = -3",), {"x": ("-3",)}),
    _p("L05", "linear", f"{SOLVE_LINEAR}\n$-3x + 5 = 2x - 10$", ("-3*x + 5 = 2*x - 10",), {"x": ("3",)}),
    _p("L06", "linear", f"{SOLVE}\n$x - 7 = -3$", ("x - 7 = -3",), {"x": ("4",)}),
    _p(
        "L07",
        "linear",
        "방정식 $6x = 2x + 20$을 만족하는 x의 값을 구하시오.",
        ("6*x = 2*x + 20",),
        {"x": ("5",)},
    ),
    _p("L08", "linear", f"{SOLVE}\n$3x - 2 = 4x + 5$", ("3*x - 2 = 4*x + 5",), {"x": ("-7",)}),
    _p("L09", "linear", f"{SOLVE_LINEAR}\n$10 - 3x = -5$", ("10 - 3*x = -5",), {"x": ("5",)}),
    _p("L10", "linear", f"{SOLVE}\n$2x + 1 = x - 4$", ("2*x + 1 = x - 4",), {"x": ("-5",)}),
    # parentheses
    _p(
        "P01",
        "parentheses",
        "방정식 $3(x - 2) = 2x + 5$의 해를 구하시오.",
        ("3*(x - 2) = 2*x + 5",),
        {"x": ("11",)},
    ),
    _p("P02", "parentheses", f"{SOLVE}\n$2(x + 3) - 5 = 3x$", ("2*(x + 3) - 5 = 3*x",), {"x": ("1",)}),
    _p("P03", "parentheses", f"{SOLVE}\n$5(x - 1) = 3(x + 1)$", ("5*(x - 1) = 3*(x + 1)",), {"x": ("4",)}),
    _p(
        "P04",
        "parentheses",
        f"{SOLVE_LINEAR}\n$4(2x - 1) = 3(x + 2)$",
        ("4*(2*x - 1) = 3*(x + 2)",),
        {"x": ("2",)},
    ),
    _p("P05", "parentheses", f"{SOLVE}\n$-2(x - 4) = x - 1$", ("-2*(x - 4) = x - 1",), {"x": ("3",)}),
    _p(
        "P06",
        "parentheses",
        f"{SOLVE}\n$3(2x + 1) - 2(x - 3) = 17$",
        ("3*(2*x + 1) - 2*(x - 3) = 17",),
        {"x": ("2",)},
    ),
    _p(
        "P07",
        "parentheses",
        f"{SOLVE_LINEAR}\n$7 - (x + 2) = 2(x - 5)$",
        ("7 - (x + 2) = 2*(x - 5)",),
        {"x": ("5",)},
    ),
    _p("P08", "parentheses", f"{SOLVE}\n$2(3x - 1) = 4(x + 2)$", ("2*(3*x - 1) = 4*(x + 2)",), {"x": ("5",)}),
    # fractions
    _p("F01", "fractions", f"{SOLVE}\n$\\frac{{x}}{{2}} + 3 = 7$", ("x/2 + 3 = 7",), {"x": ("8",)}),
    _p(
        "F02",
        "fractions",
        f"{SOLVE}\n$\\frac{{x-1}}{{2}} = \\frac{{x+2}}{{3}}$",
        ("(x - 1)/2 = (x + 2)/3",),
        {"x": ("7",)},
    ),
    _p(
        "F03",
        "fractions",
        f"{SOLVE}\n$\\frac{{x}}{{3}} - \\frac{{x}}{{4}} = 2$",
        ("x/3 - x/4 = 2",),
        {"x": ("24",)},
    ),
    _p(
        "F04",
        "fractions",
        f"{SOLVE_LINEAR}\n$\\frac{{2x+1}}{{3}} = x - 1$",
        ("(2*x + 1)/3 = x - 1",),
        {"x": ("4",)},
    ),
    _p(
        "F05",
        "fractions",
        f"{SOLVE}\n$\\frac{{x}}{{2}} + \\frac{{x}}{{3}} = 10$",
        ("x/2 + x/3 = 10",),
        {"x": ("12",)},
    ),
    _p(
        "F06",
        "fractions",
        f"{SOLVE}\n$\\frac{{x+3}}{{4}} = \\frac{{2x-1}}{{3}}$",
        ("(x + 3)/4 = (2*x - 1)/3",),
        {"x": ("13/5",)},
    ),
    _p(
        "F07",
        "fractions",
        f"{SOLVE}\n$\\frac{{1}}{{2}}x - \\frac{{1}}{{3}} = \\frac{{1}}{{6}}x + 1$",
        ("x/2 - 1/3 = x/6 + 1",),
        {"x": ("4",)},
    ),
    _p("F08", "fractions", f"{SOLVE_LINEAR}\n$\\frac{{3x-2}}{{5}} = 2$", ("(3*x - 2)/5 = 2",), {"x": ("4",)}),
    _p("F09", "fractions", f"{SOLVE}\n$x - \\frac{{x-1}}{{3}} = 3$", ("x - (x - 1)/3 = 3",), {"x": ("4",)}),
    # decimals
    _p(
        "D01",
        "decimals",
        f"{SOLVE}\n$0.3x - 1.2 = 0.5x + 0.4$",
        ("3*x/10 - 12/10 = 5*x/10 + 4/10",),
        {"x": ("-8",)},
    ),
    _p("D02", "decimals", f"{SOLVE}\n$0.2x + 1.5 = 0.5x$", ("2*x/10 + 15/10 = 5*x/10",), {"x": ("5",)}),
    _p(
        "D03",
        "decimals",
        f"{SOLVE_LINEAR}\n$1.2x - 0.4 = 0.8x + 2$",
        ("12*x/10 - 4/10 = 8*x/10 + 2",),
        {"x": ("6",)},
    ),
    _p(
        "D04",
        "decimals",
        f"{SOLVE}\n$0.5(x - 2) = 0.3x + 0.4$",
        ("(x - 2)/2 = 3*x/10 + 4/10",),
        {"x": ("7",)},
    ),
    _p(
        "D05",
        "decimals",
        f"{SOLVE}\n$0.05x + 0.1 = 0.02x + 0.4$",
        ("5*x/100 + 1/10 = 2*x/100 + 4/10",),
        {"x": ("10",)},
    ),
    _p("D06", "decimals", f"{SOLVE_LINEAR}\n$2.5x - 3 = x + 1.5$", ("5*x/2 - 3 = x + 3/2",), {"x": ("3",)}),
    _p("D07", "decimals", f"{SOLVE}\n$0.4x + 0.6 = 1.8$", ("4*x/10 + 6/10 = 18/10",), {"x": ("3",)}),
    # systems of two equations
    _p(
        "S01",
        "system",
        f"{SOLVE_SYSTEM}\n$x + y = 5$\n$x - y = 1$",
        ("x + y = 5", "x - y = 1"),
        {"x": ("3",), "y": ("2",)},
    ),
    _p(
        "S02",
        "system",
        f"{SOLVE_SYSTEM}\n$2x + y = 7$\n$x - y = 2$",
        ("2*x + y = 7", "x - y = 2"),
        {"x": ("3",), "y": ("1",)},
    ),
    _p(
        "S03",
        "system",
        f"{SOLVE_SYSTEM}\n$x + 2y = 8$\n$3x - y = 3$",
        ("x + 2*y = 8", "3*x - y = 3"),
        {"x": ("2",), "y": ("3",)},
    ),
    _p(
        "S04",
        "system",
        f"{SOLVE_SYSTEM}\n$3x + 2y = 12$\n$x - y = -1$",
        ("3*x + 2*y = 12", "x - y = -1"),
        {"x": ("2",), "y": ("3",)},
    ),
    _p(
        "S05",
        "system",
        f"{SOLVE_SYSTEM}\n$y = 2x - 1$\n$3x + y = 9$",
        ("y = 2*x - 1", "3*x + y = 9"),
        {"x": ("2",), "y": ("3",)},
    ),
    _p(
        "S06",
        "system",
        "연립방정식 $2x - 3y = 1$, $x + y = 3$의 해를 구하시오.",
        ("2*x - 3*y = 1", "x + y = 3"),
        {"x": ("2",), "y": ("1",)},
    ),
    _p(
        "S07",
        "system",
        f"{SOLVE_SYSTEM}\n$4x + 3y = 10$\n$2x - y = 0$",
        ("4*x + 3*y = 10", "2*x - y = 0"),
        {"x": ("1",), "y": ("2",)},
    ),
    _p(
        "S08",
        "system",
        f"{SOLVE_SYSTEM}\n$\\frac{{x}}{{2}} + \\frac{{y}}{{3}} = 2$\n$x - y = -1$",
        ("x/2 + y/3 = 2", "x - y = -1"),
        {"x": ("2",), "y": ("3",)},
    ),
    # simple quadratics
    _p(
        "Q01",
        "quadratic",
        f"{SOLVE_QUAD}\n$x^{{2}} - 5x + 6 = 0$",
        ("x**2 - 5*x + 6 = 0",),
        {"x": ("2", "3")},
    ),
    _p("Q02", "quadratic", f"{SOLVE_QUAD}\n$x^{{2}} - 9 = 0$", ("x**2 - 9 = 0",), {"x": ("-3", "3")}),
    _p("Q03", "quadratic", f"{SOLVE_QUAD}\n$x^{{2}} + 4x + 4 = 0$", ("x**2 + 4*x + 4 = 0",), {"x": ("-2",)}),
    _p(
        "Q04",
        "quadratic",
        f"{SOLVE_QUAD}\n$x^{{2}} - 2x - 8 = 0$",
        ("x**2 - 2*x - 8 = 0",),
        {"x": ("-2", "4")},
    ),
    _p("Q05", "quadratic", f"{SOLVE_QUAD}\n$2x^{{2}} - 8 = 0$", ("2*x**2 - 8 = 0",), {"x": ("-2", "2")}),
    _p(
        "Q06",
        "quadratic",
        f"{SOLVE_QUAD}\n$x^{{2}} + x - 12 = 0$",
        ("x**2 + x - 12 = 0",),
        {"x": ("-4", "3")},
    ),
    _p("Q07", "quadratic", f"{SOLVE_QUAD}\n$x^{{2}} - 6x = 0$", ("x**2 - 6*x = 0",), {"x": ("0", "6")}),
    _p(
        "Q08",
        "quadratic",
        f"{SOLVE_QUAD}\n$(x - 1)(x + 5) = 0$",
        ("(x - 1)*(x + 5) = 0",),
        {"x": ("-5", "1")},
    ),
]

assert len(PROBLEMS) == 50
assert len({p.id for p in PROBLEMS}) == 50
