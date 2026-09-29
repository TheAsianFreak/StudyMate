"""Phoneme sentences with lip-sync units, shared by the ja/en Kokoro frontends.

A frontend turns text into `Sentence`s: the model's phoneme string plus `Unit`s (a kana
mora in Japanese, a syllable-sized phoneme group in English) that point into it. The
engine packs sentences into model-sized chunks and turns unit spans into timings.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VOWELS = ("a", "i", "u", "e", "o", "n")


@dataclass
class Unit:
    char: str  # what `PhonemeTiming.char` reports
    vowel: str | None  # one of VOWELS; None = no mouth shape
    start: int  # phoneme index (inclusive) in the owning sentence/chunk
    end: int  # exclusive


@dataclass
class Sentence:
    phonemes: str
    units: list[Unit] = field(default_factory=list)
    text: str = ""


def shifted(units: list[Unit], offset: int) -> list[Unit]:
    return [Unit(u.char, u.vowel, u.start + offset, u.end + offset) for u in units]


def split_long(sentence: Sentence, max_len: int) -> list[Sentence]:
    """Cuts a sentence longer than `max_len` phonemes at spaces (never inside a unit)."""
    out: list[Sentence] = []
    ps, units = sentence.phonemes, list(sentence.units)
    while len(ps) > max_len:
        cut = ps.rfind(" ", 0, max_len)
        # prefer a pause (comma) in the second half of the window
        comma = max(ps.rfind(", ", 0, max_len), ps.rfind("、", 0, max_len))
        if comma > max_len // 2:
            cut = comma + 1
        if cut <= 0 or any(u.start < cut < u.end for u in units):
            cut = next((u.start for u in units if u.end > max_len and u.start > 0), max_len)
        head = [u for u in units if u.end <= cut]
        out.append(Sentence(ps[:cut].rstrip(), head))
        rest = ps[cut:]
        strip = len(rest) - len(rest.lstrip())
        units = shifted([u for u in units if u.start >= cut], -(cut + strip))
        ps = rest.lstrip()
    if ps:
        out.append(Sentence(ps, units))
    return out


def pack(sentences: list[Sentence], max_len: int) -> list[Sentence]:
    """Joins consecutive sentences (space-separated) into chunks of at most `max_len`
    phonemes: Kokoro sounds best on 100-300 tokens and weak on very short inputs."""
    chunks: list[Sentence] = []
    for sentence in sentences:
        for part in split_long(sentence, max_len):
            if chunks and len(chunks[-1].phonemes) + 1 + len(part.phonemes) <= max_len:
                last = chunks[-1]
                offset = len(last.phonemes) + 1
                chunks[-1] = Sentence(
                    last.phonemes + " " + part.phonemes, last.units + shifted(part.units, offset)
                )
            else:
                chunks.append(part)
    return chunks
