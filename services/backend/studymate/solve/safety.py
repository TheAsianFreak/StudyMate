"""Speech safety for the character (Korean, Japanese, English).

The default character's license (Tsukuyomi-chan, docs/research/default-character.md)
forbids using it for political or religious advocacy and for attacking people, and asks
that sexual content be kept away from it; Steam requires guardrails on live-generated AI
content. So:

- every LLM prompt that makes the character speak includes `safety_prompt()`;
- a user request that asks for sexual content is refused before any model runs
  (`is_unsafe_request`);
- every `say` / `write` string passes `filter_steps` before it reaches the client.

Patterns of all three languages are always applied: model output can mix languages.
"""

from __future__ import annotations

import re
import unicodedata

from studymate.i18n import tr
from studymate.protocol.backend import ScriptStep


def safety_prompt() -> str:
    return tr(
        "안전 규칙: 정치(정당, 정치인, 선거, 투표, 정책 논쟁)나 종교에 대해 지지하거나 반대하는 말, "
        "권유하는 말을 하지 마세요. 특정 사람이나 집단을 비난하거나 모욕하거나 공격하는 말, 욕설도 하지 마세요. "
        "성적인 내용(성행위, 몸의 성적인 묘사, 야한 농담, 연인·성적 역할극)은 절대 말하지 마세요. "
        "불법이거나 위험한 일(무기, 마약, 해킹, 자해 방법 등)도 알려주지 마세요. "
        "그런 요청을 받으면 정중하게 거절하고 공부 이야기로 부드럽게 돌아가세요.",
        "安全ルール: 政治（政党、政治家、選挙、投票、政策論争）や宗教について、支持・反対・勧誘する発言はしないでください。"
        "特定の人や集団を非難・侮辱・攻撃する発言や暴言もしないでください。"
        "性的な内容（性行為、体の性的な描写、エッチな冗談、恋人・性的なロールプレイ）は絶対に話さないでください。"
        "違法・危険なこと（武器、薬物、ハッキング、自傷の方法など）も教えないでください。"
        "そういう頼みには丁寧に断って、勉強の話にやさしく戻ってください。",
        "Safety rules: never support, oppose or promote a political side (parties, politicians, elections, "
        "votes, policy debates) or a religion. Never insult, attack or demean any person or group, and no "
        "profanity. Never say anything sexual (sex acts, sexual descriptions of bodies, dirty jokes, romantic "
        "or sexual role-play). Never explain illegal or dangerous things (weapons, drugs, hacking, self-harm "
        "methods). If asked, politely decline and gently steer back to studying.",
    )


def refusal_say() -> str:
    return tr(
        "그 이야기는 제가 말씀드리기 어려워요. 우리 다시 공부 이야기로 돌아가요!",
        "そのお話はちょっとできないんです。お勉強のお話に戻りましょう！",
        "That's not something I can talk about. Let's get back to studying!",
    )


REFUSAL_SAY = "그 이야기는 제가 말씀드리기 어려워요. 우리 다시 공부 이야기로 돌아가요!"
_REFUSALS = frozenset(
    {
        REFUSAL_SAY,
        "そのお話はちょっとできないんです。お勉強のお話に戻りましょう！",
        "That's not something I can talk about. Let's get back to studying!",
    }
)

# --- Korean ------------------------------------------------------------------------------

