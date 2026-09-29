"""Lite-tier problem reading: RapidOCR (PaddleOCR Korean model) + pix2tex for formulas.

Text lines containing Hangul come from RapidOCR. The remaining ink (formulas, often
with stacked fractions or exponents that line OCR cannot read) is cut into regions and
read by pix2tex; RapidOCR's reading of the same region is the fallback.

All model files are loaded from explicit paths so nothing is downloaded at runtime:
the Korean recognition model and pix2tex weights come from models/ (models.json), the
detection/orientation models ship inside the rapidocr wheel.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from studymate.verify.latex import HANGUL, has_relation, parse_math, split_top, to_plain

log = logging.getLogger(__name__)

_DET_FILE = "PP-OCRv6_det_small.onnx"
_CLS_FILE = "ch_ppocr_mobile_v2.0_cls_mobile.onnx"


@dataclass
class TextBox:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    score: float

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def h(self) -> float:
        return self.y1 - self.y0

    @property
    def hangul(self) -> bool:
        return bool(HANGUL.search(self.text))


class TextOcr:
    def __init__(self, rec_model: Path, text_score: float) -> None:
        import rapidocr
        from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

        bundled = Path(rapidocr.__file__).parent / "models"
        det, cls = bundled / _DET_FILE, bundled / _CLS_FILE
        for p in (det, cls, rec_model):
            if not p.exists():
                raise FileNotFoundError(p)
        self.engine = RapidOCR(
            params={
                "Global.log_level": "error",
                "Global.use_cls": False,
                "Global.text_score": text_score,
                # must be a str: rapidocr's own Path default breaks omegaconf on Windows
                "Global.model_root_dir": str(bundled),
                "Det.model_path": str(det),
                "Cls.model_path": str(cls),
                "Rec.model_path": str(rec_model),
                "Rec.lang_type": LangRec.KOREAN,
                "Rec.ocr_version": OCRVersion.PPOCRV5,
                "Rec.model_type": ModelType.MOBILE,
            }
        )

    def __call__(self, img: np.ndarray) -> list[TextBox]:
        out: Any = self.engine(img)
        boxes = getattr(out, "boxes", None)
        if boxes is None:
            return []
        result = []
        for box, text, score in zip(boxes, out.txts, out.scores, strict=False):
            pts = np.asarray(box)
            result.append(
                TextBox(
                    float(pts[:, 0].min()),
                    float(pts[:, 1].min()),
                    float(pts[:, 0].max()),
                    float(pts[:, 1].max()),
                    str(text).strip(),
                    float(score),
                )
            )
        return result


def _ink_mask(gray: np.ndarray) -> np.ndarray:
    """Dark-on-light ink mask; inverts dark-mode screenshots."""
    if gray.mean() < 128:
        gray = 255 - gray
    thresh = min(160.0, float(gray.mean()) - 40.0)
    return gray < thresh


def _runs(flags: np.ndarray, max_gap: int) -> list[tuple[int, int]]:
    """[start, end) runs of True, merging runs separated by gaps <= max_gap."""
    idx = np.flatnonzero(flags)
    if idx.size == 0:
        return []
    runs = []
    start = prev = int(idx[0])
    for i in idx[1:]:
        i = int(i)
        if i - prev > max_gap + 1:
            runs.append((start, prev + 1))
            start = i
        prev = i
    runs.append((start, prev + 1))
    return runs


@dataclass
class _Item:
    x: float
    text: str
    is_math: bool


def _clean_ocr_math(text: str) -> str:
    t = text.replace("×", "\\times ").replace("÷", "\\div ").replace("−", "-").replace("：", ":")
    t = t.replace("X", "x").replace("Y", "y")  # the Korean model often reads variables in caps
    return t.strip()


def _parses(latex: str) -> bool:
    plain = to_plain(latex)
    if plain is None or HANGUL.search(plain):
        return False
    segs = split_top(plain, ",;")
    if not segs:
        return False
    for seg in segs:
        if has_relation(seg):
            from studymate.verify.problem import parse_relations

            if parse_relations(seg) is None:
                return False
        elif parse_math(seg) is None:
            return False
    return True


_PIX2TEX_FIXES = [
    (re.compile(r"\\chi(?![A-Za-z])"), "x"),  # frequent x/chi confusion
    (re.compile(r"\\(?:mathrm|mathit|operatorname|mathbf)\s*\{\s*([^{}]*)\}"), r"\1"),
    (re.compile(r"\\(?:mathbf|mathrm|mathit|boldsymbol)(?![A-Za-z])"), ""),
    (re.compile(r"\\(?:[ ,;:!]|quad|qquad)|~"), " "),
    (re.compile(r"\\(?:displaystyle|textstyle|scriptstyle)(?![A-Za-z])"), ""),
]


def _clean_pix2tex(latex: str) -> str:
    s = latex.strip()
    for pattern, rep in _PIX2TEX_FIXES:
        s = pattern.sub(rep, s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" ,.")


def _single_row(parts: list[TextBox], line_h: float) -> bool:
    """True when OCR boxes of a region sit on one text row (no stacked fraction)."""
    if len(parts) < 2:
        return True
    cys = sorted(b.cy for b in parts)
    return cys[-1] - cys[0] < line_h * 0.5


_OPS = "+-=<>"


def _signature(latex: str) -> Counter[str] | None:
    """Letters, digits and + - = < > of a reading, independent of layout (fraction, exponent)."""
    plain = to_plain(latex)
    if plain is None:
        return None
    plain = re.sub(r"sqrt|root|Abs|pi", " ", plain).replace("**", " ")
    return Counter(c for c in plain if c.isascii() and (c.isalnum() or c in _OPS))


def _consistent(pix: str, ocr_text: str) -> bool:
    """pix2tex agrees with line OCR: everything line OCR saw is in the pix2tex reading.
    Line OCR often misses isolated small glyphs (a lone '9', '=' or a denominator), so it
    may see less, but at least half of the letters/digits."""
    a, b = _signature(pix), _signature(ocr_text)
    if a is None or b is None or not b:
        return False
    if any(b[k] > a[k] for k in b):
        return False
    alnum_a = sum(v for k, v in a.items() if k not in _OPS)
    alnum_b = sum(v for k, v in b.items() if k not in _OPS)
    return alnum_b >= max(1, alnum_a / 2)


def _parses_fragment(latex: str) -> bool:
    """A formula piece cut out of a Korean sentence ("- 2) = 2x +") parses once dangling
    operators and unmatched parentheses at its ends are removed."""
    if _parses(latex):
        return True
    plain = to_plain(latex)
    if plain is None or HANGUL.search(plain):
        return False
    s = plain.strip(" +-*/=<>")
    depth, kept = 0, []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                continue
            depth -= 1
        kept.append(ch)
    s = "".join(kept).strip(" +-*/=<>")
    while depth > 0 and "(" in s:
        i = s.rfind("(")
        s = (s[:i] + s[i + 1 :]).strip(" +-*/=<>")
        depth -= 1
    return bool(s) and bool(re.search(r"[0-9A-Za-z]", s)) and _parses(s)


def _pix2tex_variants(img: Image.Image, box: tuple[int, int, int, int], margin: int) -> list[Image.Image]:
    x0, y0, x1, y1 = box
    crops = []
    for m in (margin, margin * 2):
        crops.append(
            img.crop((max(0, x0 - m), max(0, y0 - m), min(img.width, x1 + m), min(img.height, y1 + m)))
        )
    base = crops[0]
    for scale in (1.5, 0.7, 0.5, 1.2):
        size = (max(8, int(base.width * scale)), max(8, int(base.height * scale)))
        crops.append(base.resize(size, Image.Resampling.LANCZOS))
    return crops


def _read_region(
    img: Image.Image,
    box: tuple[int, int, int, int],
    parts: list[TextBox],
    line_h: float,
    math_ocr: Any | None,
) -> tuple[str, bool]:
    """(reading, confirmed): confirmed when pix2tex and line OCR agree on the characters."""
    ocr_text = _clean_ocr_math(" ".join(b.text for b in sorted(parts, key=lambda b: b.x0)))
    single_row = bool(ocr_text) and _single_row(parts, line_h)
    fallback = ""
    if math_ocr is not None:
        for crop in _pix2tex_variants(img, box, max(4, int(line_h * 0.3))):
            try:
                latex = _clean_pix2tex(math_ocr(crop))
            except Exception:
                log.warning("pix2tex failed on a region", exc_info=True)
                continue
            if not latex or not _parses_fragment(latex):
                continue
            if _consistent(latex, ocr_text):
                return latex, True
            if _parses(latex):
                fallback = fallback or latex
            if single_row and _parses(ocr_text):
                break  # line OCR has a clean reading; no need for more pix2tex attempts
    if single_row and _parses(ocr_text):
        return ocr_text, math_ocr is None
    if fallback:
        return fallback, False
    return (ocr_text if single_row else ocr_text or ""), False


def read_image(img: Image.Image, text_ocr: TextOcr, math_ocr: Any | None) -> list[str]:
    """Reads a problem image into lines of Korean text with inline LaTeX math."""
    return read_image_detailed(img, text_ocr, math_ocr)[0]


def read_image_detailed(img: Image.Image, text_ocr: TextOcr, math_ocr: Any | None) -> tuple[list[str], bool]:
    """(lines, uncertain): uncertain when some formula was not confirmed by both OCR engines."""
    rgb = np.asarray(img.convert("RGB"))
    boxes = [b for b in text_ocr(rgb) if b.text]
    gray = np.asarray(img.convert("L")).astype(np.float32)
    ink = _ink_mask(gray)
    hangul_boxes = [b for b in boxes if b.hangul]
    heights = [b.h for b in hangul_boxes] or [b.h for b in boxes] or [24.0]
    line_h = float(np.median(heights))

    masked = ink.copy()
    formula_img = img.convert("RGB")  # Korean text whited out, so formula crops never include it
    painter = ImageDraw.Draw(formula_img)
    pad = max(2, int(line_h * 0.08))
    for b in hangul_boxes:
        masked[max(0, int(b.y0) - pad) : int(b.y1) + pad, max(0, int(b.x0) - pad) : int(b.x1) + pad] = False
        painter.rectangle((b.x0 - pad, b.y0 - pad, b.x1 + pad, b.y1 + pad), fill=(255, 255, 255))

    # rows of remaining ink -> bands (a stacked fraction stays in one band)
    bands = _runs(masked.sum(axis=1) > 0, max_gap=max(2, int(line_h * 0.3)))
    lines: list[tuple[float, list[_Item]]] = []
    used: set[int] = set()
    uncertain = False
    for y0, y1 in bands:
        if y1 - y0 < max(4, line_h * 0.25):
            continue  # specks, underlines
        cols = masked[y0:y1].sum(axis=0) > 0
        items: list[_Item] = []
        for x0, x1 in _runs(cols, max_gap=max(8, int(line_h * 1.6))):
            if x1 - x0 < 4:
                continue
            ocr_parts = [
                (i, b)
                for i, b in enumerate(boxes)
                if not b.hangul and b.x1 > x0 and b.x0 < x1 and b.y1 > y0 and b.y0 < y1
            ]
            used.update(i for i, _ in ocr_parts)
            parts = [b for _, b in ocr_parts]
            chosen, confirmed = _read_region(formula_img, (x0, y0, x1, y1), parts, line_h, math_ocr)
            if chosen:
                uncertain = uncertain or not confirmed
                items.append(_Item(float(x0), chosen, True))
        if items:
            lines.append(((y0 + y1) / 2, items))

    for i, b in enumerate(boxes):
        if b.hangul:
            lines.append((b.cy, [_Item(b.x0, b.text, False)]))
        elif i not in used and b.score > 0.6:
            lines.append((b.cy, [_Item(b.x0, _clean_ocr_math(b.text), True)]))

    # merge items whose vertical centres are close into one reading line
    lines.sort(key=lambda p: p[0])
    merged: list[tuple[float, list[_Item]]] = []
    for cy, items in lines:
        if merged and abs(merged[-1][0] - cy) < line_h * 0.6:
            merged[-1][1].extend(items)
        else:
            merged.append((cy, list(items)))
    out = []
    for _, items in merged:
        items.sort(key=lambda it: it.x)
        out.append(" ".join(it.text for it in items).strip())
    return [ln for ln in out if ln], uncertain
