"""Korean CSAT (수능) subjects other than math: guides for evidence-style lessons.

Each unit is a CSAT subject area or question type. The lesson for these units does not
transform equations; it finds evidence in the passage / data, judges every option and
only then gives the answer (prompts.evidence_system). Japanese and English text reuses
the same ids with the equivalent exam skills (共通テスト / SAT·AP style wording).
"""

from __future__ import annotations

from studymate.solve.curriculum_types import Unit, UnitText

_CHECK = (
    "정답 선택지의 근거 문장을 지문(자료)에서 다시 찾고, 가장 헷갈리는 오답이 틀린 이유를 한 번 더 확인한다."
)


def _u(
    uid: str,
    subject: str,
    grade: str,
    name: str,
    examples: str,
    concept: str,
    method: tuple[str, ...],
    pitfalls: str = "",
    check: str = _CHECK,
) -> Unit:
    return Unit(uid, grade, name, examples, concept, method, "", pitfalls, check, subject)


UNITS: tuple[Unit, ...] = (
    # --- 국어 ---------------------------------------------------------------------------
    _u(
        "kor_reading", "korean", "수능 국어", "독서(비문학)",
        "인문·사회·과학·기술 지문을 읽고 내용 일치, 추론, <보기> 적용, 문맥상 의미를 묻는 문제",
        "답은 반드시 지문에 근거한다. 문단별 핵심 내용과 개념 사이의 관계(원인-결과, 비교, 조건)를 정리하면 선택지를 판단할 수 있다.",
        (
            "발문에서 묻는 것(일치/불일치, 추론, 적용)을 확인한다",
            "문단별 핵심어와 개념의 관계를 짧게 정리한다",
            "선택지마다 관련 문단을 찾아 근거와 대조한다 (반대로 서술·범위 확대·인과 뒤바뀜 확인)",
            "<보기> 적용 문제는 지문의 원리를 <보기> 사례에 그대로 대입한다",
        ),
        "지문에 없는 배경지식으로 판단하는 것, '항상/모든/유일한'처럼 범위를 넓힌 선택지를 놓치는 것.",
    ),
    _u(
        "kor_literature_poem", "korean", "수능 국어", "문학(현대시·고전시가)",
        "시의 화자·태도·정서, 표현상 특징(비유·반복·대조·시어), <보기>를 바탕으로 한 감상",
        "시는 화자의 상황과 정서, 그것을 드러내는 표현 방법을 함께 본다. <보기>가 있으면 <보기>의 관점이 해석의 기준이다.",
        (
            "화자와 상황, 정서(태도)를 먼저 파악한다",
            "선택지가 말하는 표현 방법이 실제 시구에 있는지 해당 구절을 찾아 확인한다",
            "<보기> 문제는 <보기>의 해석 관점에 맞는지, 시구와 연결이 맞는지 둘 다 확인한다",
        ),
        "시에 없는 표현 방법(예: 설의법, 색채 대비)을 있다고 고르는 것, 정서를 과장해서 해석하는 것.",
    ),
    _u(
        "kor_literature_prose", "korean", "수능 국어", "문학(소설·수필·극)",
        "현대·고전 소설의 서술상 특징, 인물의 심리와 관계, 사건 전개, 소재의 기능, <보기> 감상",
        "서술자(시점)와 인물 관계, 사건의 흐름을 정리하면 서술상 특징과 소재의 기능을 판단할 수 있다.",
        (
            "서술자의 위치(1인칭/3인칭, 전지적/관찰자)를 확인한다",
            "인물 관계와 갈등, 사건 순서를 짧게 정리한다",
            "선택지의 내용이 해당 장면에 실제로 나오는지 근거 문장을 찾아 대조한다",
        ),
        "장면에 없는 사건을 추측으로 채우는 것, 서술 방식(요약적 제시·장면 전환 등)을 잘못 판단하는 것.",
    ),
    _u(
        "kor_speech_writing", "korean", "수능 국어", "화법과 작문",
        "발표·토론·협상의 말하기 방식, 글쓰기 계획과 자료 활용, 고쳐쓰기",
        "말하기는 청중을 고려한 전략(질문, 자료 제시, 요약)을, 작문은 계획-자료-초고의 일치를 본다.",
        (
            "대화·발표문에서 선택지가 말하는 전략이 쓰인 부분을 찾는다",
            "작문은 작성 계획이나 조건(<조건>)이 초고에 모두 반영되었는지 하나씩 확인한다",
        ),
        "조건 중 하나만 만족하는 선택지를 고르는 것.",
    ),
    _u(
        "kor_language", "korean", "수능 국어", "언어와 매체(문법·매체)",
        "음운 변동(교체·탈락·첨가·축약), 품사와 문장 성분, 높임·시제·피동, 중세 국어, 매체 자료의 특징",
        "문법 문제는 개념 정의를 정확히 적용한다. 예: 음운 변동은 발음 과정을 단계별로 쓰고 음운 개수 변화를 센다.",
        (
            "문제에 쓰인 문법 개념의 정의를 떠올린다",
            "선택지의 예시 단어·문장에 정의를 한 단계씩 적용한다 (예: 표준 발음 → 변동 종류)",
            "매체 문제는 매체의 특성(쌍방향성, 복합 양식 등)이 자료에 실제로 나타나는지 확인한다",
        ),
        "비슷한 변동(비음화·유음화, 된소리되기)을 헷갈리는 것, 음운 개수를 잘못 세는 것.",
        "정답 예시에 개념을 다시 적용해 결과가 맞는지, 다른 선택지 예시가 왜 조건에 맞지 않는지 확인한다.",
    ),
    # --- 영어 ---------------------------------------------------------------------------
    _u(
        "eng_purpose_mood", "english", "수능 영어", "목적·심경·분위기",
        "글의 목적 고르기, 필자·인물의 심경 변화, 글의 분위기",
        "목적은 글쓴이가 결국 요청하거나 알리려는 문장에, 심경 변화는 앞뒤 상황의 전환점에 드러난다.",
        (
            "요청·안내 표현(I would like to ask, Please 등)이나 전환 신호(But, However)를 찾는다",
            "처음과 끝의 감정을 나타내는 단어를 찾아 비교한다",
        ),
        "글의 앞부분 배경 설명을 목적으로 착각하는 것.",
    ),
    _u(
        "eng_main_idea", "english", "수능 영어", "주제·제목·요지·주장",
        "글의 주제, 제목, 요지, 필자의 주장 고르기",
        "주제는 글 전체를 포괄해야 하며, 주제문은 보통 도입부 뒤 전환(However, In fact)이나 결론부에 있다.",
        (
            "반복되는 핵심 어구와 주제문(일반적 진술)을 찾는다",
            "예시·세부 내용과 주제를 구별한다",
            "선택지가 너무 넓거나 좁지 않은지, 글의 방향(긍정/부정)과 맞는지 판단한다",
        ),
        "예시 하나만 다루는 좁은 선택지, 글에 없는 단어로 넓게 일반화한 선택지.",
    ),
    _u(
        "eng_blank", "english", "수능 영어", "빈칸 추론",
        "빈칸에 들어갈 단어·어구·문장 고르기",
        "빈칸은 글의 주제나 핵심 논지와 연결된다. 빈칸 문장의 앞뒤 논리(재진술, 대조, 인과)를 따라 들어갈 내용을 먼저 예측한다.",
        (
            "빈칸 문장이 주제문인지 세부 문장인지 확인한다",
            "빈칸과 같은 내용을 다시 말하는 문장(재진술)이나 반대되는 문장을 찾는다",
            "예측한 내용과 가장 가까운 선택지를 고르고, 논리 방향이 반대인 선택지를 지운다",
        ),
        "지문에 나온 단어가 들어 있다는 이유만으로 고르는 것, 논리 방향을 뒤집어 고르는 것.",
    ),
    _u(
        "eng_order", "english", "수능 영어", "글의 순서·무관한 문장",
        "주어진 글 다음에 이어질 (A)(B)(C)의 순서, 흐름과 관계없는 문장 고르기",
        "지시어(this, these, such), 대명사, 연결어(However, For example, Therefore), 관사(a → the)가 앞 문장과의 연결 단서이다.",
        (
            "각 단락의 첫 문장에서 연결 단서를 찾는다",
            "단서가 가리키는 대상이 앞 단락에 있는지 확인하며 순서를 정한다",
            "무관한 문장은 주제에서 벗어나 다른 대상을 다루는 문장을 찾는다",
        ),
        "소재가 같다는 이유로 무관한 문장을 놓치는 것.",
    ),
    _u(
        "eng_insert", "english", "수능 영어", "문장 삽입",
        "주어진 문장이 들어가기에 가장 적절한 곳 고르기",
        "주어진 문장의 연결어·지시어가 가리키는 내용이 바로 앞에 있어야 하고, 넣은 뒤 다음 문장과도 자연스러워야 한다.",
        (
            "주어진 문장의 단서(연결어, 지시어, 대명사)를 확인한다",
            "글의 흐름이 끊기는 곳(논리 비약, 가리키는 대상이 없는 지시어)을 찾는다",
            "그 자리에 넣고 앞뒤 문장과 이어 읽어 확인한다",
        ),
    ),
    _u(
        "eng_summary", "english", "수능 영어", "요약문 완성",
        "글을 한 문장으로 요약할 때 (A), (B)에 들어갈 말",
        "요약문은 글의 주제문을 다른 말로 바꾼 것이다. (A), (B) 각각에 해당하는 글의 근거를 찾아 같은 뜻의 단어를 고른다.",
        ("요약문의 구조를 보고 (A), (B)가 무엇을 묻는지 확인한다", "글에서 각각의 근거를 찾는다", "같은 의미로 바꿔 쓴 선택지를 고른다"),
    ),
    _u(
        "eng_grammar", "english", "수능 영어", "어법",
        "밑줄 친 부분 중 어법상 틀린 것 고르기",
        "자주 나오는 문법 포인트: 주어-동사 수 일치, 동사/준동사, 능동/수동, 관계대명사 what/that/which, 대명사 수 일치, 형용사/부사.",
        (
            "밑줄마다 문장 구조(주어, 동사, 수식 관계)를 확인한다",
            "해당 문법 규칙을 적용해 맞는지 판단한다",
            "틀린 것을 고치면 어떻게 되는지 말한다",
        ),
        "긴 수식어 때문에 진짜 주어를 놓치는 것.",
    ),
    _u(
        "eng_vocab", "english", "수능 영어", "어휘·함축 의미",
        "문맥상 낱말의 쓰임이 적절하지 않은 것, 밑줄 친 어구의 함축 의미",
        "문맥의 논리 방향(긍정/부정, 증가/감소)과 반대되는 낱말이 답이다.",
        ("글의 주제와 논리 흐름을 파악한다", "밑줄 낱말을 반대말로 바꿨을 때 더 자연스러운 것을 찾는다"),
    ),
    _u(
        "eng_detail", "english", "수능 영어", "내용 일치·도표·안내문",
        "글·안내문의 내용과 일치하지 않는 것, 도표 해석",
        "선택지 순서는 대체로 글의 순서를 따른다. 숫자·조건·예외 표현을 정확히 대조한다.",
        ("선택지의 핵심어를 글에서 찾는다", "숫자·비교(more/less, twice)·예외(except, only)를 정확히 대조한다"),
    ),
    # --- 한국사 --------------------------------------------------------------------------
    _u(
        "hist_korean", "korean_history", "수능 한국사", "한국사",
        "시대별 사건·제도·인물, 자료(사료·사진)를 보고 시기와 사건 판단, 사건의 순서",
        "자료 속 핵심 단서(인물, 제도, 사건 이름)로 시기를 먼저 특정한 뒤, 선택지를 그 시기의 사실과 대조한다.",
        (
            "자료의 단서로 시대와 사건을 특정한다",
            "선택지마다 해당 시기의 사실인지 확인한다 (시기가 다른 사실을 섞은 오답에 주의)",
            "순서 문제는 각 사건의 연도나 선후 관계를 적는다",
        ),
        "비슷한 제도·사건(예: 갑신정변과 갑오개혁)의 시기를 혼동하는 것.",
        "정답 선택지의 사실이 특정한 시기와 맞는지, 다른 선택지의 사실이 어느 시기의 것인지 다시 확인한다.",
    ),
    # --- 사회탐구 -----------------------------------------------------------------------
    _u(
        "soc_ethics", "social", "수능 사회탐구", "생활과 윤리·윤리와 사상",
        "사상가(칸트, 공리주의, 롤스, 노직, 공자·맹자·순자, 불교, 노장 등)의 입장 비교, 응용 윤리 쟁점",
        "제시문의 핵심 주장으로 사상가를 특정하고, 각 사상가의 대표 입장을 기준으로 선택지를 판단한다.",
        (
            "제시문의 핵심 개념어로 사상가·입장을 특정한다",
            "그 사상가가 동의할 진술인지 선택지마다 판단한다",
            "비교 문제는 두 사상가의 공통점과 차이점을 나눠 적는다",
        ),
        "비슷한 입장(예: 벤담과 밀, 롤스와 노직)을 섞는 것.",
    ),
    _u(
        "soc_geography", "social", "수능 사회탐구", "한국지리·세계지리",
        "기후 그래프, 지형, 인구·도시·산업 통계, 지도 속 지역 판단",
        "자료(그래프·지도·통계)의 특징적인 값으로 지역을 먼저 특정한 뒤, 선택지를 지역의 특성과 대조한다.",
        (
            "자료에서 가장 두드러진 값(최대·최소, 계절 차)을 찾는다",
            "그 특징에 맞는 지역·현상을 특정한다",
            "선택지의 비교 진술을 자료의 값으로 확인한다",
        ),
        "비율과 절대량을 혼동하는 것.",
    ),
    _u(
        "soc_history", "social", "수능 사회탐구", "동아시아사·세계사",
        "왕조·국가의 제도, 사건의 시기와 순서, 교류, 자료 속 국가·시기 판단",
        "자료의 단서로 국가와 시기를 특정한 뒤 선택지의 사실을 그 시기와 대조한다.",
        ("자료의 단서로 국가·시기를 특정한다", "선택지의 사실이 같은 국가·시기의 것인지 확인한다", "순서 문제는 연도를 적는다"),
        "다른 왕조의 제도를 섞은 선택지.",
    ),
    _u(
        "soc_economy", "social", "수능 사회탐구", "경제",
        "수요·공급과 균형 가격, 탄력성, 기회비용, 시장 실패, 국민 소득, 환율, 무역",
        "수요·공급 변화는 곡선의 이동(수요 증가 → 오른쪽 이동)으로 판단하고, 계산 문제는 식을 세워 수치로 확인한다.",
        (
            "변화 요인이 수요와 공급 중 무엇을 움직이는지 정한다",
            "곡선 이동에 따른 균형 가격·거래량 변화를 판단한다",
            "계산 문제는 식을 세워 값을 구한다 (예: 기회비용 = 포기한 것 중 가장 큰 가치)",
        ),
        "곡선 위의 이동과 곡선 자체의 이동을 혼동하는 것.",
    ),
    _u(
        "soc_politics_law", "social", "수능 사회탐구", "정치와 법",
        "헌법·기본권, 국가 기관, 선거 제도, 민법(계약·불법 행위·가족), 형법, 국제 관계",
        "법 조항과 제도의 요건을 사례에 하나씩 적용해 판단한다.",
        ("사례에 적용할 법·제도를 특정한다", "요건을 하나씩 사례에 대입한다", "결론(성립/불성립, 권리·의무)을 확인한다"),
        "요건 중 하나를 빠뜨리고 결론을 내리는 것.",
    ),
    _u(
        "soc_society_culture", "social", "수능 사회탐구", "사회·문화",
        "사회 현상 탐구 방법(양적·질적), 사회 계층, 문화의 특성, 집단, 자료(표) 분석",
        "탐구 방법 문제는 연구 설계의 특징으로, 표 분석 문제는 비율과 실제 수를 구분해 계산한다.",
        ("자료의 단위(%, 명)와 기준을 확인한다", "필요한 값을 계산한다", "선택지의 비교를 계산 결과로 확인한다"),
        "비율로 절대 수를 비교하는 실수.",
    ),
    # --- 과학탐구 -----------------------------------------------------------------------
    _u(
        "sci_physics", "science", "수능 과학탐구", "물리학Ⅰ",
        "운동(등가속도, 뉴턴 법칙, 운동량·충격량), 역학적 에너지, 열역학, 전기·자기, 파동, 빛과 물질",
        "물리량 사이의 관계식(예: v = v_0 + at, F = ma, 에너지 보존)을 세우고 주어진 값을 대입해 판단한다.",
        (
            "그림·그래프에서 주어진 물리량을 정리한다",
            "관계식(법칙)을 세운다",
            "값을 대입해 계산하고 ㄱ·ㄴ·ㄷ(또는 선택지)을 하나씩 판단한다",
        ),
        "단위를 맞추지 않는 것, 방향(부호)을 빠뜨리는 것.",
        "구한 값을 식에 다시 넣어 확인하고, 단위와 방향이 맞는지 본다.",
    ),
    _u(
        "sci_chemistry", "science", "수능 과학탐구", "화학Ⅰ",
        "몰과 화학 반응식의 양적 관계, 원자 구조와 주기율, 화학 결합, 산화·환원, 산과 염기·중화 반응",
        "화학 반응식의 계수비 = 몰수비. 양적 관계는 몰로 바꿔서 계산한다.",
        ("반응식을 쓰고 계수를 맞춘다", "주어진 양을 몰로 바꾼다", "계수비로 필요한 양을 구하고 선택지를 판단한다"),
        "질량비와 몰수비를 혼동하는 것.",
        "구한 몰수로 질량 보존이나 전하 균형이 맞는지 확인한다.",
    ),
    _u(
        "sci_biology", "science", "수능 과학탐구", "생명과학Ⅰ",
        "세포와 물질대사, 항상성과 몸의 조절(신경·호르몬·면역), 유전(가계도·염색체), 생태계",
        "그림·표의 조건을 하나씩 대입해 가능한 경우를 좁힌다. 유전 문제는 우성/열성, 상염색체/X 염색체를 먼저 정한다.",
        ("자료에서 주어진 조건을 정리한다", "개념(유전 방식, 조절 경로)을 조건에 적용해 경우를 좁힌다", "ㄱ·ㄴ·ㄷ을 하나씩 판단한다"),
        "한 가지 가능성만 보고 결론을 내리는 것.",
        "정한 유전자형·경로가 자료의 모든 조건을 만족하는지 다시 확인한다.",
    ),
    _u(
        "sci_earth", "science", "수능 과학탐구", "지구과학Ⅰ",
        "판 구조론, 지층과 지질 시대, 대기와 해양(기압, 해류, 엘니뇨), 별의 특성(H-R도), 외계 행성, 우주",
        "자료(그래프·단면도)의 값을 개념과 연결해 판단한다. 예: 절대 등급이 작을수록 밝다, 수온 약층은 바람이 강할수록 깊다.",
        ("자료의 축과 단위를 확인한다", "필요한 개념을 떠올려 자료에 적용한다", "선택지의 비교를 자료 값으로 확인한다"),
        "그래프의 축(예: 온도 축이 반대 방향)을 잘못 읽는 것.",
    ),
    _u(
        "etc_general", "other", "기타 과목", "개념·자료 이해",
        "위 과목에 속하지 않는 비수학 문제 (제2외국어·한문·일반 상식 등)",
        "문제에서 묻는 것과 주어진 자료를 먼저 정리하고, 근거를 들어 답한다.",
        ("묻는 것을 정리한다", "근거가 되는 지식이나 자료를 찾는다", "선택지를 하나씩 판단한다"),
    ),
)  # fmt: skip