# Names are matched on text with whitespace kept, bounded by non-Hangul characters.
_KO_PARTIES = (
    "더불어민주당",
    "민주당",
    "국민의힘",
    "정의당",
    "조국혁신당",
    "개혁신당",
    "진보당",
    "기본소득당",
    "새누리당",
    "자유한국당",
    "미래통합당",
    "공화당",
    "노동당",
)
_KO_POLITICS_TOPIC = (
    r"(?:대통령|국회의원|정치인|정당|정권|정부|여당|야당|보수|진보|좌파|우파"
    r"|빨갱이|수꼴|토착왜구|민주당|국민의힘)"
)
_KO_ADVOCACY = (
    r"(?:지지합니다|지지해요|지지하세요|지지해야|반대합니다|반대해요|반대하세요|반대해야|찍어|찍으세요|찍자|뽑아야"
    r"|뽑으세요|뽑자|투표하세요|투표해야|심판해야|심판합시다|탄핵해야|퇴진해야|몰아내|응원합니다|응원해요"
    r"|최고예요|최고입니다|최악|나쁜 사람|좋은 사람|잘못하고|무능)"
)
_KO_RELIGION = (
    r"(?:하나님|하느님|예수님?|그리스도|부처님?|석가|알라|여호와|성경|불경|코란|꾸란|교회|성당|기독교|개신교"
    r"|천주교|불교|이슬람|힌두교|유대교|사이비|이단|무신론)"
)
_KO_RELIGION_ADVOCACY = (
    r"(?:믿으세요|믿어야 해|믿어야 합니다|믿읍시다|영접하|전도하|개종하|다니세요|믿지 마|진짜 종교|가짜 종교"
    r"|최고의 종교|유일한 진리|틀렸어요|거짓말|사기|미신이)"
)
_KO_GROUPS = (
    r"(?:여자|여성|남자|남성|노인|장애인|외국인|흑인|백인|동양인|이민자|난민|성소수자|동성애자|유대인|무슬림"
    r"|기독교인|불교도|중국인|일본인|조선족|전라도|경상도|좌파|우파)"
)
_KO_GROUP_ATTACK = r"(?:열등|멍청|쓰레기|벌레|없어져야|사라져야|추방해|혐오스|더럽|미개|죽어야|싫어해야)"

# --- Japanese ----------------------------------------------------------------------------

_JA_PARTIES = (
    r"(?:自民党|自由民主党|立憲民主党|公明党|日本維新の会|維新の会|共産党|国民民主党|れいわ新選組|参政党"
    r"|社民党|社会民主党|日本保守党)"
)
# Party names alone are fine (civics, history); only advocacy around them is flagged.
_JA_POLITICS_TOPIC = rf"(?:首相|総理|大統領|政治家|政党|政権|政府|与党|野党|保守|リベラル|右翼|左翼|ネトウヨ|パヨク|{_JA_PARTIES})"
_JA_ADVOCACY = (
    r"(?:支持します|支持しよう|支持すべき|反対します|反対しよう|反対すべき|投票して|投票しよう|投票すべき|に入れて"
    r"|に入れよう|応援します|応援しよう|打倒|退陣すべき|辞めるべき|最悪|最高です|無能|悪い人|良い人)"
)
_JA_RELIGION = (
    r"(?:神様|イエス|キリスト|仏陀|ブッダ|お釈迦様|アッラー|聖書|コーラン|教会|キリスト教|仏教|イスラム教|イスラム"
    r"|ヒンドゥー教|ユダヤ教|カルト|新興宗教|無神論)"
)
_JA_RELIGION_ADVOCACY = r"(?:信じなさい|信じるべき|信じましょう|入信|改宗|布教|唯一の真理|本当の宗教|偽物の宗教|間違って|嘘|迷信|詐欺)"
_JA_GROUPS = (
    r"(?:女|女性|男|男性|老人|高齢者|障害者|外国人|黒人|白人|移民|難民|同性愛者|ユダヤ人|イスラム教徒|中国人"
    r"|韓国人|朝鮮人|日本人)"
)
_JA_GROUP_ATTACK = (
    r"(?:劣って|劣等|バカ|馬鹿|ゴミ|消えろ|消えるべき|死ね|死ぬべき|出ていけ|気持ち悪い|キモい|下等|害虫)"
)

# --- English -----------------------------------------------------------------------------

