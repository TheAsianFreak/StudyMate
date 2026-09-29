from __future__ import annotations

from studymate.solve.schema import SOLVE_SCHEMA, lesson_steps


def _line(write: str, note: str = "") -> dict[str, str]:
    return {"say": "설명해요.", "write": write, "note": note, "gesture": "write", "emotion": "neutral"}


def test_lesson_slots_flatten_in_teaching_order() -> None:
    raw = {
        "intro": _line("x + y = 3"),
        "concept": _line("가감법"),
        "solve": [_line("3x = 9", "①+②"), _line("x = 3", "양변 ÷ 3")],
        "check": _line("3 + 0 = 3", "검산"),
        "summary": _line("정리"),
    }
    steps = lesson_steps(raw)
    assert [s.role for s in steps] == ["intro", "concept", "solve", "solve", "check", "summary"]
    assert SOLVE_SCHEMA["required"][1:-1] == ["intro", "concept", "solve", "check", "summary"]


def test_equation_label_moves_from_line_to_note() -> None:
    steps = lesson_steps({"solve": [_line("① + ②: 3x = 9"), _line("②: x - y = 2", "② 정리")]})
    assert steps[0].write == "3x = 9" and steps[0].note == "① + ②"
    # the model's own note wins over the stripped label
    assert steps[1].write == "x - y = 2" and steps[1].note == "② 정리"
