"""School-curriculum guide: Korean (2022 개정 교육과정, 수학 중1~고1 and the 수능 subjects
수학Ⅰ, 수학Ⅱ, 확률과 통계, 미적분, 기하) with Japanese and US text for the same unit ids
(curriculum_ja.py, curriculum_en.py).

The solve prompt is built from the unit a problem belongs to, so explanations follow the
order, vocabulary and notation students see in their textbooks (e.g. 이항 rather than
"add 5 to both sides" on every line in Korea; "do the same to both sides" in the US)
instead of a generic symbolic derivation. `unit()` returns the unit in the request's
language.
"""

from __future__ import annotations

from dataclasses import replace

from studymate.i18n import lang, tr
from studymate.solve import curriculum_csat
from studymate.solve.curriculum_math_csat import CSAT_MATH_UNITS
from studymate.solve.curriculum_types import Unit, UnitText

__all__ = [
    "GENERAL",
    "UNITS",
    "Unit",
    "classifier_prompt",
    "classifier_schema",
    "is_general",
    "teaching_guide",
    "unit",
]


UNITS: tuple[Unit, ...] = (
    Unit(
        "m1_integer_rational",
        "중1",
        "정수와 유리수의 계산",
        "(-3)+(+5), (-2)×(-3)÷(+4), 괄호와 거듭제곱이 섞인 계산",
        "덧셈의 교환·결합법칙, 부호가 같으면 절댓값의 합에 공통 부호, 다르면 절댓값의 차에 큰 쪽 부호. "
        "곱셈·나눗셈은 음수의 개수가 짝수면 +, 홀수면 -.",
        (
            "거듭제곱 → 괄호 → 곱셈·나눗셈 → 덧셈·뺄셈 순서로 계산한다",
            "나눗셈은 역수의 곱셈으로 바꾼다",
            "부호를 먼저 정하고 절댓값을 계산한다",
        ),
        "음수는 괄호로 감싸 쓴다 (예: (-3)×(+2)).",
        "(-2)^2와 -2^2를 헷갈리지 않는다.",
        "계산 순서를 거꾸로 따라가며 다시 계산해 본다.",
    ),
    Unit(
        "m1_expression",
        "중1",
        "문자와 식 (일차식의 계산)",
        "3(x-2)-2(x+1) 간단히, 식의 값 구하기, 2x+3x",
        "동류항끼리만 더하거나 뺄 수 있다. 분배법칙 a(b+c)=ab+ac.",
        (
            "괄호가 있으면 분배법칙으로 먼저 푼다 (괄호 앞이 -이면 모든 항의 부호가 바뀐다)",
            "동류항끼리 모은다",
            "계수끼리 계산해 간단히 한다",
        ),
        "곱셈 기호는 생략하고 수를 문자 앞에 쓴다 (2×x → 2x, 1×x → x).",
        "-(x-3)을 풀 때 -3의 부호를 바꾸지 않는 실수.",
        "문자에 간단한 수를 넣어 처음 식과 결과 식의 값이 같은지 본다.",
    ),
    Unit(
        "m1_linear_equation",
        "중1",
        "일차방정식",
        "2x-5=11, 3(x-1)=2x+4, \\frac{x}{2}+1=\\frac{x+3}{3}, 0.2x+0.5=1.1",
        "등식의 성질: 양변에 같은 수를 더하거나 빼거나 곱하거나 (0이 아닌 수로) 나누어도 등식은 성립한다. "
        "이 성질을 이용해 항을 부호를 바꾸어 다른 변으로 옮기는 것이 이항이다.",
        (
            "괄호가 있으면 분배법칙으로 푼다",
            "계수가 분수면 양변에 분모의 최소공배수를, 소수면 10의 거듭제곱을 곱해 정수로 만든다",
            "x항은 좌변, 상수항은 우변으로 이항한다 (부호를 바꾸어 한 번에 옮겨 쓴다)",
            "양변을 정리해 ax=b 꼴로 만든다",
            "양변을 x의 계수로 나누어 해를 구한다",
        ),
        "이항은 식을 한 번에 옮겨 쓴다 (2x-5=11 → 2x=11+5). 해는 x=8처럼 쓴다. "
        "'+5+5'처럼 양변에 더하는 과정을 매번 따로 쓰지 않는다.",
        "이항할 때 부호를 바꾸지 않는 실수, 분모를 없앨 때 모든 항에 곱하지 않는 실수.",
        "x=해를 처음 방정식에 대입해 좌변과 우변이 같은지 확인한다.",
    ),
    Unit(
        "m1_proportion",
        "중1",
        "좌표평면과 그래프 (정비례·반비례)",
        "y가 x에 정비례하고 x=2일 때 y=6, y=\\frac{a}{x}의 그래프",
        "정비례는 y=ax (a≠0), 반비례는 y=\\frac{a}{x} (a≠0). 주어진 점을 대입해 a를 구한다.",
        (
            "관계식의 꼴을 정한다 (y=ax 또는 y=\\frac{a}{x})",
            "주어진 x, y 값을 대입해 a를 구한다",
            "구한 식으로 묻는 값을 계산한다",
        ),
        check="구한 식에 주어진 점을 다시 대입해 본다.",
    ),
    Unit(
        "m2_rational_decimal",
        "중2",
        "유리수와 순환소수",
        "0.\\dot{3}을 분수로, 순환소수의 계산",
        "순환소수는 분수로 나타낼 수 있다. 순환마디만큼 10의 거듭제곱을 곱해 빼면 순환하는 부분이 사라진다.",
        (
            "x=순환소수로 놓는다",
            "적당한 10의 거듭제곱을 곱한 식을 만든다",
            "두 식을 빼서 x를 분수로 구하고 약분한다",
        ),
        check="구한 분수를 나눗셈해 순환소수가 나오는지 확인한다.",
    ),
    Unit(
        "m2_monomial_polynomial",
        "중2",
        "식의 계산 (지수법칙·다항식)",
        "a^3×a^4, (2x^2y)^3, (6x^2-4x)÷2x, 2(a+3b)-(a-b)",
        "지수법칙: a^m×a^n=a^{m+n}, (a^m)^n=a^{mn}, (ab)^n=a^nb^n. 다항식의 덧셈·뺄셈은 동류항끼리.",
        ("계수는 계수끼리, 문자는 문자끼리 계산한다", "지수법칙을 적용한다", "동류항을 정리한다"),
        "곱셈 기호를 생략하고 문자는 알파벳 순으로 쓴다.",
        "(a^2)^3=a^5로 더해 버리는 실수.",
        "문자에 간단한 수를 넣어 값을 비교한다.",
    ),
    Unit(
        "m2_linear_inequality",
        "중2",
        "일차부등식",
        "3x-2<7, 2(x+1)\\ge x-3, 연립일차부등식",
        "부등식의 성질: 양변에 같은 수를 더하거나 빼도, 양수를 곱하거나 나누어도 부등호 방향은 그대로, "
        "음수를 곱하거나 나누면 부등호 방향이 바뀐다.",
        (
            "괄호·분수·소수를 정리한다 (일차방정식과 같은 방법)",
            "x항은 좌변, 상수항은 우변으로 이항한다",
            "ax>b 꼴로 정리한다",
            "x의 계수로 양변을 나눈다 (음수로 나누면 부등호 방향을 바꾼다)",
        ),
        "해는 x>3처럼 쓰고, 필요하면 수직선에 나타낸다.",
        "음수로 나눌 때 부등호 방향을 바꾸지 않는 실수.",
        "경계값과 해에 속하는 수를 하나 넣어 부등식이 성립하는지 확인한다.",
    ),
    Unit(
        "m2_simultaneous",
        "중2",
        "연립일차방정식",
        "x+y=5, x-y=1 / 2x+3y=12, y=x+1",
        "두 방정식을 동시에 만족하는 x, y를 구한다. 한 미지수를 없애는 가감법과 대입법이 있다.",
        (
            "계수를 맞추기 쉬우면 가감법, 한 식이 x= 또는 y= 꼴이면 대입법을 고른다",
            "가감법: 한 미지수의 계수의 절댓값을 같게 만든 뒤 두 식을 더하거나 뺀다",
            "남은 일차방정식을 풀어 한 미지수를 구한다",
            "구한 값을 한 식에 대입해 다른 미지수를 구한다",
        ),
        "각 식에 ①, ② 번호를 붙여 '①+②', '①×2-②'처럼 쓴다. 해는 x=2, y=3 또는 (2, 3).",
        "두 식을 뺄 때 모든 항의 부호를 바꾸지 않는 실수.",
        "구한 x, y를 두 식 모두에 대입해 확인한다.",
    ),
    Unit(
        "m2_linear_function",
        "중2",
        "일차함수와 그래프",
        "기울기가 2이고 (1, 3)을 지나는 직선, 두 점을 지나는 일차함수, y절편",
        "일차함수 y=ax+b에서 a는 기울기(x가 1 증가할 때 y의 증가량), b는 y절편. "
        "기울기 = (y의 값의 증가량)/(x의 값의 증가량).",
        (
            "구하는 식을 y=ax+b로 놓는다",
            "기울기 a를 구한다 (주어졌거나 두 점으로 계산)",
            "지나는 점을 대입해 b를 구한다",
            "y=ax+b 꼴로 답한다",
        ),
        check="주어진 점을 구한 식에 대입해 본다.",
    ),
    Unit(
        "m2_pythagoras",
        "중2",
        "피타고라스 정리",
        "직각삼각형에서 빗변 구하기, 3, 4, x",
        "직각삼각형에서 빗변의 길이를 c, 나머지 두 변을 a, b라 하면 a^2+b^2=c^2.",
        ("빗변(직각의 대변)을 찾는다", "a^2+b^2=c^2에 대입한다", "제곱근을 구한다 (길이는 양수)"),
        check="세 변으로 a^2+b^2=c^2가 성립하는지 계산해 본다.",
    ),
    Unit(
        "m2_probability",
        "중2",
        "경우의 수와 확률",
        "주사위 두 개를 던질 때 합이 7일 확률, 동전 3개",
        "확률 = (사건이 일어나는 경우의 수)/(모든 경우의 수). 동시에 일어나면 곱, 동시에 일어나지 않으면 합.",
        ("모든 경우의 수를 구한다", "사건이 일어나는 경우를 빠짐없이 센다", "나누어 기약분수로 답한다"),
        check="표나 나뭇가지 그림으로 경우를 다시 세어 본다.",
    ),
    Unit(
        "m3_square_root",
        "중3",
        "제곱근과 실수",
        "\\sqrt{12}+\\sqrt{27}, \\frac{2}{\\sqrt{3}} 분모의 유리화, \\sqrt{a^2}",
        "\\sqrt{a^2b}=a\\sqrt{b} (a>0). 분모에 근호가 있으면 분모와 분자에 같은 근호를 곱해 유리화한다.",
        (
            "근호 안을 소인수분해해 제곱인 수를 밖으로 꺼낸다",
            "근호 안이 같은 것끼리 계산한다",
            "분모를 유리화한다",
        ),
        "답은 근호 안을 가장 작은 자연수로 만든 꼴로 쓴다.",
        "\\sqrt{a}+\\sqrt{b}=\\sqrt{a+b}로 계산하는 실수.",
        "제곱해서 처음 값과 같은지 확인한다.",
    ),
    Unit(
        "m3_factorization",
        "중3",
        "다항식의 곱셈과 인수분해",
        "(x+3)(x-2) 전개, x^2-5x+6 인수분해, x^2-9",
        "곱셈 공식: (a+b)^2=a^2+2ab+b^2, (a+b)(a-b)=a^2-b^2, (x+a)(x+b)=x^2+(a+b)x+ab. 인수분해는 그 반대.",
        (
            "공통인수가 있으면 먼저 묶어 낸다",
            "곱셈 공식의 꼴(완전제곱식, 합차, x^2+(a+b)x+ab)을 찾는다",
            "곱해서 상수항, 더해서 일차항 계수가 되는 두 수를 찾는다",
        ),
        check="인수분해한 식을 다시 전개해 처음 식과 같은지 확인한다.",
    ),
    Unit(
        "m3_quadratic_equation",
        "중3",
        "이차방정식",
        "x^2-5x+6=0, 2x^2+3x-2=0, x^2-4x-1=0, (x-3)^2=5",
        "AB=0이면 A=0 또는 B=0. 인수분해가 안 되면 완전제곱식이나 근의 공식 "
        "x=\\frac{-b\\pm\\sqrt{b^2-4ac}}{2a}를 쓴다.",
        (
            "ax^2+bx+c=0 꼴로 정리한다",
            "인수분해가 되면 인수분해해서 AB=0을 이용한다",
            "인수분해가 어려우면 근의 공식(짝수 계수면 짝수 공식)을 쓴다",
            "해를 x=a 또는 x=b로 쓴다",
        ),
        "두 근은 'x=2 또는 x=3', 중근은 'x=3 (중근)'으로 쓴다.",
        "양변을 x로 나누어 x=0인 근을 잃어버리는 실수.",
        "각 근을 처음 식에 대입해 0이 되는지 확인한다.",
    ),
    Unit(
        "m3_quadratic_function",
        "중3",
        "이차함수와 그래프",
        "y=2(x-1)^2+3의 꼭짓점, y=x^2-4x+1을 표준형으로",
        "y=a(x-p)^2+q의 꼭짓점은 (p, q), 축은 x=p. 일반형은 완전제곱식으로 고쳐 표준형으로 바꾼다.",
        ("x^2의 계수로 묶는다", "완전제곱식을 만든다", "꼭짓점과 축을 읽는다"),
        check="표준형을 다시 전개해 처음 식과 같은지 확인한다.",
    ),
    Unit(
        "m3_trigonometry",
        "중3",
        "삼각비",
        "sin 30°, 직각삼각형에서 tan A",
        "직각삼각형에서 sin A=(높이)/(빗변), cos A=(밑변)/(빗변), tan A=(높이)/(밑변).",
        (
            "기준각과 빗변·높이·밑변을 정한다",
            "정의에 맞게 비를 쓴다",
            "특수각(30°, 45°, 60°)은 값을 이용한다",
        ),
    ),
    Unit(
        "h1_polynomial",
        "고1",
        "다항식의 연산·나머지정리",
        "(x^3+2x-1)÷(x-1)의 나머지, 항등식의 계수 결정",
        "나머지정리: 다항식 f(x)를 x-a로 나눈 나머지는 f(a). 항등식은 모든 x에 대해 성립하므로 계수비교나 수치대입을 쓴다.",
        ("나누는 식이 일차식이면 나머지정리로 f(a)를 계산한다", "필요하면 조립제법으로 몫을 구한다"),
        check="(나누는 식)×(몫)+(나머지)를 전개해 처음 식과 비교한다.",
    ),
    Unit(
        "h1_complex_quadratic",
        "고1",
        "복소수와 이차방정식",
        "판별식으로 근 판별, 두 근의 합과 곱, x^2+2x+5=0의 허근",
        "판별식 D=b^2-4ac: D>0 서로 다른 두 실근, D=0 중근, D<0 서로 다른 두 허근. "
        "근과 계수의 관계: \\alpha+\\beta=-\\frac{b}{a}, \\alpha\\beta=\\frac{c}{a}.",
        (
            "묻는 것이 근인지, 근의 종류인지, 두 근의 합·곱인지 정한다",
            "판별식 또는 근과 계수의 관계를 적용한다",
            "허근은 i를 써서 나타낸다 (i^2=-1)",
        ),
    ),
    Unit(
        "h1_inequality",
        "고1",
        "여러 가지 부등식",
        "x^2-3x-4<0, |x-2|<3, 연립이차부등식",
        "이차부등식은 이차함수 그래프가 x축보다 위/아래인 범위로 푼다. |x-a|<b ⇔ -b<x-a<b.",
        (
            "대응하는 이차방정식의 근을 구한다",
            "그래프(위로 볼록/아래로 볼록)를 떠올려 범위를 정한다",
            "절댓값은 경우를 나누거나 정의로 푼다",
        ),
        check="범위 안과 밖의 수를 하나씩 넣어 본다.",
    ),
    Unit(
        "h1_counting",
        "고1",
        "경우의 수·순열과 조합",
        "5명 중 2명을 뽑아 줄 세우기, _5C_2",
        "순서를 따지면 순열 _nP_r, 따지지 않으면 조합 _nC_r=\\frac{_nP_r}{r!}.",
        ("순서를 따지는지 판단한다", "순열 또는 조합 공식을 세운다", "계산한다"),
    ),
    Unit(
        "h1_equation_of_figure",
        "고1",
        "도형의 방정식",
        "두 점 사이의 거리, 직선의 방정식, 원의 방정식 (x-1)^2+(y+2)^2=9",
        "두 점 사이의 거리 \\sqrt{(x_2-x_1)^2+(y_2-y_1)^2}, 원 (x-a)^2+(y-b)^2=r^2의 중심 (a, b), 반지름 r.",
        ("구하는 도형의 식의 꼴을 정한다", "주어진 조건을 대입한다", "표준형으로 정리한다"),
    ),
    *CSAT_MATH_UNITS,
)

