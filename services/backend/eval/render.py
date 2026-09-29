"""Renders a problem ("Korean text $LaTeX$ ...") to a PNG like a textbook/worksheet line.

A tiny layout engine for the LaTeX subset used by the evaluation set: \\frac (stacked),
^ superscripts, \\sqrt, \\times, \\div, \\le, \\ge, \\pm and parentheses. Lines are
separated by newlines. Only PIL is used.
"""

from __future__ import annotations

import io
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_REPO = Path(__file__).resolve().parents[3]
FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/malgun.ttf"),
    _REPO / "apps/shell/src/renderer/assets/fonts/Jua-Regular.ttf",
]
# Typeset math look (serif, italic variables) like printed worksheets; Korean font as fallback.
MATH_FONT = Path("C:/Windows/Fonts/times.ttf")
MATH_ITALIC_FONT = Path("C:/Windows/Fonts/timesi.ttf")
_SYMBOLS = {
    "times": "×",
    "div": "÷",
    "le": "≤",
    "leq": "≤",
    "ge": "≥",
    "geq": "≥",
    "pm": "±",
    "cdot": "·",
    "left": "",
    "right": "",
    "quad": "   ",
    ",": " ",
    ";": " ",
    " ": " ",
}

DrawFn = Callable[[ImageDraw.ImageDraw, float, float], None]


@dataclass
class Box:
    w: float
    asc: float
    desc: float
    draw: DrawFn


def font_path() -> Path:
    for p in FONT_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError("no Korean TTF font found")


class _Fonts:
    def __init__(self, path: Path) -> None:
        self.paths = {
            "text": path,
            "math": MATH_FONT if MATH_FONT.exists() else path,
            "var": MATH_ITALIC_FONT if MATH_ITALIC_FONT.exists() else path,
        }
        self._cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}

    def get(self, size: float, kind: str = "text") -> ImageFont.FreeTypeFont:
        key = (kind, max(8, int(size)))
        if key not in self._cache:
            self._cache[key] = ImageFont.truetype(str(self.paths[kind]), key[1])
        return self._cache[key]


def _tokenize(s: str) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            j = i + 1
            while j < len(s) and s[j].isalpha():
                j += 1
            if j == i + 1 and j < len(s):
                j += 1
            out.append(s[i:j])
            i = j
        else:
            out.append(c)
            i += 1
    return out


def _group(tokens: list[str], i: int) -> tuple[list[str], int]:
    if i < len(tokens) and tokens[i] == "{":
        depth, j = 0, i
        while j < len(tokens):
            if tokens[j] == "{":
                depth += 1
            elif tokens[j] == "}":
                depth -= 1
                if depth == 0:
                    return tokens[i + 1 : j], j + 1
            j += 1
        return tokens[i + 1 :], len(tokens)
    return tokens[i : i + 1], i + 1


def _text_box(fonts: _Fonts, text: str, size: float, kind: str = "text") -> Box:
    font = fonts.get(size, kind)
    asc, desc = font.getmetrics()
    w = font.getlength(text)

    def draw(d: ImageDraw.ImageDraw, x: float, base: float) -> None:
        d.text((x, base), text, font=font, fill=(20, 20, 20), anchor="ls")

    return Box(w, asc * 0.8, desc * 0.6, draw)


def _hbox(boxes: list[Box]) -> Box:
    w = sum(b.w for b in boxes)
    asc = max((b.asc for b in boxes), default=0.0)
    desc = max((b.desc for b in boxes), default=0.0)

    def draw(d: ImageDraw.ImageDraw, x: float, base: float) -> None:
        for b in boxes:
            b.draw(d, x, base)
            x += b.w

    return Box(w, asc, desc, draw)


