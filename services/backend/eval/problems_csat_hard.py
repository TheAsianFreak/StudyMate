# ruff: noqa: E501
"""Original killer / 준킬러 CSAT (수능)-style math problems: the hard companion of
eval/problems_csat_math.py.

Every problem is a 4점 item written for StudyMate in the style of 공통 14·15·20·21·22번 and
선택 28·29·30번 (none is taken or paraphrased from KICE 수능/모의평가 or EBS material). They
need case analysis or a hidden condition rather than one formula: recursive sequences read
backwards, parameters whose naive solution violates the domain, root counts of composite
functions, limits that must exist everywhere, counting with several interacting conditions.

The dataclass, the 5지선다 / 단답형 helpers, `judge` and `gt_text` are shared with
eval/problems_csat_math.py. `truth` recomputes each answer independently: brute force over
the finite objects (sequences, functions, arrangements, walks, lattice points), exact
enumeration for probabilities, or SymPy solving the stated conditions from a general
parametrisation and then re-checking every condition on the survivors (and, for the one
area problem, a numeric grid estimate). `derivation` is a short Korean solution sketch.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from fractions import Fraction
from itertools import combinations, permutations, product
from typing import Any

import mpmath
import numpy as np
import sympy
from sympy import (
    E,
    Interval,
    LambertW,
    Matrix,
    Rational,
    cos,
    diff,
    exp,
    integrate,
    limit,
    oo,
    pi,
    sin,
    sqrt,
    summation,
)
from sympy.calculus.util import maximum, minimum

from eval.problems_csat_math import (
    MARKS,
    SUBJECTS,
    CsatMathProblem,
    _mc,
    _short,
    correct_choice,
    gt_text,
    judge,
)

__all__ = [
    "MARKS",
    "PROBLEMS",
    "SUBJECTS",
    "SUBJECT_COUNTS",
    "CsatMathProblem",
    "correct_choice",
    "gt_text",
    "judge",
    "validate_problems",
]

x = sympy.Symbol("x", real=True)

# how many problems each subject has (공통 8, 확률과 통계 4, 미적분 5, 기하 3)
SUBJECT_COUNTS = {"수학Ⅰ": 4, "수학Ⅱ": 4, "확률과 통계": 4, "미적분": 5, "기하": 3}


# ---------------------------------------------------------------------------------------
# Independent recomputations
# ---------------------------------------------------------------------------------------


def _hm1_01() -> int:
    """Every a_1 simulated forward. a_{n+1} >= a_n / 2, so a_6 = 6 needs a_1 <= 2^5 * 6."""
    found = []
    for a1 in range(1, 2 * 2**5 * 6):
        a = a1
        for n in range(1, 6):
            a = a // 2 if a % 2 == 0 else a + n
        if a == 6:
            found.append(a1)
    assert found and max(found) <= 2**5 * 6
    return sum(found)


def _hm1_02() -> sympy.Expr:
    """Candidates of M(a) - m(a) = 6 from every pair of candidate extreme values, kept only
    when SymPy's own maximum/minimum over the x-interval confirm the difference."""
    a = sympy.Symbol("a", real=True)
    s = sympy.Symbol("s", real=True)
    # sin x covers [-1/2, 1] on [0, 7pi/6]; cos 2x + 2a sin x = 1 - 2s^2 + 2as there
    fs = 1 - 2 * s**2 + 2 * a * s
    vertex = sympy.solve(diff(fs, s), s)[0]
    cands = [fs.subs(s, v) for v in (Rational(-1, 2), 1, vertex)]
    roots: set[Any] = set()
    for i, hi in enumerate(cands):
        for j, lo in enumerate(cands):
            if i != j:
                roots.update(r for r in sympy.solve(sympy.Eq(hi - lo, 6), a) if r.is_real)
    dom = Interval(0, 7 * pi / 6)
    good = []
    for r in roots:
        fx = cos(2 * x) + 2 * r * sin(x)
        if sympy.simplify(maximum(fx, x, dom) - minimum(fx, x, dom) - 6) == 0:
            good.append(r)
    assert len(good) == 2
    return sympy.Mul(*good)


