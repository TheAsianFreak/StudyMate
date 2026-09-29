"""JSON schemas that constrain every LLM output of solve / ask / quiz (CLAUDE.md rule 6),
plus conversion of the constrained output into protocol `ScriptStep`s."""

from __future__ import annotations

import re
from typing import Any

from studymate.protocol.backend import Mark, ScriptStep
from studymate.verify.latex import HANGUL, repair_escapes

GESTURES = ["write", "point", "nod", "tap_desk", "idle"]
ROLES = ["intro", "concept", "solve", "check", "summary"]
NOTE_MAX = 24
EMOTIONS = ["neutral", "happy", "surprised"]
SAY_MAX = 240  # English needs more characters than Korean or Japanese for the same sentence
WRITE_MAX = 160
ANSWER_MAX = 120


def step_schema(*, write: bool = True, mark: bool = True, note: bool = False) -> dict[str, Any]:
    props: dict[str, Any] = {}
    required: list[str] = []
    props["say"] = {"type": "string", "minLength": 2, "maxLength": SAY_MAX}
    required.append("say")
    if write:
        props["write"] = {"type": "string", "maxLength": WRITE_MAX}
        required.append("write")
        if note:
            props["note"] = {"type": "string", "maxLength": NOTE_MAX}
            required.append("note")
    props["gesture"] = {"enum": GESTURES if write else [g for g in GESTURES if g != "write"]}
    props["emotion"] = {"enum": EMOTIONS}
    required += ["gesture", "emotion"]
    if write and mark:
        props["mark"] = {
            "type": "object",
            "properties": {
                "type": {"enum": ["circle", "underline", "arrow"]},
                "target": {"type": "string", "minLength": 1, "maxLength": 40},
            },
            "required": ["type", "target"],
            "additionalProperties": False,
        }
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


def steps_schema(
    min_items: int, max_items: int, *, write: bool = True, mark: bool = True, note: bool = False
) -> dict[str, Any]:
    return {
        "type": "array",
        "items": step_schema(write=write, mark=mark, note=note),
        "minItems": min_items,
        "maxItems": max_items,
    }


def answer_schema() -> dict[str, Any]:
    return {"type": "string", "minLength": 1, "maxLength": ANSWER_MAX}


SOLVE_LINES_MAX = 8

# A lesson in fixed slots (the order a teacher follows), so a long working can never crowd
# out the check or the summary. final_answer last so the working comes first.
# lesson_steps() flattens it into role-tagged ScriptSteps.
ANALYSIS_MAX = 2400


def solve_schema(*, analysis: bool = False) -> dict[str, Any]:
    """The lesson slots; with `analysis`, a scratch field comes first where the model works
    the problem out (option by option, calculation to the end) before the lesson. The final
    answer stays last, written from the lesson: putting it right after the scratch work cost
    first-attempt accuracy on CSAT math (truncated scratch work -> partial answers). The
    scratch work is never shown or spoken."""
    props: dict[str, Any] = {}
    if analysis:
        props["analysis"] = {"type": "string", "minLength": 20, "maxLength": ANALYSIS_MAX}
    props |= {
        "problem_latex": {"type": "string", "maxLength": 400},
        "intro": step_schema(note=True),
        "concept": step_schema(note=True),
        "solve": steps_schema(1, SOLVE_LINES_MAX, note=True),
        "check": step_schema(note=True),
        "summary": step_schema(note=True),
        "final_answer": answer_schema(),
    }
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


SOLVE_SCHEMA: dict[str, Any] = solve_schema()

# Reasoning pass (thinking mode): the thinking itself comes back apart from this content.
THINK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "outline": {"type": "string", "maxLength": 1500},
        "final_answer": answer_schema(),
    },
    "required": ["outline", "final_answer"],
    "additionalProperties": False,
}

RESOLVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "work": {"type": "string", "maxLength": 900},
        "final_answer": answer_schema(),
    },
    "required": ["work", "final_answer"],
    "additionalProperties": False,
}


_EMOJI = re.compile("[\U0001f000-\U0001faff\u2600-\u27bf\ufe0f\u200d]+")
_STYLE = re.compile(r"\\(?:textit|textbf|mathit|mathbf|emph)\s*\{([^{}]*)\}")
_WHOLE_TEXT = re.compile(r"^\\text\s*\{(.*)\}$", re.S)


def clean_say(say: Any) -> str:
    """Spoken line for TTS: no emoji."""
    return re.sub(r"\s{2,}", " ", _EMOJI.sub("", str(say))).strip()


def _clean_write(write: Any) -> str | None:
    if not isinstance(write, str):
        return None
    w = repair_escapes(write).strip()
    if w.startswith("$$") and w.endswith("$$") and len(w) > 4:
        w = w[2:-2]
    elif w.startswith("$") and w.endswith("$") and len(w) > 2:
        w = w[1:-1]
    for _ in range(3):
        w = _STYLE.sub(r"\1", w)
    m = _WHOLE_TEXT.match(w.strip())
    if m and "\\" in m.group(1) and not HANGUL.search(m.group(1)):
        w = m.group(1)  # math wrapped in \text{} does not render in KaTeX
    w = _wrap_bare_hangul(_balance_braces(w)).strip()
    if "\\" not in w and _ENGLISH_PROSE.search(w) and not re.search(r"[=<>^_{}]", w):
        w = "\\text{" + w + "}"  # an English sentence in math mode renders as italic run-on letters
    return w or None