GENERAL = Unit(
    "general",
    "공통",
    "기타",
    "",
    "문제에서 주어진 조건과 구하는 것을 먼저 정리한다.",
    ("구하는 것과 주어진 것을 정리한다", "알맞은 개념이나 공식을 떠올린다", "한 단계씩 계산한다"),
)

# Math units above, then the other CSAT subjects (evidence-style lessons).
ALL_UNITS: tuple[Unit, ...] = UNITS + curriculum_csat.UNITS
BY_ID: dict[str, Unit] = {u.id: u for u in ALL_UNITS}


def _texts() -> tuple[dict[str, UnitText], UnitText] | None:
    """Japanese / English text tables for the current language (None for Korean)."""
    current = lang()
    if current == "ja":
        from studymate.solve import curriculum_ja

        return {**curriculum_ja.TEXT, **curriculum_csat.TEXT_JA}, curriculum_ja.GENERAL
    if current == "en":
        from studymate.solve import curriculum_en

        return {**curriculum_en.TEXT, **curriculum_csat.TEXT_EN}, curriculum_en.GENERAL
    return None


def _localize(u: Unit) -> Unit:
    tables = _texts()
    if tables is None:
        return u
    text = tables[0].get(u.id, tables[1])
    return replace(u, **text._asdict())