def _layout(fonts: _Fonts, tokens: list[str], size: float) -> Box:
    boxes: list[Box] = []
    buf: list[str] = []
    i = 0

    def flush() -> None:
        if buf:
            for run in re.findall(r"[A-Za-z]+|[^A-Za-z]+", "".join(buf)):
                boxes.append(_text_box(fonts, run, size, "var" if run[0].isalpha() else "math"))
            buf.clear()

    while i < len(tokens):
        t = tokens[i]
        if t in ("\\frac", "\\dfrac"):
            flush()
            num, i = _group(tokens, i + 1)
            den, i = _group(tokens, i)
            boxes.append(_frac(fonts, num, den, size))
            continue
        if t == "\\sqrt":
            flush()
            arg, i = _group(tokens, i + 1)
            boxes.append(_sqrt(fonts, arg, size))
            continue
        if t == "^":
            flush()
            exp, i = _group(tokens, i + 1)
            boxes.append(_sup(fonts, exp, size))
            continue
        if t in ("{", "}"):
            i += 1
            continue
        if t.startswith("\\"):
            buf.append(_SYMBOLS.get(t[1:], ""))
        elif t in "+=<>":
            buf.append(f" {t} ")
        elif t == "-":
            prev = "".join(buf).strip()
            # typeset minus sign (U+2212), as in printed worksheets; a hyphen reads like a dot
            buf.append(" − " if (prev and prev[-1] not in "(=<>") or (not prev and boxes) else "−")
        else:
            buf.append(t)
        i += 1
    flush()
    return _hbox(boxes)


def _frac(fonts: _Fonts, num: list[str], den: list[str], size: float) -> Box:
    n = _layout(fonts, num, size * 0.85)
    dn = _layout(fonts, den, size * 0.85)
    pad = size * 0.12
    w = max(n.w, dn.w) + 2 * pad
    axis = size * 0.3
    gap = size * 0.12
    asc = axis + gap + n.asc + n.desc
    desc = -axis + gap + dn.asc + dn.desc

    def draw(d: ImageDraw.ImageDraw, x: float, base: float) -> None:
        bar_y = base - axis
        n.draw(d, x + (w - n.w) / 2, bar_y - gap - n.desc)
        dn.draw(d, x + (w - dn.w) / 2, bar_y + gap + dn.asc)
        d.line(
            [(x + pad * 0.3, bar_y), (x + w - pad * 0.3, bar_y)],
            fill=(20, 20, 20),
            width=max(2, int(size / 18)),
        )

    return Box(w, asc, max(desc, 0.0), draw)


def _sup(fonts: _Fonts, exp: list[str], size: float) -> Box:
    e = _layout(fonts, exp, size * 0.6)
    rise = size * 0.42

    def draw(d: ImageDraw.ImageDraw, x: float, base: float) -> None:
        e.draw(d, x + size * 0.03, base - rise)

    return Box(e.w + size * 0.06, rise + e.asc, 0.0, draw)


def _sqrt(fonts: _Fonts, arg: list[str], size: float) -> Box:
    a = _layout(fonts, arg, size)
    sign = _text_box(fonts, "√", size * 1.05)

    def draw(d: ImageDraw.ImageDraw, x: float, base: float) -> None:
        sign.draw(d, x, base)
        a.draw(d, x + sign.w, base)
        top = base - a.asc - size * 0.08
        d.line(
            [(x + sign.w * 0.85, top), (x + sign.w + a.w, top)],
            fill=(20, 20, 20),
            width=max(2, int(size / 20)),
        )

    return Box(sign.w + a.w, a.asc + size * 0.12, a.desc, draw)


def _line_box(fonts: _Fonts, line: str, size: float) -> Box:
    parts = line.split("$")
    boxes: list[Box] = []
    for k, part in enumerate(parts):
        if not part:
            continue
        if k % 2 == 0:
            boxes.append(_text_box(fonts, part, size))
        else:
            boxes.append(_layout(fonts, _tokenize(part), size))
    return _hbox(boxes)


def render_problem(text: str, size: int = 40, margin: int = 36) -> Image.Image:
    fonts = _Fonts(font_path())
    lines = [ln for ln in text.split("\n") if ln.strip()]
    boxes = [_line_box(fonts, ln, size) for ln in lines]
    spacing = size * 0.7
    width = int(max(b.w for b in boxes) + 2 * margin)
    height = int(sum(b.asc + b.desc for b in boxes) + spacing * (len(boxes) - 1) + 2 * margin)
    img = Image.new("RGB", (width, height), (255, 255, 255))
    d = ImageDraw.Draw(img)
    y = float(margin)
    for b in boxes:
        base = y + b.asc
        b.draw(d, margin, base)
        y = base + b.desc + spacing
    return img


def render_png(text: str, size: int = 40) -> bytes:
    buf = io.BytesIO()
    render_problem(text, size).save(buf, format="PNG")
    return buf.getvalue()