def _balance_braces(w: str) -> str:
    """Drops unmatched closing braces and closes open ones ("\\text{호흡 }}" breaks KaTeX)."""
    out: list[str] = []
    depth = 0
    for i, ch in enumerate(w):
        escaped = i > 0 and w[i - 1] == "\\"
        if ch == "{" and not escaped:
            depth += 1
        elif ch == "}" and not escaped:
            if depth == 0:
                continue
            depth -= 1
        out.append(ch)
    return "".join(out) + "}" * depth


_TEXT_GROUP = re.compile(r"\\text\s*\{[^{}]*\}")
_ENGLISH_PROSE = re.compile(r"[A-Za-z]{3,}\s+[A-Za-z]{2,}\s+[A-Za-z]{2,}")
# Korean or Japanese prose (kana, kanji, Japanese punctuation) outside \text{}.
_CJK_CHARS = "\uac00-\ud7a3\u3131-\u318e\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff"
_BARE_HANGUL = re.compile(f"[{_CJK_CHARS}][{_CJK_CHARS}\\s.,!?~\u3001\u3002\u300c\u300d\uff08\uff09]*")


def _wrap_bare_hangul(w: str) -> str:
    """Korean outside \\text{} is not valid KaTeX math: wrap each run (spaces kept inside,
    since math mode drops them)."""

    def wrap(segment: str) -> str:
        def one(h: re.Match[str]) -> str:
            core = h.group(0).rstrip()
            before = " " if h.start() > 0 else ""
            after = " " if h.start() + len(core) < len(segment) else ""
            return "\\text{" + before + core + after + "}"

        # keep a LaTeX escaped space ("\ ") at the end: dropping it glues "\" to the next command
        return re.sub(r"(?<!\\)\s+$", "", _BARE_HANGUL.sub(one, segment)) if segment.strip() else segment

    out, last = [], 0
    for m in _TEXT_GROUP.finditer(w):
        out.append(wrap(w[last : m.start()]))
        out.append(m.group(0))
        last = m.end()
    out.append(wrap(w[last:]))
    return "".join(out)


# "① + ②: 3x = 9" — equation labels belong in the margin note, not in the working line.
_EQ_LABEL = re.compile(r"^\s*([①-⑳][^:=]*?)\s*:\s*(?=\S)")


def _split_label(write: Any) -> tuple[str, Any]:
    if isinstance(write, str) and (m := _EQ_LABEL.match(write)):
        return m.group(1), write[m.end() :]
    return "", write


def to_steps(raw_steps: Any) -> list[ScriptStep]:
    """Constrained LLM step dicts -> ScriptSteps (drops empty lines and marks not in the line)."""
    steps: list[ScriptStep] = []
    if not isinstance(raw_steps, list):
        return steps
    for raw in raw_steps:
        if not isinstance(raw, dict):
            continue
        say = clean_say(raw.get("say", ""))
        if not say:
            continue
        label, write_raw = _split_label(raw.get("write"))
        write = _clean_write(write_raw)
        mark = None
        m = raw.get("mark")
        if write and isinstance(m, dict) and m.get("type") in ("circle", "underline", "arrow"):
            target = repair_escapes(str(m.get("target", ""))).strip()
            if target and target in write:
                mark = Mark(type=m["type"], target=target)
        gesture = raw.get("gesture") if raw.get("gesture") in GESTURES else None
        emotion = raw.get("emotion") if raw.get("emotion") in EMOTIONS else None
        role = raw.get("role") if raw.get("role") in ROLES else None
        note = clean_say(raw.get("note", "") or label)[:NOTE_MAX] or None
        steps.append(
            ScriptStep(
                say=say, write=write, mark=mark, gesture=gesture, emotion=emotion, role=role, note=note
            )
        )
    return steps


def lesson_steps(raw: dict[str, Any]) -> list[ScriptStep]:
    """SOLVE_SCHEMA output (one slot per role, a list for the working) -> role-tagged steps."""
    items: list[dict[str, Any]] = []
    for role in ROLES:
        slot = raw.get(role)
        for item in slot if isinstance(slot, list) else [slot]:
            if isinstance(item, dict):
                items.append({**item, "role": role})
    return to_steps(items)


def solve_line_indices(steps: list[ScriptStep]) -> list[int]:
    """Indices of the steps whose board line is working SymPy must verify. Concept, check and
    summary lines state rules, substitutions or takeaways, not equivalent forms of the problem.
    Scripts without roles (older prompts, ask/quiz) verify every line."""
    if not any(s.role for s in steps):
        return list(range(len(steps)))
    return [i for i, s in enumerate(steps) if s.role in ("solve", None)]
