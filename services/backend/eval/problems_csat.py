# ruff: noqa: E501
"""Original CSAT (수능)-style multiple-choice items for the non-math subjects.

Every passage and item here was written for StudyMate (not taken from KICE 수능/모의평가 or
EBS material). Literary texts are public-domain works (김소월, 윤동주, 고시조) or our own.
`text` is what a student would capture: instructions, passage, <보기> and the five options.
Plain text cannot carry underlines, so an underlined span is written as [ ... ].

`answer` is the circled option number; `rationale` says why, for whoever reviews a failure.
`validate_problems` checks the set (used by eval/run_csat.py and tests/test_eval_csat.py).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

MARKS = ("①", "②", "③", "④", "⑤")

SUBJECT_AREA: dict[str, str] = {
    "국어": "국어",
    "영어": "영어",
    "한국사": "한국사",
    "생활과 윤리": "사회탐구",
    "윤리와 사상": "사회탐구",
    "한국지리": "사회탐구",
    "세계지리": "사회탐구",
    "동아시아사": "사회탐구",
    "세계사": "사회탐구",
    "경제": "사회탐구",
    "정치와 법": "사회탐구",
    "사회·문화": "사회탐구",
    "물리학Ⅰ": "과학탐구",
    "화학Ⅰ": "과학탐구",
    "생명과학Ⅰ": "과학탐구",
    "지구과학Ⅰ": "과학탐구",
}

_INQUIRY_SUBTYPES = ("개념", "자료 분석", "사상가 비교", "사례 적용", "계산")
SUBTYPES: dict[str, tuple[str, ...]] = {
    "국어": (
        "독서-인문",
        "독서-사회",
        "독서-과학",
        "독서-기술",
        "문학-현대시",
        "문학-고전시가",
        "문학-현대소설",
        "문학-고전소설",
        "화법과 작문",
        "언어와 매체",
    ),
    "영어": (
        "글의 목적",
        "심경",
        "주장",
        "요지",
        "주제",
        "제목",
        "내용 일치",
        "어법",
        "어휘",
        "빈칸 추론",
        "무관한 문장",
        "순서 배열",
        "문장 삽입",
        "요약문 완성",
    ),
    "한국사": ("고대", "고려", "조선", "근대", "일제 강점기", "현대"),
} | {s: _INQUIRY_SUBTYPES for s, area in SUBJECT_AREA.items() if area in ("사회탐구", "과학탐구")}

# Subtypes whose option markers sit inside the passage ("( ③ )", "③[word]") instead of a list.
INLINE_OPTION_SUBTYPES = ("어법", "어휘", "무관한 문장", "문장 삽입")


@dataclass(frozen=True)
class CsatProblem:
    id: str
    subject: str
    subtype: str
    text: str
    answer: str  # "③"
    rationale: str

    @property
    def area(self) -> str:
        return SUBJECT_AREA[self.subject]

    @property
    def choice(self) -> int:
        return MARKS.index(self.answer) + 1


def _q(*parts: str, options: Sequence[str] = ()) -> str:
    """Problem text: non-empty parts separated by blank lines, then one option per line."""
    blocks = [p.strip("\n") for p in parts if p.strip()]
    if options:
        blocks.append("\n".join(f"{m} {o}" for m, o in zip(MARKS, options, strict=True)))
    return "\n\n".join(blocks)


def _box(body: str) -> str:
    return f"<보기>\n{body.strip()}"


def _p(pid: str, subject: str, subtype: str, text: str, answer: str, rationale: str) -> CsatProblem:
    return CsatProblem(pid, subject, subtype, text, answer, rationale)


# <보기> answer sets (ascending, as printed on the CSAT)
SET_1 = ("ㄱ", "ㄷ", "ㄱ, ㄴ", "ㄴ, ㄷ", "ㄱ, ㄴ, ㄷ")
SET_3 = ("ㄱ", "ㄱ, ㄴ", "ㄱ, ㄷ", "ㄴ, ㄷ", "ㄱ, ㄴ, ㄷ")
SET_4 = ("ㄱ", "ㄴ", "ㄷ", "ㄱ, ㄴ", "ㄴ, ㄷ")
SET_5 = ("ㄱ", "ㄷ", "ㄱ, ㄴ", "ㄱ, ㄷ", "ㄴ, ㄷ")
PICK = "옳은 것만을 <보기>에서 있는 대로 고른 것은?"

# ---------------------------------------------------------------------------------------------
# 국어 — reading passages (독서)
# ---------------------------------------------------------------------------------------------

READ_SET = "[1~2] 다음 글을 읽고 물음에 답하시오."

HUME = """\
인과 관계는 우리가 세계를 이해하는 가장 기본적인 틀이다. 불 위에 올려 둔 물이 끓는 것을 보면 우리는 불이 물을 끓게 했다고 생각한다. 그런데 18세기 영국의 철학자 흄은 이러한 믿음이 어디에서 오는지를 물었다. 그는 인간의 모든 관념이 감각 경험에서 비롯된다고 보는 경험론의 입장에서, 원인과 결과 사이의 '필연적 연결'이라는 관념이 과연 경험에서 나올 수 있는지를 따졌다.
흄에 따르면 우리가 두 사건을 관찰할 때 실제로 경험하는 것은 세 가지뿐이다. 원인이 결과보다 시간적으로 앞선다는 것, 두 사건이 시간적·공간적으로 인접해 있다는 것, 그리고 같은 종류의 사건이 반복해서 함께 일어난다는 것이다. 당구공 하나가 다른 공에 부딪히고 두 번째 공이 움직이는 장면을 아무리 주의 깊게 살펴도, 첫 번째 공이 두 번째 공을 반드시 움직이게 하는 '힘' 자체는 보이지 않는다. 필연적 연결은 감각에 주어지지 않는다는 것이다.
그렇다면 필연성의 관념은 어디에서 오는가? 흄은 그것이 대상 쪽이 아니라 마음 쪽에 있다고 답했다. 같은 종류의 사건이 반복해서 이어지는 것을 경험하면, 마음은 하나가 나타날 때 다른 하나를 기대하는 습관을 갖게 된다. 이 습관에서 생기는 기대의 느낌을 우리는 대상 사이의 필연적 연결로 착각한다는 것이다. 따라서 과거에 늘 그러했다는 사실로부터 미래에도 반드시 그러할 것이라고 이끌어 내는 추론은 논리적으로 정당화되지 않는다. 내일 해가 뜨지 않는다고 생각해도 아무런 모순이 생기지 않기 때문이다.
흄의 이러한 주장은 자연 과학의 지식이 확실하다는 당시의 믿음에 도전하는 것이었다. 이후 칸트는 흄의 문제 제기를 진지하게 받아들이면서도, 인과성은 경험에서 얻어지는 것이 아니라 경험을 가능하게 하는 인간 지성의 틀이라고 보았다. 칸트에 따르면 우리는 인과성이라는 틀을 통해서만 사건들을 객관적인 시간 순서로 경험할 수 있으므로, 경험 세계 안에서 인과 법칙은 보편적으로 성립한다."""

LEMONS = """\
시장에서 거래되는 상품의 품질을 판매자는 잘 알지만 구매자는 잘 모르는 경우가 있다. 이처럼 거래 당사자들이 가진 정보의 양이 서로 다른 상황을 정보의 비대칭이라 한다. 중고차 시장을 예로 들어 보자. 중고차 중에는 상태가 좋은 차도 있고 겉보기와 달리 결함이 있는 차도 있다. 판매자는 자기 차의 상태를 알지만, 구매자는 겉모습만으로 이를 구별하기 어렵다. 그러면 구매자는 시장에 나온 차들의 평균적인 품질을 기준으로 지불할 가격을 정하게 된다.
이때 문제가 생긴다. 좋은 차를 가진 판매자는 평균 품질에 맞춘 가격이 자기 차의 가치보다 낮다고 여겨 차를 시장에 내놓지 않는다. 좋은 차가 빠져나가면 시장에 남은 차들의 평균 품질은 낮아지고, 구매자가 지불하려는 가격도 다시 낮아진다. 이 과정이 되풀이되면 결국 시장에는 품질이 낮은 차만 남게 된다. 이처럼 정보가 부족한 쪽이 바람직하지 않은 상대방과 거래하게 될 가능성이 커지는 현상을 역선택이라 한다. 역선택은 보험 시장에서도 나타난다. 보험사가 가입자의 건강 상태를 정확히 알 수 없어 평균적인 위험에 맞추어 보험료를 정하면, 건강한 사람은 보험료가 비싸다고 느껴 가입을 꺼리고 위험이 높은 사람 위주로 가입하게 된다.
역선택을 줄이는 방법 가운데 하나는 정보를 가진 쪽이 자신의 유형을 드러내는 것이다. 이를 신호 발송이라 한다. 좋은 차를 가진 판매자는 일정 기간 무상 수리를 보증함으로써 자기 차의 품질이 높다는 신호를 보낼 수 있다. 결함이 있는 차의 판매자가 같은 보증을 하면 수리 비용을 크게 부담해야 하므로 이를 흉내 내기 어렵다. 신호가 효과를 가지려면 이처럼 유형에 따라 신호를 보내는 데 드는 비용이 달라야 한다. 반대로 정보가 부족한 쪽이 상대방의 유형을 가려내기 위해 여러 조건을 제시하는 것을 선별이라 한다. 보험사가 자기 부담금이 높은 대신 보험료가 낮은 상품과 자기 부담금이 낮은 대신 보험료가 높은 상품을 함께 내놓으면, 가입자는 자신의 위험 수준에 맞는 상품을 스스로 고르게 되어 유형이 드러난다.
한편 정보의 비대칭은 거래가 이루어진 뒤에도 문제를 일으킨다. 보험에 가입한 사람이 사고가 나도 보험사가 손실을 보상해 준다는 생각에 주의를 덜 기울이는 경우가 그 예이다. 이처럼 거래 이후 정보를 가진 쪽이 상대방이 관찰하기 어려운 행동을 바꾸어 상대방에게 손해를 끼치는 현상을 도덕적 해이라 한다. 역선택이 거래 이전에 숨겨진 '유형'에서 생기는 문제라면, 도덕적 해이는 거래 이후의 숨겨진 '행동'에서 생기는 문제이다. 보험사가 사고가 났을 때 손실의 일부를 가입자가 부담하게 하는 것은 가입자가 계속 주의를 기울이도록 하여 도덕적 해이를 줄이려는 장치이기도 하다."""

STARS = """\
밤하늘의 별은 밝기가 저마다 다르다. 고대 그리스의 히파르코스는 맨눈에 가장 밝게 보이는 별을 1등급, 가장 어둡게 보이는 별을 6등급으로 나누었다. 이후 천문학자들은 이 체계를 정밀하게 다듬어, 1등급 별이 6등급 별보다 정확히 100배 밝도록 정하였다. 따라서 등급이 1 작아질 때마다 밝기는 약 2.5배 커지며, 등급 값이 작을수록 밝은 별이다. 매우 밝은 천체는 0등급이나 음수 등급을 갖기도 한다.
그런데 지구에서 보이는 밝기만으로는 별이 실제로 얼마나 많은 빛을 내는지 알 수 없다. 별의 밝기는 거리의 제곱에 반비례하여 어두워지기 때문이다. 같은 양의 빛을 내는 별이라도 거리가 2배 멀어지면 밝기는 1/4이 된다. 그래서 지구에서 관측되는 밝기에 따른 등급을 겉보기 등급이라 하고, 모든 별을 10파섹(pc)의 거리에 옮겨 놓았다고 가정할 때의 등급을 절대 등급이라 하여 구별한다. 1pc은 약 3.26광년이다. 절대 등급은 별이 실제로 방출하는 빛의 양, 즉 광도를 비교하는 기준이 되며, 절대 등급이 작을수록 광도가 큰 별이다.
겉보기 등급(m)에서 절대 등급(M)을 뺀 값을 거리 지수라 한다. 별이 10pc보다 멀리 있으면 10pc으로 옮길 때 더 밝아지므로 절대 등급이 겉보기 등급보다 작아져 거리 지수는 양수가 되고, 10pc보다 가까이 있으면 거리 지수는 음수가 된다. 예를 들어 100pc 거리에 있는 별을 10pc으로 옮기면 거리가 1/10이 되어 밝기는 100배가 되므로 등급은 5만큼 작아진다. 즉 이 별의 거리 지수는 5이다. 이처럼 거리 지수는 별까지의 거리에 의해서만 결정되므로, 별의 절대 등급을 다른 방법으로 알아낼 수 있으면 겉보기 등급을 측정하여 별까지의 거리를 구할 수 있다."""

PARITY = """\
디지털 통신에서는 데이터를 0과 1의 비트로 바꾸어 전송하는데, 전송 과정에서 잡음 때문에 일부 비트가 바뀌는 오류가 생길 수 있다. 수신 측이 오류가 생겼는지 알아내는 가장 간단한 방법은 패리티 비트를 이용하는 것이다. 송신 측은 보낼 데이터 비트들 뒤에 패리티 비트 하나를 덧붙인다. 짝수 패리티 방식에서는 덧붙인 비트를 포함한 전체 비트 중 1의 개수가 짝수가 되도록 패리티 비트를 정한다. 예를 들어 데이터가 1011이면 1이 세 개이므로 패리티 비트 1을 붙여 10111을 보낸다. 수신 측은 받은 비트들의 1의 개수를 세어 홀수이면 오류가 발생했다고 판단한다.
그러나 이 방법에는 한계가 있다. 비트 두 개가 동시에 바뀌면 1의 개수의 홀짝이 그대로 유지되므로 오류를 알아차리지 못한다. 또 오류가 있다는 것은 알 수 있어도 어느 비트가 바뀌었는지는 알 수 없어서, 수신 측은 송신 측에 데이터를 다시 보내 달라고 요청해야 한다. 재전송은 시간이 걸리므로, 전송 지연이 큰 환경에서는 통신 효율이 크게 떨어진다.
이러한 한계를 보완하는 방법으로 2차원 패리티 검사가 있다. 이 방법에서는 데이터를 여러 행으로 나누어 표처럼 배열한 뒤, 각 행의 끝과 각 열의 끝에 모두 패리티 비트를 붙인다. 비트 하나가 바뀌면 그 비트가 속한 행과 열의 패리티가 동시에 어긋나므로, 어긋난 행과 열이 만나는 위치를 찾아 오류가 난 비트를 알아낼 수 있다. 이 경우 수신 측은 그 비트를 반대 값으로 바꾸어 재전송 요청 없이 스스로 오류를 정정할 수 있다. 다만 여러 비트가 한꺼번에 바뀌면 어긋난 행과 열이 여러 개 생겨 오류의 위치를 정확히 특정하지 못할 수도 있다."""

PARITY_TABLE = """\
수신 측이 3행 4열로 배열된 데이터 비트와 패리티 비트를 다음과 같이 받았다.

          1열  2열  3열  4열 | 행 패리티
