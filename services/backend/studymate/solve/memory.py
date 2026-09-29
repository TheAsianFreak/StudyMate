"""The last solved problems, in memory only (never on disk), so a follow-up question works
from the full problem text instead of the shell's short summary of the lesson."""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass, replace

LIMIT = 20


@dataclass(frozen=True)
class SolvedProblem:
    text: str
    final_answer: str
    is_math: bool
    #: The answer the student gave from an answer key, once they corrected the teacher.
    corrected_answer: str | None = None

    @property
    def answer(self) -> str:
        return self.corrected_answer or self.final_answer


class SolvedProblems:
    def __init__(self, limit: int = LIMIT) -> None:
        self._items: OrderedDict[str, SolvedProblem] = OrderedDict()
        self._limit = limit
        self._lock = threading.Lock()

    def add(self, problem: SolvedProblem) -> str:
        problem_id = uuid.uuid4().hex
        with self._lock:
            self._items[problem_id] = problem
            while len(self._items) > self._limit:
                self._items.popitem(last=False)
        return problem_id

    def get(self, problem_id: str | None) -> SolvedProblem | None:
        if not problem_id:
            return None
        with self._lock:
            return self._items.get(problem_id)

    def correct(self, problem_id: str, answer: str) -> None:
        """Remembers the answer the student reported, for the next follow-up."""
        with self._lock:
            if (p := self._items.get(problem_id)) is not None:
                self._items[problem_id] = replace(p, corrected_answer=answer)