def _t(
    grade: str,
    name: str,
    examples: str,
    concept: str,
    method: tuple[str, ...],
    pitfalls: str = "",
    check: str = "",
) -> UnitText:
    return UnitText(grade, name, examples, concept, method, "", pitfalls, check)


_JA_CHECK = (
    "正解の選択肢の根拠となる文を本文（資料）でもう一度確かめ、いちばん紛らわしい誤答がなぜ違うかも確認する。"
)
_EN_CHECK = "Find the sentence (or data) that supports the correct option again, and confirm why the most tempting wrong option fails."

TEXT_JA: dict[str, UnitText] = {
    "kor_reading": _t("読解", "評論・説明文", "論理的文章の内容一致・推論・具体例への適用", "答えは必ず本文に根拠がある。段落ごとの要点と概念どうしの関係（因果・比較・条件）を整理する。",
                      ("設問が何を問うか確かめる", "段落ごとの要点を短く整理する", "選択肢ごとに該当段落を探して根拠と照らし合わせる"), "本文にない知識で判断すること、範囲を広げた選択肢を見落とすこと。", _JA_CHECK),
    "kor_literature_poem": _t("文学", "詩・和歌・古典詩歌", "語り手の心情、表現技法、鑑賞", "語り手の状況と心情、それを表す表現を合わせて読む。",
                              ("語り手と状況・心情をつかむ", "選択肢の表現技法が本文に本当にあるか確かめる"), "本文にない技法を選ぶこと。", _JA_CHECK),
    "kor_literature_prose": _t("文学", "小説・随筆・戯曲", "語りの特徴、人物の心情と関係、場面の展開", "語り手の位置、人物関係、出来事の流れを整理する。",
                               ("語り手の視点を確かめる", "人物関係と出来事の順序を整理する", "選択肢の内容が場面に実際にあるか根拠を探す"), "推測で場面を補うこと。", _JA_CHECK),
    "kor_speech_writing": _t("国語表現", "話すこと・書くこと", "発表・討論の話し方、文章の構成と推敲", "聞き手を意識した工夫や、条件どおりに書けているかを見る。",
                             ("工夫が使われている箇所を探す", "条件をひとつずつ確かめる"), "条件の一部だけ満たす選択肢を選ぶこと。", _JA_CHECK),
    "kor_language": _t("言語", "文法・メディア", "品詞、文の成分、音の変化、メディア資料の特徴", "文法の問題は定義を正確に当てはめる。",
                       ("文法の定義を思い出す", "選択肢の例に定義を一段階ずつ当てはめる"), "似た概念を混同すること。", _JA_CHECK),
    "eng_purpose_mood": _t("英語", "目的・心情", "文章の目的、登場人物の心情の変化", "目的は依頼や案内の文に、心情の変化は転換点に表れる。",
                           ("依頼表現や転換の合図を探す", "最初と最後の感情を比べる"), "前置きを目的と取り違えること。", _JA_CHECK),
    "eng_main_idea": _t("英語", "主題・要旨・タイトル", "文章の主題、タイトル、要旨", "主題は文章全体を包み、主題文は導入のあとや結論部にあることが多い。",
                        ("繰り返される語句と主題文を探す", "具体例と主張を区別する", "広すぎ・狭すぎる選択肢を除く"), "例の一つだけを扱う選択肢を選ぶこと。", _JA_CHECK),
    "eng_blank": _t("英語", "空所補充", "空所に入る語句・文", "空所は主題と結びつく。前後の論理（言い換え・対比・因果）から先に内容を予想する。",
                    ("空所の文が主題文かどうか確かめる", "言い換えや対比の文を探す", "予想に最も近い選択肢を選ぶ"), "本文の単語が入っているだけの選択肢を選ぶこと。", _JA_CHECK),
    "eng_order": _t("英語", "文の並べかえ・無関係文", "(A)(B)(C) の順序、流れに合わない文", "指示語・代名詞・つなぎの言葉・冠詞が手がかりになる。",
                    ("各段落の最初の文の手がかりを探す", "指すものが前にあるか確かめて順序を決める"), "話題が同じだけの無関係文を見落とすこと。", _JA_CHECK),
    "eng_insert": _t("英語", "文の挿入", "与えられた文が入る位置", "与えられた文のつなぎの言葉や指示語が指す内容が直前になければならない。",
                     ("与えられた文の手がかりを確かめる", "流れが途切れる箇所を探す", "入れて前後をつなげて読む")),
    "eng_summary": _t("英語", "要約文完成", "要約文の (A)(B) に入る語", "要約文は主題文の言い換え。(A)(B) それぞれの根拠を本文で探す。",
                      ("(A)(B) が何を問うか確かめる", "本文の根拠を探す", "同じ意味の言い換えを選ぶ")),
    "eng_grammar": _t("英語", "語法", "下線部のうち語法的に誤っているもの", "主語と動詞の一致、動詞と準動詞、能動と受動、関係詞、代名詞の数、形容詞と副詞。",
                      ("下線部ごとに文の構造を確かめる", "規則を当てはめて判断する"), "長い修飾語で本当の主語を見落とすこと。", _JA_CHECK),
    "eng_vocab": _t("英語", "語彙・含意", "文脈に合わない語、下線部の含意", "論理の向き（肯定・否定、増加・減少）と反対の語が答え。",
                    ("主題と論理の流れをつかむ", "反対の語に替えると自然になるものを探す")),
    "eng_detail": _t("英語", "内容一致・図表", "本文・案内文との内容一致、図表の読み取り", "数字・比較・例外の表現を正確に照らし合わせる。",
                     ("選択肢のキーワードを本文で探す", "数字・比較・例外を確かめる")),
    "hist_korean": _t("歴史", "韓国史", "時代ごとの出来事・制度・人物、資料からの時期判断", "資料の手がかりで時期を特定してから、選択肢をその時期の事実と照らし合わせる。",
                      ("資料の手がかりで時代を特定する", "選択肢が同じ時期の事実か確かめる", "順序の問題は年代を書く"), "似た出来事の時期を混同すること。", _JA_CHECK),
    "soc_ethics": _t("公民", "倫理", "思想家の立場の比較、応用倫理の論点", "資料の中心主張から思想家を特定し、その代表的な立場で選択肢を判断する。",
                     ("キーワードで思想家を特定する", "その思想家が賛成する文か判断する"), "近い立場の思想家を混同すること。", _JA_CHECK),
    "soc_geography": _t("地理", "地理", "気候グラフ、地形、人口・都市・産業の統計、地図", "資料の特徴的な値で地域を特定してから選択肢を判断する。",
                        ("最も目立つ値を探す", "地域・現象を特定する", "比較の記述を資料の値で確かめる"), "割合と実数を混同すること。", _JA_CHECK),
    "soc_history": _t("歴史", "世界史・東アジア史", "王朝・国家の制度、出来事の時期と順序", "資料の手がかりで国と時期を特定してから判断する。",
                      ("国・時期を特定する", "選択肢が同じ国・時期のものか確かめる"), "別の王朝の制度を混ぜた選択肢。", _JA_CHECK),
    "soc_economy": _t("公民", "経済", "需要と供給、弾力性、機会費用、市場の失敗、国民所得、為替、貿易", "需要・供給の変化は曲線の移動で判断し、計算は式を立てて確かめる。",
                      ("変化が需要と供給のどちらを動かすか決める", "均衡価格・取引量の変化を判断する", "計算は式を立てる"), "曲線上の移動と曲線の移動を混同すること。", _JA_CHECK),
    "soc_politics_law": _t("公民", "政治・経済（法）", "憲法と基本的人権、国の機関、選挙制度、民法、刑法", "法や制度の要件を事例にひとつずつ当てはめる。",
                           ("適用する法・制度を特定する", "要件をひとつずつ当てはめる"), "要件の一つを落とすこと。", _JA_CHECK),
    "soc_society_culture": _t("公民", "現代社会", "社会調査の方法、社会階層、文化、表の分析", "調査方法は研究設計の特徴で、表は割合と実数を区別して計算する。",
                              ("資料の単位を確かめる", "必要な値を計算する"), "割合で実数を比べること。", _JA_CHECK),
    "sci_physics": _t("理科", "物理", "運動、力学的エネルギー、熱、電気と磁気、波、光", "物理量の関係式を立てて値を代入する。",
                      ("与えられた量を整理する", "関係式を立てる", "計算して選択肢を判断する"), "単位や向きを落とすこと。", "求めた値を式に戻し、単位と向きを確かめる。"),
    "sci_chemistry": _t("理科", "化学", "物質量と化学反応式、原子の構造と周期表、化学結合、酸化還元、酸と塩基", "化学反応式の係数比 = 物質量比。量的関係は物質量にして計算する。",
                        ("反応式を書く", "物質量に直す", "係数比で求める"), "質量比と物質量比を混同すること。", "質量保存や電荷のつり合いで確かめる。"),
    "sci_biology": _t("理科", "生物", "細胞と代謝、恒常性、遺伝、生態系", "条件をひとつずつ当てはめて可能性を絞る。遺伝は優性・劣性と染色体を先に決める。",
                      ("条件を整理する", "概念を当てはめて絞る", "選択肢をひとつずつ判断する"), "一つの可能性だけで結論を出すこと。", "決めた遺伝子型などがすべての条件を満たすか確かめる。"),
    "sci_earth": _t("理科", "地学", "プレートテクトニクス、地層と地質時代、大気と海洋、恒星、宇宙", "資料の値を概念と結びつけて判断する。",
                    ("軸と単位を確かめる", "概念を資料に当てはめる", "比較を資料の値で確かめる"), "グラフの軸を読み違えること。", _JA_CHECK),
    "etc_general": _t("その他", "知識・資料の理解", "上記以外の数学でない問題", "問われていることと資料を整理し、根拠をあげて答える。",
                      ("問われていることを整理する", "根拠を探す", "選択肢をひとつずつ判断する")),
}  # fmt: skip