1행        1    0    1    1  |    1
2행        0    1    1    1  |    0
3행        1    1    1    1  |    0
열 패리티  0    0    1    0"""

# ---------------------------------------------------------------------------------------------
# 국어 — literature, speech/writing, grammar
# ---------------------------------------------------------------------------------------------

AZALEA = """\
나 보기가 역겨워
가실 때에는
말없이 고이 보내 드리우리다

영변에 약산
진달래꽃
아름 따다 가실 길에 뿌리우리다

가시는 걸음걸음
놓인 그 꽃을
사뿐히 즈려밟고 가시옵소서

나 보기가 역겨워
가실 때에는
죽어도 아니 눈물 흘리우리다

- 김소월, 「진달래꽃」 -"""

YUN_PAIR = """\
(가)
죽는 날까지 하늘을 우러러
한 점 부끄럼이 없기를,
잎새에 이는 바람에도
나는 괴로워했다.
별을 노래하는 마음으로
모든 죽어 가는 것을 사랑해야지
그리고 나한테 주어진 길을
걸어가야겠다.

오늘 밤에도 별이 바람에 스치운다.

- 윤동주, 「서시」 -

(나)
산모퉁이를 돌아 논가 외딴 우물을 홀로 찾아가선 가만히 들여다봅니다.

우물 속에는 달이 밝고 구름이 흐르고 하늘이 펼치고 파아란 바람이 불고 가을이 있습니다.

그리고 한 사나이가 있습니다.
어쩐지 그 사나이가 미워져 돌아갑니다.

돌아가다 생각하니 그 사나이가 가엾어집니다.
도로 가 들여다보니 사나이는 그대로 있습니다.

다시 그 사나이가 미워져 돌아갑니다.
돌아가다 생각하니 그 사나이가 그리워집니다.

우물 속에는 달이 밝고 구름이 흐르고 하늘이 펼치고 파아란 바람이 불고 가을이 있고 추억처럼 사나이가 있습니다.

- 윤동주, 「자화상」 -"""

SIJO_PAIR = """\
(가)
이런들 어떠하며 저런들 어떠하리
만수산 드렁칡이 얽어진들 어떠하리
우리도 이같이 얽어져 백 년까지 누리리라
- 이방원 -

(나)
이 몸이 죽고 죽어 일백 번 고쳐 죽어
백골이 진토 되어 넋이라도 있고 없고
임 향한 일편단심이야 가실 줄이 있으랴
- 정몽주 -"""

HWANG = """\
동짓달 기나긴 밤을 한 허리를 베어 내어
춘풍 이불 아래 서리서리 넣었다가
어론 님 오신 날 밤이거든 굽이굽이 펴리라
- 황진이 -"""

STRAW_SHOES = """\
장터가 파한 뒤에도 윤 노인은 좀처럼 자리를 뜨지 않았다. 팔다 남은 짚신 여섯 켤레가 멍석 위에 가지런히 놓여 있었다. 나는 아버지의 심부름으로 막걸리 한 되를 받아 오던 길에 그 모습을 보았다. 노인은 해가 기우는 쪽을 한참 바라보다가, 짚신 한 켤레를 집어 들고 먼지를 털었다. 털 먼지도 없는 신이었다.
"얘야, 너 신 한 켤레 신어 볼 테냐."
노인이 나를 불렀을 때 나는 얼른 대답하지 못했다. 내 발에는 읍내에서 산 고무신이 신겨 있었다. 반들반들 윤이 나는 검정 고무신이었다. 노인의 눈이 내 발에 머물렀다가 천천히 멍석 위로 돌아갔다.
"하긴, 요새 누가 이런 걸 신누."
노인은 웃었다. 그런데 그 웃음이 어쩐지 우는 얼굴처럼 보였다고 나는 지금도 생각한다. 그날 밤 나는 아버지에게 윤 노인 이야기를 했다. 아버지는 대꾸 없이 담배만 태우다가, 내일 장에 가거든 짚신 두 켤레만 사 오라며 동전 몇 닢을 내 손에 쥐여 주었다. 우리 집에 짚신을 신을 사람은 아무도 없었다.
이튿날 장터에 윤 노인은 나오지 않았다. 멍석이 깔려 있던 자리에는 누군가 버리고 간 고무신 한 짝이 뒤집힌 채 나뒹굴고 있었다. 나는 동전을 쥔 주먹을 풀지도 못하고 한참을 거기 서 있었다."""

OLD_TALE = """\
[앞부분의 줄거리] 몰락한 양반의 아들 유생은 난리 중에 부모를 잃고 떠돌다가 산속에서 한 노승을 만나 도술을 배운다.

