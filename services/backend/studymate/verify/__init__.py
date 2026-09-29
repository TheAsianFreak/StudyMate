"""SymPy verification of solutions and answers (CLAUDE.md rule 5)."""

from studymate.verify.answer import Answer, answers_equivalent, normalize_text, parse_answer
from studymate.verify.check import VerifyResult, check_answer, check_steps, verify_answer, verify_solution
from studymate.verify.problem import ParsedProblem, analyze_problem, format_expected

__all__ = [
    "Answer",
    "ParsedProblem",
    "VerifyResult",
    "analyze_problem",
    "answers_equivalent",
    "check_answer",
    "check_steps",
    "format_expected",
    "normalize_text",
    "parse_answer",
    "verify_answer",
    "verify_solution",
]