def _hm1_03() -> int:
    """Lattice points counted two ways: the inequality 2^i - n <= j <= log2(i + n) over a
    box, and column by column between the two numerically found intersections."""

    def by_box(n: int) -> int:
        return sum(
            1
            for i in range(1 - n, 3 * n)
            for j in range(-3 * n, 3 * n)
            if Fraction(2) ** i - n <= j and Fraction(2) ** j <= i + n
        )

    def by_columns(n: int) -> int:
        gap = lambda v: mpmath.power(2, v) - n - mpmath.log(v + n, 2)  # noqa: E731
        left = mpmath.findroot(gap, (-n + mpmath.mpf("1e-9"), 0), solver="bisect")
        right = mpmath.findroot(gap, (0, n), solver="bisect")
        total = 0
        for i in range(int(mpmath.ceil(left)), int(mpmath.floor(right)) + 1):
            top = (i + n).bit_length() - 1  # floor(log2(i + n))
            low = Fraction(2) ** i - n
            bottom = -((-low.numerator) // low.denominator)  # ceil
            total += max(0, top - bottom + 1)
        return total

    for n in (4, 6):
        assert by_box(n) == by_columns(n), n
    return by_box(4) + by_box(6)


def _hm1_04() -> sympy.Expr:
    """Coordinates: A = O, B on the x-axis, cos A unknown; D where the bisector (sum of the
    unit vectors along AB, AC) meets BC; E the second intersection with the circumcircle."""
    c = sympy.Symbol("c", real=True)  # cos A
    B = Matrix([6, 0])
    C = Matrix([4 * c, 4 * sqrt(1 - c**2)])
    u = B / 6 + C / 4
    lam, mu = sympy.symbols("lam mu", real=True)
    sol = sympy.solve(list(lam * u - B - mu * (C - B)), [lam, mu], dict=True)[0]
    D = (lam * u).subs(sol)
    cvals = [v for v in sympy.solve(sympy.simplify(D.dot(D)) - 18, c) if -1 < v < 1]
    assert len(cvals) == 1
    Cn, Dn = C.subs(c, cvals[0]), D.subs(c, cvals[0]).applyfunc(sympy.simplify)
    ox, oy, tt = sympy.symbols("ox oy tt", real=True)
    cc = Matrix([ox, oy])  # circumcenter: equidistant from A = origin, B and C
    eqs = [cc.dot(cc) - (cc - B).dot(cc - B), cc.dot(cc) - (cc - Cn).dot(cc - Cn)]
    On = cc.subs(sympy.solve(eqs, [ox, oy], dict=True)[0])
    ts = [v for v in sympy.solve((tt * Dn - On).dot(tt * Dn - On) - On.dot(On), tt) if v != 0]
    En = ts[0] * Dn
    u1, u2 = B - En, Cn - En
    return sympy.radsimp(sympy.simplify(sympy.Abs(u1[0] * u2[1] - u1[1] * u2[0]) / 2))


def _hm2_01() -> int:
    """Distinct real roots of the degree-9 polynomial f(f(x)) for each k (square-free part)."""
    total = 0
    for kv in range(5):
        f = x**3 - 3 * x**2 + kv
        comp = sympy.Poly(sympy.expand(f.subs(x, f)), x)
        total += comp.sqf_part().count_roots()
    return total


def _limit_exists_everywhere(f: sympy.Expr) -> bool:
    """lim_{x -> alpha} f(2x - 1) / f(x) is finite for every real alpha (only zeros of f matter)."""
    ratio = f.subs(x, 2 * x - 1) / f
    for r in set(sympy.Poly(f, x).real_roots()):
        try:
            if not limit(ratio, x, r, dir="+-").is_finite:
                return False
        except ValueError:  # the one-sided limits differ
            return False
    return True


def _hm2_02() -> sympy.Expr:
    """General monic cubic with f(0) = -4 and f'(2) = f(2)^2; condition (가) forces the real
    zeros to be 1 (they are closed under r -> 2r - 1), then (가) is re-checked with limits."""
    b, c = sympy.symbols("b c", real=True)
    f = x**3 + b * x**2 + c * x - 4
    eqs = [f.subs(x, 1), diff(f, x).subs(x, 2) - f.subs(x, 2) ** 2]
    values = set()
    rejected = 0
    for sol in sympy.solve(eqs, [b, c], dict=True):
        fs = sympy.expand(f.subs(sol))
        if _limit_exists_everywhere(fs):
            values.add(fs.subs(x, 5))
        else:
            rejected += 1
    assert len(values) == 1 and rejected == 1  # (x - 1)(x - 2)^2 fails at alpha = 2
    return values.pop()


def _hm2_03() -> sympy.Expr:
    """f = p(x - 2m) + mk on [2m, 2m + 2); continuity and differentiability at x = 2 and the
    integral condition fix a, b, k; the integral is summed piece by piece."""
    a, b, k = sympy.symbols("a b k", real=True)
    p = x**3 + a * x**2 + b * x
    eqs = [
        p.subs(x, 2) - (p.subs(x, 0) + k),  # f(2-) = f(2) = f(0) + k
        diff(p, x).subs(x, 2) - diff(p, x).subs(x, 0),  # f'(2-) = f'(2+) = p'(0)
        integrate(p, (x, 0, 2)) - 4,
    ]
    sol = sympy.solve(eqs, [a, b, k], dict=True)
    assert len(sol) == 1
    pp, kk = p.subs(sol[0]), k.subs(sol[0])
    total = sympy.Integer(0)
    for m in range(-1, 3):
        lo, hi = max(2 * m, -1), min(2 * m + 2, 5)
        total += integrate(pp.subs(x, x - 2 * m) + m * kk, (x, lo, hi))
    return total


def _quartic_ok(g: sympy.Expr) -> bool:
    """(가) g >= 0, (나) exactly two distinct real zeros, (다) every local maximum value is 4."""
    gp = sympy.Poly(diff(g, x), x)
    crit = sorted(set(gp.real_roots()), key=float)
    if any(g.subs(x, cp) < 0 for cp in crit):  # positive leading term: the minimum is critical
        return False
    if sympy.Poly(g, x).sqf_part().count_roots() != 2:
        return False
    maxima = [g.subs(x, cp) for cp in crit if diff(g, x, 2).subs(x, cp) < 0]
    return bool(maxima) and all(sympy.simplify(v - 4) == 0 for v in maxima)


def _hm2_04() -> sympy.Expr:
    """g = x^4/4 + p x^3/3 + q x^2/2 (g(0) = 0 is a minimum of g >= 0, so f(0) = 0); the other
    zero s is a minimum too; a critical value equals 4; survivors are re-checked."""
    p, q, s = sympy.symbols("p q s", real=True)
    g = x**4 / 4 + p * x**3 / 3 + q * x**2 / 2
    values = set()
    for sol in sympy.solve([g.subs(x, s), diff(g, x).subs(x, s)], [p, q], dict=True):
        gs = sympy.factor(g.subs(sol))
        for cp in sympy.solve(diff(gs, x), x):
            for sv in sympy.solve(gs.subs(x, cp) - 4, s):
                if not sv.is_real or sv == 0:
                    continue
                gv = sympy.expand(gs.subs(s, sv))
                if _quartic_ok(gv):
                    values.add(diff(gv, x).subs(x, 3))
    assert len(values) == 2
    return sympy.Add(*values)


def _hps_01() -> int:
    count = 0
    for vals in product(range(1, 7), repeat=6):
        f = dict(zip(range(1, 7), vals, strict=True))
        if f[1] <= f[2] <= f[3] <= f[4] and f[f[4]] == 4 and f[5] + f[6] == f[1] + f[4]:
            count += 1
    return count


def _hps_02() -> sympy.Expr:
    """Exact enumeration of the die, the moved balls and the two balls drawn from B."""
    bag_a = "WWWBB"
    bag_b = "WBBB"
    both_white = Fraction(0)
    three_and_white = Fraction(0)
    for die in range(1, 7):
        moved = 1 if die <= 2 else 2 if die <= 4 else 3
        picks = list(combinations(range(5), moved))
        for pick in picks:
            bag = bag_b + "".join(bag_a[i] for i in pick)
            pairs = list(combinations(bag, 2))
            pr = Fraction(1, 6) / len(picks) * Fraction(sum(pair == ("W", "W") for pair in pairs), len(pairs))
            both_white += pr
            if moved == 3:
                three_and_white += pr
    ans = three_and_white / both_white
    return Rational(ans.numerator, ans.denominator)


def _hps_03() -> int:
    good = 0
    for tosses in product((1, -1), repeat=8):  # 1: x + 1, -1: y + 1
        diff_xy = 0
        ok = True
        for step in tosses:
            diff_xy += step
            ok = ok and abs(diff_xy) <= 2
        good += ok
    return good  # 256p


def _hps_04() -> int:
    words = set(permutations("AABBCCD"))
    return sum(1 for w in words if all(w[i] != w[i + 1] for i in range(6)) and w[0] != "D" and w[-1] != "D")


def _hca_01() -> sympy.Expr:
    """With w = x^(2n): w -> 0 inside |x| < 1, w -> oo outside; f(+-1) straight from n -> oo.
    Continuity and equal one-sided derivatives of f(x)g(x) at x = 1 and x = -1."""
    n = sympy.Symbol("n", integer=True, positive=True)
    w = sympy.Symbol("w", positive=True)
    frac = (x * w - 1) / (w + 1)
    inner, outer = limit(frac, w, 0), limit(frac, w, oo)
    at = {v: limit((v ** (2 * n + 1) - 1) / (v ** (2 * n) + 1), n, oo) for v in (1, -1)}
    assert limit((Rational(1, 2) ** (2 * n + 1) - 1) / (Rational(1, 2) ** (2 * n) + 1), n, oo) == inner.subs(
        x, Rational(1, 2)
    )
    b, c, d = sympy.symbols("b c d", real=True)
    g = x**3 + b * x**2 + c * x + d
    eqs = []
    for v, left, right in ((1, inner, outer), (-1, outer, inner)):
        hl, hr, hv = left * g, right * g, at[v] * g.subs(x, v)
        eqs += [hl.subs(x, v) - hv, hr.subs(x, v) - hv, diff(hl, x).subs(x, v) - diff(hr, x).subs(x, v)]
    sol = sympy.solve(eqs, [b, c, d], dict=True)
    assert len(sol) == 1
    return g.subs(sol[0]).subs(x, 3)


def _hca_02() -> sympy.Expr:
    """g(X) integrated symbolically; its critical points k*pi are classified by the sign of
    g' on both sides, then the series is summed by SymPy."""
    t = sympy.Symbol("t", real=True)
    big_x = sympy.Symbol("X", positive=True)
    g = integrate(exp(-t) * sin(t), (t, 0, big_x))

    def gp(v: sympy.Expr) -> sympy.Expr:  # g'(v)
        return exp(-v) * sin(v)

    for kk in range(1, 9):
        before, after = gp(kk * pi - pi / 2), gp(kk * pi + pi / 2)
        assert (before > 0 > after) if kk % 2 else (before < 0 < after)
    nn = sympy.Symbol("nn", integer=True, positive=True)
    term = sympy.simplify(g.subs(big_x, (2 * nn - 1) * pi) - g.subs(big_x, 2 * nn * pi))
    # SymPy sums q^n but not exp(-2 pi n): write every exp(z) as q^(-z/pi) with q = e^(-pi)
    q = sympy.Symbol("q", positive=True)
    term_q = sympy.powsimp(term.replace(exp, lambda z: q ** sympy.expand(-z / pi)))
    assert sympy.simplify(term_q.subs(q, exp(-pi)) - term) == 0
    total = summation(term_q, (nn, 1, oo)).subs(q, exp(-pi))
    return sympy.simplify(sympy.piecewise_fold(total).doit())


def _sin_extrema(a: sympy.Expr, b: sympy.Expr) -> list[tuple[Any, str]]:
    """Extremum points of g(x) = f(sin x), f = x^3 + ax^2 + bx, on (0, 2pi) with their kind."""
    s = sympy.Symbol("s", real=True)
    pts: list[Any] = [pi / 2, 3 * pi / 2]  # zeros of cos x
    for r in sympy.solve(3 * s**2 + 2 * a * s + b, s):
        if r.is_real and abs(r) <= 1:
            base = sympy.asin(r)
            for v in (base, pi - base, base + 2 * pi):
                if 0 < v < 2 * pi:
                    pts.append(v)
    crit = sorted({sympy.nsimplify(v) for v in pts}, key=float)
    edges = [sympy.Integer(0), *crit, 2 * pi]

    def gprime(v: sympy.Expr) -> sympy.Expr:
        return cos(v) * (3 * sin(v) ** 2 + 2 * a * sin(v) + b)

    signs = [sympy.sign(sympy.N(gprime((lo + hi) / 2), 30)) for lo, hi in zip(edges, edges[1:], strict=False)]
    out = []
    for i, cp in enumerate(crit):
        if signs[i] > 0 > signs[i + 1]:
            out.append((cp, "max"))
        elif signs[i] < 0 < signs[i + 1]:
            out.append((cp, "min"))
    return out


def _hca_03() -> sympy.Expr:
    """(가) gives b = -3/4 - a. The extremum count can only change when the other zero r(a)
    of f' crosses s = -1, 0, 1/2 or 1; the count is evaluated at those a and in between."""
    a = sympy.Symbol("a", real=True)
    s = sympy.Symbol("s", real=True)
    b = -Rational(3, 4) - a
    zeros = sympy.solve(3 * s**2 + 2 * a * s + b, s)
    other = next(z for z in zeros if sympy.simplify(z - Rational(1, 2)) != 0)
    special = sorted({sympy.solve(other - s0, a)[0] for s0 in (-1, 0, Rational(1, 2), 1)})
    samples = [special[0] - 1, *special, special[-1] + 1]
    samples += [(lo + hi) / 2 for lo, hi in zip(special, special[1:], strict=False)]
    hits = []
    for av in samples:
        ext = _sin_extrema(av, b.subs(a, av))
        if len(ext) == 5 and any(sympy.simplify(p - pi / 6) == 0 for p, _ in ext):
            hits.append((av, ext))
    assert len(hits) == 1
    av, ext = hits[0]
    bv = b.subs(a, av)

    def f(v: sympy.Expr) -> sympy.Expr:
        return v**3 + av * v**2 + bv * v

    big_m = sum(f(sin(p)) for p, kind in ext if kind == "max")
    small_m = sum(f(sin(p)) for p, kind in ext if kind == "min")
    return sympy.nsimplify(16 * (big_m - small_m))


def _hca_04() -> sympy.Expr:
    """The inverse of x e^x (x >= 0) is the principal Lambert W; W(e) = 1, W(2e^2) = 2."""
    v = sympy.Symbol("v", positive=True)
    val = integrate(LambertW(v) / v, (v, E, 2 * E**2))
    assert sympy.simplify(2 * exp(2) - 2 * E**2) == 0 and LambertW(E) == 1
    val = sympy.simplify(val.subs(LambertW(2 * E**2), 2))
    mpmath.mp.dps = 30
    num = mpmath.quad(lambda t: mpmath.lambertw(t).real / t, [mpmath.e, 2 * mpmath.e**2])
    assert abs(num - mpmath.mpf(sympy.N(val, 30))) < mpmath.mpf("1e-20")
    return val


def _hca_05() -> sympy.Expr:
    """Coordinates for P, Q, H; S = triangle OPQ minus sector OAP; r = 2 * area / perimeter."""
    th = sympy.Symbol("theta", positive=True)
    P = Matrix([cos(th), sin(th)])
    qx = sympy.solve(P[0] * x - 1, x)[0]  # the tangent P . X = 1 meets y = 0
    Q, H, origin = Matrix([qx, 0]), Matrix([cos(th), 0]), Matrix([0, 0])

    def area(u: Matrix, v: Matrix, w: Matrix) -> sympy.Expr:
        e1, e2 = v - u, w - u
        return sympy.Abs(e1[0] * e2[1] - e1[1] * e2[0]) / 2

    def dist(u: Matrix, v: Matrix) -> sympy.Expr:
        return sqrt((u - v).dot(u - v))

    big_s = area(origin, P, Q) - th / 2  # triangle OPQ minus the sector OAP
    r = 2 * area(P, H, Q) / (dist(P, H) + dist(H, Q) + dist(Q, P))
    exact = big_s / (th * r)
    # only theta -> 0+ matters: drop each |z| with the sign z has on (0, 1/10]
    ratio = exact.replace(
        lambda e: isinstance(e, sympy.Abs),
        lambda e: e.args[0] if sympy.N(e.args[0].subs(th, Rational(1, 10))) > 0 else -e.args[0],
    )
    small = Rational(1, 1000)
    assert abs(float(ratio.subs(th, small)) - float(exact.subs(th, small))) < 1e-9
    return limit(ratio, th, 0, "+")


def _hge_01() -> sympy.Expr:
    """From the incircle (center (2, 1), radius 1): F' from the tangent of slope 5/12, P from
    the other tangent through F; a from |PF' - PF| = 2a; P re-checked on the hyperbola."""
    center = Matrix([2, 1])
    c = sympy.Symbol("c", positive=True)
    # line 5x - 12y + 5c = 0 through F'(-c, 0) tangent to the circle
    cvals = sympy.solve((5 * center[0] - 12 * center[1] + 5 * c) ** 2 - 13**2, c)
    assert len(cvals) == 1
    cv = cvals[0]
    # lines through F: (x - c) cos(phi) + y sin(phi) = 0 with cos, sin rational in t = tan(phi/2)
    # (this also covers a vertical line); the x-axis itself has cos(phi) = 0
    t = sympy.Symbol("t", real=True)
    cph, sph = (1 - t**2) / (1 + t**2), 2 * t / (1 + t**2)
    normals = {
        (cph.subs(t, tv), sph.subs(t, tv))
        for tv in sympy.solve(((center[0] - cv) * cph + center[1] * sph) ** 2 - 1, t)
        if cph.subs(t, tv) != 0
    }
    assert len(normals) == 1
    nu, nv = normals.pop()
    y = sympy.Symbol("y", real=True)
    psol = sympy.solve([nu * (x - cv) + nv * y, y - Rational(5, 12) * (x + cv)], [x, y], dict=True)[0]
    P = Matrix([psol[x], psol[y]])
    F, F2 = Matrix([cv, 0]), Matrix([-cv, 0])
    pf, pf2, ff = (P - F).norm(), (P - F2).norm(), 2 * cv
    incenter = (ff * P + pf * F2 + pf2 * F) / (ff + pf + pf2)
    assert sympy.simplify(incenter - center) == Matrix([0, 0])
    a = (pf2 - pf) / 2
    b2 = cv**2 - a**2
    assert P[0] > 0 < P[1] and sympy.simplify(P[0] ** 2 / a**2 - P[1] ** 2 / b2 - 1) == 0
    return 4 * (ff * P[1] / 2)


def _hge_02() -> sympy.Expr:
    """X = P + Q sweeps the unit circles centered on the upper half of the circle of radius 2
    around (6, 0): {X : dist(X, arc) <= 1} (the farthest arc point is always >= 2 away).
    Exact: half annulus 1 <= |X - (6, 0)| <= 3 above the axis plus two half unit disks below;
    checked against a grid estimate using the distance to the arc."""
    exact = pi * (3**2 - 1**2) / 2 + 2 * (pi * 1**2 / 2)
    h = 0.004
    gx, gy = np.meshgrid(np.arange(2.5, 9.5, h), np.arange(-1.5, 3.5, h))
    u, v = gx - 6.0, gy
    radial = np.abs(np.hypot(u, v) - 2.0)
    to_ends = np.minimum(np.hypot(u - 2.0, v), np.hypot(u + 2.0, v))
    dist = np.where(v >= 0, radial, to_ends)
    estimate = float(np.count_nonzero(dist <= 1.0)) * h * h
    assert abs(estimate - float(exact)) < 0.02 * float(exact), estimate
    return exact


def _hge_03() -> sympy.Expr:
    """Lagrange multipliers for the maximum of |AB x AP|^2 on the sphere, then the area of the
    projected triangle."""
    center = Matrix([-1, -1, 2])
    A, B = Matrix([6, 0, 0]), Matrix([0, 6, 0])
    px, py, pz, lam = sympy.symbols("px py pz lam", real=True)
    P = Matrix([px, py, pz])
    cr = (B - A).cross(P - A)
    obj = cr.dot(cr)
    con = (P - center).dot(P - center) - 9
    eqs = [diff(obj, v) - lam * diff(con, v) for v in (px, py, pz)] + [con]
    sols = sympy.solve(eqs, [px, py, pz, lam], dict=True)
    best = max(sols, key=lambda so: float(obj.subs(so)))
    P0 = P.subs(best)
    proj = Matrix([P0[0], P0[1], 0])
    pc = (B - A).cross(proj - A)
    return sympy.simplify(sqrt(pc.dot(pc)) / 2)


# ---------------------------------------------------------------------------------------
# Problems
# ---------------------------------------------------------------------------------------

PROBLEMS: list[CsatMathProblem] = [
    # ------------------------------------------------------------------ 수학Ⅰ
    _short(
        "HM1-01",
        "수학Ⅰ",
        "모든 항이 자연수인 수열 $\\{a_n\\}$이 모든 자연수 $n$에 대하여 다음 조건을 만족시킨다.\n"
        "$a_n$이 짝수이면 $a_{n+1} = \\frac{a_n}{2}$이고, $a_n$이 홀수이면 $a_{n+1} = a_n + n$이다.\n"
        "$a_6 = 6$일 때, 가능한 모든 $a_1$의 값의 합을 구하시오.",
        4,
        "473",
        _hm1_01,
        "거꾸로 추적: $a_{n+1} = m$이면 $a_n = 2m$ 또는 ($m - n$이 홀수인 자연수일 때) $a_n = m - n$. "
        "$a_5 \\in \\{12, 1\\}$, $a_4 \\in \\{24, 2\\}$ ($12 - 4 = 8$은 짝수라 제외), $a_3 \\in \\{48, 21, 4\\}$, "
        "$a_2 \\in \\{96, 42, 19, 8\\}$ ($46$, $2$는 짝수라 제외), $a_1 \\in \\{192, 95, 84, 41, 38, 16, 7\\}$ ($18$, $6$ 제외). 합 473.",
    ),
    _mc(
        "HM1-02",
        "수학Ⅰ",
        "실수 $a$에 대하여 닫힌구간 $\\left[0, \\frac{7}{6}\\pi\\right]$에서 정의된 함수 $f(x) = \\cos 2x + 2a\\sin x$의 "
        "최댓값을 $M(a)$, 최솟값을 $m(a)$라 하자. $M(a) - m(a) = 6$을 만족시키는 모든 실수 $a$의 값의 곱은?",
        4,
        ("-\\frac{15}{4}", "-3", "-\\frac{9}{4}", "-\\frac{3}{2}", "-\\frac{3}{4}"),
        "Rational(-15, 4)",
        _hm1_02,
        "$\\sin x = s$로 두면 $s \\in [-\\frac{1}{2}, 1]$에서 $h(s) = -2s^2 + 2as + 1$. 꼭짓점 $s = \\frac{a}{2}$가 구간 안($-1 \\le a \\le 2$)이면 "
        "$M - m = \\frac{(a-2)^2}{2}$ ($a < \\frac{1}{2}$) 또는 $\\frac{(a+1)^2}{2}$ ($a \\ge \\frac{1}{2}$)인데 $= 6$의 해 $2 - 2\\sqrt{3}$, $-1 + 2\\sqrt{3}$은 범위 밖. "
        "$a < -1$이면 $M - m = \\frac{3}{2} - 3a = 6$에서 $a = -\\frac{3}{2}$, $a > 2$이면 $3a - \\frac{3}{2} = 6$에서 $a = \\frac{5}{2}$. 곱 $-\\frac{15}{4}$.",
    ),
    _short(
        "HM1-03",
        "수학Ⅰ",
        "자연수 $n$에 대하여 두 곡선 $y = 2^x - n$, $y = \\log_2(x + n)$으로 둘러싸인 부분의 내부 또는 경계 위에 있는 점 중 "
        "$x$좌표와 $y$좌표가 모두 정수인 점의 개수를 $a_n$이라 하자. $a_4 + a_6$의 값을 구하시오.",
        4,
        "87",
        _hm1_03,
        "두 곡선은 서로 역함수 관계라 교점은 $y = x$ 위에 있고, 둘러싸인 부분은 $2^x - n \\le y \\le \\log_2(x + n)$. "
        "정수 $x = i$마다 $\\lceil 2^i - n \\rceil \\le j \\le \\lfloor \\log_2(i + n) \\rfloor$를 센다. "
        "$n = 4$ (교점 $x \\approx -3.94, 2.76$): $i = -3, \\dots, 2$에서 $4 + 5 + 5 + 6 + 5 + 3 = 28$. "
        "$n = 6$ (교점 $x \\approx -5.98, 3.21$):$i = -5, \\dots, 3$에서 $6 + 7 + 7 + 8 + 8 + 8 + 7 + 6 + 2 = 59$. 합 87.",
    ),
    _mc(
        "HM1-04",
        "수학Ⅰ",
        "삼각형 $ABC$에서 $\\overline{AB} = 6$, $\\overline{AC} = 4$이다. 각 $A$의 이등분선이 선분 $BC$와 만나는 점을 $D$라 할 때 "
        "$\\overline{AD} = 3\\sqrt{2}$이다. 직선 $AD$가 삼각형 $ABC$의 외접원과 만나는 점 중 $A$가 아닌 점을 $E$라 할 때, "
        "삼각형 $BEC$의 넓이는?",
        4,
        (
            "\\frac{3\\sqrt{7}}{4}",
            "\\sqrt{7}",
            "\\frac{5\\sqrt{7}}{4}",
            "\\frac{3\\sqrt{7}}{2}",
            "\\frac{7\\sqrt{7}}{4}",
        ),
        "5*sqrt(7)/4",
        _hm1_04,
        "넓이 분할 $\\frac{1}{2} \\cdot 6 \\cdot AD \\sin\\frac{A}{2} + \\frac{1}{2} \\cdot 4 \\cdot AD \\sin\\frac{A}{2} = \\frac{1}{2} \\cdot 24 \\sin A$에서 "
        "$\\cos\\frac{A}{2} = \\frac{5\\sqrt{2}}{8}$, $\\cos A = \\frac{9}{16}$, $BC = 5$. $E$는 호 $BC$의 중점이라 $EB = EC = \\frac{BC}{2\\cos(A/2)} = 2\\sqrt{2}$, "
        "$\\angle BEC = \\pi - A$. 넓이 $\\frac{1}{2} \\cdot 8 \\cdot \\sin A = 4 \\cdot \\frac{5\\sqrt{7}}{16} = \\frac{5\\sqrt{7}}{4}$.",
    ),
    # ------------------------------------------------------------------ 수학Ⅱ
    _short(
        "HM2-01",
        "수학Ⅱ",
        "정수 $k$에 대하여 함수 $f(x) = x^3 - 3x^2 + k$라 하고, $x$에 대한 방정식 $f(f(x)) = 0$의 서로 다른 실근의 개수를 $a_k$라 하자. "
        "$a_0 + a_1 + a_2 + a_3 + a_4$의 값을 구하시오.",
        4,
        "30",
        _hm2_01,
        "$f$의 극댓값 $k$ ($x = 0$), 극솟값 $k - 4$ ($x = 2$). $f(f(x)) = 0 \\iff f(x) = r$ ($f(r) = 0$)이고, $f(x) = r$의 실근은 "
        "$k - 4 < r < k$이면 3개, $r = k$ 또는 $k - 4$이면 2개, 아니면 1개. "
        "$k = 0$: $r = 0$(중근), $3$ → $2 + 1 = 3$. $k = 1, 2$: 세 근 중 둘만 $(k - 4, k)$ 안 → $3 + 3 + 1 = 7$. "
        "$k = 3$: $f(-1) = -1 < 0$이라 가장 작은 근도 $(-1, 0)$ 안 → 9. $k = 4$: $r = -1, 2$(중근) → $1 + 3 = 4$. 합 30.",
    ),
    _short(
        "HM2-02",
        "수학Ⅱ",
        "최고차항의 계수가 $1$인 삼차함수 $f(x)$가 다음 조건을 만족시킨다.\n"
        "(가) 모든 실수 $\\alpha$에 대하여 $\\lim_{x \\to \\alpha} \\frac{f(2x - 1)}{f(x)}$의 값이 존재한다.\n"
        "(나) $f(0) = -4$\n"
        "(다) $f'(2) = \\{f(2)\\}^2$\n"
        "$f(5)$의 값을 구하시오.",
        4,
        "51",
        _hm2_02,
        "$f(\\alpha) = 0$이면 $f(2\\alpha - 1) = 0$이어야 하므로 실근 집합이 $r \\mapsto 2r - 1$에 대해 닫혀 있고, 유한집합이라 $r = 1$뿐. "
        "$f = (x - 1)(x^2 + px + q)$ ($x^2 + px + q$는 실근이 없음), (나)에서 $q = 4$. (다): $12 + 3p = (8 + 2p)^2$에서 $p = -\\frac{13}{4}$ 또는 $-4$인데 "
        "$p = -4$는 $(x - 2)^2$를 만들어 (가)에 모순. $f(5) = 4\\left(25 - \\frac{65}{4} + 4\\right) = 51$.",
    ),
    _short(
        "HM2-03",
        "수학Ⅱ",
        "실수 전체의 집합에서 미분가능한 함수 $f(x)$가 다음 조건을 만족시킨다.\n"
        "(가) $0 \\le x < 2$일 때, $f(x) = x^3 + ax^2 + bx$이다.\n"
        "(나) 모든 실수 $x$에 대하여 $f(x + 2) = f(x) + k$이다.\n"
        "(다) $\\int_{0}^{2} f(x)\\,dx = 4$\n"
        "$\\int_{-1}^{5} f(x)\\,dx$의 값을 구하시오. (단, $a$, $b$, $k$는 상수이다.)",
        4,
        "24",
        _hm2_03,
        "$x = 2$에서 연속: $8 + 4a + 2b = k$, 미분가능: $12 + 4a + b = b$이므로 $a = -3$. (다): $4 - 8 + 2b = 4$에서 $b = 4$, $k = 4$. "
        "$\\int_{-1}^{0} f = \\int_{1}^{2}(f - 4) = \\frac{11}{4} - 4$, $\\int_0^2 f = 4$, $\\int_2^4 f = 4 + 8$, $\\int_4^5 f = \\int_0^1 (f + 8) = \\frac{5}{4} + 8$. 합 24.",
    ),
    _mc(
        "HM2-04",
        "수학Ⅱ",
        "최고차항의 계수가 $1$인 삼차함수 $f(x)$에 대하여 함수 $g(x) = \\int_{0}^{x} f(t)\\,dt$가 다음 조건을 만족시킨다.\n"
        "(가) 모든 실수 $x$에 대하여 $g(x) \\ge 0$이다.\n"
        "(나) 방정식 $g(x) = 0$의 서로 다른 실근의 개수는 $2$이다.\n"
        "(다) 함수 $g(x)$의 극댓값은 $4$이다.\n"
        "가능한 모든 $f(3)$의 값의 합은?",
        4,
        ("93", "96", "99", "102", "105"),
        "102",
        _hm2_04,
        "$g(0) = 0$이 최솟값이라 $g'(0) = f(0) = 0$, $g = x^2\\left(\\frac{x^2}{4} + \\cdots\\right)$. 다른 근 $s \\ne 0$도 최솟점이라 중근: "
        "$g = \\frac{1}{4}x^2(x - s)^2$. 극댓값 $g\\left(\\frac{s}{2}\\right) = \\frac{s^4}{64} = 4$에서 $s = \\pm 4$. "
        "$f = g' = \\frac{1}{2}x(x - s)(2x - s)$: $s = 4$이면 $f(3) = -3$, $s = -4$이면 $f(3) = 105$. 합 102.",
    ),
    # ------------------------------------------------------------------ 확률과 통계
    _short(
        "HPS-01",
        "확률과 통계",
        "집합 $X = \\{1, 2, 3, 4, 5, 6\\}$에 대하여 다음 조건을 만족시키는 함수 $f: X \\to X$의 개수를 구하시오.\n"
        "(가) $f(1) \\le f(2) \\le f(3) \\le f(4)$\n"
        "(나) $f(f(4)) = 4$\n"
        "(다) $f(5) + f(6) = f(1) + f(4)$",
        4,
        "180",
        _hps_01,
        "$f(4) = c$, $f(c) = 4$. $c \\le 4$이면 $4 = f(c) \\le f(4) = c$라 $c = 4$. 따라서 $c = 4$, $5$ ($f(5) = 4$), $6$ ($f(6) = 4$). "
        "$c = 4$: $f(1) = i$일 때 $(f(2), f(3))$은 $\\binom{6 - i}{2}$가지, $f(5) + f(6) = i + 4$의 해는 $4, 5, 6, 5$가지 → $40 + 30 + 18 + 5 = 93$. "
        "$c = 5$: $f(6) = f(1) + 1$, $\\sum_{i=1}^{5}\\binom{7-i}{2} = 35$. $c = 6$: $f(5) = f(1) + 2$라 $f(1) \\le 4$, $\\sum_{i=1}^{4}\\binom{8-i}{2} = 52$. 합 180.",
    ),
    _mc(
        "HPS-02",
        "확률과 통계",
        "주머니 A에는 흰 공 $3$개와 검은 공 $2$개가 들어 있고, 주머니 B에는 흰 공 $1$개와 검은 공 $3$개가 들어 있다. "
        "한 개의 주사위를 한 번 던져 나온 눈의 수가 $2$ 이하이면 주머니 A에서 임의로 $1$개의 공을, $3$ 또는 $4$이면 임의로 $2$개의 공을, "
        "$5$ 이상이면 임의로 $3$개의 공을 동시에 꺼내어 주머니 B에 넣는다. 그 후 주머니 B에서 임의로 $2$개의 공을 동시에 꺼냈더니 모두 흰 공이었을 때, "
        "주사위의 눈의 수가 $5$ 이상이었을 확률은?",
        4,
        ("\\frac{35}{101}", "\\frac{40}{101}", "\\frac{45}{101}", "\\frac{50}{101}", "\\frac{55}{101}"),
        "Rational(45, 101)",
        _hps_02,
        "옮긴 흰 공 수 $w$에 따라 B에서 두 흰 공을 뽑을 확률 $\\binom{1+w}{2}/\\binom{4+m}{2}$ ($m$: 옮긴 공 수). "
        "$m = 1$: $\\frac{3}{5} \\cdot \\frac{1}{10} = \\frac{3}{50}$. $m = 2$: $\\frac{3}{10} \\cdot \\frac{3}{15} + \\frac{6}{10} \\cdot \\frac{1}{15} = \\frac{1}{10}$. "
        "$m = 3$: $\\frac{1}{10} \\cdot \\frac{6}{21} + \\frac{6}{10} \\cdot \\frac{3}{21} + \\frac{3}{10} \\cdot \\frac{1}{21} = \\frac{9}{70}$. "
        "각 $\\frac{1}{3}$을 곱해 $\\frac{9/70}{3/50 + 1/10 + 9/70} = \\frac{45}{101}$.",
    ),
    _short(
        "HPS-03",
        "확률과 통계",
        "좌표평면의 원점에 점 P가 있다. 한 개의 동전을 한 번 던져 앞면이 나오면 점 P를 $x$축의 양의 방향으로 $1$만큼, "
        "뒷면이 나오면 점 P를 $y$축의 양의 방향으로 $1$만큼 이동시키는 시행을 한다. 이 시행을 $8$번 반복할 때, "
        "매번 시행한 후의 점 P의 좌표 $(x, y)$가 모두 $|x - y| \\le 2$를 만족시킬 확률을 $p$라 하자. $256p$의 값을 구하시오.",
        4,
        "108",
        _hps_03,
        "$d = x - y$는 $\\pm 1$씩 움직이고 $|d| \\le 2$를 유지해야 한다. 짝수 번째마다 $d \\in \\{-2, 0, 2\\}$: "
        "$d = 0$에서 두 번 뒤 $0$으로 2가지, $\\pm 2$로 각 1가지; $d = \\pm 2$에서 $0$으로 1가지, $\\pm 2$ 유지 1가지. "
        "상태 $(N_0, N_2)$ (두 번마다): $(1, 0) \\to (2, 2) \\to (6, 6) \\to (18, 18) \\to (54, 54)$. 합 108.",
    ),
    _short(
        "HPS-04",
        "확률과 통계",
        "$7$개의 문자 A, A, B, B, C, C, D를 모두 일렬로 나열할 때, 같은 문자끼리는 서로 이웃하지 않고 문자 D는 양 끝에 오지 않도록 "
        "나열하는 경우의 수를 구하시오.",
        4,
        "186",
        _hps_04,
        "같은 문자가 이웃하지 않는 배열 수(포함배제): $630 - 3 \\cdot 180 + 3 \\cdot 60 - 24 = 246$. "
        "D가 맨 앞인 경우: 나머지 AABBCC가 이웃하지 않는 배열 $90 - 3 \\cdot 30 + 3 \\cdot 12 - 6 = 30$, 맨 뒤도 30. $246 - 60 = 186$.",
    ),
    # ------------------------------------------------------------------ 미적분
    _short(
        "HCA-01",
        "미적분",
        "함수 $f(x) = \\lim_{n \\to \\infty} \\frac{x^{2n+1} - 1}{x^{2n} + 1}$과 최고차항의 계수가 $1$인 삼차함수 $g(x)$에 대하여 "
        "함수 $f(x)g(x)$가 실수 전체의 집합에서 미분가능할 때, $g(3)$의 값을 구하시오.",
        4,
        "16",
        _hca_01,
        "$|x| < 1$이면 $f = -1$, $|x| > 1$이면 $f = x$, $f(1) = 0$, $f(-1) = -1$ ($x = -1$에서는 연속). "
        "$x = 1$: 연속에서 $g(1) = 0$, 미분계수 $-g'(1) = g(1) + g'(1)$에서 $g'(1) = 0$. "
        "$x = -1$: 좌미분 $g(-1) - g'(-1)$ = 우미분 $-g'(-1)$에서 $g(-1) = 0$. $g = (x - 1)^2(x + 1)$, $g(3) = 16$.",
    ),
    _mc(
        "HCA-02",
        "미적분",
        "$x > 0$에서 정의된 함수 $g(x) = \\int_{0}^{x} e^{-t}\\sin t\\,dt$가 극대가 되는 $x$의 값을 작은 것부터 차례로 "
        "$\\alpha_1, \\alpha_2, \\alpha_3, \\cdots$, 극소가 되는 $x$의 값을 작은 것부터 차례로 $\\beta_1, \\beta_2, \\beta_3, \\cdots$이라 할 때, "
        "$\\sum_{n=1}^{\\infty}\\{g(\\alpha_n) - g(\\beta_n)\\}$의 값은?",
        4,
        (
            "\\frac{1}{2(e^{\\pi} + 1)}",
            "\\frac{1}{2(e^{\\pi} - 1)}",
            "\\frac{1}{e^{\\pi} - 1}",
            "\\frac{e^{\\pi}}{2(e^{\\pi} - 1)}",
            "\\frac{e^{\\pi}}{e^{\\pi} - 1}",
        ),
        "1/(2*(exp(pi) - 1))",
        _hca_02,
        "$g'(x) = e^{-x}\\sin x$이므로 $\\alpha_n = (2n - 1)\\pi$, $\\beta_n = 2n\\pi$. 부분적분 두 번으로 "
        "$g(x) = \\frac{1}{2} - \\frac{e^{-x}(\\sin x + \\cos x)}{2}$, $g(\\alpha_n) - g(\\beta_n) = \\frac{e^{-(2n-1)\\pi} + e^{-2n\\pi}}{2}$. "
        "합 $\\frac{1}{2} \\cdot \\frac{e^{-\\pi}(1 + e^{-\\pi})}{1 - e^{-2\\pi}} = \\frac{1}{2(e^{\\pi} - 1)}$.",
    ),
    _short(
        "HCA-03",
        "미적분",
        "두 상수 $a$, $b$에 대하여 함수 $f(x) = x^3 + ax^2 + bx$라 할 때, 함수 $g(x) = f(\\sin x)$가 다음 조건을 만족시킨다.\n"
        "(가) 함수 $g(x)$는 $x = \\frac{\\pi}{6}$에서 극값을 갖는다.\n"
        "(나) 열린구간 $(0, 2\\pi)$에서 함수 $g(x)$가 극값을 갖는 서로 다른 $x$의 개수는 $5$이다.\n"
        "열린구간 $(0, 2\\pi)$에서 함수 $g(x)$의 모든 극댓값의 합을 $M$, 모든 극솟값의 합을 $m$이라 할 때, $16(M - m)$의 값을 구하시오.",
        4,
        "34",
        _hca_03,
        "$g'(x) = \\cos x \\cdot f'(\\sin x)$. (가)에서 $f'(\\frac{1}{2}) = 0$, $f'(s) = 3(s - \\frac{1}{2})(s - r)$. "
        "$x = \\frac{\\pi}{2}, \\frac{3\\pi}{2}$는 항상 극값, $\\sin x = \\frac{1}{2}$의 두 점은 $r \\ne \\frac{1}{2}$일 때 극값, $\\sin x = r$은 "
        "$|r| < 1$, $r \\ne 0$이면 두 점, $r = 0$이면 $x = \\pi$ 한 점. 개수 5는 $r = 0$뿐: $f = x^3 - \\frac{3}{4}x^2$. "
        "극대 $g(\\frac{\\pi}{2}) = \\frac{1}{4}$, $g(\\pi) = 0$; 극소 $g(\\frac{\\pi}{6}) = g(\\frac{5\\pi}{6}) = -\\frac{1}{16}$, $g(\\frac{3\\pi}{2}) = -\\frac{7}{4}$. "
        "$M - m = \\frac{1}{4} + \\frac{15}{8} = \\frac{17}{8}$, 답 34.",
    ),
    _mc(
        "HCA-04",
        "미적분",
        "함수 $f(x) = xe^{x}$ $(x \\ge 0)$의 역함수를 $g(x)$라 할 때, $\\int_{e}^{2e^{2}} \\frac{g(x)}{x}\\,dx$의 값은?",
        4,
        ("\\frac{3}{2}", "\\frac{7}{4}", "2", "\\frac{9}{4}", "\\frac{5}{2}"),
        "Rational(5, 2)",
        _hca_04,
        "$x = f(u) = ue^u$로 치환하면 $g(x) = u$, $dx = (1 + u)e^u\\,du$, 구간은 $u = 1$에서 $2$. "
        "$\\int_1^2 \\frac{u}{ue^u}(1 + u)e^u\\,du = \\int_1^2 (1 + u)\\,du = \\frac{5}{2}$.",
    ),
    _mc(
        "HCA-05",
        "미적분",
        "좌표평면에서 원 $x^2 + y^2 = 1$ 위의 점 $P(\\cos\\theta, \\sin\\theta)$ $\\left(0 < \\theta < \\frac{\\pi}{2}\\right)$에서의 접선이 "
        "$x$축과 만나는 점을 $Q$, 점 $P$에서 $x$축에 내린 수선의 발을 $H$라 하자. 점 $A(1, 0)$에 대하여 선분 $AQ$, 선분 $QP$와 호 $AP$로 "
        "둘러싸인 부분의 넓이를 $S(\\theta)$, 삼각형 $PHQ$에 내접하는 원의 반지름의 길이를 $r(\\theta)$라 할 때, "
        "$\\lim_{\\theta \\to 0+} \\frac{S(\\theta)}{\\theta \\times r(\\theta)}$의 값은?",
        4,
        ("\\frac{1}{12}", "\\frac{1}{6}", "\\frac{1}{4}", "\\frac{1}{3}", "\\frac{1}{2}"),
        "Rational(1, 3)",
        _hca_05,
        "$Q = (\\sec\\theta, 0)$. $S = \\frac{1}{2}\\tan\\theta - \\frac{\\theta}{2} \\approx \\frac{\\theta^3}{6}$. 직각삼각형 $PHQ$: "
        "$PH = \\sin\\theta$, $HQ = \\frac{\\sin^2\\theta}{\\cos\\theta}$, $PQ = \\tan\\theta$, "
        "$r = \\frac{PH + HQ - PQ}{2} = \\frac{\\sin\\theta(\\sin\\theta + \\cos\\theta - 1)}{2\\cos\\theta} \\approx \\frac{\\theta^2}{2}$. 극한 $\\frac{1/6}{1/2} = \\frac{1}{3}$.",
    ),
    # ------------------------------------------------------------------ 기하
    _short(
        "HGE-01",
        "기하",
        "두 초점이 $F(c, 0)$, $F'(-c, 0)$ $(c > 0)$인 쌍곡선 $\\frac{x^2}{a^2} - \\frac{y^2}{b^2} = 1$ 위의 제$1$사분면에 있는 점 $P$가 "
        "다음 조건을 만족시킨다.\n"
        "(가) 삼각형 $PF'F$에 내접하는 원의 중심의 좌표는 $(2, 1)$이다.\n"
        "(나) 직선 $PF'$의 기울기는 $\\frac{5}{12}$이다.\n"
        "삼각형 $PF'F$의 넓이를 $S$라 할 때, $4S$의 값을 구하시오. (단, $a$, $b$는 양수이다.)",
        4,
        "30",
        _hge_01,
        "내접원이 $F'F$에 접하는 점 $T$에서 $F'T - FT = PF' - PF = 2a$이므로 $T = (a, 0)$: $a = 2$, 반지름 1. "
        "직선 $5x - 12y + 5c = 0$이 원에 접하므로 $|5c - 2| = 13$, $c = 3$, $b^2 = 5$. $F$에서 그은 다른 접선은 $x = 3$이므로 "
        "$P = \\left(3, \\frac{5}{2}\\right)$. $S = \\frac{1}{2} \\cdot 6 \\cdot \\frac{5}{2} = \\frac{15}{2}$, $4S = 30$.",
    ),
    _mc(
        "HGE-02",
        "기하",
        "좌표평면에서 원 $x^2 + y^2 = 4$ 위의 점 중 $y$좌표가 $0$ 이상인 점 $P$와 원 $(x - 6)^2 + y^2 = 1$ 위의 점 $Q$에 대하여 "
        "$\\overrightarrow{OX} = \\overrightarrow{OP} + \\overrightarrow{OQ}$를 만족시키는 점 $X$ 전체의 집합이 나타내는 도형의 넓이는? "
        "(단, $O$는 원점이다.)",
        4,
        ("4\\pi", "5\\pi", "6\\pi", "8\\pi", "9\\pi"),
        "5*pi",
        _hge_02,
        "$P$를 고정하면 $X$는 중심 $(6, 0) + \\overrightarrow{OP}$, 반지름 1인 원(곡선) 위. 중심은 $(6, 0)$을 중심으로 하는 반지름 2인 위쪽 반원을 움직이므로 "
        "$X$의 영역은 그 반원과의 거리가 1 이하인 점들. 위쪽은 반지름 1과 3 사이의 반원환 $\\frac{\\pi(9 - 1)}{2} = 4\\pi$, "
        "아래쪽은 양 끝점 $(4, 0)$, $(8, 0)$ 중심의 반원 두 개 $\\pi$. 합 $5\\pi$ (원판 $9\\pi$나 원환 $8\\pi$가 아님).",
    ),
    _short(
        "HGE-03",
        "기하",
        "좌표공간에 구 $S: (x + 1)^2 + (y + 1)^2 + (z - 2)^2 = 9$와 두 점 $A(6, 0, 0)$, $B(0, 6, 0)$이 있다. "
        "구 $S$ 위의 점 $P$에 대하여 삼각형 $PAB$의 넓이가 최대가 되도록 하는 점 $P$를 $P_0$이라 할 때, "
        "삼각형 $P_0AB$의 $xy$평면 위로의 정사영의 넓이를 구하시오.",
        4,
        "36",
        _hge_03,
        "넓이 $= \\frac{1}{2}\\overline{AB} \\times$ (직선 $AB$까지의 거리). 중심 $C(-1, -1, 2)$에서 직선 $AB$에 내린 수선의 발 $M(3, 3, 0)$, "
        "$\\overline{CM} = 6$. 최대일 때 $P_0 = C + 3 \\cdot \\frac{\\overrightarrow{MC}}{6} = (-3, -3, 3)$. 정사영 $(-3, -3, 0)$에서 "
        "직선 $x + y = 6$까지 거리 $6\\sqrt{2}$, $\\overline{AB} = 6\\sqrt{2}$이므로 넓이 36.",
    ),
]


def validate_problems(problems: Iterable[CsatMathProblem] = PROBLEMS) -> None:
    """Independent recomputation equals the stored answer; the answer is exactly one of five
    options (5지선다) or an integer 1~999 (단답형); ids unique; all 4점; subject mix of the set."""
    problems = list(problems)
    dup = [i for i, c in Counter(p.id for p in problems).items() if c > 1]
    if dup:
        raise AssertionError(f"duplicate ids {dup}")
    for p in problems:
        if p.subject not in SUBJECTS:
            raise AssertionError(f"{p.id}: unknown subject {p.subject}")
        if "[4점]" not in p.text:
            raise AssertionError(f"{p.id}: every hard problem is a 4점 item")
        got = sympy.sympify(p.truth())
        if sympy.simplify(got - p.answer) != 0:
            raise AssertionError(f"{p.id}: stored answer {p.answer} but recomputed {got}")
        if p.choices:
            if len(p.choices) != 5 or correct_choice(p) is None:
                raise AssertionError(f"{p.id}: the answer must be exactly one of five options")
        elif not (p.answer.is_Integer and 1 <= int(p.answer) <= 999):
            raise AssertionError(f"{p.id}: 단답형 answers are integers from 1 to 999")
    if len(problems) == len(PROBLEMS) and Counter(p.subject for p in problems) != Counter(SUBJECT_COUNTS):
        raise AssertionError(f"subject mix {Counter(p.subject for p in problems)} != {SUBJECT_COUNTS}")