유생이 노승 앞에 꿇어앉아 하직을 고하니, 노승이 이르되,
"네 재주가 이미 이루어졌으나 아직 때가 이르지 아니하였으니, 삼 년을 더 기다려 세상에 나아가라. 만일 때를 기다리지 않으면 반드시 화를 입으리라."
유생이 머리를 조아려 사례하되, 마음속으로는 도적에게 짓밟히는 백성을 생각하여 차마 기다리지 못하더라. 이튿날 새벽에 유생이 몰래 산문을 나서매, 구름 한 조각이 발아래 일어나 순식간에 천 리를 가니라.
이때 도적의 무리가 고을을 에워싸고 불을 놓으니 백성의 울음소리 하늘에 사무치더라. 유생이 공중에서 이를 보고 부채를 들어 한 번 부치니 큰바람이 일어나 불길이 도적의 진으로 돌아가고, 두 번 부치니 모래와 돌이 날려 도적들이 눈을 뜨지 못하는지라. 도적의 괴수가 크게 놀라 말하기를,
"이는 사람의 재주가 아니로다."
하고 달아나니 고을이 비로소 평안하였다.
슬프다. 유생이 스승의 말을 좇았던들 어찌 뒷날의 고초를 겪었으리오. 그러나 백성을 건진 그 마음이야 어찌 탓하리오."""

BEE_SPEECH = """\
안녕하세요. 저는 오늘 '꿀벌이 사라지면 우리 식탁은 어떻게 될까'라는 주제로 발표하겠습니다. 여러분, 오늘 아침에 먹은 사과나 딸기가 꿀벌과 관련이 있다는 사실을 알고 계셨나요? (청중의 반응을 살피며) 모르시는 분이 많군요. 꿀벌은 꽃가루를 옮겨 식물이 열매를 맺도록 돕는데, 이를 수분이라고 합니다. (화면을 가리키며) 이 그래프는 우리나라의 한 지역에서 조사한 꿀벌 군집 수의 변화를 보여 줍니다. 몇 년 사이에 군집 수가 크게 줄어든 것을 볼 수 있습니다. 전문가들은 그 원인으로 기후 변화, 농약 사용, 서식지 감소 등을 꼽습니다. 그렇다면 우리가 할 수 있는 일은 무엇일까요? 학교 화단이나 집 베란다에 꿀벌이 좋아하는 꽃을 심는 것만으로도 꿀벌에게 먹이를 제공할 수 있습니다. 작은 실천이 모이면 꿀벌과 우리의 식탁을 함께 지킬 수 있을 것입니다. 이상으로 발표를 마치겠습니다."""

CUP_DRAFT = """\
[학생의 초고]
우리 학교 매점 옆 분리수거함은 점심시간이 지나면 일회용 컵으로 가득 찬다. 일회용 컵은 여러 재질이 섞여 있거나 음료가 남아 있어 재활용되지 못하고 버려지는 경우가 많다. 재활용되지 못한 컵은 소각되거나 매립되어 환경에 부담을 준다. 텀블러를 사용하면 이러한 쓰레기를 줄일 수 있고, 일부 카페에서는 텀블러를 가져온 손님에게 음료 가격을 할인해 주기도 한다.
[A]"""

KOREAN: list[CsatProblem] = [
    _p(
        "KO01",
        "국어",
        "독서-인문",
        _q(
            READ_SET,
            HUME,
            "1. 윗글의 내용과 일치하지 않는 것은?",
            options=(
                "흄은 인간의 모든 관념이 감각 경험에서 비롯된다고 보았다.",
                "흄은 원인이 결과보다 시간적으로 앞선다는 것은 경험할 수 있다고 보았다.",
                "흄은 반복된 경험에서 생긴 마음의 습관을 필연성 관념의 근원으로 보았다.",
                "흄은 과거의 경험으로부터 미래의 일을 이끌어 내는 추론이 논리적으로 정당하다고 보았다.",
                "칸트는 인과성을 경험을 가능하게 하는 인간 지성의 틀로 보았다.",
            ),
        ),
        "④",
        "3문단: 과거로부터 미래를 이끌어 내는 추론은 논리적으로 정당화되지 않는다고 했다.",
    ),
    _p(
        "KO02",
        "국어",
        "독서-인문",
        _q(
            READ_SET,
            HUME,
            "2. 윗글의 '흄'의 입장에서 <보기>를 평가한 내용으로 가장 적절한 것은?",
            _box(
                "어느 마을 사람들은 수탉이 울고 나면 곧 해가 뜨는 것을 수십 년 동안 보아 왔다. 그래서 그들은 수탉의 울음이 해를 뜨게 한다고 굳게 믿게 되었다."
            ),
            options=(
                "마을 사람들은 수탉의 울음과 해돋이 사이의 필연적 연결을 감각을 통해 직접 관찰하였다.",
                "마을 사람들의 믿음은 반복된 경험에서 생긴 기대의 습관에서 비롯된 것이다.",
                "마을 사람들이 경험한 것은 두 사건의 시간적 선후뿐이며, 두 사건이 반복해서 함께 일어나는 것은 경험하지 못했다.",
                "수탉이 울어도 해가 뜨지 않는 날을 생각하면 논리적 모순이 생기므로 마을 사람들의 믿음은 확실하다.",
                "인과성은 경험을 가능하게 하는 지성의 틀이므로 마을 사람들의 믿음은 경험 세계 안에서 보편적으로 성립한다.",
            ),
        ),
        "②",
        "흄은 반복 경험이 만든 기대의 습관을 필연적 연결로 착각한다고 본다. ①은 필연적 연결이 관찰된다고 해 틀리고, ⑤는 칸트의 입장이다.",
    ),
    _p(
        "KO03",
        "국어",
        "독서-사회",
        _q(
            READ_SET,
            LEMONS,
            "1. 윗글에 대한 이해로 적절하지 않은 것은?",
            options=(
                "역선택이 되풀이되면 시장에 남은 상품의 평균 품질은 점차 높아진다.",
                "정보의 비대칭 상황에서 구매자는 시장에 나온 상품의 평균적인 품질을 기준으로 가격을 정하게 된다.",
                "보험료를 평균적인 위험에 맞추어 정하면 건강한 사람의 보험 가입이 줄어들 수 있다.",
                "신호 발송은 정보를 가진 쪽이 자신의 유형을 드러내는 방법이다.",
                "선별은 정보가 부족한 쪽이 여러 조건을 제시하여 상대방의 유형을 가려내는 방법이다.",
            ),
        ),
        "①",
        "2문단: 좋은 차가 빠져나가면서 남은 차들의 평균 품질은 낮아진다.",
    ),
    _p(
        "KO04",
        "국어",
        "독서-사회",
        _q(
            READ_SET,
            LEMONS,
            "2. 윗글을 바탕으로 <보기>를 이해한 내용으로 가장 적절한 것은?",
            _box(
                "어느 회사가 신입 사원을 채용하려 하는데, 면접만으로는 지원자의 업무 능력을 알기 어렵다. 능력이 뛰어난 지원자는 비교적 적은 노력으로 어려운 자격증을 딸 수 있지만, 능력이 부족한 지원자는 같은 자격증을 따는 데 훨씬 많은 노력이 든다."
            ),
            options=(
                "회사는 정보를 가진 쪽이고, 지원자는 정보가 부족한 쪽이다.",
                "지원자가 자격증을 따서 제출하는 것은 선별에 해당한다.",
                "자격증이 신호로 기능할 수 있는 것은 능력에 따라 자격증을 따는 데 드는 비용이 다르기 때문이다.",
                "능력이 부족한 지원자도 같은 노력으로 자격증을 딸 수 있다면 자격증은 더 효과적인 신호가 된다.",
                "회사가 조건이 서로 다른 근로 계약을 제시하여 지원자가 고르게 하는 것은 신호 발송에 해당한다.",
            ),
        ),
        "③",
        "3문단: 신호가 효과를 가지려면 유형에 따라 신호 비용이 달라야 한다. 자격증 제출은 신호 발송, 계약 조건 제시는 선별이다.",
    ),
    _p(
        "KO05",
        "국어",
        "독서-과학",
        _q(
            READ_SET,
            STARS,
            "1. 윗글의 내용과 일치하지 않는 것은?",
            options=(
                "등급 값이 작을수록 밝은 별이다.",
                "1등급 별은 6등급 별보다 100배 밝다.",
                "절대 등급은 별을 10pc의 거리에 옮겨 놓았다고 가정할 때의 등급이다.",
                "10pc보다 가까이 있는 별은 거리 지수가 양수이다.",
                "같은 양의 빛을 내는 별이라도 거리가 2배 멀어지면 밝기는 1/4이 된다.",
            ),
        ),
        "④",
        "3문단: 10pc보다 가까이 있으면 거리 지수는 음수이다.",
    ),
    _p(
        "KO06",
        "국어",
        "독서-과학",
        _q(
            READ_SET,
            STARS,
            "2. 윗글을 바탕으로 <보기>의 별 A~C에 대해 이해한 내용으로 가장 적절한 것은?",
            _box(
                "별 A: 겉보기 등급 3, 절대 등급 3\n별 B: 겉보기 등급 3, 절대 등급 -2\n별 C: 겉보기 등급 8, 절대 등급 3"
            ),
            options=(
                "A는 B보다 광도가 크다.",
                "지구에서 볼 때 C는 A보다 밝게 보인다.",
                "A는 10pc보다 멀리 있다.",
                "C의 거리 지수는 음수이다.",
                "B와 C는 지구로부터의 거리가 같다.",
            ),
        ),
        "⑤",
        "거리 지수 m-M: A 0(10pc), B 5(100pc), C 5(100pc). B와 C 모두 100pc. 광도는 절대 등급이 작은 B가 A보다 크다.",
    ),
    _p(
        "KO07",
        "국어",
        "독서-기술",
        _q(
            READ_SET,
            PARITY,
            "1. 윗글을 바탕으로 <보기>를 이해한 내용으로 가장 적절한 것은? (단, 짝수 패리티 방식을 사용하였고, 패리티 비트에는 오류가 없다.)",
            _box(PARITY_TABLE),
            options=(
                "2행과 4열의 패리티가 어긋나 있으므로, 2행 4열의 비트를 0으로 바꾸면 오류가 정정된다.",
                "1행의 데이터 비트 중 1의 개수가 홀수이므로 1행에 오류가 있다.",
                "3열의 열 패리티 비트가 1이므로 3열에 오류가 있다.",
                "오류가 생긴 비트의 위치를 알 수 없으므로 재전송을 요청해야 한다.",
                "2행에서 비트 두 개가 동시에 바뀌었으므로 수신 측은 오류를 알아차릴 수 없다.",
            ),
        ),
        "①",
        "행 패리티 포함 1의 개수: 1행 4, 2행 3(홀수), 3행 4. 열: 1열 2, 2열 2, 3열 4, 4열 3(홀수). 2행 4열의 1을 0으로 바꾸면 된다.",
    ),
    _p(
        "KO08",
        "국어",
        "독서-기술",
        _q(
            READ_SET,
            PARITY,
            "2. 윗글에 대한 이해로 가장 적절한 것은?",
            options=(
                "짝수 패리티 방식에서 데이터 1011에는 패리티 비트 0을 덧붙인다.",
                "1차원 패리티 검사로는 비트 두 개가 동시에 바뀐 오류도 검출할 수 있다.",
                "1차원 패리티 검사에서는 오류가 난 비트의 위치를 알아낼 수 있다.",
                "2차원 패리티 검사에서 비트 하나가 바뀌면 그 비트가 속한 행과 열의 패리티가 모두 어긋난다.",
                "2차원 패리티 검사에서는 여러 비트가 한꺼번에 바뀌어도 항상 오류의 위치를 특정할 수 있다.",
            ),
        ),
        "④",
        "3문단 내용. ①은 1을 붙이고, ②③은 2문단에서 불가능하다고 했으며, ⑤는 특정하지 못할 수도 있다고 했다.",
    ),
    _p(
        "KO09",
        "국어",
        "문학-현대시",
        _q(
            "다음 시에 대한 설명으로 적절하지 않은 것은?",
            AZALEA,
            options=(
                "1연과 4연에서 유사한 구절을 반복하는 수미상관의 구성을 취하고 있다.",
                "3음보의 율격을 바탕으로 민요적 리듬을 형성하고 있다.",
                "'죽어도 아니 눈물 흘리우리다'에서 반어적 표현을 통해 이별의 슬픔을 드러내고 있다.",
                "임이 가실 길에 꽃을 뿌리는 행위에는 임에 대한 헌신과 축복의 태도가 담겨 있다.",
                "계절의 변화를 통해 시간의 흐름에 따른 화자의 정서 변화를 드러내고 있다.",
            ),
        ),
        "⑤",
        "계절의 변화는 나타나지 않는다. 수미상관, 3음보, 반어, 헌신의 태도는 모두 적절하다.",
    ),
    _p(
        "KO10",
        "국어",
        "문학-현대시",
        _q(
            "다음 (가)와 (나)의 공통점으로 가장 적절한 것은?",
            YUN_PAIR,
            options=(
                "자연물을 매개로 화자가 자신의 내면을 성찰하고 있다.",
                "대화 형식을 활용하여 주제를 드러내고 있다.",
                "계절의 순환을 통해 삶의 무상함을 드러내고 있다.",
                "명령형 어조로 청자에게 행동을 촉구하고 있다.",
                "과거와 현재의 대비를 통해 고향을 잃은 비애를 드러내고 있다.",
            ),
        ),
        "①",
        "(가)는 하늘·바람·별, (나)는 우물 속 달·구름·하늘에 비친 자신을 통해 자아를 성찰한다.",
    ),
    _p(
        "KO11",
        "국어",
        "문학-고전시가",
        _q(
            "다음 (가), (나)에 대한 설명으로 적절하지 않은 것은?",
            SIJO_PAIR,
            options=(
                "(가)는 설의적 표현을 활용하여 상대에게 회유의 뜻을 전하고 있다.",
                "(가)는 '드렁칡'이 얽힌 모습에 빗대어 함께 어울려 살자는 뜻을 드러내고 있다.",
                "(나)는 죽음을 거듭 가정하여 변함없는 마음을 강조하고 있다.",
                "(나)의 '임'은 화자가 끝까지 충절을 지키려는 대상이다.",
                "(가)와 (나)는 모두 시조의 정형에서 벗어나 자유로운 형식을 취하고 있다.",
            ),
        ),
        "⑤",
        "(가) 하여가, (나) 단심가 모두 3장 6구 4음보의 평시조 정형을 지킨다.",
    ),
    _p(
        "KO12",
        "국어",
        "문학-고전시가",
        _q(
            "다음 시조에 대한 설명으로 가장 적절한 것은?",
            HWANG,
            options=(
                "추상적인 시간을 구체적인 사물처럼 형상화하고 있다.",
                "임과 함께 지내는 현재의 기쁨을 노래하고 있다.",
                "계절의 변화에 따른 자연의 아름다움을 예찬하고 있다.",
                "대상에게 말을 건네는 방식으로 이별을 만류하고 있다.",
                "임금에 대한 충성을 다짐하며 연군의 정을 드러내고 있다.",
            ),
        ),
        "①",
        "동짓달 밤의 '허리를 베어' 이불 아래 넣었다가 펴겠다는 것은 시간의 구체화이다. 임은 부재한다.",
    ),
    _p(
        "KO13",
        "국어",
        "문학-현대소설",
        _q(
            "다음 글의 서술상 특징으로 가장 적절한 것은?",
            STRAW_SHOES,
            options=(
                "작품 밖의 서술자가 모든 인물의 내면을 꿰뚫어 보며 서술하고 있다.",
                "작품 속 인물인 '나'가 관찰한 사건을 회상하며 서술하고 있다.",
                "여러 인물의 시각을 번갈아 제시하여 사건을 입체적으로 보여 주고 있다.",
                "대화를 배제하고 요약적 서술로만 사건을 전개하고 있다.",
                "공간의 잦은 이동을 통해 긴박한 분위기를 조성하고 있다.",
            ),
        ),
        "②",
        "'나'가 윤 노인을 관찰한 일을 '지금도 생각한다'며 회상하는 1인칭 서술이다. 대화도 있다.",
    ),
    _p(
        "KO14",
        "국어",
        "문학-현대소설",
        _q(
            "다음 글에 대한 이해로 적절하지 않은 것은?",
            STRAW_SHOES,
            options=(
                "'고무신'은 윤 노인의 짚신이 더 이상 팔리지 않는 시대의 변화를 드러낸다.",
                "윤 노인이 먼지도 없는 짚신을 터는 행동에서 팔리지 않는 물건에 대한 애착과 쓸쓸함을 짐작할 수 있다.",
                "아버지가 짚신을 사 오라고 한 것은 집안에 짚신이 꼭 필요했기 때문이다.",
                "'나'가 동전을 쥔 주먹을 풀지 못한 것은 윤 노인을 돕지 못한 안타까움과 관련된다.",
                "윤 노인의 웃음이 '우는 얼굴처럼 보였다'는 것은 노인의 체념과 슬픔을 드러낸다.",
            ),
        ),
        "③",
        "'우리 집에 짚신을 신을 사람은 아무도 없었다' — 아버지는 노인을 돕기 위해 사 오라고 했다.",
    ),
    _p(
        "KO15",
        "국어",
        "문학-고전소설",
        _q(
            "다음 글의 서술상 특징으로 적절하지 않은 것은?",
            OLD_TALE,
            options=(
                "비현실적인 사건을 통해 인물의 영웅적 면모를 드러내고 있다.",
                "서술자가 직접 개입하여 인물에 대한 평가를 드러내고 있다.",
                "인물의 말을 통해 앞으로 일어날 일을 암시하고 있다.",
                "인물의 속마음을 드러내어 행동의 동기를 제시하고 있다.",
                "현재와 과거를 교차하여 사건의 인과를 역순으로 밝히고 있다.",
            ),
        ),
        "⑤",
        "사건은 시간 순서대로 전개된다. 구름·부채의 도술(전기성), '슬프다'의 서술자 개입, 노승의 경고(복선), 백성을 생각하는 마음(동기)은 모두 있다.",
    ),
    _p(
        "KO16",
        "국어",
        "화법과 작문",
        _q(
            "다음 발표에 활용된 말하기 방식으로 적절하지 않은 것은?",
            BEE_SPEECH,
            options=(
                "청중에게 질문을 던져 발표 내용에 대한 관심을 유도하고 있다.",
                "자신의 경험을 소개하며 발표 주제를 선정한 동기를 밝히고 있다.",
                "시각 자료를 활용하여 청중의 이해를 돕고 있다.",
                "청중의 반응을 확인하며 발표를 진행하고 있다.",
                "전문가의 견해를 인용하여 문제의 원인을 제시하고 있다.",
            ),
        ),
        "②",
        "발표자의 개인 경험이나 주제 선정 동기는 나오지 않는다.",
    ),
    _p(
        "KO17",
        "국어",
        "화법과 작문",
        _q(
            "다음은 '일회용 컵 사용 줄이기'를 주제로 학생이 쓴 글의 초고이다. <조건>에 따라 [A]에 들어갈 마지막 문단을 작성할 때, 가장 적절한 것은?",
            CUP_DRAFT,
            "<조건>\n○ 비유적 표현을 활용할 것.\n○ 독자에게 구체적인 실천을 촉구할 것.",
            options=(
                "일회용 컵을 줄이는 일은 생각보다 어렵지 않습니다. 오늘부터 함께 시작해 봅시다.",
                "지구는 우리 모두가 함께 타고 있는 배와 같습니다. 그 배는 지금 조금씩 가라앉고 있습니다.",
                "통계에 따르면 우리나라에서 하루에 버려지는 일회용 컵의 수가 매우 많다고 합니다.",
                "지구는 우리 모두가 함께 타고 있는 배입니다. 배에 난 작은 구멍을 막는 마음으로, 내일부터 일회용 컵 대신 텀블러를 가방에 챙겨 다닙시다.",
                "일회용 컵 문제는 개인이 아니라 정부와 기업이 먼저 나서서 해결해야 할 문제입니다.",
            ),
        ),
        "④",
        "④만 비유(지구=배)와 구체적 실천 촉구(텀블러 챙기기)를 모두 갖췄다. ①은 비유가 없고 ②는 촉구가 없다.",
    ),
    _p(
        "KO18",
        "국어",
        "언어와 매체",
        _q(
            "<보기>의 ㄱ~ㅁ 중 음운 변동의 결과 음운의 개수가 줄어든 것만을 고른 것은?",
            _box("ㄱ. 국물[궁물]\nㄴ. 좋고[조코]\nㄷ. 솜이불[솜니불]\nㄹ. 닭[닥]\nㅁ. 신라[실라]"),
            options=("ㄱ, ㄴ", "ㄱ, ㅁ", "ㄴ, ㄹ", "ㄷ, ㄹ", "ㄷ, ㅁ"),
        ),
        "③",
        "ㄴ 거센소리되기(축약, 5→4), ㄹ 자음군 단순화(탈락, 4→3). ㄱ 비음화·ㅁ 유음화는 교체(개수 불변), ㄷ ㄴ 첨가(7→8).",
    ),
    _p(
        "KO19",
        "국어",
        "언어와 매체",
        _q(
            "밑줄 친 단어의 품사가 나머지 넷과 다른 것은? (밑줄 친 부분은 [ ]로 표시함)",
            options=(
                "[새] 옷을 샀다.",
                "[모든] 학생이 모였다.",
                "[예쁜] 꽃이 피었다.",
                "[헌] 책을 버렸다.",
                "[온갖] 꽃이 피었다.",
            ),
        ),
        "③",
        "'예쁜'은 형용사 '예쁘다'의 관형사형이고, 나머지는 활용하지 않는 관형사이다.",
    ),
    _p(
        "KO20",
        "국어",
        "언어와 매체",
        _q(
            "<보기>의 ㄱ~ㄷ에 대한 설명으로 가장 적절한 것은?",
            _box(
                "ㄱ. 할머니께서 방에 계신다.\nㄴ. 나는 선생님께 꽃을 드렸다.\nㄷ. 동생이 할아버지를 모시고 병원에 갔다."
            ),
            options=(
                "ㄱ은 특수 어휘를 사용하여 객체를 높이고 있다.",
                "ㄴ은 조사와 특수 어휘를 사용하여 객체를 높이고 있다.",
                "ㄷ은 선어말 어미 '-시-'를 사용하여 주체를 높이고 있다.",
                "ㄱ과 ㄷ은 모두 주체 높임이 실현되어 있다.",
                "ㄴ과 ㄷ은 모두 상대 높임의 하십시오체가 쓰였다.",
            ),
        ),
        "②",
        "ㄴ은 조사 '께'와 '드리다'로 객체(선생님)를 높인다. ㄱ은 주체 높임, ㄷ은 '모시다'로 객체만 높이며 해라체이다.",
    ),
    _p(
        "KO21",
        "국어",
        "언어와 매체",
        _q(
            "<보기>의 ㄱ~ㅁ에 대한 설명으로 적절하지 않은 것은?",
            _box(
                'ㄱ. 나는 그가 돌아왔음을 알았다.\nㄴ. 이 책은 내용이 어렵다.\nㄷ. 친구가 "내일 보자."라고 말했다.\nㄹ. 나는 비가 오는 소리를 들었다.\nㅁ. 그는 발에 땀이 나도록 뛰었다.'
            ),
            options=(
                "ㄱ에는 목적어 역할을 하는 명사절이 안겨 있다.",
                "ㄴ에는 서술어 역할을 하는 절이 안겨 있다.",
                "ㄷ에는 간접 인용의 방식으로 인용절이 안겨 있다.",
                "ㄹ에는 관형어 역할을 하는 절이 안겨 있다.",
                "ㅁ에는 부사어 역할을 하는 절이 안겨 있다.",
            ),
        ),
        "③",
        "ㄷ은 큰따옴표와 '라고'를 쓴 직접 인용이다.",
    ),
]

# ---------------------------------------------------------------------------------------------
# 영어
# ---------------------------------------------------------------------------------------------

ENGLISH: list[CsatProblem] = [
    _p(
        "EN01",
        "영어",
        "글의 목적",
        _q(
            "다음 글의 목적으로 가장 적절한 것은?",
            """\