TEXT_EN: dict[str, UnitText] = {
    "kor_reading": _t("Reading", "Informational passages", "Detail, inference and application questions on nonfiction passages", "The answer is always supported by the passage. Summarize each paragraph's point and how the ideas relate (cause-effect, comparison, condition).",
                      ("Check what the question asks", "Note each paragraph's key point", "Match every option against the relevant paragraph"), "Judging from outside knowledge; missing options that overgeneralize ('always', 'all').", _EN_CHECK),
    "kor_literature_poem": _t("Literature", "Poetry", "Speaker, tone, figurative language", "Read the speaker's situation and feeling together with the devices that express them.",
                              ("Identify the speaker, situation and tone", "Check that the device an option names really appears in the lines"), "Picking a device the poem doesn't use.", _EN_CHECK),
    "kor_literature_prose": _t("Literature", "Fiction and drama", "Narration, characters, plot, symbols", "Point of view, character relationships and plot order explain narration and symbols.",
                               ("Identify the narrator's point of view", "Order the characters' relationships and events", "Find the sentence that supports each option"), "Filling gaps with guesses.", _EN_CHECK),
    "kor_speech_writing": _t("Writing", "Speaking and writing", "Presentation strategies, planning and revising", "Check audience-aware strategies and whether every stated condition is met.",
                             ("Find where each strategy is used", "Check the conditions one by one"), "Choosing an option that meets only one condition.", _EN_CHECK),
    "kor_language": _t("Language", "Grammar and media", "Parts of speech, sentence structure, media features", "Apply the grammatical definition exactly.",
                       ("Recall the definition", "Apply it step by step to each example"), "Mixing up similar concepts.", _EN_CHECK),
    "eng_purpose_mood": _t("English", "Purpose and mood", "Purpose of a text, change of feelings", "The purpose shows in the request or notice; a change of feeling shows at the turning point.",
                           ("Find request phrases and signal words", "Compare the feelings at the start and the end"), "Taking background information for the purpose.", _EN_CHECK),
    "eng_main_idea": _t("English", "Main idea and title", "Topic, title, main point", "The main idea covers the whole text; the topic sentence usually follows the introduction or ends the text.",
                        ("Find repeated key phrases and the topic sentence", "Separate examples from the claim", "Drop options that are too broad or too narrow"), "Choosing an option about only one example.", _EN_CHECK),
    "eng_blank": _t("English", "Fill in the blank", "Word, phrase or sentence for a blank", "The blank ties to the main idea; predict its content from the logic around it (restatement, contrast, cause).",
                    ("Decide whether the blank sentence states the main idea", "Find restatements or contrasts", "Choose the option closest to your prediction"), "Picking an option just because it repeats words from the text.", _EN_CHECK),
    "eng_order": _t("English", "Sentence order", "Order of (A)(B)(C), the irrelevant sentence", "Demonstratives, pronouns, transitions and articles link each part to what comes before.",
                    ("Find the link clue at the start of each part", "Check that what it refers to comes earlier"), "Missing an irrelevant sentence that shares the topic.", _EN_CHECK),
    "eng_insert": _t("English", "Sentence insertion", "Where a given sentence fits", "What the given sentence refers to must come right before it.",
                     ("Check the given sentence's clues", "Find the break in the flow", "Insert it and read across")),
    "eng_summary": _t("English", "Summary completion", "Words for (A) and (B) in a summary", "The summary restates the main idea; find the evidence for (A) and (B).",
                      ("Check what (A) and (B) ask", "Find the evidence", "Choose the paraphrase")),
    "eng_grammar": _t("English", "Grammar", "The ungrammatical underlined part", "Subject-verb agreement, verbs vs. verbals, active vs. passive, relative pronouns, pronoun number, adjective vs. adverb.",
                      ("Check the structure around each underline", "Apply the rule"), "Losing the real subject behind a long modifier.", _EN_CHECK),
    "eng_vocab": _t("English", "Vocabulary in context", "The word that doesn't fit, implied meaning", "The answer runs against the logic of the text (positive/negative, increase/decrease).",
                    ("Follow the main idea and logic", "Flip the word and see if it fits better")),
    "eng_detail": _t("English", "Details and graphs", "Matching details, reading a chart or notice", "Match numbers, comparisons and exceptions exactly.",
                     ("Find each option's key words in the text", "Check numbers, comparisons and exceptions")),
    "hist_korean": _t("History", "Korean history", "Events, institutions and figures by period; dating sources", "Pin down the period from the clues first, then check each option against that period.",
                      ("Date the source from its clues", "Check that each option belongs to that period", "For ordering, write the years"), "Confusing similar events from different periods.", _EN_CHECK),
    "soc_ethics": _t("Social studies", "Ethics", "Comparing thinkers, applied ethics", "Identify the thinker from the key claim, then judge each option by that thinker's position.",
                     ("Identify the thinker", "Ask whether they would agree"), "Mixing up similar thinkers.", _EN_CHECK),
    "soc_geography": _t("Social studies", "Geography", "Climate graphs, landforms, population and industry data, maps", "Identify the region from its most distinctive data, then check the options.",
                        ("Find the standout values", "Identify the region", "Check comparisons against the data"), "Confusing rates with totals.", _EN_CHECK),
    "soc_history": _t("Social studies", "World and East Asian history", "Dynasties, institutions, dates and order of events", "Identify the country and period from the clues, then check the options.",
                      ("Identify the country and period", "Check each option belongs there"), "Options that mix in another dynasty.", _EN_CHECK),
    "soc_economy": _t("Social studies", "Economics", "Supply and demand, elasticity, opportunity cost, market failure, GDP, exchange rates, trade", "Model shifts as curve shifts; set up equations for calculations.",
                      ("Decide whether demand or supply shifts", "Read the new equilibrium", "Calculate where needed"), "Confusing a movement along a curve with a shift of the curve.", _EN_CHECK),
    "soc_politics_law": _t("Social studies", "Government and law", "Constitutional rights, government bodies, elections, civil and criminal law", "Apply each legal requirement to the case in turn.",
                           ("Identify the rule", "Apply its requirements one by one"), "Skipping a requirement.", _EN_CHECK),
    "soc_society_culture": _t("Social studies", "Sociology", "Research methods, stratification, culture, table analysis", "Tell rates from counts and calculate before comparing.",
                              ("Check the units", "Calculate what you need"), "Comparing totals using percentages.", _EN_CHECK),
    "sci_physics": _t("Science", "Physics", "Motion, energy, thermodynamics, electricity and magnetism, waves, light", "Write the relation between the quantities and substitute the values.",
                      ("List the given quantities", "Write the law", "Calculate and judge each option"), "Dropping units or directions.", "Put the value back into the equation and check units and direction."),
    "sci_chemistry": _t("Science", "Chemistry", "Moles and equations, atomic structure, bonding, redox, acids and bases", "Coefficient ratio = mole ratio; convert amounts to moles first.",
                        ("Write the balanced equation", "Convert to moles", "Use the ratio"), "Confusing mass ratios with mole ratios.", "Check conservation of mass or charge."),
    "sci_biology": _t("Science", "Biology", "Cells and metabolism, homeostasis, genetics, ecosystems", "Apply each condition to narrow the possibilities; in genetics decide dominance and chromosome first.",
                      ("List the conditions", "Apply the concept to narrow the cases", "Judge each option"), "Concluding from one possibility.", "Check the chosen genotype or pathway against every condition."),
    "sci_earth": _t("Science", "Earth science", "Plate tectonics, strata and geologic time, atmosphere and ocean, stars, the universe", "Connect the data values to the concept.",
                    ("Check axes and units", "Apply the concept", "Check comparisons against the data"), "Misreading reversed axes.", _EN_CHECK),
    "etc_general": _t("Other", "Knowledge and data", "Non-math questions outside the subjects above", "Sort out what is asked and the given material, and answer with evidence.",
                      ("Note what is asked", "Find the evidence", "Judge each option")),
}  # fmt: skip
