"""Text clean-up and chunking for imported documents.

Pipeline: raw page text -> `normalize_text` (Unicode/Korean fixes) -> repeated header,
footer and page-number removal across pages -> paragraphs (PDF line breaks are layout,
not meaning) -> sentence units -> chunks of at most `chunk_chars` per page.

Chunks never span pages so every chunk has one page number. When a paragraph has to be
split, the next chunk repeats the last sentence(s) of the previous one (up to
`overlap` chars); a chunk that starts at a paragraph boundary gets no overlap.
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from collections import Counter
from dataclasses import dataclass

# Fullwidth ASCII (common in Korean documents) -> ASCII, ideographic space -> space.
_WIDTH_TABLE: dict[int, int | str] = {code: code - 0xFEE0 for code in range(0xFF01, 0xFF5F)}
_WIDTH_TABLE[0x3000] = " "
_WIDTH_TABLE.update(
    {
        0xFB00: "ff",
        0xFB01: "fi",
        0xFB02: "fl",
        0xFB03: "ffi",
        0xFB04: "ffl",
        0x2018: "'",
        0x2019: "'",
        0x201C: '"',
        0x201D: '"',
        0x00A0: " ",
        0x2002: " ",
        0x2003: " ",
        0x2009: " ",
        0x202F: " ",
    }
)
# Zero-width / soft-hyphen / BOM / private-use (unmapped symbol-font glyphs).
_INVISIBLE = re.compile("[­​-‍⁠﻿-￾￿]")
_CONTROL = re.compile(r"[\x00-\x01\x03-\x08\x0b\x0c\x0e-\x1f\x7f]")  # keeps \x02 (pdfium hyphen mark)
_SPACES = re.compile(r"[ \t]+")

_PAGE_NUMBER = re.compile(
    r"^(?:[-–—\s]*\d{1,4}[-–—\s]*|\d{1,4}\s*/\s*\d{1,4}|(?:p\.?|page)\s*\d{1,4}|\d{1,4}\s*쪽|-\s*\d{1,4}\s*-)$",
    re.IGNORECASE,
)
_BLOCK_START = re.compile(
    r"^(?:[-•·▪■□◆◇○●※▶►◦*]\s"
    r"|\(?\d{1,2}[.)]\s"
    r"|\(?[가-하][.)]\s"
    r"|[①-⑳]"
    r"|[ⅰ-ⅹⅠ-Ⅹ][.)]?\s"
    r"|제\s*\d+\s*[장절항편부]"
    r"|\d+(?:\.\d+)+\s"
    r"|\[[^\]]{1,20}\]"
    r"|(?:예제|문제|정리|정의|증명|풀이|참고|보기|예시|유형|공식|Example|Theorem|Definition|Proof|Lemma)\b)"
)
_SENTENCE_END = re.compile(r"[.!?。？！…:]['\")\]]*$")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。？！…])\s+|(?<=[.!?。？！…]['\")\]])\s+")
_SINGLE_SYLLABLE = re.compile(r"^[가-힣]$")


@dataclass(frozen=True)
class Chunk:
    page: int  # 1-based
    ord: int
    text: str


def normalize_text(text: str) -> str:
    """Unicode clean-up: composes decomposed Hangul (NFC), folds fullwidth forms and
    ligatures, drops invisible/control characters and unifies line endings."""
    text = unicodedata.normalize("NFC", text)
    text = text.translate(_WIDTH_TABLE)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    text = _INVISIBLE.sub("", text)
    return _CONTROL.sub("", text)


def _fix_spaced_hangul(line: str) -> str:
    """Undoes letter-spaced Korean ("이 차 방 정 식 의 근") that justified layouts produce."""
    tokens = line.split(" ")
    if len(tokens) < 8:
        return line
    singles = sum(1 for t in tokens if _SINGLE_SYLLABLE.match(t))
    if singles / len(tokens) < 0.85:
        return line
    out: list[str] = []
    for tok in tokens:
        if out and _SINGLE_SYLLABLE.match(tok) and re.search(r"[가-힣]$", out[-1]):
            out[-1] += tok
        else:
            out.append(tok)
    return " ".join(out)


def page_lines(raw: str) -> list[str]:
    lines = []
    for line in normalize_text(raw).split("\n"):
        line = _SPACES.sub(" ", line).strip()
        lines.append(_fix_spaced_hangul(line) if line else "")
    return lines


def strip_page_furniture(pages: list[list[str]]) -> list[list[str]]:
    """Removes page numbers and headers/footers repeated on many pages."""

    def edges(lines: list[str]) -> list[int]:
        """First/last line (two each on longer pages); short pages keep their body."""
        idx = [i for i, line in enumerate(lines) if line]
        k = 2 if len(idx) >= 6 else 1
        return sorted(set(idx[:k] + idx[-k:]))

    def key(line: str) -> str:
        return re.sub(r"\d+", "#", line)

    with_text = [p for p in pages if sum(1 for line in p if line) >= 3]
    counts: Counter[str] = Counter()
    for lines in with_text:
        counts.update({key(lines[i]) for i in edges(lines)})
    threshold = max(3, (len(with_text) + 1) // 2)
    repeated = {k for k, n in counts.items() if n >= threshold}

    out: list[list[str]] = []
    for lines in pages:
        lines = list(lines)
        for i in edges(lines):
            if _PAGE_NUMBER.match(lines[i]) or key(lines[i]) in repeated:
                lines[i] = ""
        out.append(lines)
    return out


def paragraphs(lines: list[str]) -> list[str]:
    """Joins layout lines into paragraphs."""
    lengths = [len(line) for line in lines if len(line) > 20]
    typical = statistics.median(lengths) if lengths else 0.0
    paras: list[str] = []
    cur = ""
    for line in lines:
        if not line:
            if cur:
                paras.append(cur)
            cur = ""
            continue
        if cur and _BLOCK_START.match(line):
            paras.append(cur)
            cur = ""
        cur = _join(cur, line) if cur else line
        if _SENTENCE_END.search(line) and typical and len(line) < 0.8 * typical:
            paras.append(cur)
            cur = ""
    if cur:
        paras.append(cur)
    return [p.replace("\x02", "") for p in paras if p.strip()]


def _join(cur: str, line: str) -> str:
    if cur.endswith("\x02"):  # pdfium marks a hyphenated line break with \x02
        return cur[:-1] + line
    if len(cur) >= 2 and cur[-1] == "-" and cur[-2].isascii() and cur[-2].isalpha() and line[:1].islower():
        return cur[:-1] + line
    return f"{cur} {line}"


def clean_document(raw_pages: list[str]) -> list[list[str]]:
    """Paragraphs per page (index 0 = page 1)."""
    return [paragraphs(lines) for lines in strip_page_furniture([page_lines(p) for p in raw_pages])]


def split_sentences(paragraph: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(paragraph) if s and s.strip()]


def _hard_split(text: str, limit: int) -> list[str]:
    pieces: list[str] = []
    while len(text) > limit:
        cut = text.rfind(" ", limit // 2, limit)
        if cut <= 0:
            cut = limit
        pieces.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        pieces.append(text)
    return pieces


def _tail(sentences: list[str], budget: int) -> list[str]:
    """Last whole sentences fitting in `budget` chars (or the end of the last one)."""
    out: list[str] = []
    used = 0
    for sent in reversed(sentences):
        extra = len(sent) + (1 if out else 0)
        if used + extra > budget:
            break
        out.insert(0, sent)
        used += extra
    if not out and sentences and budget > 0:
        last = sentences[-1][-budget:]
        cut = last.find(" ")
        last = last[cut + 1 :] if 0 <= cut < len(last) // 2 else last
        if last.strip():
            out = [last.strip()]
    return out


def chunk_page(paras: list[str], limit: int, overlap: int) -> list[str]:
    """Packs sentences into chunks of at most `limit` chars, preferring paragraph ends."""
    units: list[tuple[str, bool]] = []  # (text, starts a paragraph)
    for para in paras:
        first = True
        for sent in split_sentences(para):
            for piece in _hard_split(sent, limit):
                units.append((piece, first))
                first = False

    chunks: list[list[tuple[str, bool]]] = []
    cur: list[tuple[str, bool]] = []
    cur_len = 0

    def length(parts: list[tuple[str, bool]]) -> int:
        return sum(len(t) for t, _ in parts) + max(0, len(parts) - 1)

    for text, new_para in units:
        if cur:
            overflow = cur_len + 1 + len(text) > limit
            para_break = new_para and cur_len >= limit * 0.6
            if overflow or para_break:
                chunks.append(cur)
                seed: list[tuple[str, bool]] = []
                if not new_para and overlap > 0:
                    budget = min(overlap, limit - len(text) - 1)
                    seed = [(t, False) for t in _tail([t for t, _ in cur], budget)]
                    if seed:
                        seed[0] = (seed[0][0], True)
                cur = seed
                cur_len = length(cur)
        cur.append((text, new_para and bool(cur)))
        cur_len = length(cur)
    if cur:
        chunks.append(cur)

    rendered: list[str] = []
    for parts in chunks:
        out = ""
        for text, new_para in parts:
            out = text if not out else f"{out}{chr(10) if new_para else ' '}{text}"
        rendered.append(out)
    return rendered


def chunk_document(pages: list[list[str]], limit: int, overlap: int, min_chars: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page_no, paras in enumerate(pages, start=1):
        texts = chunk_page(paras, limit, overlap)
        if (
            len(texts) >= 2
            and _visible(texts[-1]) < min_chars
            and len(texts[-2]) + 1 + len(texts[-1]) <= limit
        ):
            texts[-2] = f"{texts[-2]}\n{texts.pop()}"
        for text in texts:
            if _visible(text) >= min_chars:
                chunks.append(Chunk(page=page_no, ord=len(chunks), text=text))
    return chunks


def _visible(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())