Dear Residents,

I am writing on behalf of the Greenwood Apartments management office. As many of you have noticed, the elevator in Building C has been making unusual noises for the past few weeks. After a full inspection, the repair company informed us that several of its main parts need to be replaced. The work will take place from Monday, March 9 to Wednesday, March 11, and the elevator will not be available during this period. We understand that this may cause inconvenience, especially for elderly residents and families with small children. If you need help carrying heavy items during the repair, please call the management office at 555-0147, and our staff will be glad to assist you. Thank you for your patience and cooperation.

Sincerely,
Daniel Moore
Building Manager""",
            options=(
                "엘리베이터 소음의 원인을 문의하려고",
                "엘리베이터 수리 업체의 선정 결과를 발표하려고",
                "노약자를 위한 엘리베이터 추가 설치를 요청하려고",
                "관리 사무소 직원의 채용 계획을 공지하려고",
                "엘리베이터 수리 일정과 운행 중단을 안내하려고",
            ),
        ),
        "⑤",
        "수리 기간(3/9~3/11) 동안 엘리베이터를 쓸 수 없음을 알리는 공지이다.",
    ),
    _p(
        "EN02",
        "영어",
        "심경",
        _q(
            "다음 글에 드러난 Emma의 심경 변화로 가장 적절한 것은?",
            """\
Emma sat in the back row of the concert hall, her hands pressed tightly together. The judges had been talking in low voices for what felt like hours. She kept replaying the moment in the second movement when her finger had slipped. "That mistake must have ruined everything," she thought, and her stomach tightened. Finally, the head judge stepped onto the stage and opened a white envelope. "This year's first prize goes to... Emma Lawson!" For a second, she could not move. Then her friends were hugging her and shouting her name. As she walked toward the stage, tears of joy ran down her cheeks, and she could not stop smiling.""",
            options=(
                "anxious → delighted",
                "bored → excited",
                "calm → nervous",
                "hopeful → disappointed",
                "proud → ashamed",
            ),
        ),
        "①",
        "실수 때문에 초조해하다가(stomach tightened) 1등 발표에 기쁨의 눈물을 흘린다.",
    ),
    _p(
        "EN03",
        "영어",
        "주장",
        _q(
            "다음 글에서 필자가 주장하는 바로 가장 적절한 것은?",
            """\
