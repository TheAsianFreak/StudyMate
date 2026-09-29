"""`read_problem`: screenshot of a problem -> Problem (text, LaTeX, subject).

Uses Qwen2.5-VL when the tier has a vision model, otherwise (lite tier, or when the
vision server fails) RapidOCR + pix2tex. Both paths run fully offline.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import io
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from PIL import Image, UnidentifiedImageError

from studymate.errors import ModelMissingError, UserFacingError
from studymate.i18n import lang, tr
from studymate.llm.client import image_message
from studymate.verify.latex import HANGUL, HANGUL_RUN, repair_escapes

if TYPE_CHECKING:
    from studymate.services import Services
    from studymate.vision.mathocr import MathOcr
    from studymate.vision.ocr import TextOcr

log = logging.getLogger(__name__)

# Subject labels per language, in the same order: math, science, national language,
# foreign language, social studies, other.
_SUBJECTS = {
    "ko": ("수학", "과학", "국어", "영어", "사회", "기타"),
    "ja": ("数学", "理科", "国語", "英語", "社会", "その他"),
    "en": ("Math", "Science", "English", "Foreign language", "Social studies", "Other"),
}
SUBJECTS = list(_SUBJECTS["ko"])


def subjects() -> tuple[str, ...]:
    return _SUBJECTS[lang()]


def vl_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "problem_text": {"type": "string", "maxLength": 6000},  # whole reading passages
            "problem_latex": {"type": "string", "maxLength": 800},
            "subject": {"enum": list(subjects())},
        },
        "required": ["problem_text", "problem_latex", "subject"],
        "additionalProperties": False,
    }


def vl_prompt() -> str:
    names = ", ".join(subjects())
    return tr(
        "이미지 속 문제를 정확히 옮겨 적어 주세요. 문제를 풀지 마세요.\n"
        "- problem_text: 문제 전체를 보이는 그대로 적어요. "
        "한국어 문장은 그대로, 수식은 LaTeX로 적어요 ($ 기호 없이). "
        "분수는 \\frac{}{}, 거듭제곱은 ^, 곱하기는 \\times, 나누기는 \\div, 부등호는 \\le, \\ge를 써요. "
        "연립방정식은 식을 쉼표로 구분해요. 보기(①②③④⑤)가 있으면 함께 적어요.\n"
        "- problem_latex: 칠판에 쓸 문제의 핵심 수식만 LaTeX로 적어요. "
        "수식이 없으면 짧은 문장을 \\text{} 안에 적어요.\n"
        f"- subject: 과목 ({names}).",
        "画像の中の問題を正確に書き写してください。問題は解かないでください。\n"
        "- problem_text: 問題全体を見えるとおりに書きます。"
        "日本語の文はそのまま、数式は LaTeX で書きます（$ 記号なし）。"
        "分数は \\frac{}{}、累乗は ^、かけ算は \\times、わり算は \\div、不等号は \\le, \\ge を使います。"
        "連立方程式は式をコンマで区切ります。選択肢（①②③④⑤）があれば一緒に書きます。\n"
        "- problem_latex: 黒板に書く問題の中心となる式だけを LaTeX で書きます。"
        "式がなければ短い文を \\text{} の中に書きます。\n"
        f"- subject: 教科（{names}）。",
        "Copy the problem in the image exactly. Do not solve it.\n"
        "- problem_text: the whole problem as it appears. Keep sentences as they are and write math in LaTeX "
        "(no $). Use \\frac{}{} for fractions, ^ for powers, \\times, \\div, \\le and \\ge. "
        "Separate the equations of a system with commas. Include answer choices (①②③④⑤) if there are any.\n"
        "- problem_latex: only the problem's main expression in LaTeX, for the board. "
        "If there is no math, a short sentence inside \\text{}.\n"
        f"- subject: the subject ({names}).",
    )


Source = Literal["vision", "ocr", "text"]


@dataclass
class Problem:
    text: str
    latex: str
    subject: str
    source: Source
    uncertain: bool = False  # OCR engines disagreed on a formula: never claim "high"


def decode_image(png_b64: str, max_bytes: int) -> Image.Image:
    data = png_b64.strip()
    if data.startswith("data:"):
        data = data.split(",", 1)[-1]
    if len(data) * 3 // 4 > max_bytes:
        raise UserFacingError("image_too_large", "이미지가 너무 큽니다. 문제 부분만 잘라서 보내주세요.")
    try:
        raw = base64.b64decode(data, validate=False)
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (binascii.Error, UnidentifiedImageError, OSError, ValueError) as exc:
        raise UserFacingError("bad_image", "이미지를 읽을 수 없습니다.") from exc
    if img.width < 8 or img.height < 8:
        raise UserFacingError("bad_image", "이미지가 너무 작습니다.")
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    return img.convert("RGB")


def encode_png(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


_MATH_WORDS = re.compile(
    r"방정식|부등식|계산|값을|값은|함수|넓이|둘레|확률|인수분해|식을|근|해를|약분|분수|소수|비례|좌표|각도|삼각형|넓이"
    r"|方程式|不等式|計算|値を|関数|面積|確率|因数分解|約分|分数|小数|比例|座標|角度|三角形"
    r"|\b(?:equation|inequality|calculate|evaluate|simplify|function|area|perimeter|probability|factor|fraction"
    r"|decimal|proportion|coordinate|angle|triangle)s?\b",
    re.IGNORECASE,
)
_SCIENCE_WORDS = re.compile(
    r"원자|분자|이온|전류|전압|저항|자기장|속력|가속도|힘|에너지|세포|광합성|유전|화학|물질|기체|액체|고체|지구|태양|행성|생물|호흡|소화"
    r"|原子|分子|イオン|電流|電圧|抵抗|磁界|速さ|加速度|エネルギー|細胞|光合成|遺伝|化学|物質|気体|液体|固体|地球|太陽|惑星|生物|呼吸|消化"
    r"|\b(?:atoms?|molecules?|ions?|current|voltage|resistance|magnetic|velocity|acceleration|force|energy|cells?"
    r"|photosynthesis|genetics?|chemical|gas|liquid|solid|earth|sun|planets?|organisms?|respiration|digestion)\b",
    re.IGNORECASE,
)
_SOCIAL_WORDS = re.compile(
    r"역사|조선|고려|신라|백제|왕|정부|헌법|경제|지리|기후|인구|문화|사회|시장|민주|국회|법원"
    r"|歴史|江戸|幕府|天皇|政府|憲法|経済|地理|気候|人口|文化|社会|市場|民主|国会|裁判所"
    r"|\b(?:history|empire|kingdom|government|constitution|economy|geography|climate|population|culture"
    r"|society|market|democracy|congress|court)\b",
    re.IGNORECASE,
)
_NATIONAL_LANGUAGE_WORDS = {
    "ko": re.compile(r"문학|시에서|소설|화자|문장|품사|맞춤법|어휘|주제|글쓴이|비유|운율|문법"),
    "ja": re.compile(r"文学|小説|随筆|古文|漢文|作者|筆者|品詞|敬語|語彙|主題|比喩|文法|漢字"),
    "en": re.compile(
        r"\b(?:poem|poetry|novel|narrator|sentence|grammar|spelling|vocabulary|theme|author|metaphor|simile)\b",
        re.IGNORECASE,
    ),
}


def guess_subject(text: str, hint: str | None = None) -> str:
    """Heuristic subject label (current language) for OCR / typed problems."""
    names = subjects()
    math, science, national, foreign, social, other = names
    if hint:
        for s in names:
            if s.lower() in hint.lower():
                return s
    # "<보기>", "<조건>" (or their HTML-escaped form) are box labels, not inequality signs
    clean = re.sub(r"&lt;|&gt;|&amp;", " ", text)
    clean = re.sub(r"<[^<>\n]{1,8}>", " ", clean)
    mathy = bool(
        re.search(r"[=<>≤≥]|\\frac|\\times|\\div|\^|\d\s*[+\-×÷*/]\s*\d|\d[a-z]\b", clean)
        or _MATH_WORDS.search(clean)
    )
    is_science = _SCIENCE_WORDS.search(clean) is not None
    is_social = _SOCIAL_WORDS.search(clean) is not None
    is_language = _NATIONAL_LANGUAGE_WORDS[lang()].search(clean) is not None
    # a physics formula or an economics table has math in it but stays its own subject
    if mathy and not (is_science or is_social or is_language):
        return math
    if is_science:
        return science
    if is_social:
        return social
    if is_language:
        return national
    latin = len(re.findall(r"[A-Za-z]", clean))
    if lang() != "en" and latin > 20 and latin > 2 * len(HANGUL.findall(clean)):
        return foreign
    if mathy:
        return math
    return other


def board_latex(text: str) -> str:
    """Board-ready LaTeX: the math of the problem, or the text wrapped in \\text{}."""
    from studymate.verify.problem import math_segments

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    math_lines = [ln for ln in lines if not HANGUL.search(ln)]
    if math_lines:
        return ", \\quad ".join(math_lines)
    if any(math_segments(ln) for ln in lines):
        return " ".join(_wrap_hangul(ln) for ln in lines)
    return "\\text{" + (lines[0] if lines else "").replace("{", "").replace("}", "") + "}"


def _wrap_hangul(line: str) -> str:
    return HANGUL_RUN.sub(lambda m: "\\text{" + m.group(0) + "}", line.replace("$", ""))


async def _read_vl(services: Services, img: Image.Image) -> Problem:
    max_side = services.settings.solve.vision_max_side
    if max(img.size) > max_side:
        img = img.copy()
        img.thumbnail((max_side, max_side))
    png = await asyncio.to_thread(encode_png, img)
    out = await services.llm.chat_json(
        [image_message(vl_prompt(), png)],
        vl_schema(),
        role="vision",
        name="problem",
        temperature=0.0,
        max_tokens=services.settings.solve.vision_max_tokens,
        seed=0,
    )
    text = repair_escapes(str(out.get("problem_text", ""))).strip()
    latex = repair_escapes(str(out.get("problem_latex", ""))).strip() or board_latex(text)
    subject = out.get("subject") if out.get("subject") in subjects() else guess_subject(text)
    if not text:
        raise UserFacingError("ocr_empty", "이미지에서 문제를 찾지 못했어요. 문제 부분을 다시 잘라 주세요.")
    return Problem(text, latex, str(subject), "vision")


def ocr_available(services: Services) -> bool:
    return services.registry.installed(services.settings.solve.ocr_rec_model)


def _text_ocr(services: Services) -> TextOcr:
    from studymate.vision.ocr import TextOcr

    cfg = services.settings.solve
    return TextOcr(services.registry.path(cfg.ocr_rec_model), cfg.ocr_text_score)


def _math_ocr(services: Services) -> MathOcr | None:
    from studymate.vision.mathocr import MathOcr

    model_id = services.settings.solve.math_ocr_model
    if not services.registry.installed(model_id):
        log.warning("pix2tex model %s not installed; formulas are read by text OCR only", model_id)
        return None
    entry = services.registry.entries[model_id]
    resizer = services.registry.path(model_id, 1) if len(entry.files) > 1 else None
    return MathOcr(services.registry.path(model_id), resizer)


async def _read_ocr(services: Services, img: Image.Image) -> Problem:
    from studymate.vision.ocr import read_image_detailed

    if not ocr_available(services):
        raise ModelMissingError("문자 인식(OCR)")
    text_ocr = await services.lazy_async("vision.text_ocr", lambda: _text_ocr(services))
    math_ocr = await services.lazy_async("vision.math_ocr", lambda: _math_ocr(services))
    lines, uncertain = await asyncio.to_thread(read_image_detailed, img, text_ocr, math_ocr)
    if not lines:
        raise UserFacingError("ocr_empty", "이미지에서 글자를 찾지 못했어요. 문제 부분을 다시 잘라 주세요.")
    text = "\n".join(lines)
    return Problem(text, board_latex(text), guess_subject(text), "ocr", uncertain)


async def read_problem(services: Services, png_b64: str) -> Problem:
    """Reads the problem in a (cropped) screenshot."""
    img = await asyncio.to_thread(decode_image, png_b64, services.settings.solve.max_image_bytes)
    if services.llama.available("vision"):
        try:
            return await _read_vl(services, img)
        except UserFacingError as exc:
            if not ocr_available(services) or exc.code == "ocr_empty":
                raise
            log.warning("vision model failed (%s); falling back to OCR", exc.code)
    return await _read_ocr(services, img)