def unit(unit_id: str | None) -> Unit:
    """The unit in the current request's language (general when unknown)."""
    return _localize(BY_ID.get(unit_id or "", GENERAL))


def is_general(u: Unit) -> bool:
    return u.id == GENERAL.id


# CSAT-level math (고2~고3 electives): harder, so the model works it out in a scratch field first.
_ADVANCED_GRADES = frozenset({"수학Ⅰ", "수학Ⅱ", "확률과 통계", "미적분", "기하"})


def is_advanced(u: Unit) -> bool:
    """Non-math CSAT subjects and CSAT-level math get the hidden analysis field."""
    return not u.is_math or BY_ID.get(u.id, GENERAL).grade in _ADVANCED_GRADES


# Subjects for the first classification step; "korean" is the student's national language
# (국어 / 国語 / language arts), "english" the foreign-language English exam.
SUBJECTS: tuple[str, ...] = ("math", "korean", "english", "korean_history", "social", "science", "other")


def subject_schema() -> dict[str, object]:
    return {
        "type": "object",
        # has_task first: asked on its own, the model tells a heading ("제3장 이차방정식") or a
        # bare answer ("y = 7") from a problem; offered as a subject option it still picked math.
        "properties": {"has_task": {"type": "boolean"}, "subject": {"enum": list(SUBJECTS)}},
        "required": ["has_task", "subject"],
        "additionalProperties": False,
    }