During adolescence, the body's internal clock shifts, so teenagers naturally tend to fall asleep and wake up later than children or adults. This is not a matter of laziness but of biology. Yet many high schools begin classes early in the morning, forcing students to get up while their bodies still need sleep. As a result, many teenagers arrive at school tired, find it hard to concentrate, and are more likely to feel stressed. Some schools that moved their start times later have reported that students were absent less often and paid more attention in class. Schools should therefore adjust their schedules to the sleep patterns of teenagers by starting the school day later.""",
            options=(
                "청소년은 규칙적인 운동으로 수면의 질을 높여야 한다.",
                "청소년은 잠들기 전에 전자 기기 사용을 줄여야 한다.",
                "학교는 청소년의 수면 특성에 맞게 등교 시간을 늦춰야 한다.",
                "학교는 수업 시간을 줄이고 자율 학습 시간을 늘려야 한다.",
                "부모는 자녀의 수면 습관에 관심을 기울여야 한다.",
            ),
        ),
        "③",
        "마지막 문장: Schools should ... start the school day later.",
    ),
    _p(
        "EN04",
        "영어",
        "요지",
        _q(
            "다음 글의 요지로 가장 적절한 것은?",
            """\
Many students believe that they understand a topic once they have read their notes several times. However, rereading often creates only a feeling of familiarity, not real understanding. A much more effective way to check and deepen your knowledge is to explain the material to someone else. When you try to teach a concept, you have to organize the ideas in a logical order, choose clear examples, and answer unexpected questions. In this process, the gaps in your own understanding quickly become visible. You may realize that you cannot explain why a certain step is necessary, which shows you exactly what to study again. Even if no one is available to listen, explaining the material aloud to an imaginary student can bring similar benefits. In short, teaching is not only a way of sharing knowledge but also one of the best ways of learning it.""",
            options=(
                "같은 내용을 반복해서 읽는 것이 가장 효과적인 복습 방법이다.",
                "공부는 혼자 할 때보다 여러 사람과 함께할 때 효율적이다.",
                "교사는 학생들의 예상치 못한 질문에 대비해야 한다.",
                "다른 사람에게 설명하는 것은 자신의 이해를 점검하고 심화하는 좋은 방법이다.",
                "학습 내용을 논리적으로 정리하려면 예시를 줄여야 한다.",
            ),
        ),
        "④",
        "설명(가르치기)이 이해의 빈틈을 드러내 학습을 깊게 한다는 내용이다.",
    ),
    _p(
        "EN05",
        "영어",
        "주제",
        _q(
            "다음 글의 주제로 가장 적절한 것은?",
            """\
Cities are often several degrees warmer than the surrounding countryside, a phenomenon known as the urban heat island effect. Concrete and asphalt absorb sunlight during the day and release the stored heat slowly at night, keeping temperatures high. Trees offer a simple but powerful way to reduce this problem. Their leaves block sunlight before it reaches the ground, so shaded surfaces can be much cooler than surfaces in direct sun. In addition, trees release water vapor through their leaves, a process that cools the surrounding air in much the same way that sweating cools our skin. For these reasons, many cities have started planting trees along streets and in parking lots, not just for beauty but as a practical tool for keeping neighborhoods cooler in summer.""",
            options=(
                "the role of trees in lowering temperatures in cities",
                "the main causes of air pollution in urban areas",
                "the importance of protecting forests in the countryside",
                "difficulties of planting trees in parking lots",
                "the effects of sweating on body temperature",
            ),
        ),
        "①",
        "도시 열섬을 나무가 그늘과 증산으로 완화한다는 내용이다.",
    ),
    _p(
        "EN06",
        "영어",
        "제목",
        _q(
            "다음 글의 제목으로 가장 적절한 것은?",
            """\
We usually think of boredom as something to escape as quickly as possible. At the first sign of it, we reach for our phones. Yet researchers have found that boredom may have a hidden benefit. In one study, participants who first completed a dull task, such as copying numbers from a list, later came up with more creative uses for everyday objects than those who had not been bored. When the mind is not occupied by outside stimulation, it begins to wander, and this wandering allows it to connect ideas that normally remain separate. In other words, boredom pushes us to search for something new inside our own heads. So the next time you feel bored, instead of immediately filling the empty moment, you might let your mind drift for a while. You may be surprised by the ideas that appear.""",
            options=(
                "How to Spend Less Time on Your Phone",
                "Why Dull Tasks Lower Our Productivity",
                "The Hidden Dangers of a Wandering Mind",
                "Creative People Never Feel Bored",
                "Boredom: An Unexpected Door to Creativity",
            ),
        ),
        "⑤",
        "지루함이 마음을 방황하게 해 창의성을 높인다는 내용이다.",
    ),
    _p(
        "EN07",
        "영어",
        "내용 일치",
        _q(
            "axolotl에 관한 다음 글의 내용과 일치하지 않는 것은?",
            """\
The axolotl is a type of salamander that is native to the lake system of Xochimilco, near Mexico City. Unlike most salamanders, axolotls usually do not go through metamorphosis. Even as adults, they keep the feathery external gills they had as young animals and spend their whole lives in water. Axolotls are famous for their remarkable ability to regenerate lost body parts. They can regrow not only limbs and tails but also parts of their heart and brain. In the wild, axolotls are usually dark brown or black with spots, although pale pink ones are popular as pets. Because of water pollution and the loss of their habitat, wild axolotls are now critically endangered.""",
            options=(
                "멕시코시티 근처의 호수 지역이 원산지이다.",
                "대부분의 도롱뇽과 달리 대개 변태를 거치지 않는다.",
                "성체가 되면 외부 아가미를 잃고 육지로 올라온다.",
                "다리와 꼬리뿐 아니라 심장과 뇌의 일부도 재생할 수 있다.",
                "야생 개체는 수질 오염과 서식지 감소로 심각한 멸종 위기에 처해 있다.",
            ),
        ),
        "③",
        "성체도 외부 아가미를 유지하고 평생 물속에서 산다.",
    ),
    _p(
        "EN08",
        "영어",
        "어법",
        _q(
            "다음 글의 밑줄 친 부분 중, 어법상 틀린 것은? (밑줄 친 부분은 [ ]로 표시함)",
            """\
Honeybees communicate the location of food through a special movement ①[known] as the waggle dance. When a worker bee returns to the hive after finding flowers, she moves in a figure-eight pattern, ②[shaking] her body during the straight part of the dance. The direction of this straight run shows the direction of the food source relative to the sun, and the length of the run indicates ③[how] far away the food is. Other bees gather around the dancer and ④[follows] her movements closely. By doing so, they learn exactly ⑤[where] to fly to find the flowers.""",
        ),
        "④",
        "주어 Other bees(복수)의 동사로 gather와 병렬이므로 follow가 되어야 한다.",
    ),
    _p(
        "EN09",
        "영어",
        "어휘",
        _q(
            "다음 글의 밑줄 친 부분 중, 문맥상 낱말의 쓰임이 적절하지 않은 것은? (밑줄 친 부분은 [ ]로 표시함)",
            """\
When people make decisions in groups, they often feel pressure to agree with the majority. This tendency can be ①[useful] when the group needs to act quickly, but it can also lead to poor choices. Members who have doubts may keep silent because they do not want to ②[protect] the harmony of the group. As a result, the group may ③[overlook] important information that only a few members possess. To prevent this, some organizations ask one member to play the role of a "devil's advocate," whose job is to ④[challenge] the group's plan as strongly as possible. This practice ⑤[encourages] open discussion and helps the group examine its decisions more carefully.""",
        ),
        "②",
        "의심을 말하면 조화를 '깨뜨릴까(disturb)' 봐 침묵하는 것이므로 protect는 부적절하다.",
    ),
    _p(
        "EN10",
        "영어",
        "빈칸 추론",
        _q(
            "다음 빈칸에 들어갈 말로 가장 적절한 것은?",
            """\
Many animals that live in the desert are active mainly at night. During the day, the sand can become hot enough to burn their feet, and the strong sun can quickly dry out their bodies. By staying in underground burrows while the sun is high and coming out only after dark, these animals avoid the most dangerous conditions of their environment. Some desert plants show a similar strategy: they open their pores to take in carbon dioxide only at night, when the air is cooler and less water escapes. In both cases, survival in the desert depends less on fighting the heat than on ____________.""",
            options=(
                "growing larger bodies",
                "finding other species to cooperate with",
                "storing food for long periods",
                "moving to cooler regions",
                "choosing the right time to be active",
            ),
        ),
        "⑤",
        "동물은 밤에 활동하고 식물은 밤에만 기공을 연다 — 활동 시간의 선택이 핵심이다.",
    ),
    _p(
        "EN11",
        "영어",
        "빈칸 추론",
        _q(
            "다음 빈칸에 들어갈 말로 가장 적절한 것은?",
            """\
The value of a map lies not in how much it shows but in what it leaves out. A map that included every tree, every stone, and every house would be as large and as complicated as the land itself, and therefore useless. A subway map, for example, ignores the actual distances between stations and the curves of the tracks; it shows only the order of the stations and where the lines connect. Yet this simplified picture is exactly what a passenger needs. The same is true of scientific models. A model of the climate or of the economy cannot include every detail of the real world, and it should not try to. Its usefulness comes from ____________, so that the important patterns become visible.""",
            options=(
                "collecting as much data as possible",
                "reflecting the real world in every detail",
                "deliberately leaving out what is unimportant",
                "being approved by many experts",
                "using the latest computer technology",
            ),
        ),
        "③",
        "지도와 모델의 가치는 무엇을 생략하느냐에 있다는 글이다.",
    ),
    _p(
        "EN12",
        "영어",
        "무관한 문장",
        _q(
            "다음 글에서 전체 흐름과 관계 없는 문장은?",
            """\
Handwriting notes in class may help students learn better than typing them on a laptop. ① Because people usually write more slowly than they type, students who take notes by hand cannot write down every word the teacher says. ② Instead, they must listen carefully, decide what is important, and put the ideas into their own words. ③ This process of summarizing requires deeper thinking, which helps the information stay in memory longer. ④ Laptops have also become lighter and cheaper over the past decade, so more students can afford them. ⑤ Students who type, in contrast, tend to copy lectures word for word without really processing the meaning.""",
        ),
        "④",
        "손 필기와 학습 효과에 관한 글에 노트북 가격 이야기는 무관하다.",
    ),
    _p(
        "EN13",
        "영어",
        "순서 배열",
        _q(
            "주어진 글 다음에 이어질 글의 순서로 가장 적절한 것은?",
            """\
When you drop a spoonful of sugar into a cup of hot tea, it seems to disappear within seconds.

(A) In cold water, by contrast, the molecules move more slowly and strike the crystals less often. As a result, the same amount of sugar dissolves much more slowly, and some of it may even remain at the bottom of the glass.

(B) This happens because the water molecules in hot tea move quickly and strike the surface of the sugar crystals often and with great energy, pulling sugar molecules away one after another.

(C) This is why people who enjoy sweet iced tea often dissolve the sugar in a little hot water first and then add ice.""",
            options=(
                "(A) - (C) - (B)",
                "(B) - (A) - (C)",
                "(B) - (C) - (A)",
                "(C) - (A) - (B)",
                "(C) - (B) - (A)",
            ),
        ),
        "②",
        "(B)가 주어진 현상의 원인을 설명하고, (A)가 by contrast로 찬물과 대비하며, (C)가 그 결과 생긴 습관을 말한다.",
    ),
    _p(
        "EN14",
        "영어",
        "문장 삽입",
        _q(
            "글의 흐름으로 보아, 주어진 문장이 들어가기에 가장 적절한 곳은?",
            "Without this effect, Earth's average surface temperature would be about -18°C, far too cold for most living things.",
            """\
Earth's atmosphere acts like a blanket around the planet. ( ① ) Sunlight passes through the air and warms the ground. ( ② ) The warm ground then gives off heat, and gases in the atmosphere, such as water vapor and carbon dioxide, absorb much of this heat and send part of it back toward the surface. ( ③ ) This natural process, called the greenhouse effect, is what keeps our planet warm enough for life. ( ④ ) Problems arise, however, when human activities add large amounts of these gases to the atmosphere. ( ⑤ ) As a result, more heat is trapped than before, and global temperatures rise.""",
        ),
        "④",
        "'this effect'는 greenhouse effect를 가리키므로 그 명칭이 처음 나온 문장 뒤(④)에 와야 한다.",
    ),
    _p(
        "EN15",
        "영어",
        "요약문 완성",
        _q(
            "다음 글의 내용을 한 문장으로 요약하고자 한다. 빈칸 (A), (B)에 들어갈 말로 가장 적절한 것은?",
            """\
In an experiment, researchers asked participants to taste several glasses of juice and rate how much they liked each one. Before each tasting, participants were told the price of the juice. What they did not know was that two of the glasses contained exactly the same juice; one was described as costing ten dollars a bottle, while the other was described as costing two dollars. Participants consistently rated the "expensive" juice as more delicious. Brain scans taken during the experiment showed that an area of the brain linked to pleasure was more active when participants drank the juice they believed was expensive, even though the drinks were identical.

→ The experiment shows that people's ____(A)____ of a product can be influenced by information about its ____(B)____, even when the product itself is the same.""",
            options=(
                "(A) enjoyment …… (B) price",
                "(A) enjoyment …… (B) color",
                "(A) memory …… (B) ingredients",
                "(A) purchase …… (B) price",
                "(A) memory …… (B) origin",
            ),
        ),
        "①",
        "같은 주스라도 비싸다고 들으면 더 맛있게(쾌감) 느꼈다 — enjoyment / price.",
    ),
]

# ---------------------------------------------------------------------------------------------
# 한국사
# ---------------------------------------------------------------------------------------------

HISTORY: list[CsatProblem] = [
    _p(
        "HI01",
        "한국사",
        "고려",
        _q(
            "다음 자료의 정책을 추진한 왕의 재위 기간에 있었던 사실로 옳은 것은?",
            "왕은 노비를 조사하여 본래 양인이었던 사람을 풀어 주게 하였다. 또 후주에서 귀화한 쌍기의 건의를 받아들여 처음으로 과거를 실시하였다.",
            options=(
                "전시과 제도를 처음 마련하였다.",
                "전국에 12목을 설치하고 지방관을 파견하였다.",
                "관리의 등급에 따라 공복을 제정하였다.",
                "후대 왕들에게 훈요 10조를 남겼다.",
                "별무반을 편성하여 여진을 정벌하였다.",
            ),
        ),
        "③",
        "노비안검법·과거제 → 광종. 광종은 공복을 제정했다. 전시과는 경종, 12목은 성종, 훈요 10조는 태조, 별무반은 숙종~예종.",
    ),
    _p(
        "HI02",
        "한국사",
        "조선",
        _q(
            "다음 자료의 왕이 재위하던 시기에 있었던 사실로 옳은 것은?",
            "왕은 백성이 쉽게 익혀 날마다 편하게 쓸 수 있도록 스물여덟 글자를 새로 만들었다.",
            options=(
                "경국대전을 완성하여 반포하였다.",
                "우리 풍토에 맞는 농법을 정리한 농사직설을 편찬하였다.",
                "경기도에서 처음으로 대동법을 실시하였다.",
                "성균관 앞에 탕평비를 세웠다.",
                "수원 화성을 축조하였다.",
            ),
        ),
        "②",
        "훈민정음 창제 → 세종. 농사직설(1429). 경국대전은 성종, 대동법은 광해군, 탕평비는 영조, 화성은 정조.",
    ),
    _p(
        "HI03",
        "한국사",
        "근대",
        _q(
            "다음 자료의 인물이 추진한 정책으로 옳은 것은?",
            "이 인물은 왕실의 권위를 높이기 위해 경복궁 중건을 추진하면서 원납전을 거두고 당백전을 발행하였다.",
            options=(
                "전국의 서원을 정리하여 47개소만 남겼다.",
                "토지 소유자에게 지계를 발급하였다.",
                "군국기무처를 설치하여 개혁을 추진하였다.",
                "통리기무아문을 설치하였다.",
                "균역법을 시행하였다.",
            ),
        ),
        "①",
        "경복궁 중건·당백전 → 흥선 대원군. 서원 철폐(47개소). 지계는 광무개혁, 군국기무처는 1차 갑오개혁, 통리기무아문은 1880년, 균역법은 영조.",
    ),
    _p(
        "HI04",
        "한국사",
        "일제 강점기",
        _q(
            "다음 자료의 민족 운동에 대한 설명으로 옳은 것은?",
            "1919년 민족 대표의 이름으로 독립 선언서가 발표되었고, 탑골 공원에 모인 학생과 시민들이 만세 시위를 벌였다. 시위는 곧 전국 각지와 국외로 퍼져 나갔다.",
            options=(
                "순종의 장례일을 계기로 일어났다.",
                "광주에서 한·일 학생 간의 충돌을 계기로 일어났다.",
                "국채 보상 운동과 함께 전개되었다.",
                "대한민국 임시 정부가 수립되는 계기가 되었다.",
                "신간회의 지원을 받아 전국으로 확산되었다.",
            ),
        ),
        "④",
        "3·1 운동 → 대한민국 임시 정부 수립(1919). ①은 6·10 만세 운동, ②⑤는 광주 학생 항일 운동, ③은 1907년.",
    ),
    _p(
        "HI05",
        "한국사",
        "현대",
        _q(
            "다음 자료의 사건에 대한 설명으로 옳은 것은?",
            "1960년 3·15 부정 선거에 항의하는 시위가 전국으로 확산되었고, 대학교수단의 시국 선언이 이어지는 가운데 결국 대통령이 하야하였다.",
            options=(
                "유신 체제가 붕괴하는 계기가 되었다.",
                "대통령 직선제 개헌을 이끌어 냈다.",
                "장면 내각이 성립하는 계기가 되었다.",
                "신군부의 비상계엄 확대에 반대하여 일어났다.",
                "한·일 국교 정상화 추진에 반대하여 일어났다.",
            ),
        ),
        "③",
        "4·19 혁명 → 내각 책임제 개헌, 장면 내각 출범. ①은 부마 항쟁·10·26, ②는 6월 민주 항쟁, ④는 5·18, ⑤는 6·3 시위.",
    ),
    _p(
        "HI06",
        "한국사",
        "고대",
        _q(
            "다음 자료의 나라에 대한 설명으로 옳은 것은?",
            "고구려 출신 대조영이 고구려 유민과 말갈인을 이끌고 동모산에서 건국하였다. 전성기에는 중국으로부터 '해동성국'이라 불렸다.",
            options=(
                "정사암 회의에서 재상을 선출하였다.",
                "3성 6부의 중앙 관제를 운영하였다.",
                "골품제를 바탕으로 신분을 구분하였다.",
                "지방의 22담로에 왕족을 파견하였다.",
                "화백 회의에서 국가 중대사를 결정하였다.",
            ),
        ),
        "②",
        "발해는 3성 6부(정당성 중심)를 운영했다. 정사암·22담로는 백제, 골품제·화백 회의는 신라.",
    ),
    _p(
        "HI07",
        "한국사",
        "조선",
        _q(
            "다음 자료의 (가) 제도에 대한 설명으로 옳은 것은?",
            "(가) 은/는 집집마다 토산물을 거두던 공납을 토지 결수에 따라 쌀·베·동전 등으로 내게 한 제도로, 이를 관리하기 위해 선혜청이 설치되었다.",
            options=(
                "1년에 납부하는 군포를 2필에서 1필로 줄였다.",
                "전세를 풍흉에 관계없이 토지 1결당 쌀 4~6두로 고정하였다.",
                "토지의 비옥도와 해마다의 풍흉에 따라 전세를 차등 징수하였다.",
                "양반에게도 군포를 징수하는 호포제를 실시하였다.",
                "광해군 때 경기도에서 처음 실시되었다.",
            ),
        ),
        "⑤",
        "(가)는 대동법. 1608년 광해군 때 경기도에서 시작. ①균역법 ②영정법 ③세종의 공법 ④흥선 대원군의 호포제.",
    ),
]