_EN_PARTIES = (
    r"\b(?:democrats?|democratic party|republicans?|republican party|gop|maga|labour party|labour"
    r"|tories|tory|conservative party|liberal party|lib dems?|reform uk|green party)\b"
)
_EN_POLITICS_TOPIC = (
    r"(?:\b(?:president|prime minister|politicians?|party|government|administration|senators?|congress"
    rf"|candidates?|election|left[- ]wing|right[- ]wing|liberals?|conservatives?|leftists?)\b|{_EN_PARTIES})"
)
# Imperatives and verdicts only: descriptive civics ("Congress can impeach the president")
# must pass.
_EN_ADVOCACY = (
    r"\b(?:vote for|vote against|you should vote|don't vote|support them|support him|support her"
    r"|should win|should lose|must go|is the best|are the best|is evil|are evil|is corrupt|are corrupt"
    r"|is a disaster|incompetent)\b"
)
_EN_RELIGION = (
    r"\b(?:god|jesus|christ|buddha|allah|jehovah|bible|quran|koran|church|christianity|christians?|islam"
    r"|muslims?|hinduism|judaism|atheism|cult)\b"
)
_EN_RELIGION_ADVOCACY = (
    r"\b(?:you should believe|you must believe|you should convert|convert to|accept jesus|the only truth"
    r"|the true religion|the real religion|false religion|fake religion|is a lie|is fake|is a superstition)\b"
)
_EN_GROUPS = (
    r"\b(?:women|girls|men|boys|old people|the elderly|disabled people|foreigners|black people|white people"
    r"|asians|immigrants|refugees|gay people|gays|lgbt people|trans people|jews|muslims|christians|mexicans"
    r"|chinese people|japanese people|koreans)\b"
)
_EN_GROUP_ATTACK = (
    r"\b(?:are inferior|are stupid|are trash|are garbage|are vermin|should die|should disappear"
    r"|should be deported|are disgusting|are subhuman|are animals|don't deserve)\b"
)

# --- Sexual content (all languages) -------------------------------------------------------
# Explicit terms only: health / biology education words (생식, 정자, 性教育, reproduction,
# sex chromosomes) must stay usable in a study app.
_SEXUAL = re.compile(
    r"섹스|섹시|야한\s*(?:거|것|얘기|이야기|사진|농담|말|짓)|야동|음란|자위|포르노|야짤|성행위를?\s*(?:하|해|묘사)"
    r"|벗어\s*(?:줘|봐|주세요)|옷\s*(?:을\s*)?벗|팬티|속옷|브래지어|가슴\s*(?:을\s*)?(?:만지|보여)|엉덩이\s*(?:를\s*)?(?:만지|보여)"
    r"|몸매|알몸|나체|키스\s*(?:해\s*줘|하자|해요)|뽀뽀\s*(?:해\s*줘|하자)|같이\s*자자|애무|꼴려|꼴린다|딸딸이"
    r"|セックス|エッチ|えっち|エロ(?!ージョン)|淫ら|いやらしい|オナニー|自慰|ポルノ|裸(?:の(?:写真|画像)|になって|を見せ)|全裸"
    r"|脱いで|脱がせ|パンツ見|下着|ブラジャー"
    r"|おっぱい|胸を(?:触|揉|見せ)|お尻を(?:触|見せ)|キスして|キスしよう|一緒に寝よう|抱いて|夜のお相手|ちんこ|まんこ"
    r"|\bsex(?:y|ual(?:ly)? (?:act|content|role|fantas))|\bhave sex\b|\bnudes?\b|\bget naked\b"
    r"|\bnaked (?:body|bodies|girl|woman|women|man|men|picture|photo|pic)s?\b|\bporn|\bhorny\b|\berotic"
    r"|\bmasturbat|\bundress|take off (?:your|her|my) (?:clothes|shirt|skirt|underwear)|\bunderwear\b|\blingerie\b"
    r"|\bboobs?\b|\btits\b|\bpussy\b|\bdick\b|\bcock\b|\bblowjob|\bnsfw\b|\blewd\b|\bhentai\b|\bstrip for\b"
    r"|\bkiss me\b|\bmake out\b|\bsleep with me\b|\bseduc",
    re.IGNORECASE,
)

# Matched on text with whitespace and punctuation removed (catches "씨 발", "f u c k").
_SLURS = re.compile(
    r"씨발|시발(?!점|역)|ㅅㅂ|씨바|병신(?!년)|븅신|ㅂㅅ|좆|개새끼|새끼야|느금마|엠창|한남충|김치녀|된장녀|틀딱"
    r"|짱깨|쪽바리|쪽발이|깜둥이|흑형|급식충|맘충|닥쳐|죽여버|미친놈|미친년|또라이"
    r"|死ね|殺すぞ|ぶっ殺|ガイジ(?!ン)|支那人|クソ野郎|くそやろう|カス野郎"
)
# English needs word boundaries: compact text would find "shit" in "push it up".
_EN_SLURS = re.compile(
    r"\b(?:fuck\w*|shit|shitty|bullshit|bitch\w*|bastards?|assholes?|retards?|retarded|faggots?|niggers?"
    r"|niggas?|chinks?|spics?|kill yourself|kys|stfu)\b",
    re.IGNORECASE,
)

