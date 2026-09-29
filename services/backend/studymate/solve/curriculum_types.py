"""Curriculum unit types (see curriculum.py; unit ids are shared by all languages)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple


@dataclass(frozen=True)
class Unit:
    id: str
    grade: str
    name: str
    examples: str  # typical problem shapes, for the classifier
    concept: str  # the key idea to recall in the concept step
    method: tuple[str, ...]  # textbook solution order
    notation: str = ""
    pitfalls: str = ""
    check: str = "구한 답을 처음 식에 대입해 성립하는지 확인한다."
    # "math" units get the equation-style lesson and SymPy checks; other CSAT subjects
    # (curriculum_csat.py) get the evidence-style lesson (passage/data → options → answer).
    subject: str = "math"

    @property
    def label(self) -> str:
        return f"{self.grade} · {self.name}"

    @property
    def is_math(self) -> bool:
        return self.subject == "math"


class UnitText(NamedTuple):
    grade: str
    name: str
    examples: str
    concept: str
    method: tuple[str, ...]
    notation: str = ""
    pitfalls: str = ""
    check: str = ""