# ---------------------------------------------------------------------------------------------
# 사회탐구
# ---------------------------------------------------------------------------------------------

SOCIAL: list[CsatProblem] = [
    _p(
        "LE01",
        "생활과 윤리",
        "사상가 비교",
        _q(
            "다음 갑, 을 사상가의 입장에 대한 설명으로 옳은 것은?",
            "갑: 살인을 저지른 자는 반드시 죽어야 한다. 형벌은 범죄자가 범죄를 저질렀다는 이유만으로 부과되어야 하며, 다른 목적을 위한 수단이 되어서는 안 된다.\n을: 사형은 인간이 사회 계약을 통해 양도한 적이 없는 생명을 빼앗는 것이다. 범죄를 예방하는 효과 면에서도 사형보다 평생 노역형이 더 효과적이다.",
            options=(
                "갑은 형벌의 목적이 사회 전체의 행복 증진에 있다고 본다.",
                "을은 형벌을 정할 때 범죄 예방 효과를 고려해야 한다고 본다.",
                "갑은 살인죄에 대해 사형 이외의 형벌을 부과하는 것이 정의롭다고 본다.",
                "을은 형벌이 오직 응보의 원리에만 근거해야 한다고 본다.",
                "갑, 을은 모두 사형 제도를 폐지해야 한다고 본다.",
            ),
        ),
        "②",
        "갑은 칸트(응보주의, 사형 존치), 을은 베카리아(사형 폐지, 예방 효과 중시).",
    ),
    _p(
        "LE02",
        "생활과 윤리",
        "사상가 비교",
        _q(
            "다음 사상가의 입장으로 가장 적절한 것은?",
            "쾌락과 고통을 느낄 수 있는 존재의 이익은 그 존재가 어떤 종에 속하든 똑같이 고려되어야 한다. 종이 다르다는 이유만으로 동물의 고통을 무시하는 것은 인종 차별과 다를 바 없는 종 차별주의이다.",
            options=(
                "동물은 삶의 주체로서 내재적 가치를 지니므로 도덕적 권리를 갖는다.",
                "동물에 대한 의무는 인간에 대한 간접적 의무일 뿐이다.",
                "생명 공동체 전체의 온전성과 안정성을 보전하는 것이 옳다.",
                "모든 생명체는 목적론적 삶의 중심으로서 동등한 고유의 가치를 지닌다.",
                "고통을 느낄 수 있는 존재의 이익은 종과 관계없이 평등하게 고려되어야 한다.",
            ),
        ),
        "⑤",
        "싱어의 이익 평등 고려 원칙. ①레건 ②칸트 ③레오폴드 ④테일러.",
    ),
    _p(
        "ET01",
        "윤리와 사상",
        "사상가 비교",
        _q(
            "다음 갑, 을 사상가의 입장에 대한 설명으로 옳은 것은?",
            "갑: 자기의 사사로운 욕심을 이기고 예(禮)로 돌아가는 것이 인(仁)이다. 예가 아니면 보지도, 듣지도, 말하지도, 움직이지도 말아야 한다.\n을: 큰 도(道)가 무너지자 인의(仁義)가 생겨났다. 성인은 억지로 일을 꾸미지 않는 무위(無爲)로 다스려 사람들이 소박하고 욕심 없는 삶으로 돌아가게 한다.",
            options=(
                "갑은 인위적인 규범을 버리고 자연의 순리를 따라야 한다고 본다.",
                "을은 예(禮)에 따른 사회 질서의 확립을 강조한다.",
                "갑은 자기를 이기고 예로 돌아가는 수양을 통해 인(仁)을 실천해야 한다고 본다.",
                "을은 작은 나라에 적은 백성이 사는 공동체를 부정적으로 본다.",
                "갑, 을은 모두 인의(仁義)를 도덕의 근본으로 본다.",
            ),
        ),
        "③",
        "갑은 공자(극기복례), 을은 노자(무위자연, 소국과민 지향).",
    ),
    _p(
        "ET02",
        "윤리와 사상",
        "사상가 비교",
        _q(
            "다음 갑, 을 사상가의 입장에 대한 설명으로 옳은 것은?",
            "갑: 사회적·경제적 불평등은 그것이 사회에서 가장 불리한 처지에 있는 사람들에게 최대의 이익이 되도록, 그리고 공정한 기회 균등의 조건 아래 모든 사람에게 개방된 직위와 결부되도록 편성되어야 한다.\n을: 정당한 절차에 따라 취득하거나 이전받은 소유물에 대해 개인은 소유 권리를 가진다. 재분배를 위해 노동 소득에 세금을 부과하는 것은 강제 노동과 다름없다.",
            options=(
                "갑은 최소 수혜자에게 최대 이익이 되는 사회적·경제적 불평등을 허용한다.",
                "을은 국가가 복지를 위해 재분배 정책을 적극적으로 시행해야 한다고 본다.",
                "을은 최소 국가보다 기능이 확대된 국가가 정당하다고 본다.",
                "갑은 개인의 소유권은 어떠한 경우에도 제한될 수 없다고 본다.",
                "갑, 을은 모두 결과의 평등을 분배의 최우선 원칙으로 삼는다.",
            ),
        ),
        "①",
        "갑은 롤스(차등의 원칙), 을은 노직(소유 권리론, 최소 국가).",
    ),
    _p(
        "KG01",
        "한국지리",
        "자료 분석",
        _q(
            "표는 우리나라 세 지역의 기후 자료이다. (가)~(다)에 해당하는 지역을 바르게 짝지은 것은? (단, 세 지역은 강릉, 대관령, 서귀포 중 하나이며, 수치는 평년값을 반올림한 것이다.)",
            "지역 | 1월 평균 기온(℃) | 연평균 기온(℃) | 연 강수량(mm)\n(가) | 7 | 17 | 1,990\n(나) | -7 | 7 | 1,900\n(다) | 1 | 13 | 1,460",
            options=(
                "(가) 강릉, (나) 대관령, (다) 서귀포",
                "(가) 강릉, (나) 서귀포, (다) 대관령",
                "(가) 서귀포, (나) 대관령, (다) 강릉",
                "(가) 서귀포, (나) 강릉, (다) 대관령",
                "(가) 대관령, (나) 강릉, (다) 서귀포",
            ),
        ),
        "③",
        "가장 따뜻하고 비가 많은 (가)는 서귀포, 해발 고도가 높아 가장 추운 (나)는 대관령, (다)는 강릉.",
    ),
    _p(
        "KG02",
        "한국지리",
        "개념",
        _q(
            "다음 글의 (가), (나) 지형에 대한 설명으로 옳은 것은?",
            "(가) 석회암이 빗물이나 지하수에 녹아 형성된 깔때기 모양의 움푹 파인 땅으로, 배수가 잘 되어 주로 밭으로 이용된다.\n(나) 뜨거운 용암이 급격히 식으면서 수축하여 형성된 다각형 기둥 모양의 절리로, 제주도 해안 등에서 볼 수 있다.",
            options=(
                "(가)는 주로 제주도와 철원 일대의 현무암 지대에 분포한다.",
                "(나)는 석회암이 빗물에 용식되어 형성된다.",
                "(나)는 빙하의 침식 작용으로 형성된다.",
                "(가)는 주로 고생대 조선 누층군의 석회암 지대에 발달한다.",
                "(가), (나)는 모두 화산 활동으로 형성된 지형이다.",
            ),
        ),
        "④",
        "(가)는 돌리네(강원 남부·충북 북동부의 조선 누층군 석회암 지대), (나)는 주상 절리(용암의 냉각·수축).",
    ),
    _p(
        "WG01",
        "세계지리",
        "개념",
        _q(
            "다음 기후 특징이 나타나는 지역에서 볼 수 있는 모습으로 가장 적절한 것은?",
            "여름에는 아열대 고압대의 영향으로 고온 건조하고, 겨울에는 편서풍과 전선의 영향으로 온난 습윤하다.",
            options=(
                "올리브, 포도, 코르크참나무 등을 재배하는 수목 농업이 발달하였다.",
                "연중 비가 많아 이동식 화전 농업이 이루어진다.",
                "영구 동토층이 녹지 않도록 고상 가옥을 짓는다.",
                "이끼와 풀을 찾아 순록을 유목한다.",
                "오아시스 주변에서 대추야자를 재배한다.",
            ),
        ),
        "①",
        "여름 건조·겨울 습윤은 지중해성 기후로, 건조한 여름을 견디는 수목 농업이 발달한다.",
    ),
    _p(
        "WG02",
        "세계지리",
        "개념",
        _q(
            "다음 글의 (가) 종교에 대한 설명으로 옳은 것은?",
            "(가) 의 신자들은 하루 다섯 번 성지 메카를 향해 예배를 드리고, 라마단 기간에는 해가 떠 있는 동안 음식을 먹지 않는다. 경전은 쿠란이다.",
            options=(
                "소를 신성시하여 쇠고기를 먹지 않는다.",
                "카스트 제도와 밀접한 관련이 있다.",
                "성탄절을 가장 중요한 축일 중 하나로 기념한다.",
                "갠지스강에서 몸을 씻는 종교 의식을 행한다.",
                "돼지고기와 술을 먹거나 마시는 것을 금기로 여긴다.",
            ),
        ),
        "⑤",
        "(가)는 이슬람교. ①②④는 힌두교, ③은 크리스트교.",
    ),
    _p(
        "EA01",
        "동아시아사",
        "자료 분석",
        _q(
            "다음 자료의 조약에 대한 설명으로 옳은 것은?",
            "청이 영국과 맺은 이 조약에 따라 홍콩섬이 영국에 할양되었고, 광저우·상하이 등 5개 항구가 개항되었으며, 공행의 무역 독점이 폐지되었다.",
            options=(
                "제1차 아편 전쟁의 결과로 체결되었다.",
                "청일 전쟁의 결과로 체결되었다.",
                "미국 페리 함대의 개항 요구로 체결되었다.",
                "운요호 사건을 계기로 체결되었다.",
                "의화단 운동이 진압된 뒤 체결되었다.",
            ),
        ),
        "①",
        "난징 조약(1842). ②시모노세키 조약 ③미일 화친 조약 ④강화도 조약 ⑤신축 조약.",
    ),
    _p(
        "EA02",
        "동아시아사",
        "자료 분석",
        _q(
            "다음 자료의 전쟁에 대한 설명으로 옳은 것은?",
            "도요토미 히데요시가 대군을 보내 조선을 침략하면서 시작된 이 전쟁에는 명도 군대를 보내 참전하였으며, 7년 만에 일본군이 물러나면서 끝났다.",
            options=(
                "몽골의 침입으로 시작되었다.",
                "전쟁의 결과 청이 조선에 군신 관계를 강요하였다.",
                "전쟁이 끝난 뒤 일본에서 가마쿠라 막부가 수립되었다.",
                "전쟁 이후 명이 쇠퇴하고 여진이 성장하는 계기가 되었다.",
                "백강 전투에서 왜와 백제 부흥군이 승리하였다.",
            ),
        ),
        "④",
        "임진전쟁 후 명은 쇠퇴하고 누르하치의 여진이 성장(후금). ②는 병자호란, ③ 전후 수립된 것은 에도 막부, ⑤ 백강 전투는 패배.",
    ),
    _p(
        "WH01",
        "세계사",
        "자료 분석",
        _q(
            "다음 자료의 혁명에 대한 설명으로 옳은 것은?",
            "국민 의회는 '인간과 시민의 권리 선언'을 발표하여 모든 인간은 자유롭고 평등한 권리를 가지고 태어나며, 모든 주권은 본질적으로 국민에게 있다고 선언하였다.",
            options=(
                "권리 장전을 승인하여 입헌 군주제의 토대를 마련하였다.",
                "바스티유 감옥 습격을 계기로 전국으로 확산되었다.",
                "보스턴 차 사건이 발단이 되었다.",
                "레닌이 이끄는 볼셰비키가 임시 정부를 무너뜨렸다.",
                "크롬웰이 국왕을 처형하고 공화정을 수립하였다.",
            ),
        ),
        "②",
        "프랑스 혁명. ①명예혁명 ③미국 혁명 ④러시아 10월 혁명 ⑤청교도 혁명.",
    ),
    _p(
        "WH02",
        "세계사",
        "자료 분석",
        _q(
            "다음 자료의 인물에 대한 설명으로 옳은 것은?",
            "이 인물은 비텐베르크에서 95개조 반박문을 발표하여 교황청의 면벌부 판매를 비판하였고, 인간은 오직 믿음을 통해 구원받는다고 주장하였다.",
            options=(
                "예정설을 주장하며 제네바에서 종교 개혁을 이끌었다.",
                "수장법을 발표하여 영국 국교회를 세웠다.",
                "예수회를 창설하여 가톨릭 선교에 힘썼다.",
                "트리엔트 공의회를 소집하여 가톨릭 교리를 재확인하였다.",
                "신약 성경을 독일어로 번역하였다.",
            ),
        ),
        "⑤",
        "루터. ①칼뱅 ②헨리 8세 ③로욜라 ④교황(바오로 3세).",
    ),
    _p(
        "EC01",
        "경제",
        "계산",
        _q(
            "X재 시장의 수요 함수와 공급 함수가 다음과 같다. 이에 대한 분석으로 옳은 것은? (단, P는 가격, Q는 수량이다.)",
            "수요 함수: Qd = 100 - 2P\n공급 함수: Qs = 20 + 2P",
            options=(
                "균형 가격은 25이다.",
                "정부가 가격 상한을 15로 정하면 시장 거래량은 70이 된다.",
                "정부가 가격 상한을 15로 정하면 20만큼의 초과 수요가 발생한다.",
                "정부가 가격 상한을 15로 정하면 초과 공급이 발생한다.",
                "정부가 가격 상한을 25로 정하면 시장 거래량은 50이 된다.",
            ),
        ),
        "③",
        "균형 P=20, Q=60. 상한 15: Qd=70, Qs=50 → 초과 수요 20, 거래량 50. 상한 25는 구속력 없음(거래량 60).",
    ),
    _p(
        "EC02",
        "경제",
        "계산",
        _q(
            "표는 갑국의 연도별 명목 GDP와 GDP 디플레이터를 나타낸다. 이에 대한 설명으로 옳은 것은? (단, 기준 연도는 2023년이고, 물가 수준은 GDP 디플레이터로 측정한다.)",
            "구분 | 2023년 | 2024년 | 2025년\n명목 GDP(억 달러) | 200 | 231 | 242\nGDP 디플레이터 | 100 | 105 | 110",
            options=(
                "2024년의 실질 GDP는 220억 달러이다.",
                "2025년의 경제 성장률은 양(+)의 값이다.",
                "2024년의 물가 수준은 전년 대비 10% 상승하였다.",
                "2025년의 실질 GDP는 2024년보다 작다.",
                "2023년의 명목 GDP는 실질 GDP보다 크다.",
            ),
        ),
        "①",
        "실질 GDP = 명목/디플레이터×100: 200, 220, 220. 2025년 성장률 0%, 2024년 물가 5% 상승, 기준 연도는 명목=실질.",
    ),
    _p(
        "EC03",
        "경제",
        "개념",
        _q(
            "원/달러 환율이 1달러당 1,200원에서 1,300원으로 변동하였다. 이러한 변동이 우리나라 경제에 미치는 영향으로 옳은 것은? (단, 다른 조건은 일정하다.)",
            options=(
                "원화 가치가 상승하였다.",
                "미국산 수입품의 원화 표시 가격이 하락한다.",
                "미국을 여행하는 한국인의 원화 표시 경비 부담이 줄어든다.",
                "한국 수출품의 달러 표시 가격이 상승한다.",
                "달러 표시 외채를 가진 국내 기업의 원화 환산 상환 부담이 커진다.",
            ),
        ),
        "⑤",
        "환율 상승 = 원화 가치 하락: 수입품·해외여행 원화 비용 증가, 수출품 달러 가격 하락, 달러 부채 부담 증가.",
    ),
    _p(
        "PL01",
        "정치와 법",
        "사례 적용",
        _q(
            "다음 사례에 대한 법적 판단으로 옳은 것은? (단, 제시된 내용 외의 다른 조건은 고려하지 않는다.)",
            "17세인 갑은 법정 대리인의 동의 없이 전자 제품 판매점을 운영하는 을로부터 노트북을 150만 원에 구입하는 계약을 체결하였다. 갑은 이 계약에 쓸 돈에 대해 법정 대리인으로부터 처분을 허락받은 적이 없다.",
            options=(
                "갑은 법정 대리인의 동의 없이 단독으로 계약을 취소할 수 없다.",
                "을은 갑의 법정 대리인에게 계약의 추인 여부에 대한 확답을 촉구할 수 있다.",
                "을이 계약 당시 갑이 미성년자임을 알았더라도 을은 계약을 철회할 수 있다.",
                "갑이 속임수를 써서 을이 자신을 성년자로 믿게 하였더라도 갑은 계약을 취소할 수 있다.",
                "계약이 취소되면 계약은 취소한 때부터 장래를 향해서만 효력을 잃는다.",
            ),
        ),
        "②",
        "민법 15조 2항(법정 대리인에게 확답 촉구). ①미성년자 본인도 취소 가능(140조) ③악의의 상대방은 철회 불가(16조) ④속임수 시 취소 불가(17조) ⑤처음부터 무효(141조).",
    ),
    _p(
        "PL02",
        "정치와 법",
        "개념",
        _q(
            "우리나라 헌법 재판소의 권한에 해당하지 않는 것은?",
            options=(
                "탄핵 심판",
                "정당 해산 심판",
                "권한 쟁의 심판",
                "명령·규칙의 위헌·위법 여부가 재판의 전제가 된 경우 이에 대한 최종 심사",
                "헌법 소원 심판",
            ),
        ),
        "④",
        "헌법 107조 2항: 재판의 전제가 된 명령·규칙의 위헌·위법 최종 심사는 대법원 권한이다.",
    ),
    _p(
        "SC01",
        "사회·문화",
        "사례 적용",
        _q(
            "다음 연구에 대한 설명으로 옳은 것은?",
            "연구자 갑은 '독서 시간이 어휘력 향상에 영향을 미칠 것이다.'라는 가설을 세웠다. 갑은 ○○고등학교 1학년 학생 200명을 무작위로 두 집단으로 나누어, A 집단에는 8주 동안 매일 30분씩 독서 시간을 제공하고 B 집단에는 제공하지 않았다. 8주 전과 후에 두 집단의 어휘력 검사 점수를 측정하여 비교하였다.",
            options=(
                "독립 변수는 어휘력 검사 점수이다.",
                "질적 연구 방법을 활용하였다.",
                "실험법을 활용하여 변수 간의 인과 관계를 파악하고자 하였다.",
                "B 집단에는 독립 변수에 해당하는 처치가 가해졌다.",
                "참여 관찰을 통해 연구 대상의 주관적 의미를 해석하고자 하였다.",
            ),
        ),
        "③",
        "실험 집단(A)과 통제 집단(B)을 둔 실험법(양적 연구). 독립 변수는 독서 시간, 종속 변수는 어휘력 점수.",
    ),
    _p(
        "SC02",
        "사회·문화",
        "사례 적용",
        _q(
            "다음 사례에 나타난 갑의 문화 이해 태도에 대한 설명으로 옳은 것은?",
            "해외여행 중 현지 사람들이 손으로 음식을 먹는 모습을 본 갑은 '비위생적이고 미개한 풍습'이라며, 숟가락과 젓가락을 쓰는 자기 나라의 식사 방식이 훨씬 우수하다고 말했다.",
            options=(
                "다른 문화를 그 사회의 맥락에서 이해하려는 태도이다.",
                "자기 문화를 기준으로 다른 문화를 평가하는 태도이다.",
                "다른 문화를 동경하여 자기 문화를 낮게 평가하는 태도이다.",
                "보편 윤리에 어긋나는 문화까지 인정하는 태도이다.",
                "문화 간의 우열을 인정하지 않는 태도이다.",
            ),
        ),
        "②",
        "자문화 중심주의. ①⑤는 문화 상대주의, ③은 문화 사대주의, ④는 극단적 문화 상대주의.",
    ),
    _p(
        "SC03",
        "사회·문화",
        "자료 분석",
        _q(
            "표는 갑국의 계층별 인구 비율을 나타낸다. 이에 대한 설명으로 옳은 것은?",
            "(단위: %)\n연도 | 상층 | 중층 | 하층\n2000년 | 10 | 30 | 60\n2020년 | 15 | 60 | 25",
            options=(
                "2000년의 계층 구조는 다이아몬드형이다.",
                "2000년 대비 2020년에 하층의 비율은 증가하였다.",
                "2020년에는 상층의 비율이 하층의 비율보다 높다.",
                "2020년에는 중층의 비율이 가장 높다.",
                "2000년 대비 2020년에 계층 구조가 피라미드형으로 변하였다.",
            ),
        ),
        "④",
        "2000년은 하층이 가장 많은 피라미드형, 2020년은 중층이 60%로 가장 많은 다이아몬드형.",
    ),
]