def subject_prompt() -> str:
    return tr(
        "학생이 보낸 글을 보고 두 가지를 답하세요.\n"
        "has_task: 학생이 할 일이 있으면 true — 질문, 지시(구하시오, 고르시오, 계산하시오 등), 또는 "
        "지시문이 없어도 계산하거나 풀 수 있는 식·방정식. 할 일이 없으면 false — 답만 있는 것('③', "
        "'정답: 2', 'x = 3'처럼 문자 하나가 숫자 하나와 같은 식), 단원·장 제목('제3장 이차방정식', "
        "'3. 함수의 극한', 'Unit 2'), 메뉴·쪽수·인사말 같은 화면 글자.\n"
        "subject: 어느 과목인지 하나 (할 일이 없어도 가장 가까운 과목).\n"
        "- math: 수학 (계산, 식, 방정식·부등식, 함수, 도형, 경우의 수·확률·통계, 수열, 극한, 미적분, 벡터)\n"
        "- korean: 국어 (국어 지문 독해, 시·소설 등 문학, 화법과 작문, 문법·매체)\n"
        "- english: 영어 (영어 지문이나 영어 문장에 대한 문제)\n"
        "- korean_history: 한국사\n"
        "- social: 사회탐구 (윤리, 한국지리·세계지리, 동아시아사·세계사, 경제, 정치와 법, 사회·문화)\n"
        "- science: 과학탐구 (물리, 화학, 생명과학, 지구과학 — 계산이 있어도 과학 개념 문제면 science)\n"
        "- other: 그 밖의 과목 (제2외국어, 한문, 일반 상식 등)",
        "生徒が送った文を見て、2つ答えてください。\n"
        "has_task: 生徒がすることがあれば true — 問い、指示（求めよ、選べ、計算せよ など）、または指示文が"
        "なくても計算したり解いたりできる式・方程式。することがなければ false — 答えだけのもの（「③」"
        "「答え: 2」、「x = 3」のように文字1つが数1つに等しいだけの式）、章・単元の見出し（「第2章 二次関数」"
        "「3. 関数の極限」「Unit 2」）、メニュー・ページ番号・あいさつなど画面の文字。\n"
        "subject: どの教科かを1つ（することがなくても一番近い教科）。\n"
        "- math: 数学（計算、式、方程式・不等式、関数、図形、場合の数・確率・統計、数列、極限、微分積分、ベクトル）\n"
        "- korean: 国語（評論・小説・詩・古文・漢文、話すこと書くこと、文法）\n"
        "- english: 英語（英文や英語の文についての問題）\n"
        "- korean_history: 韓国史\n"
        "- social: 地理歴史・公民（倫理、地理、世界史・東アジア史、経済、政治と法、現代社会）\n"
        "- science: 理科（物理、化学、生物、地学 — 計算があっても理科の概念の問題なら science）\n"
        "- other: その他の教科",
        "Answer two things about the text the student sent.\n"
        "has_task: true when there is something for the student to do — a question, an instruction (find, "
        "choose, calculate, ...), or, even without one, an expression or equation that can be computed or "
        "solved. false when there is nothing to do — only an answer ('③', 'Answer: 2', or 'x = 3': one "
        "letter equal to one number), a chapter or unit heading ('Chapter 3 Quadratic Equations', "
        "'3. Limits of Functions', 'Unit 2'), or screen text such as menus, page numbers or greetings.\n"
        "subject: the one subject it belongs to (the closest one even when there is nothing to do).\n"
        "- math: math (arithmetic, algebra, equations and inequalities, functions, geometry, counting, "
        "probability and statistics, sequences, limits, calculus, vectors)\n"
        "- korean: reading and literature in the student's own language (passages, poems, stories, writing, "
        "grammar)\n"
        "- english: English as a foreign-language exam (questions about an English passage or sentence)\n"
        "- korean_history: Korean history\n"
        "- social: social studies (ethics, geography, world and East Asian history, economics, government "
        "and law, sociology)\n"
        "- science: science (physics, chemistry, biology, earth science — a calculation about a science "
        "concept is still science)\n"
        "- other: anything else",
    )


