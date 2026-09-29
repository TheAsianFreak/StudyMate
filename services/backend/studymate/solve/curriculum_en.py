"""English curriculum text (US Common Core: grades 7-8, Algebra 1, Geometry, Algebra 2) for
the shared unit ids.

US classes teach equations as "do the same thing to both sides" (inverse operations)
rather than transposition, and usually show the operation beside each step.
"""

from __future__ import annotations

from studymate.solve.curriculum_types import UnitText

CHECK = "Substitute the answer back into the original problem and see that it holds."
# Answer conventions for choice problems (Korean CSAT-style ① ~ ⑤).
CHOICE = "With answer choices (① to ⑤), answer with the option number; Korean CSAT short answers are integers from 0 to 999."

# Korean CSAT (수능) math units, placed in the US course where each topic is taught
# (Algebra 2, Precalculus, AP Calculus AB/BC, AP Statistics).
CSAT_TEXT: dict[str, UnitText] = {
    "s1_exp_log": UnitText(
        grade="Algebra 2",
        name="Exponents, radicals and logarithms",
        examples="\\sqrt[3]{8} \\times 4^{\\frac{1}{2}}, \\log_2 12 - \\log_2 3, a^{\\frac{2}{3}} \\times a^{\\frac{1}{3}}, \\log 2 \\approx 0.3010",
        concept="Rational exponents (a>0): a^m a^n = a^{m+n}, (a^m)^n = a^{mn}, a^{\\frac{m}{n}} = \\sqrt[n]{a^m}. "
        "Definition: a^x = N ⇔ x = \\log_a N (a>0, a≠1, N>0). Properties: \\log_a MN = \\log_a M + \\log_a N, "
        "\\log_a \\frac{M}{N} = \\log_a M - \\log_a N, \\log_a M^k = k\\log_a M, change of base \\log_a b = \\frac{\\log_c b}{\\log_c a}.",
        method=(
            "Rewrite radicals as rational exponents (\\sqrt[3]{8} = 8^{\\frac{1}{3}})",
            "Factor the bases into primes so they match",
            "Combine logs with the properties or switch to one base with the change-of-base formula",
            "Evaluate with the exponent and log rules",
        ),
        notation="In \\log_a b, a is the base and b the argument; \\log x means base 10 and \\ln x base e. "
        + CHOICE,
        pitfalls="Writing \\log_a(M+N) = \\log_a M + \\log_a N, forgetting the base/argument conditions, using rational exponents on a negative base.",
        check="Turn the log back into an exponent (a^{answer} = N), or raise a root back to its power.",
    ),
    "s1_exp_log_function": UnitText(
        grade="Algebra 2",
        name="Exponential and logarithmic functions and equations",
        examples="2^{x+1} = 8, 4^x - 3 \\cdot 2^x - 4 = 0, \\log_2(x-1) < 3, shifting y = 2^x, the maximum of y = \\log_3 x on an interval",
        concept="y = a^x and y = \\log_a x are inverse functions, symmetric about y = x; increasing if a>1, decreasing if 0<a<1. "
        "Solve equations by matching bases and comparing exponents (arguments); for inequalities with a base below 1 the sign flips.",
        method=(
            "With logs, find the domain first (argument > 0)",
            "Match the bases or substitute t = a^x (t > 0)",
            "Compare exponents (arguments) and solve, flipping the inequality when 0 < base < 1",
            "Keep only solutions inside the domain and the substitution's range",
        ),
        notation='After substituting, write the range too: "t = a^x (t > 0)". ' + CHOICE,
        pitfalls="Keeping an extraneous solution outside the domain, not flipping the inequality for a base below 1, dropping t > 0.",
        check="Substitute each solution into the original equation and check the domain.",
    ),
    "s1_trig_function": UnitText(
        grade="Precalculus",
        name="Trigonometric functions (unit circle, graphs, equations)",
        examples="\\sin\\frac{7}{6}\\pi, \\cos\\theta when \\sin\\theta = \\frac{3}{5} and \\frac{\\pi}{2} < \\theta < \\pi, the period of y = 2\\sin 3x, "
        "2\\cos x - 1 = 0 on 0 \\le x < 2\\pi",
        concept="Radian measure: 180° = π. For a point (x, y) on the terminal side, r = \\sqrt{x^2+y^2}: \\sin\\theta = \\frac{y}{r}, "
        "\\cos\\theta = \\frac{x}{r}, \\tan\\theta = \\frac{y}{x}. Pythagorean identity \\sin^2\\theta + \\cos^2\\theta = 1. "
        "y = a\\sin(bx + c) + d has period \\frac{2\\pi}{|b|} and amplitude |a|.",
        method=(
            "Use the reference angle (angles of the form \\pi \\pm \\theta, 2\\pi - \\theta, \\frac{\\pi}{2} \\pm \\theta)",
            "Choose the sign from the quadrant (ASTC)",
            "Use the identities to find the remaining values",
            "For equations, find every solution in the given interval on the unit circle or graph",
        ),
        notation="Angles in radians, e.g. \\frac{\\pi}{6}. " + CHOICE,
        pitfalls="The wrong sign for the quadrant, computing the period as 2\\pi b, missing solutions or including ones outside the interval.",
        check="Substitute back or re-check the sign and size on the unit circle.",
    ),
    "s1_triangle_law": UnitText(
        grade="Precalculus",
        name="Law of sines and law of cosines",
        examples="c when a = 3, b = 5, C = 60°, the circumradius R, \\frac{a}{\\sin A} = 2R, area \\frac{1}{2}ab\\sin C",
        concept="Law of sines \\frac{a}{\\sin A} = \\frac{b}{\\sin B} = \\frac{c}{\\sin C} = 2R. Law of cosines a^2 = b^2 + c^2 - 2bc\\cos A. "
        "Area S = \\frac{1}{2}ab\\sin C.",
        method=(
            "List what is given (SAS, SSS, AAS/ASA, circumcircle)",
            "SAS or SSS: law of cosines; an angle with its opposite side: law of sines",
            "Use the area formula if the area is asked",
        ),
        notation="Side a is opposite angle A, and so on. " + CHOICE,
        pitfalls="Forgetting 2R in the law of sines, using an angle that is not the included angle, the sign of -2bc\\cos A.",
        check="The largest side must face the largest angle; recompute with the other law.",
    ),
    "s1_sequence": UnitText(
        grade="Algebra 2",
        name="Arithmetic and geometric sequences and series",
        examples="a_{10} of an arithmetic sequence with a_3 = 8, a_6 = 17, a geometric sequence with a_2 = 6, a_5 = 48, the sum S_n",
        concept="Arithmetic: a_n = a_1 + (n-1)d, S_n = \\frac{n(a_1 + a_n)}{2}. Geometric: a_n = a_1r^{n-1}, S_n = \\frac{a_1(r^n - 1)}{r - 1} (r ≠ 1). "
        "a_1 = S_1 and a_n = S_n - S_{n-1} for n ≥ 2.",
        method=(
            "Let the first term and the common difference (ratio) be a_1, d (a_1, r)",
            "Write each condition as an equation in them",
            "Solve the system (use the problem's conditions to pick the sign of r)",
            "Substitute into the formula for the term or the sum",
        ),
        notation="Write the sequence as \\{a_n\\}, the nth term a_n and the partial sum S_n. " + CHOICE,
        pitfalls="Writing the nth term as a_1 + nd, ignoring a condition on r, forgetting to check n = 1 when a_n comes from S_n.",
        check="Recompute the given terms with the values you found.",
    ),
    "s1_sigma": UnitText(
        grade="Precalculus",
        name="Sigma notation and sums",
        examples="\\sum_{k=1}^{10}(2k+1), \\sum_{k=1}^{n} k^2, \\sum_{k=1}^{n}\\frac{1}{k(k+1)}",
        concept="Sums split over + and - and constant factors come out; \\sum_{k=1}^{n} c = cn. \\sum k = \\frac{n(n+1)}{2}, "
        "\\sum k^2 = \\frac{n(n+1)(2n+1)}{6}, \\sum k^3 = \\left(\\frac{n(n+1)}{2}\\right)^2. Telescope fractions with partial fractions.",
        method=(
            "Split the sum term by term",
            "Apply the power-sum formulas",
            "For fractions, write \\frac{1}{k(k+1)} = \\frac{1}{k} - \\frac{1}{k+1} so the terms cancel (telescoping)",
        ),
        notation="Show the index range, as in \\sum_{k=1}^{n} a_k. " + CHOICE,
        pitfalls="Writing \\sum a_kb_k = \\sum a_k \\cdot \\sum b_k, taking \\sum c as c, miscounting terms when the index doesn't start at 1.",
        check="Add the first few terms by hand for a small n and compare.",
    ),
    "s1_recursion_induction": UnitText(
        grade="Precalculus",
        name="Recursive sequences and mathematical induction",
        examples="a_{10} when a_1 = 2, a_{n+1} = a_n + 3, a_{n+1} = 2a_n - 1, filling in an induction proof",
        concept="A recursive formula gives the first term and how each term follows from the previous one; a_{n+1} - a_n = d is arithmetic, "
        "a_{n+1} = ra_n geometric. Induction: (1) base case n = 1, (2) if true for n = k, then true for n = k+1.",
        method=(
            "Check whether the recursion is arithmetic or geometric",
            "Otherwise compute n = 1, 2, 3, … up to the term you need, or find the pattern",
            "Write the proof as a base case and an inductive step",
        ),
        notation='"Base case: n = 1 ...", "Inductive step: assume it holds for n = k ...". ' + CHOICE,
        pitfalls="Shifting the index by one, not using the inductive hypothesis in the inductive step.",
        check="Plug the terms you found back into the recursion.",
    ),
    "s2_limit_continuity": UnitText(
        grade="Calculus AB",
        name="Limits and continuity",
        examples="\\lim_{x\\to 2}\\frac{x^2-4}{x-2}, \\lim_{x\\to\\infty}\\frac{3x^2+1}{x^2-2x}, one-sided limits \\lim_{x\\to 1^+}f(x), "
        "\\lim_{x\\to 1}\\frac{x^2+ax+b}{x-1} = 3, continuity at x = a",
        concept="For 0/0, factor or rationalize and cancel; for ∞/∞, divide by the highest power in the denominator. "
        "A limit exists only if the left- and right-hand limits agree. If the denominator → 0 and the limit exists, the numerator → 0. "
        "f is continuous at a ⇔ \\lim_{x\\to a} f(x) = f(a).",
        method=(
            "Substitute to identify the form (0/0, ∞/∞, ∞ - ∞)",
            "Factor, rationalize, or divide by the highest power",
            "Simplify and substitute to get the limit",
            "For unknown constants, use 'denominator → 0 forces numerator → 0'",
        ),
        notation="Right- and left-hand limits: \\lim_{x\\to a^+} and \\lim_{x\\to a^-}. " + CHOICE,
        pitfalls="Substituting before canceling, not checking both one-sided limits, forgetting f(a) in the continuity condition.",
        check="Evaluate the function at values very close to a and see that it approaches your limit.",
    ),
    "s2_derivative": UnitText(
        grade="Calculus AB",
        name="The derivative (definition and rules)",
        examples="f'(2) for f(x) = x^3 - 2x^2 + 3x, \\lim_{h\\to 0}\\frac{f(1+2h) - f(1)}{h}, the derivative of (x^2+1)(x-3), average rate of change",
        concept="f'(a) = \\lim_{h\\to 0}\\frac{f(a+h) - f(a)}{h} is the slope of the tangent line. Power rule (x^n)' = nx^{n-1}, "
        "constant multiple, sum and difference rules, product rule (fg)' = f'g + fg'. Differentiable implies continuous.",
        method=(
            "Rewrite a limit to match the definition (\\frac{f(a+2h) - f(a)}{h} = 2 \\cdot \\frac{f(a+2h) - f(a)}{2h})",
            "Find f'(x) with the rules",
            "Substitute x = a",
        ),
        notation="Write the derivative as f'(x), y' or \\frac{dy}{dx}. " + CHOICE,
        pitfalls="Not matching the increment in the numerator and denominator, using f'g' for the product rule.",
        check="Expand and differentiate again, or compare with a nearby average rate of change.",
    ),
    "s2_derivative_use": UnitText(
        grade="Calculus AB",
        name="Applications of derivatives (tangent lines, extrema, optimization)",
        examples="the tangent line to y = x^3 - x at (1, 0), the local maximum of the cubic f(x) = x^3 - 3x + 2, "
        "constants a, b when f(x) = x^3 + ax^2 + bx has a local max at x = -1 and a local min at x = 3, the maximum on [0, 3], "
        "the number of real roots of f(x) = k, velocity and acceleration",
        concept="Tangent line at (a, f(a)): y - f(a) = f'(a)(x - a). f' > 0 increasing, f' < 0 decreasing; f' changing from + to - is a local max, "
        "from - to + a local min; a differentiable f with an extremum at α has f'(α) = 0. On a closed interval compare critical values "
        "with the endpoints (Extreme Value Theorem). The number of solutions of f(x) = k is the number of intersections of y = f(x) and y = k.",
        method=(
            "Find f'(x) and the critical numbers where f'(x) = 0",
            "If the extrema are at given x = α, β, solve f'(α) = f'(β) = 0 for the constants "
            "(for a cubic x^3 + ax^2 + bx + c, match f'(x) = 3(x - α)(x - β))",
            "Make a sign chart for f'",
            "Write the tangent line, or compare critical values and endpoints",
            "Sketch the graph to count intersections or check an inequality",
        ),
        notation="Use a sign chart for f'(x) with arrows for increasing/decreasing. " + CHOICE,
        pitfalls="Assuming f'(a) = 0 always gives an extremum (check the sign change), skipping the endpoints, confusing the point of tangency with a point the line passes through, "
        "sign errors in (-1)^3 and (-1)^2 when substituting after finding the constants.",
        check="Recheck the sign of f' on each side of the critical numbers and compare with the graph.",
    ),
    "s2_integral": UnitText(
        grade="Calculus AB",
        name="Antiderivatives and definite integrals",
        examples="\\int (3x^2 - 2x + 1)dx, \\int_0^2 (3x^2 - 2x + 1)dx, \\int_{-1}^{1}(x^3 + 3x^2)dx, \\frac{d}{dx}\\int_1^x (t^2 - 1)dt",
        concept="If F' = f then \\int f(x)dx = F(x) + C; \\int x^n dx = \\frac{x^{n+1}}{n+1} + C. Fundamental Theorem of Calculus: "
        "\\int_a^b f(x)dx = F(b) - F(a) and \\frac{d}{dx}\\int_a^x f(t)dt = f(x). On [-a, a], odd functions integrate to 0.",
        method=(
            "Find an antiderivative term by term",
            "Evaluate F(b) - F(a)",
            "On a symmetric interval, use even/odd symmetry",
        ),
        notation="Write the evaluation as \\left[F(x)\\right]_a^b = F(b) - F(a) and add + C to indefinite integrals. "
        + CHOICE,
        pitfalls="Dropping + C, subtracting in the wrong order, mixing up the variables when differentiating \\int_a^x f(t)dt.",
        check="Differentiate your antiderivative and compare with the integrand.",
    ),
    "s2_integral_use": UnitText(
        grade="Calculus AB",
        name="Area between curves and motion (distance traveled)",
        examples="the area enclosed by y = x^2 - 4x + 3 and the x-axis, the area between y = x^2 and y = 2x, "
        "the distance traveled from t = 0 to t = 4 with v(t) = t^2 - 4t + 3",
        concept="Area between curves S = \\int_a^b |f(x) - g(x)|dx. Motion on a line: displacement \\int_a^b v(t)dt, "
        "total distance traveled \\int_a^b |v(t)|dt.",
        method=(
            "Find the intersection points to get the limits of integration",
            "Decide which curve is on top on each interval (or where v changes sign)",
            "Integrate (top - bottom) or |v(t)|, splitting at sign changes",
        ),
        notation="Split the integral where the sign changes. " + CHOICE,
        pitfalls="Integrating across a sign change without splitting, confusing displacement with distance traveled.",
        check="Sketch the region: the area must be positive and about the right size.",
    ),
    "ps_counting": UnitText(
        grade="Algebra 2",
        name="Counting (permutations, combinations, the binomial theorem)",
        examples="_5P_2, permutations with repetition 3^4, arrangements of letters with repeats \\frac{6!}{2!3!}, circular arrangements, "
        "combinations with repetition, the coefficient of x^3 in (x+2)^5",
        concept="Permutations _nP_r = \\frac{n!}{(n-r)!}, circular (n-1)!, with repetition n^r, with identical items \\frac{n!}{p!q!r!}, "
        "combinations \\binom{n}{r} = \\frac{n!}{r!(n-r)!}, combinations with repetition (stars and bars) \\binom{n+r-1}{r}. "
        "Binomial theorem: the general term \\binom{n}{r}a^{n-r}b^r.",
        method=(
            "Decide whether order matters, repetition is allowed, or items are identical",
            "Handle restrictions first (fix or group items); count 'at least' with the complement",
            "Calculate with the formula",
            "For the binomial theorem, find r from the exponent condition in the general term",
        ),
        notation="Write _nP_r, \\binom{n}{r} (also _nC_r); Korean _nH_r means \\binom{n+r-1}{r}. " + CHOICE,
        pitfalls="Mixing up permutations and combinations, swapping n and r in stars and bars, forgetting the power of the constant in a binomial term.",
        check="List a small case by hand and compare with the formula.",
    ),
    "ps_probability": UnitText(
        grade="Statistics",
        name="Probability (addition rule, conditional probability, independence)",
        examples="P(A \\cap B) when P(A) = \\frac{1}{3}, P(A \\cup B) = \\frac{1}{2}, conditional probability P(B|A), independent events, "
        "the probability of exactly 2 multiples of 3 in 4 dice rolls",
        concept="Addition rule P(A \\cup B) = P(A) + P(B) - P(A \\cap B), complement P(A^c) = 1 - P(A), conditional P(B|A) = \\frac{P(A \\cap B)}{P(A)}, "
        "multiplication rule P(A \\cap B) = P(A)P(B|A), independent ⇔ P(A \\cap B) = P(A)P(B), binomial probability \\binom{n}{r}p^r(1-p)^{n-r}.",
        method=(
            "Name the events (A, B)",
            "Decide whether to count outcomes or use the probability rules",
            "Use the complement for 'at least', conditional probability for 'given that', the binomial formula for repeated trials",
            "Compute and simplify the fraction",
        ),
        notation="Complement A^c (or A'), conditional probability P(B|A). " + CHOICE,
        pitfalls="Confusing mutually exclusive with independent, swapping P(B|A) and P(A|B), forgetting \\binom{n}{r} for repeated trials.",
        check="Probabilities of all outcomes must add to 1; check with a table or a Venn diagram.",
    ),
    "ps_distribution": UnitText(
        grade="Statistics",
        name="Random variables (binomial and normal distributions)",
        examples="V(4X+1) for X \\sim B(20, \\frac{1}{4}), E(X^2) when E(X) = 4, V(X) = 2, P(X \\ge 54) for X \\sim N(50, 4^2), the z-table",
        concept="E(X) = \\sum x_ip_i, Var(X) = E(X^2) - (E(X))^2, \\sigma = \\sqrt{Var(X)}; E(aX+b) = aE(X)+b, Var(aX+b) = a^2Var(X). "
        "Binomial B(n, p): mean np, variance np(1-p). Normal N(\\mu, \\sigma^2): standardize with z = \\frac{x - \\mu}{\\sigma}.",
        method=(
            "Identify the distribution (table, binomial, normal)",
            "Apply the mean/variance/standard deviation formulas",
            "For normal probabilities, standardize and use the z-table",
        ),
        notation="In N(\\mu, \\sigma^2) the second parameter is the variance (Korean notation writes E(X), V(X)). "
        + CHOICE,
        pitfalls="Computing Var(aX+b) as aVar(X)+b, reading \\sigma^2 as the standard deviation, dividing by the variance when standardizing.",
        check="The probabilities add to 1 and the mean sits at the center of the distribution.",
    ),
    "ps_estimation": UnitText(
        grade="Statistics",
        name="Sampling distributions and confidence intervals for a mean",
        examples="the mean and variance of the sample mean \\bar{X} for samples of size n, a 95% confidence interval for \\mu",
        concept="E(\\bar{X}) = \\mu, Var(\\bar{X}) = \\frac{\\sigma^2}{n}, SD(\\bar{X}) = \\frac{\\sigma}{\\sqrt{n}}; for a normal population "
        "\\bar{X} \\sim N(\\mu, \\frac{\\sigma^2}{n}). 95% confidence interval: \\bar{x} \\pm 1.96\\frac{\\sigma}{\\sqrt{n}} (99%: 2.58).",
        method=(
            "List the population mean, the population standard deviation and the sample size",
            "Find the distribution of \\bar{X}",
            "Standardize, or substitute into the confidence interval",
        ),
        notation="Distinguish the random variable \\bar{X} from its observed value \\bar{x}. " + CHOICE,
        pitfalls="Using \\frac{\\sigma}{n} instead of \\frac{\\sigma}{\\sqrt{n}}, forgetting the factor 2 in the interval's width.",
        check="A larger sample must give a narrower interval.",
    ),
    "calc_sequence_limit": UnitText(
        grade="Calculus BC",
        name="Limits of sequences and infinite series",
        examples="\\lim_{n\\to\\infty}\\frac{3n+1}{n}, \\lim_{n\\to\\infty}(\\sqrt{n^2+4n} - n), \\lim_{n\\to\\infty}\\frac{2^{n+1}+3^n}{3^{n+1}-2^n}, "
        "\\sum_{n=1}^{\\infty}\\left(\\frac{1}{3}\\right)^n, telescoping series",
        concept="For ∞/∞ divide by the dominant term; for ∞ - ∞ rationalize. r^n converges for -1 < r \\le 1. A series is the limit of its "
        "partial sums; a geometric series \\sum_{n=1}^{\\infty}ar^{n-1} = \\frac{a}{1-r} when |r| < 1. If \\sum a_n converges then a_n → 0 (not conversely).",
        method=(
            "Identify the form (∞/∞, ∞ - ∞, geometric)",
            "Divide by the dominant term or rationalize",
            "For series, find the partial sum (telescoping) or use the geometric series formula",
        ),
        notation='Give the limit, or say "diverges". ' + CHOICE,
        pitfalls="Using the geometric series formula without |r| < 1, the wrong first term, thinking a_n → 0 makes a series converge.",
        check="Plug in a large n and see that the value approaches your limit.",
    ),
    "calc_transcendental": UnitText(
        grade="Calculus AB",
        name="Limits and derivatives of exponential, logarithmic and trig functions",
        examples="\\lim_{x\\to 0}\\frac{e^{2x}-1}{x}, \\lim_{x\\to 0}\\frac{\\ln(1+3x)}{x}, \\lim_{x\\to 0}\\frac{\\sin 3x}{x}, (e^x\\sin x)', (\\ln x)'",
        concept="\\lim_{x\\to 0}(1+x)^{1/x} = e, \\lim_{x\\to 0}\\frac{e^x - 1}{x} = 1, \\lim_{x\\to 0}\\frac{\\ln(1+x)}{x} = 1, \\lim_{x\\to 0}\\frac{\\sin x}{x} = 1. "
        "(e^x)' = e^x, (a^x)' = a^x\\ln a, (\\ln x)' = \\frac{1}{x}, (\\sin x)' = \\cos x, (\\cos x)' = -\\sin x; angle addition formulas.",
        method=(
            "Rewrite into a standard limit (\\frac{\\sin 3x}{x} = 3 \\cdot \\frac{\\sin 3x}{3x})",
            "Apply the derivative rules and the product rule",
            "Substitute the value",
        ),
        notation="Natural log is \\ln x; angles are in radians. " + CHOICE,
        pitfalls="Taking \\lim\\frac{\\sin 3x}{x} as 1, forgetting \\ln a in (a^x)', working in degrees.",
        check="Estimate the limit with a small x, or integrate the derivative back.",
    ),
    "calc_diff_methods": UnitText(
        grade="Calculus BC",
        name="Differentiation techniques (quotient, chain, implicit, parametric, inverse)",
        examples="\\left(\\frac{x}{x^2+1}\\right)', (\\sin 2x)', \\frac{dy}{dx} for x = t^2, y = t^3, \\frac{dy}{dx} for x^2 + y^2 = 4, "
        "the derivative of an inverse function, second derivatives",
        concept="Quotient rule \\left(\\frac{f}{g}\\right)' = \\frac{f'g - fg'}{g^2}, chain rule (f(g(x)))' = f'(g(x))g'(x), parametric "
        "\\frac{dy}{dx} = \\frac{dy/dt}{dx/dt}, implicit differentiation (treat y as a function of x), inverse (f^{-1})'(b) = \\frac{1}{f'(a)} with b = f(a).",
        method=(
            "Identify the structure (quotient, composition, parametric, implicit, inverse)",
            "Apply the matching rule (chain rule: outside derivative × inside derivative)",
            "Substitute the point",
        ),
        notation="Write \\frac{dy}{dx}, f'(x) and f''(x). " + CHOICE,
        pitfalls="Dropping the inside derivative, mixing up a and b for the inverse, forgetting \\frac{dy}{dx} on y-terms in implicit differentiation.",
        check="If possible, rewrite explicitly and differentiate again to compare.",
    ),
    "calc_derivative_use": UnitText(
        grade="Calculus AB",
        name="Curve sketching and motion (concavity, inflection points)",
        examples="the tangent to y = xe^x, the local minimum of f(x) = x\\ln x, inflection points, concavity, velocity and acceleration of a particle in the plane",
        concept="Tangent y - f(a) = f'(a)(x - a). The sign of f' gives increase/decrease and extrema; the sign of f'' gives concavity "
        "(f'' > 0 concave up), and a sign change of f'' is an inflection point. Plane motion: velocity (x'(t), y'(t)), speed \\sqrt{x'(t)^2 + y'(t)^2}.",
        method=(
            "Check the domain and find f' and f''",
            "Make sign charts",
            "Compute the extrema, inflection points or tangent line asked for",
        ),
        notation="Use concave up / concave down (Korean texts say 아래로 볼록 / 위로 볼록). " + CHOICE,
        pitfalls="Ignoring the domain (\\ln x needs x > 0), assuming f''(a) = 0 always gives an inflection point.",
        check="The sketch must match the sign charts for f' and f''.",
    ),
    "calc_integration": UnitText(
        grade="Calculus BC",
        name="Integration techniques (u-substitution, integration by parts)",
        examples="\\int_0^1 xe^x dx (by parts), \\int_0^1 2x(x^2+1)^3 dx (u-substitution), \\int_1^e \\ln x\\,dx, \\int \\frac{f'(x)}{f(x)}dx",
        concept="u-substitution \\int f(g(x))g'(x)dx = \\int f(u)du (change the limits too). Integration by parts \\int u\\,dv = uv - \\int v\\,du. "
        "\\int e^x dx = e^x + C, \\int \\frac{1}{x}dx = \\ln|x| + C, \\int \\sin x\\,dx = -\\cos x + C, \\int \\frac{f'(x)}{f(x)}dx = \\ln|f(x)| + C.",
        method=(
            "An inside function with its derivative present: substitute; a product like polynomial × exp/trig/log: by parts",
            "For parts, choose u by LIATE (log, inverse trig, algebraic, trig, exponential)",
            "Integrate and evaluate at the limits",
        ),
        notation='Write the substitution: "u = x^2 + 1, du = 2x\\,dx". ' + CHOICE,
        pitfalls="Not changing the limits after substituting, sign errors in by parts, dropping the absolute value in \\ln|x|.",
        check="Differentiate the antiderivative and compare with the integrand.",
    ),
    "calc_integral_use": UnitText(
        grade="Calculus BC",
        name="Applications of integration (Riemann sums, area, volume, arc length)",
        examples="\\lim_{n\\to\\infty}\\sum_{k=1}^{n}\\frac{1}{n}f\\left(\\frac{k}{n}\\right), the area under y = e^x, volume by cross sections \\int_a^b A(x)dx, "
        "arc length, distance traveled in the plane",
        concept="\\lim_{n\\to\\infty}\\sum_{k=1}^{n}f\\left(a + \\frac{(b-a)k}{n}\\right)\\frac{b-a}{n} = \\int_a^b f(x)dx. Area \\int_a^b |f - g|dx, "
        "volume \\int_a^b A(x)dx, arc length \\int_a^b \\sqrt{1 + (f'(x))^2}dx, distance \\int_a^b \\sqrt{x'(t)^2 + y'(t)^2}dt.",
        method=(
            "Set up the integral for the quantity asked (area, volume, length, distance)",
            "Choose the limits (for a Riemann sum, k/n becomes x and 1/n becomes dx)",
            "Evaluate with substitution or by parts",
        ),
        notation="Rewrite a limit of a Riemann sum as a definite integral. " + CHOICE,
        pitfalls="The wrong interval when converting a Riemann sum, setting up the cross-sectional area incorrectly.",
        check="Sketch it and compare with a rough estimate.",
    ),
    "geo_conic": UnitText(
        grade="Precalculus",
        name="Conic sections (parabolas, ellipses, hyperbolas)",
        examples="the focus of y^2 = 8x, the distance between the foci of \\frac{x^2}{25} + \\frac{y^2}{9} = 1, "
        "the asymptotes of \\frac{x^2}{4} - \\frac{y^2}{5} = 1, tangent lines to conics",
        concept="Parabola y^2 = 4px: focus (p, 0), directrix x = -p; each point is equidistant from focus and directrix. "
        "Ellipse \\frac{x^2}{a^2} + \\frac{y^2}{b^2} = 1 (a > b > 0): foci (\\pm c, 0) with c^2 = a^2 - b^2, sum of distances 2a. "
        "Hyperbola \\frac{x^2}{a^2} - \\frac{y^2}{b^2} = 1: c^2 = a^2 + b^2, difference of distances 2a, asymptotes y = \\pm\\frac{b}{a}x.",
        method=(
            "Rewrite in standard form and read off a, b, c (or p)",
            "Find the foci, vertices, directrix or asymptotes",
            "Use the focal definitions or the tangent-line formulas to set up the condition",
        ),
        notation="Write conics in standard form. " + CHOICE,
        pitfalls="Swapping c^2 = a^2 - b^2 (ellipse) and c^2 = a^2 + b^2 (hyperbola), reading 4p as p in y^2 = 4px.",
        check="Check the focal definition (sum or difference of distances) with one point on the curve.",
    ),
    "geo_vector": UnitText(
        grade="Precalculus",
        name="Vectors in the plane (components, dot product)",
        examples="\\vec{a} \\cdot \\vec{b} for \\vec{a} = (2, 1), \\vec{b} = (1, -3), |\\vec{a} + 2\\vec{b}|, perpendicular vectors, "
        "the position vector of a point dividing a segment",
        concept="Component operations, magnitude |\\vec{a}| = \\sqrt{a_1^2 + a_2^2}. Dot product \\vec{a} \\cdot \\vec{b} = |\\vec{a}||\\vec{b}|\\cos\\theta = a_1b_1 + a_2b_2. "
        "Perpendicular ⇔ \\vec{a} \\cdot \\vec{b} = 0, parallel ⇔ \\vec{b} = k\\vec{a}; "
        "|m\\vec{a} + n\\vec{b}|^2 = m^2|\\vec{a}|^2 + 2mn\\,\\vec{a} \\cdot \\vec{b} + n^2|\\vec{b}|^2 "
        "(e.g. |2\\vec{a} - \\vec{b}|^2 = 4|\\vec{a}|^2 - 4\\vec{a} \\cdot \\vec{b} + |\\vec{b}|^2).",
        method=(
            "Write the vectors in components or in terms of two base vectors",
            "Given the angle, first compute \\vec{a} \\cdot \\vec{b} = |\\vec{a}||\\vec{b}|\\cos\\theta",
            "Square a magnitude and expand it (keep the middle coefficient 2mn)",
            "Turn perpendicular/parallel/angle conditions into dot-product equations",
        ),
        notation="Write vectors as \\vec{a} or \\overrightarrow{AB}. " + CHOICE,
        pitfalls="Writing |\\vec{a} + \\vec{b}| = |\\vec{a}| + |\\vec{b}|, treating the dot product as a vector, "
        "dropping the 2 (or m, n) in the middle term 2mn\\,\\vec{a} \\cdot \\vec{b} when expanding |m\\vec{a} + n\\vec{b}|^2.",
        check="Check directions and lengths on a sketch, or recompute in components.",
    ),
    "geo_space": UnitText(
        grade="Precalculus",
        name="Solid geometry and 3D coordinates",
        examples="the three perpendiculars theorem, projected area S\\cos\\theta, the distance between A(1, 2, 3) and B(3, -1, 9), "
        "the point dividing a segment, the sphere (x-1)^2 + (y+2)^2 + z^2 = 9",
        concept="Three perpendiculars theorem (a perpendicular to a plane and a perpendicular to a line in it). Orthogonal projection: "
        "length l\\cos\\theta, area S\\cos\\theta. Distance \\sqrt{(x_2-x_1)^2 + (y_2-y_1)^2 + (z_2-z_1)^2}, sphere (x-a)^2 + (y-b)^2 + (z-c)^2 = r^2.",
        method=(
            "Drop perpendiculars and find right triangles",
            "Set up coordinates if helpful and use the distance or section formula",
            "For a projection, multiply by \\cos\\theta of the angle between the planes",
        ),
        notation="Coordinates in the order (x, y, z). " + CHOICE,
        pitfalls="Multiplying a projection by \\sin instead of \\cos, choosing the wrong angle between the planes.",
        check="Recheck lengths with the Pythagorean theorem in a right triangle.",
    ),
}