# ---------------------------------------------------------------------------------------------
# 과학탐구
# ---------------------------------------------------------------------------------------------

SCIENCE: list[CsatProblem] = [
    _p(
        "PH01",
        "물리학Ⅰ",
        "계산",
        _q(
            "정지해 있던 물체가 직선 경로를 따라 일정한 가속도로 운동하여 4초 동안 32 m를 이동하였다. 이 물체의 가속도의 크기와 출발 후 4초일 때의 속력으로 옳은 것은?",
            options=(
                "가속도 2 m/s², 속력 8 m/s",
                "가속도 4 m/s², 속력 16 m/s",
                "가속도 4 m/s², 속력 32 m/s",
                "가속도 8 m/s², 속력 16 m/s",
                "가속도 8 m/s², 속력 32 m/s",
            ),
        ),
        "②",
        "s = at²/2 → 32 = 8a, a = 4 m/s². v = at = 16 m/s.",
    ),
    _p(
        "PH02",
        "물리학Ⅰ",
        "계산",
        _q(
            f"마찰이 없는 수평면에서 질량 2 kg인 물체 A가 6 m/s의 속력으로 운동하다가 정지해 있던 질량 1 kg인 물체 B와 충돌한 후, A와 B가 한 덩어리가 되어 운동하였다. 이에 대한 설명으로 {PICK}",
            _box(
                "ㄱ. 충돌 후 한 덩어리의 속력은 4 m/s이다.\nㄴ. 충돌하는 동안 A가 B에 작용한 충격량의 크기는 4 N·s이다.\nㄷ. 충돌 전후 A와 B의 운동 에너지의 합은 보존된다."
            ),
            options=SET_1,
        ),
        "③",
        "운동량 보존: 12 = 3v, v = 4 m/s. B의 운동량 변화 1×4 = 4 N·s. 운동 에너지 36 J → 24 J로 감소.",
    ),
    _p(
        "PH03",
        "물리학Ⅰ",
        "계산",
        _q(
            f"저항값이 3 Ω과 6 Ω인 두 저항을 병렬로 연결하고, 여기에 저항값이 4 Ω인 저항을 직렬로 연결한 뒤, 전체 회로에 전압이 12 V인 전원 장치를 연결하였다. 이에 대한 설명으로 {PICK} (단, 전원 장치와 도선의 저항은 무시한다.)",
            _box(
                "ㄱ. 회로의 합성 저항은 6 Ω이다.\nㄴ. 6 Ω인 저항 양단에 걸리는 전압은 4 V이다.\nㄷ. 4 Ω인 저항에서 소비되는 전력은 16 W이다."
            ),
            options=SET_1,
        ),
        "⑤",
        "3∥6 = 2 Ω, 합성 6 Ω, 전류 2 A. 병렬부 전압 2×2 = 4 V, 4 Ω 전력 2²×4 = 16 W. 모두 옳다.",
    ),
    _p(
        "PH04",
        "물리학Ⅰ",
        "계산",
        _q(
            f"어떤 파동이 x축과 나란하게 진행하고 있다. 이 파동의 진동수는 5 Hz이고, 이웃한 마루와 마루 사이의 거리는 2 m이다. 이에 대한 설명으로 {PICK}",
            _box("ㄱ. 파장은 2 m이다.\nㄴ. 파동의 진행 속력은 10 m/s이다.\nㄷ. 주기는 5 s이다."),
            options=SET_4,
        ),
        "④",
        "파장 2 m, v = fλ = 10 m/s, 주기 1/5 = 0.2 s.",
    ),
    _p(
        "CH01",
        "화학Ⅰ",
        "계산",
        _q(
            f"물(H₂O) 36 g에 대한 설명으로 {PICK} (단, H, O의 원자량은 각각 1, 16이고, 아보가드로수는 6.0×10²³이다.)",
            _box(
                "ㄱ. 물 분자의 양은 2 mol이다.\nㄴ. 수소 원자의 수는 1.2×10²⁴이다.\nㄷ. 산소 원자의 질량은 16 g이다."
            ),
            options=SET_1,
        ),
        "①",
        "36/18 = 2 mol. H 원자 4 mol = 2.4×10²⁴개, O 원자 2 mol = 32 g. ㄱ만 옳다.",
    ),
    _p(
        "CH02",
        "화학Ⅰ",
        "계산",
        _q(
            "다음은 프로페인(C₃H₈)이 완전 연소하는 반응의 화학 반응식이다.",
            "C₃H₈ + aO₂ → bCO₂ + cH₂O (a~c는 반응 계수)",
            f"이에 대한 설명으로 {PICK} (단, H, C, O의 원자량은 각각 1, 12, 16이다.)",
            _box(
                "ㄱ. a + b + c = 12이다.\nㄴ. C₃H₈ 1 mol이 완전 연소하면 H₂O 4 mol이 생성된다.\nㄷ. C₃H₈ 44 g이 완전 연소하면 CO₂ 88 g이 생성된다."
            ),
            options=SET_3,
        ),
        "②",
        "C₃H₈ + 5O₂ → 3CO₂ + 4H₂O, a+b+c = 12. 44 g = 1 mol → CO₂ 3 mol = 132 g.",
    ),
    _p(
        "CH03",
        "화학Ⅰ",
        "개념",
        _q(
            "다음은 금속 아연(Zn)을 황산 구리(Ⅱ)(CuSO₄) 수용액에 넣었을 때 일어나는 반응의 이온 반응식이다.",
            "Zn(s) + Cu²⁺(aq) → Zn²⁺(aq) + Cu(s)",
            f"이에 대한 설명으로 {PICK}",
            _box(
                "ㄱ. Zn은 산화된다.\nㄴ. Cu²⁺은 환원제로 작용한다.\nㄷ. Zn 1 mol이 반응할 때 이동하는 전자는 2 mol이다."
            ),
            options=SET_5,
        ),
        "④",
        "Zn은 전자 2개를 잃고 산화, Cu²⁺은 환원되므로 산화제이다.",
    ),
    _p(
        "CH04",
        "화학Ⅰ",
        "계산",
        _q(
            f"25 ℃에서 0.1 M 염산(HCl(aq)) 100 mL에 0.1 M 수산화 나트륨(NaOH) 수용액 50 mL를 넣어 혼합 용액을 만들었다. 이에 대한 설명으로 {PICK} (단, 혼합 용액의 부피는 혼합 전 두 용액의 부피의 합과 같다.)",
            _box(
                "ㄱ. 혼합 용액은 산성이다.\nㄴ. 중화 반응으로 생성된 물의 양은 0.005 mol이다.\nㄷ. 혼합 용액에서 Cl⁻의 수는 Na⁺의 수의 2배이다."
            ),
            options=SET_1,
        ),
        "⑤",
        "H⁺ 0.01 mol, OH⁻ 0.005 mol → 물 0.005 mol, H⁺ 0.005 mol 남아 산성. Cl⁻ 0.01 : Na⁺ 0.005 = 2 : 1.",
    ),
    _p(
        "BI01",
        "생명과학Ⅰ",
        "개념",
        _q(
            f"사람의 세포 분열에 대한 설명으로 {PICK} (단, 돌연변이는 고려하지 않는다.)",
            _box(
                "ㄱ. 체세포 분열로 생성된 딸세포의 염색체 수는 모세포와 같다.\nㄴ. 감수 1분열에서 상동 염색체가 분리된다.\nㄷ. 정자의 핵상은 2n이다."
            ),
            options=SET_1,
        ),
        "③",
        "정자의 핵상은 n이다.",
    ),
    _p(
        "BI02",
        "생명과학Ⅰ",
        "계산",
        _q(
            "사람의 유전 형질 (가)는 상염색체에 있는 대립유전자 A와 a에 의해 결정되며, A는 a에 대해 완전 우성이다. (가)의 유전자형이 모두 Aa인 부모 사이에서 (가)의 표현형이 우성인 아이가 태어났을 때, 이 아이의 (가)의 유전자형이 Aa일 확률은? (단, 돌연변이는 고려하지 않는다.)",
            options=("1/4", "1/3", "1/2", "2/3", "3/4"),
        ),
        "④",
        "AA : Aa : aa = 1 : 2 : 1 중 우성 표현형(AA, Aa)에서 Aa의 비율은 2/3.",
    ),
    _p(
        "BI03",
        "생명과학Ⅰ",
        "개념",
        _q(
            f"사람의 혈당량 조절에 대한 설명으로 {PICK}",
            _box(
                "ㄱ. 인슐린은 이자섬의 β세포에서 분비된다.\nㄴ. 글루카곤은 간에서 글리코젠이 포도당으로 분해되는 과정을 촉진한다.\nㄷ. 인슐린은 혈액에서 조직 세포로의 포도당 흡수를 촉진한다."
            ),
            options=SET_1,
        ),
        "⑤",
        "세 진술 모두 옳다.",
    ),
    _p(
        "BI04",
        "생명과학Ⅰ",
        "개념",
        _q(
            f"어떤 사람에게 항원 X를 처음 주사하고 일정 시간이 지난 후 같은 항원 X를 다시 주사하였다. 이에 대한 설명으로 {PICK}",
            _box(
                "ㄱ. 항원 X를 두 번째 주사했을 때 X에 대한 기억 세포가 형질 세포로 빠르게 분화한다.\nㄴ. X에 대한 항체는 세포독성 T림프구에서 생성된다.\nㄷ. X에 대한 항체 생성 속도는 1차 면역 반응이 2차 면역 반응보다 빠르다."
            ),
            options=SET_1,
        ),
        "①",
        "항체는 형질 세포가 만들고, 2차 면역 반응이 더 빠르다. ㄱ만 옳다.",
    ),
    _p(
        "ES01",
        "지구과학Ⅰ",
        "계산",
        _q(
            "어느 화성암에 포함된 방사성 원소 X는 붕괴하여 자원소 Y가 된다. 현재 이 암석에 포함된 Y의 양은 X의 양의 7배이다. X의 반감기가 1억 년일 때, 이 암석의 절대 연령은? (단, 암석이 생성될 때 Y는 없었고, Y는 모두 X가 붕괴하여 생성되었으며, 생성 후 X와 Y의 유출입은 없었다.)",
            options=("1억 년", "2억 년", "2.5억 년", "3억 년", "7억 년"),
        ),
        "④",
        "X : Y = 1 : 7 → X는 처음의 1/8 = (1/2)³ → 반감기 3번 = 3억 년.",
    ),
    _p(
        "ES02",
        "지구과학Ⅰ",
        "개념",
        _q(
            f"해령에 대한 설명으로 {PICK}",
            _box(
                "ㄱ. 해령은 두 판이 서로 멀어지는 발산형 경계에 발달한다.\nㄴ. 해령에서 멀어질수록 해양 지각의 나이가 많아진다.\nㄷ. 해령 부근에서는 천발 지진뿐만 아니라 심발 지진도 활발하게 일어난다."
            ),
            options=SET_3,
        ),
        "②",
        "해령에서는 천발 지진만 일어난다. 심발 지진은 섭입대에서 일어난다.",
    ),
    _p(
        "ES03",
        "지구과학Ⅰ",
        "개념",
        _q(
            f"북반구에서 발생하는 태풍에 대한 설명으로 {PICK}",
            _box(
                "ㄱ. 수증기가 응결할 때 방출하는 숨은열(잠열)이 주요 에너지원이다.\nㄴ. 태풍 진행 방향의 오른쪽 반원은 위험 반원이다.\nㄷ. 태풍의 눈에서는 강한 상승 기류가 나타난다."
            ),
            options=SET_1,
        ),
        "③",
        "태풍의 눈에서는 약한 하강 기류가 나타나 날씨가 맑다.",
    ),
    _p(
        "ES04",
        "지구과학Ⅰ",
        "계산",
        _q(
            f"표면 온도가 6000 K인 별 A와 12000 K인 별 B에 대한 설명으로 {PICK} (단, 두 별은 흑체로 가정한다.)",
            _box(
                "ㄱ. 최대 에너지를 방출하는 파장은 A가 B의 2배이다.\nㄴ. 두 별의 반지름이 같다면 광도는 B가 A의 16배이다.\nㄷ. B는 A보다 파란색을 띤다."
            ),
            options=SET_1,
        ),
        "⑤",
        "빈의 법칙 λmax ∝ 1/T → 2배. L ∝ R²T⁴ → 2⁴ = 16배. 표면 온도가 높을수록 파랗다. 모두 옳다.",
    ),
]