def _units_for(subject: str | None) -> tuple[Unit, ...]:
    if subject is None:
        return ALL_UNITS
    if subject == "math":
        return tuple(u for u in ALL_UNITS if u.is_math)
    return tuple(u for u in ALL_UNITS if u.subject in (subject, "other"))


def classifier_schema(subject: str | None = None) -> dict[str, object]:
    ids = [u.id for u in _units_for(subject)]
    if subject in (None, "math"):
        ids.append(GENERAL.id)
    return {
        "type": "object",
        "properties": {"unit_id": {"enum": ids}},
        "required": ["unit_id"],
        "additionalProperties": False,
    }


def classifier_prompt(subject: str | None = None) -> str:
    eg = tr("예", "例", "e.g.")
    lines = [f"- {u.id}: {u.label} — {eg}) {u.examples}" for u in map(_localize, _units_for(subject))]
    head = tr(
        "학생이 보낸 문제가 한국 정규 교육과정의 어느 단원 문제인지 고르세요. "
        "문제를 풀 때 가장 직접 쓰이는 단원 하나를 고르고, 맞는 단원이 없으면 general을 고르세요.",
        "生徒が送った問題が、日本の学習指導要領のどの単元の問題かを選んでください。"
        "解くときにいちばん直接使う単元を1つ選び、合う単元がなければ general を選んでください。",
        "Choose which school math unit the student's problem belongs to. Pick the one unit most directly used "
        "to solve it; if none fits, choose general.",
    )
    return head + "\n" + "\n".join(lines)


def teaching_guide(u: Unit) -> str:
    """Unit guide injected into the solve prompt."""
    method = "\n".join(f"  {i}. {m}" for i, m in enumerate(u.method, 1))
    parts = [
        tr("단원", "単元", "Unit") + f": {u.label}",
        tr("핵심 개념", "大事な考え方", "Key idea") + f": {u.concept}",
        tr("교과서 풀이 순서", "教科書の解き方の手順", "Textbook steps") + f":\n{method}",
    ]
    if u.notation:
        parts.append(tr("표기 관례", "書き方のきまり", "Notation") + f": {u.notation}")
    if u.pitfalls:
        parts.append(
            tr(
                "학생이 자주 하는 실수 (설명할 때 짚어 주기)",
                "生徒がよくするまちがい（説明のときに触れる）",
                "Common student mistakes (point them out while explaining)",
            )
            + f": {u.pitfalls}"
        )
    parts.append(tr("검산 방법", "確かめ方", "How to check") + f": {u.check}")
    return "\n".join(parts)