_PATTERNS = [
    re.compile(rf"(?<![가-힣])(?:{'|'.join(_KO_PARTIES)})"),
    re.compile(rf"{_KO_POLITICS_TOPIC}.{{0,20}}{_KO_ADVOCACY}|{_KO_ADVOCACY}.{{0,12}}{_KO_POLITICS_TOPIC}"),
    re.compile(r"(?:선거|투표|총선|대선)에서.{0,20}(?:찍|뽑|지지)"),
    re.compile(
        rf"{_KO_RELIGION}.{{0,20}}{_KO_RELIGION_ADVOCACY}|{_KO_RELIGION_ADVOCACY}.{{0,12}}{_KO_RELIGION}"
    ),
    re.compile(rf"{_KO_GROUPS}(?:은|는|들은|들이|이|가|들)?.{{0,15}}{_KO_GROUP_ATTACK}"),
    re.compile(rf"{_JA_POLITICS_TOPIC}.{{0,20}}{_JA_ADVOCACY}|{_JA_ADVOCACY}.{{0,12}}{_JA_POLITICS_TOPIC}"),
    re.compile(r"選挙.{0,20}(?:入れて|投票して|支持して)"),
    re.compile(
        rf"{_JA_RELIGION}.{{0,20}}{_JA_RELIGION_ADVOCACY}|{_JA_RELIGION_ADVOCACY}.{{0,12}}{_JA_RELIGION}"
    ),
    re.compile(rf"{_JA_GROUPS}(?:は|が|なんて|って)?.{{0,15}}{_JA_GROUP_ATTACK}"),
    re.compile(
        rf"{_EN_POLITICS_TOPIC}.{{0,30}}{_EN_ADVOCACY}|{_EN_ADVOCACY}.{{0,20}}{_EN_POLITICS_TOPIC}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"{_EN_RELIGION}.{{0,30}}{_EN_RELIGION_ADVOCACY}|{_EN_RELIGION_ADVOCACY}.{{0,20}}{_EN_RELIGION}",
        re.IGNORECASE,
    ),
    re.compile(rf"{_EN_GROUPS}.{{0,20}}{_EN_GROUP_ATTACK}", re.IGNORECASE),
    _SEXUAL,
]


def _squash(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)
    t = re.sub(r"\\text\{([^}]*)\}", r"\1", t)
    return t


def is_unsafe(text: str | None) -> bool:
    """Keyword + pattern check on one spoken or written string."""
    if not text:
        return False
    t = _squash(text)
    compact = re.sub(r"[\s.,!?~·*_\-]+", "", t)
    if _SLURS.search(compact) or _EN_SLURS.search(t):
        return True
    return any(p.search(t) for p in _PATTERNS)


def is_unsafe_request(text: str | None) -> bool:
    """A user message asking for something the character must not do (checked before the LLM).

    Sexual requests are refused outright. Political/religious questions are allowed as study
    questions (the model answers neutrally under the safety prompt and the output is filtered).
    """
    if not text:
        return False
    return bool(_SEXUAL.search(_squash(text)))


def refusal_step() -> ScriptStep:
    return ScriptStep(say=refusal_say(), gesture="idle", emotion="neutral")


def filter_steps(steps: list[ScriptStep]) -> tuple[list[ScriptStep], bool]:
    """Replaces offending steps with one neutral refusal line. Returns (steps, flagged)."""
    out: list[ScriptStep] = []
    flagged = False
    for step in steps:
        texts = [step.say, step.write, step.note, step.mark.target if step.mark else None]
        if any(is_unsafe(t) for t in texts):
            flagged = True
            if not out or out[-1].say not in _REFUSALS:
                out.append(refusal_step())
            continue
        out.append(step)
    return out or [refusal_step()], flagged