PROBLEMS: list[CsatProblem] = [*KOREAN, *ENGLISH, *HISTORY, *SOCIAL, *SCIENCE]


def option_lines(text: str) -> list[str]:
    """Trailing option lines ("① ...") of a problem, in order; empty for inline-marker items."""
    lines = text.rstrip().splitlines()
    tail: list[str] = []
    for line in reversed(lines):
        if line[:1] in MARKS:
            tail.append(line)
        else:
            break
    return tail[::-1]


def validate_problems(problems: Iterable[CsatProblem]) -> None:
    """Raises ValueError describing every problem with the set (ids, labels, answers, options)."""
    problems = list(problems)
    errors: list[str] = []
    dup = [pid for pid, n in Counter(p.id for p in problems).items() if n > 1]
    if dup:
        errors.append(f"duplicate ids: {dup}")
    for p in problems:
        if p.subject not in SUBJECT_AREA:
            errors.append(f"{p.id}: unknown subject {p.subject!r}")
        elif p.subtype not in SUBTYPES[p.subject]:
            errors.append(f"{p.id}: unknown subtype {p.subtype!r} for {p.subject}")
        if p.answer not in MARKS:
            errors.append(f"{p.id}: answer {p.answer!r} is not one of {''.join(MARKS)}")
            continue
        if not p.rationale.strip():
            errors.append(f"{p.id}: empty rationale")
        opts = option_lines(p.text)
        if p.subtype in INLINE_OPTION_SUBTYPES:
            pos = [p.text.find(m) for m in MARKS]
            if any(i < 0 for i in pos) or pos != sorted(pos) or any(p.text.count(m) != 1 for m in MARKS):
                errors.append(f"{p.id}: inline option markers missing, repeated or out of order")
        elif [o[:1] for o in opts] != list(MARKS) or any(not o[1:].strip() for o in opts):
            errors.append(f"{p.id}: expected five option lines ①~⑤ at the end, got {len(opts)}")
    if errors:
        raise ValueError("invalid CSAT eval set:\n" + "\n".join(errors))