GENERAL = UnitText(
    grade="General",
    name="Other",
    examples="",
    concept="First sort out what is given and what we are asked to find.",
    method=(
        "List what is given and what is asked",
        "Recall a fitting idea or formula",
        "Work it out one step at a time",
    ),
    check=CHECK,
)

TEXT: dict[str, UnitText] = {
    "m1_integer_rational": UnitText(
        grade="Grade 7",
        name="Operations with integers and rational numbers",
        examples="(-3)+(+5), (-2)×(-3)÷(+4), mixed operations with parentheses and exponents",
        concept="Adding: same signs → add the absolute values and keep the sign; different signs → subtract the absolute "
        "values and take the sign of the larger one. Multiplying/dividing: an even number of negatives gives +, odd gives -.",
        method=(
            "Follow the order of operations: exponents → parentheses → multiplication/division → addition/subtraction",
            "Rewrite division as multiplying by the reciprocal",
            "Decide the sign first, then work out the absolute value",
        ),
        notation="Write negative numbers in parentheses (e.g. (-3)×(+2)).",
        pitfalls="Mixing up (-2)^2 and -2^2.",
        check="Redo the calculation in reverse order.",
    ),
    "m1_expression": UnitText(
        grade="Grade 7",
        name="Algebraic expressions (combining like terms)",
        examples="Simplify 3(x-2)-2(x+1), evaluate an expression, 2x+3x",
        concept="Only like terms can be combined. Distributive property: a(b+c)=ab+ac.",
        method=(
            "Distribute to remove parentheses first (a minus sign in front changes every sign inside)",
            "Group the like terms",
            "Add or subtract their coefficients",
        ),
        notation="Leave out the multiplication sign and write the number first (2×x → 2x, 1×x → x).",
        pitfalls="Forgetting to change the sign of -3 when removing -(x-3).",
        check="Plug a simple number in for the variable: the original and simplified expressions must agree.",
    ),
    "m1_linear_equation": UnitText(
        grade="Grade 8",
        name="Linear equations",
        examples="2x-5=11, 3(x-1)=2x+4, \\frac{x}{2}+1=\\frac{x+3}{3}, 0.2x+0.5=1.1",
        concept="Properties of equality: adding, subtracting, multiplying or dividing (by a nonzero number) both sides by the "
        "same number keeps the equation true, so we undo each operation with its inverse.",
        method=(
            "Distribute to remove parentheses",
            "Clear fractions by multiplying both sides by the least common denominator (decimals: by 10 or 100)",
            "Collect the variable terms on one side and the constants on the other (add/subtract on both sides)",
            "Simplify to the form ax=b",
            "Divide both sides by the coefficient of x",
        ),
        notation='Write each step as the new equation (2x-5=11 → 2x=16) and put the operation, e.g. "+5 both sides", in the '
        "margin note. Write the solution as x=8.",
        pitfalls="Doing an operation to only one side, or not multiplying every term when clearing fractions.",
        check="Substitute the solution into the original equation and check that both sides are equal.",
    ),
    "m1_proportion": UnitText(
        grade="Grade 7",
        name="Proportional relationships (direct and inverse variation)",
        examples="y varies directly with x and y=6 when x=2, the graph of y=\\frac{a}{x}",
        concept="Direct variation: y=kx (k≠0), the constant of proportionality k=y/x. Inverse variation: y=\\frac{k}{x} (k≠0). "
        "Substitute a known point to find k.",
        method=(
            "Decide the form (y=kx or y=\\frac{k}{x})",
            "Substitute the given x and y to find k",
            "Use the equation to find the requested value",
        ),
        check="Substitute the given point into the equation you found.",
    ),
    "m2_rational_decimal": UnitText(
        grade="Grade 8",
        name="Rational numbers and repeating decimals",
        examples="Write 0.\\overline{3} as a fraction, operations with repeating decimals",
        concept="Every repeating decimal is a rational number. Multiply by a power of 10 matching the repeating block and "
        "subtract, and the repeating part cancels.",
        method=(
            "Let x equal the repeating decimal",
            "Multiply by a suitable power of 10",
            "Subtract the two equations, solve for x and simplify the fraction",
        ),
        notation="A repeating block is written with a bar: 0.\\overline{3}.",
        check="Divide the fraction and see that you get the repeating decimal back.",
    ),
    "m2_monomial_polynomial": UnitText(
        grade="Algebra 1",
        name="Exponents and polynomials",
        examples="a^3×a^4, (2x^2y)^3, (6x^2-4x)÷2x, 2(a+3b)-(a-b)",
        concept="Exponent rules: a^m·a^n=a^{m+n}, (a^m)^n=a^{mn}, (ab)^n=a^nb^n. Add and subtract polynomials by combining like terms.",
        method=(
            "Multiply coefficients with coefficients and variables with variables",
            "Apply the exponent rules",
            "Combine like terms",
        ),
        notation="Leave out the multiplication sign and write variables in alphabetical order.",
        pitfalls="Adding exponents in (a^2)^3 to get a^5.",
        check="Plug in a simple number and compare the values.",
    ),
    "m2_linear_inequality": UnitText(
        grade="Algebra 1",
        name="Linear inequalities",
        examples="3x-2<7, 2(x+1)\\ge x-3, compound inequalities",
        concept="Adding or subtracting the same number, or multiplying/dividing by a positive number, keeps the inequality sign; "
        "multiplying or dividing by a negative number flips it.",
        method=(
            "Clear parentheses, fractions and decimals (as with equations)",
            "Collect the variable terms on one side and the constants on the other",
            "Simplify to ax>b",
            "Divide by the coefficient of x (flip the sign when dividing by a negative)",
        ),
        notation="Write the solution as x>3 and graph it on a number line if asked.",
        pitfalls="Forgetting to flip the inequality sign when dividing by a negative number.",
        check="Test the boundary value and one number from the solution set in the original inequality.",
    ),
    "m2_simultaneous": UnitText(
        grade="Grade 8",
        name="Systems of linear equations",
        examples="x+y=5, x-y=1 / 2x+3y=12, y=x+1",
        concept="Find the x and y that satisfy both equations at once. Eliminate one variable by elimination (adding or "
        "subtracting equations) or substitution.",
        method=(
            "Choose elimination if the coefficients line up easily, substitution if one equation is already x= or y=",
            "Elimination: make the coefficients of one variable opposites (or equal), then add (or subtract) the equations",
            "Solve the remaining one-variable equation",
            "Substitute that value back into one equation to find the other variable",
        ),
        notation='Number the equations ① and ② and note steps like "① + ②" or "2×① - ②". Write the solution as x=2, y=3 '
        "or the ordered pair (2, 3).",
        pitfalls="Not changing every sign when subtracting one equation from the other.",
        check="Substitute x and y into both original equations.",
    ),
    "m2_linear_function": UnitText(
        grade="Grade 8",
        name="Linear functions (slope-intercept form)",
        examples="The line with slope 2 through (1, 3), the linear function through two points, y-intercept",
        concept="In y=mx+b, m is the slope (rise over run: how much y changes when x increases by 1) and b is the y-intercept. "
        "Slope = (change in y)/(change in x).",
        method=(
            "Write the equation as y=mx+b",
            "Find the slope m (given, or from two points)",
            "Substitute a point on the line to find b",
            "Answer in the form y=mx+b",
        ),
        check="Substitute the given point(s) into the equation.",
    ),
    "m2_pythagoras": UnitText(
        grade="Grade 8",
        name="The Pythagorean theorem",
        examples="Find the hypotenuse of a right triangle, legs 3 and 4",
        concept="In a right triangle with legs a and b and hypotenuse c, a^2+b^2=c^2.",
        method=(
            "Find the hypotenuse (the side opposite the right angle)",
            "Substitute into a^2+b^2=c^2",
            "Take the square root (a length is positive)",
        ),
        check="Check that the three sides satisfy a^2+b^2=c^2.",
    ),
    "m2_probability": UnitText(
        grade="Grade 7",
        name="Probability",
        examples="The probability that two dice sum to 7, tossing 3 coins",
        concept="Probability = (number of favorable outcomes)/(number of equally likely outcomes). For independent events "
        "happening together, multiply; for mutually exclusive events, add.",
        method=(
            "Count all possible outcomes",
            "Count the favorable outcomes without missing any",
            "Divide and simplify the fraction",
        ),
        check="Recount with a table or a tree diagram.",
    ),
    "m3_square_root": UnitText(
        grade="Algebra 1",
        name="Square roots and radicals",
        examples="\\sqrt{12}+\\sqrt{27}, rationalize \\frac{2}{\\sqrt{3}}, \\sqrt{a^2}",
        concept="\\sqrt{a^2b}=a\\sqrt{b} (a>0). Rationalize a denominator by multiplying the top and bottom by the same radical.",
        method=(
            "Factor the radicand and take perfect squares out of the root",
            "Combine like radicals",
            "Rationalize the denominator",
        ),
        notation="Simplest radical form: the number under the root is as small as possible.",
        pitfalls="Writing \\sqrt{a}+\\sqrt{b}=\\sqrt{a+b}.",
        check="Square the result and compare with the original value.",
    ),
    "m3_factorization": UnitText(
        grade="Algebra 1",
        name="Multiplying and factoring polynomials",
        examples="Expand (x+3)(x-2), factor x^2-5x+6, x^2-9",
        concept="Special products: (a+b)^2=a^2+2ab+b^2, (a+b)(a-b)=a^2-b^2, (x+a)(x+b)=x^2+(a+b)x+ab. Factoring runs them backwards.",
        method=(
            "Factor out the greatest common factor first",
            "Look for a pattern (perfect square trinomial, difference of squares, x^2+(a+b)x+ab)",
            "Find two numbers whose product is the constant term and whose sum is the x-coefficient",
        ),
        check="Multiply the factors back out and compare with the original.",
    ),
    "m3_quadratic_equation": UnitText(
        grade="Algebra 1",
        name="Quadratic equations",
        examples="x^2-5x+6=0, 2x^2+3x-2=0, x^2-4x-1=0, (x-3)^2=5",
        concept="Zero product property: if AB=0 then A=0 or B=0. If it doesn't factor, complete the square or use the "
        "quadratic formula x=\\frac{-b\\pm\\sqrt{b^2-4ac}}{2a}.",
        method=(
            "Rewrite in standard form ax^2+bx+c=0",
            "If it factors, factor and use the zero product property",
            "Otherwise use the quadratic formula",
            "Write the solutions as x=a or x=b",
        ),
        notation='Two solutions: "x=2 or x=3"; a repeated root: "x=3 (double root)".',
        pitfalls="Dividing both sides by x and losing the solution x=0.",
        check="Substitute each solution into the original equation and check that it gives 0.",
    ),
    "m3_quadratic_function": UnitText(
        grade="Algebra 1",
        name="Quadratic functions (vertex form)",
        examples="The vertex of y=2(x-1)^2+3, rewrite y=x^2-4x+1 in vertex form",
        concept="The graph of y=a(x-h)^2+k has vertex (h, k) and axis of symmetry x=h. Complete the square to turn standard "
        "form into vertex form.",
        method=(
            "Factor out the coefficient of x^2",
            "Complete the square",
            "Read off the vertex and the axis",
        ),
        check="Expand the vertex form and compare with the original.",
    ),
    "m3_trigonometry": UnitText(
        grade="Geometry",
        name="Right-triangle trigonometry",
        examples="sin 30°, tan A in a right triangle",
        concept="In a right triangle: sin A = opposite/hypotenuse, cos A = adjacent/hypotenuse, tan A = opposite/adjacent (SOH-CAH-TOA).",
        method=(
            "Pick the reference angle and label the opposite, adjacent and hypotenuse",
            "Write the ratio from the definition",
            "Use the known values for special angles (30°, 45°, 60°)",
        ),
        check=CHECK,
    ),
    "h1_polynomial": UnitText(
        grade="Algebra 2",
        name="Polynomial division and the remainder theorem",
        examples="The remainder of (x^3+2x-1)÷(x-1), coefficients of an identity",
        concept="Remainder theorem: dividing a polynomial P(x) by x-a leaves remainder P(a). An identity holds for every x, "
        "so compare coefficients or substitute values.",
        method=(
            "For a linear divisor, compute P(a) with the remainder theorem",
            "Use synthetic division to get the quotient if needed",
        ),
        check="Expand (divisor)×(quotient)+(remainder) and compare with the original polynomial.",
    ),
    "h1_complex_quadratic": UnitText(
        grade="Algebra 2",
        name="Complex numbers and the discriminant",
        examples="Classify the roots with the discriminant, sum and product of roots, complex roots of x^2+2x+5=0",
        concept="Discriminant D=b^2-4ac: D>0 two real roots, D=0 one repeated root, D<0 two complex roots. "
        "Vieta's formulas: \\alpha+\\beta=-\\frac{b}{a}, \\alpha\\beta=\\frac{c}{a}.",
        method=(
            "Decide whether the question asks for the roots, their type, or their sum/product",
            "Use the discriminant or Vieta's formulas",
            "Write complex roots with i (i^2=-1)",
        ),
        check=CHECK,
    ),
    "h1_inequality": UnitText(
        grade="Algebra 2",
        name="Quadratic and absolute value inequalities",
        examples="x^2-3x-4<0, |x-2|<3, systems of quadratic inequalities",
        concept="Solve a quadratic inequality from where the parabola is above or below the x-axis. |x-a|<b ⇔ -b<x-a<b.",
        method=(
            "Find the roots of the related quadratic equation",
            "Picture the parabola (opening up or down) to choose the interval",
            "For absolute values, split into cases or use the definition",
        ),
        check="Test one number inside and one outside the interval.",
    ),
    "h1_counting": UnitText(
        grade="Algebra 2",
        name="Permutations and combinations",
        examples="Choose and line up 2 of 5 people, _5C_2",
        concept="If order matters, use permutations _nP_r; if not, combinations _nC_r=\\frac{_nP_r}{r!}.",
        method=("Decide whether order matters", "Set up the permutation or combination", "Calculate"),
        check=CHECK,
    ),
    "h1_equation_of_figure": UnitText(
        grade="Geometry",
        name="Coordinate geometry (lines and circles)",
        examples="Distance between two points, equation of a line, circle (x-1)^2+(y+2)^2=9",
        concept="Distance formula \\sqrt{(x_2-x_1)^2+(y_2-y_1)^2}; the circle (x-h)^2+(y-k)^2=r^2 has center (h, k) and radius r.",
        method=(
            "Decide the form of the equation",
            "Substitute the given conditions",
            "Rewrite in standard form",
        ),
        check=CHECK,
    ),
    **CSAT_TEXT,
}
