"""Korean text frontend for the MeloTTS Korean model.

- `normalize()` turns study content into speakable Hangul: LaTeX, numbers (sino/native
  Korean by counter), simple math (`=`, `+`, `x`, `^2`, fractions, inequalities), units,
  Greek letters and Latin letters/words.
- `g2p()` applies g2pkk's pronunciation rules per word *without* MeCab. We never build
  g2pkk's `G2p` object: it pip-installs `eunjeon` at runtime on Windows, and importing
  g2pkk tries to download NLTK cmudict. The import is guarded so it never touches the
  network; English words use the optional `g2p-cmudict` model when it is installed.
- `to_pieces()` splits sentences and maps them to model symbols, remembering which
  written syllable every phone belongs to (for lip-sync timings).
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from jamo import h2j, hangul_to_jamo

PUNCT = ".,!?…"
_HANGUL = re.compile(r"[가-힣]+")

# ---------------------------------------------------------------------------- g2p rules


class _Rules:
    """g2pkk rule modules, imported without triggering any network access."""

    def __init__(self) -> None:
        import nltk

        original = nltk.download

        def _no_download(*_: Any, **__: Any) -> bool:
            return False  # importing g2pkk.g2pkk calls nltk.download('cmudict') when missing

        nltk.download = _no_download
        try:
            from g2pkk import english, numerals, regular, special, utils
        finally:
            nltk.download = original
        self.special: ModuleType = special
        self.regular: ModuleType = regular
        self.utils: ModuleType = utils
        self.english: ModuleType = english
        self.numerals: ModuleType = numerals
        self.table: list[tuple[str, str, list[str]]] = utils.parse_table()
        self.idioms = _load_idioms(Path(utils.__file__).with_name("idioms.txt"))
        self.specials: tuple[Callable[..., str], ...] = (
            special.jyeo,
            special.ye,
            special.consonant_ui,
            special.josa_ui,
            special.vowel_ui,
            special.jamo,
            special.rieulgiyeok,
            special.rieulbieub,
            special.verb_nieun,
            special.balb,
            special.palatalize,
            special.modifying_rieul,
        )
        self.links: tuple[Callable[..., str], ...] = (
            regular.link1,
            regular.link2,
            regular.link3,
            regular.link4,
        )


def _load_idioms(path: Path) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.split("#")[0].strip()
        if "===" in line:
            a, b = line.split("===", 1)
            out.append((a, b))
    return out


_rules: _Rules | None = None
_rules_lock = threading.Lock()


def rules() -> _Rules:
    global _rules
    with _rules_lock:
        if _rules is None:
            _rules = _Rules()
        return _rules


def g2p(word: str) -> str:
    """Pronounced form of a Hangul word, one output syllable per input syllable."""
    r = rules()
    inp = h2j(word)
    for fn in r.specials:
        inp = fn(inp, False, False)
    inp = re.sub("/[PJEB]", "", inp)
    for pattern, repl, _ in r.table:
        inp = re.sub(pattern, repl, inp)
    for fn in r.links:
        inp = fn(inp, False, False)
    out: str = r.utils.compose(inp)
    return out if len(out) == len(word) and _HANGUL.fullmatch(out) else word


# ---------------------------------------------------------------------------- English


class Cmudict:
    """Lazy CMUdict (NLTK `corpora/cmudict` layout) for English -> Hangul transliteration."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._dict: dict[str, list[list[str]]] | None = None
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self.path is not None and self.path.is_file()

    def get(self) -> dict[str, list[list[str]]]:
        with self._lock:
            if self._dict is None:
                self._dict = {}
                if self.available:
                    assert self.path is not None
                    for line in self.path.read_text(encoding="latin-1").splitlines():
                        parts = line.split()
                        if len(parts) >= 3:
                            self._dict.setdefault(parts[0].lower(), []).append(parts[2:])
            return self._dict


LETTERS = {
    "a": "에이", "b": "비", "c": "씨", "d": "디", "e": "이", "f": "에프", "g": "지", "h": "에이치",
    "i": "아이", "j": "제이", "k": "케이", "l": "엘", "m": "엠", "n": "엔", "o": "오", "p": "피",
    "q": "큐", "r": "알", "s": "에스", "t": "티", "u": "유", "v": "브이", "w": "더블유", "x": "엑스",
    "y": "와이", "z": "제트",
}  # fmt: skip
FUNCS = {
    "sin": "사인", "cos": "코사인", "tan": "탄젠트", "sec": "시컨트", "csc": "코시컨트", "cot": "코탄젠트",
    "log": "로그", "ln": "자연로그", "lim": "리미트", "exp": "익스포넨셜", "max": "맥스", "min": "민",
    "mod": "모드", "gcd": "최대공약수", "lcm": "최소공배수",
}  # fmt: skip
WORDS = {"ok": "오케이", "okay": "오케이", "tts": "티티에스", "ai": "에이아이", "pdf": "피디에프"}
UNITS = {
    "mm": "밀리미터", "cm": "센티미터", "km": "킬로미터", "kg": "킬로그램", "mg": "밀리그램",
    "ml": "밀리리터", "mL": "밀리리터", "L": "리터", "kcal": "킬로칼로리", "cal": "칼로리",
    "kWh": "킬로와트시", "Hz": "헤르츠", "km/h": "킬로미터 퍼 아워",
}  # fmt: skip
GREEK = {
    "α": "알파", "β": "베타", "γ": "감마", "δ": "델타", "ε": "엡실론", "θ": "세타", "λ": "람다",
    "μ": "뮤", "π": "파이", "ρ": "로", "σ": "시그마", "τ": "타우", "φ": "파이", "ω": "오메가",
    "Δ": "델타", "Σ": "시그마", "Ω": "오메가",
}  # fmt: skip


def spell(word: str) -> str:
    return " ".join(LETTERS[c] for c in word.lower() if c in LETTERS)


def english_word(word: str, cmu: Cmudict | None) -> str:
    low = word.lower()
    if low in WORDS:
        return WORDS[low]
    if low in FUNCS:
        return FUNCS[low]
    if len(word) == 1 or (word.isupper() and len(word) <= 5):
        return spell(word)
    if cmu is not None and cmu.available:
        out: str = rules().english.convert_eng(low, cmu.get())
        if _HANGUL.fullmatch(out):
            return out
    return _latin_in_math(word)


# ---------------------------------------------------------------------------- numbers

# Counters read with native Korean numerals (세 개, 두 명). Longer entries first.
_SINO_COUNTERS = ("개월", "달러", "배수")
_NATIVE_COUNTERS = (
    "번째", "개", "명", "마리", "살", "시간", "시", "권", "잔", "병", "가지", "군데", "그루", "켤레",
    "척", "채", "통", "벌", "줄", "곳", "배", "쌍", "송이", "사람", "달", "알", "자루", "봉지", "모금",
    "걸음", "바퀴", "명씩", "개씩",
)  # fmt: skip
_SINO_DIGITS = "영일이삼사오육칠팔구"


def read_digits(digits: str) -> str:
    return "".join(_SINO_DIGITS[int(d)] for d in digits if d.isdigit())


def read_number(num: str, following: str = "") -> str:
    """Reads a numeral; `following` is the Hangul text right after it (counter detection)."""
    num = num.replace(",", "")
    if "." in num:
        whole, frac = num.split(".", 1)
        return f"{read_number(whole)} 점 {read_digits(frac)}"
    if not num:
        return ""
    if (len(num) > 1 and num.startswith("0")) or len(num) > 16:
        return read_digits(num)
    numerals = rules().numerals
    follow = following.lstrip()
    if follow.startswith("월"):
        if num == "6":
            return "유"
        if num == "10":
            return "시"
    native = not follow.startswith(_SINO_COUNTERS) and follow.startswith(_NATIVE_COUNTERS)
    if native and int(num) < 100:
        if num == "1" and follow.startswith("번째"):
            return "첫"
        return str(numerals.process_num(num, sino=False))
    return str(numerals.process_num(num, sino=True))


def has_batchim(syllable: str) -> bool:
    return bool(syllable) and "가" <= syllable <= "힣" and (ord(syllable) - 0xAC00) % 28 != 0


def josa(word: str, with_batchim: str, without: str) -> str:
    m = re.search(r"[가-힣](?=[^가-힣]*$)", word)
    return with_batchim if m and has_batchim(m.group()) else without


# ---------------------------------------------------------------------------- LaTeX

_LATEX_WORDS = {
    r"\times": " × ", r"\cdot": " × ", r"\div": " ÷ ", r"\pm": " ± ", r"\mp": " ∓ ",
    r"\leq": " ≤ ", r"\le": " ≤ ", r"\geq": " ≥ ", r"\ge": " ≥ ", r"\neq": " ≠ ", r"\ne": " ≠ ",
    r"\approx": " ≈ ", r"\infty": " ∞ ", r"\circ": "°", r"\degree": "°", r"\%": "%",
    r"\therefore": " 따라서 ", r"\because": " 왜냐하면 ", r"\angle": " 각 ", r"\triangle": " 삼각형 ",
    r"\sum": " 시그마 ", r"\int": " 인테그랄 ", r"\to": " ", r"\rightarrow": " ", r"\Rightarrow": ", ",
    r"\cdots": " … ", r"\ldots": " … ", r"\dots": " … ", r"\quad": " ", r"\qquad": " ",
    r"\left": "", r"\right": "", r"\,": " ", r"\;": " ", r"\:": " ", r"\!": "", r"\\": ", ",
}  # fmt: skip
_LATEX_GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε",
    "theta": "θ", "lambda": "λ", "mu": "μ", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ",
    "phi": "φ", "varphi": "φ", "omega": "ω", "Delta": "Δ", "Sigma": "Σ", "Omega": "Ω",
}  # fmt: skip


def _brace_arg(s: str, i: int) -> tuple[str, int]:
    """Returns the `{...}` group (or single char) starting at s[i] and the index after it."""
    while i < len(s) and s[i] == " ":
        i += 1
    if i >= len(s):
        return "", i
    if s[i] != "{":
        if s[i] == "\\":
            m = re.match(r"\\[A-Za-z]+", s[i:])
            if m:
                return m.group(), i + m.end()
        return s[i], i + 1
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1 : j], j + 1
    return s[i + 1 :], len(s)


def latex_to_text(s: str) -> str:
    """LaTeX math -> plain text with Unicode operators, read later by the math reader."""
    s = re.sub(r"\\\(|\\\)|\\\[|\\\]|\$\$?", " ", s)
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] != "\\":
            out.append(s[i])
            i += 1
            continue
        m = re.match(r"\\([A-Za-z]+|.)", s[i:])
        if not m:
            i += 1
            continue
        cmd = m.group(1)
        j = i + m.end()
        if cmd in ("frac", "dfrac", "tfrac"):
            num, j = _brace_arg(s, j)
            den, j = _brace_arg(s, j)
            out.append(f" {latex_to_text(den)} 분의 {latex_to_text(num)} ")
        elif cmd == "sqrt":
            index = ""
            if j < len(s) and s[j] == "[":
                k = s.find("]", j)
                if k > 0:
                    index, j = s[j + 1 : k], k + 1
            arg, j = _brace_arg(s, j)
            root = f" {latex_to_text(index)} 제곱근 " if index else " 루트 "
            out.append(f"{root}{latex_to_text(arg)} ")
        elif cmd in (
            "text",
            "mathrm",
            "mathbf",
            "mathit",
            "operatorname",
            "textbf",
            "boldsymbol",
            "overline",
        ):
            arg, j = _brace_arg(s, j)
            out.append(latex_to_text(arg))
        elif cmd in _LATEX_GREEK:
            out.append(_LATEX_GREEK[cmd])
        elif cmd in FUNCS:
            out.append(f" {cmd} ")
        elif "\\" + cmd in _LATEX_WORDS:
            out.append(_LATEX_WORDS["\\" + cmd])
        else:
            out.append(" ")  # unknown command: drop it, keep its arguments
        i = j
    text = "".join(out)
    text = re.sub(r"\^\s*\{([^{}]*)\}", lambda mm: "^(" + mm.group(1) + ")", text)
    text = re.sub(r"_\s*\{([^{}]*)\}", r" \1 ", text)
    text = text.replace("_", " ")
    return text.replace("{", " ").replace("}", " ")


def looks_like_latex(s: str) -> bool:
    return bool(re.search(r"\\[A-Za-z]+|\$|\^\{|_\{", s))


# ---------------------------------------------------------------------------- math reader

_TOKEN = re.compile(
    r"(?P<num>\d+(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"|(?P<lat>[A-Za-z]+(?:/h)?)"
    r"|(?P<han>[가-힣]+)"
    r"|(?P<greek>[α-ωΑ-Ω])"
    r"|(?P<op>[-+*/=<>^×÷±∓≤≥≠≈√∞°%()\[\]|])"
    r"|(?P<space>\s+)"
    r"|(?P<punct>[.,!?…])"
    r"|(?P<other>.)",
    re.S,
)
_RELATIONS = {"=", "<", ">", "≤", "≥", "≠", "≈"}
_MATH_KINDS = {"num", "lat", "greek", "op"}


@dataclass
class _Tok:
    kind: str
    text: str
    space_before: bool = False


def _tokens(text: str) -> list[_Tok]:
    toks: list[_Tok] = []
    space = False
    for m in _TOKEN.finditer(text):
        kind = m.lastgroup or "other"
        if kind == "space":
            space = True
            continue
        toks.append(_Tok(kind, m.group(), space))
        space = False
    return toks


def _read_operand_group(toks: list[_Tok], i: int) -> tuple[list[_Tok], int]:
    """Exponent argument: `(…)` group or a single token."""
    if i < len(toks) and toks[i].text == "(":
        depth = 0
        for j in range(i, len(toks)):
            if toks[j].text == "(":
                depth += 1
            elif toks[j].text == ")":
                depth -= 1
                if depth == 0:
                    return toks[i + 1 : j], j + 1
        return toks[i + 1 :], len(toks)
    if i < len(toks) and toks[i].text == "-" and i + 1 < len(toks):
        return toks[i : i + 2], i + 2
    return toks[i : i + 1], i + 1


def _read_expr(toks: list[_Tok], cmu: Cmudict | None, following: str) -> str:
    parts: list[str] = []
    prev = "start"  # start | operand | op
    i = 0
    n = len(toks)
    while i < n:
        t = toks[i]
        nxt = toks[i + 1] if i + 1 < n else None
        if t.kind == "num":
            is_last = all(x.text in ")]|" for x in toks[i + 1 :])
            after = following if is_last else ""
            if nxt is not None and nxt.text == "%":
                parts.append(read_number(t.text) + " 퍼센트")
                i += 1
            elif nxt is not None and nxt.text == "°":
                parts.append(read_number(t.text) + " 도")
                i += 1
                if i + 1 < n and toks[i + 1].text in ("C", "F") and not toks[i + 1].space_before:
                    i += 1
            else:
                parts.append(read_number(t.text, after))
            prev = "operand"
        elif t.kind == "lat":
            if t.text in UNITS and prev == "operand" and i > 0 and toks[i - 1].kind == "num":
                unit = UNITS[t.text]
                if nxt is not None and nxt.text == "^" and i + 2 < n and toks[i + 2].text in ("2", "3"):
                    unit = ("제곱" if toks[i + 2].text == "2" else "세제곱") + unit
                    i += 2
                parts.append(unit)
            elif (
                t.text == "x"
                and prev == "operand"
                and t.space_before
                and nxt is not None
                and nxt.kind == "num"
                and nxt.space_before
            ):
                parts.append("곱하기")
                prev = "op"
                i += 1
                continue
            else:
                parts.append(_latin_in_math(t.text))
            prev = "operand"
        elif t.kind == "greek":
            parts.append(GREEK.get(t.text, ""))
            prev = "operand"
        elif t.kind == "op":
            op = t.text
            if op == "+":
                parts.append("더하기" if prev == "operand" else "플러스")
                prev = "op"
            elif op == "-":
                parts.append("빼기" if prev == "operand" else "마이너스")
                prev = "op"
            elif op in ("*", "×"):
                parts.append("곱하기")
                prev = "op"
            elif op in ("/", "÷"):
                parts.append("나누기")
                prev = "op"
            elif op in ("±", "∓"):
                parts.append("플러스 마이너스" if op == "±" else "마이너스 플러스")
                prev = "op"
            elif op == "^":
                group, j = _read_operand_group(toks, i + 1)
                exp = "".join(x.text for x in group)
                if exp == "2":
                    parts.append("제곱")
                elif exp == "3":
                    parts.append("세제곱")
                elif group:
                    base = parts.pop() if parts else ""
                    parts.append(f"{base}의 {_read_expr(group, cmu, '')} 제곱".strip())
                i = j
                prev = "operand"
                continue
            elif op == "√":
                parts.append("루트")
                prev = "op"
            elif op == "∞":
                parts.append("무한대")
                prev = "operand"
            elif op == "%":
                parts.append("퍼센트")
            elif op == "°":
                parts.append("도")
            elif op in ")]|":
                prev = "operand"
            elif op in "([":
                prev = "op" if prev != "start" else "start"
        i += 1
    return " ".join(p for p in parts if p)


def _latin_in_math(word: str) -> str:
    """`x` -> 엑스, `xy` -> 엑스 와이, `sinx` -> 사인 엑스."""
    low = word.lower()
    for name in sorted(FUNCS, key=len, reverse=True):
        if low.startswith(name):
            rest = word[len(name) :]
            return (FUNCS[name] + " " + spell(rest)).strip()
    return spell(word)


# relation -> (final form, connective form used when another relation follows)
_REL_TAIL = {
    "<": ("보다 작다", "보다 작고"),
    ">": ("보다 크다", "보다 크고"),
    "≤": ("보다 작거나 같다", "보다 작거나 같고"),
    "≥": ("보다 크거나 같다", "보다 크거나 같고"),
    "≠": ("", ""),
}


def _read_math(toks: list[_Tok], cmu: Cmudict | None, following: str) -> str:
    operands: list[list[_Tok]] = [[]]
    rels: list[str] = []
    for t in toks:
        if t.kind == "op" and t.text in _RELATIONS:
            rels.append(t.text)
            operands.append([])
        else:
            operands[-1].append(t)
    texts = [
        _read_expr(op, cmu, following if k == len(operands) - 1 else "") for k, op in enumerate(operands)
    ]
    if not rels:
        return texts[0]
    clauses: list[str] = []
    for k, rel in enumerate(rels):
        left, right = texts[k], texts[k + 1]
        last = k == len(rels) - 1
        subj = left + josa(left, "은", "는") if left else ""
        if rel == "=":
            clause = f"{subj} {right}"
        elif rel == "≠":
            clause = f"{subj} {right}{josa(right, '과', '와')} 같지 " + ("않다" if last else "않고")
        elif rel == "≈":
            clause = f"{subj} 약 {right}"
        else:
            clause = f"{subj} {right}{_REL_TAIL[rel][0 if last else 1]}"
        clauses.append(clause.strip())
    return ", ".join(clauses)


def _read_segment(toks: list[_Tok], cmu: Cmudict | None, following: str) -> str:
    """A run of non-Hangul tokens between Hangul words."""
    if all(t.kind == "lat" for t in toks):
        return " ".join(english_word(t.text, cmu) for t in toks)
    if not any(t.kind in ("num", "lat", "greek") or t.text == "∞" for t in toks):
        return "," if any(t.text in "-=~" for t in toks) else ""  # lone dash between words
    return _read_math(toks, cmu, following)


# ---------------------------------------------------------------------------- normalize

_FULLWIDTH = {i: i - 0xFEE0 for i in range(0xFF01, 0xFF5F)}
_SUPERSCRIPTS = str.maketrans({"⁰": "^0", "¹": "^1", "²": "^2", "³": "^3", "⁴": "^4", "⁵": "^5",
                               "⁶": "^6", "⁷": "^7", "⁸": "^8", "⁹": "^9", "ⁿ": "^n"})  # fmt: skip
_SYMBOLS = {
    "㎜": "mm", "㎝": "cm", "㎞": "km", "㎏": "kg", "㎎": "mg", "㎖": "mL", "ℓ": "L", "㎡": "m^2",
    "㎥": "m^3", "℃": "°C", "−": "-", "–": "-", "—": ", ", "·": ", ", "∙": "×", "⋅": "×",
    "∴": " 따라서 ", "∵": " 왜냐하면 ", "∠": " 각 ", "△": " 삼각형 ", "→": ", ", "⇒": ", ",
    "“": " ", "”": " ", "‘": " ", "’": " ", '"': " ", "'": " ", "「": " ", "」": " ",
    "『": " ", "』": " ", "《": " ", "》": " ", "〈": " ", "〉": " ", "<<": " ", ">>": " ",
}  # fmt: skip


def normalize(text: str, cmu: Cmudict | None = None) -> str:
    """Study content -> Hangul, spaces and the punctuation the model knows (`.,!?…`)."""
    s = text.translate(_FULLWIDTH).translate(_SUPERSCRIPTS)
    for a, b in _SYMBOLS.items():
        s = s.replace(a, b)
    if looks_like_latex(s):
        s = latex_to_text(s)
    s = re.sub(r"\.{3,}", "…", s)
    s = re.sub(r"(?<![\d.])(\d+)\s*/\s*(\d+)(?![\d.])", r"\2분의 \1", s)  # 1/2 -> 2분의 1
    s = re.sub(r"(\d)\s*:\s*(\d)", r"\1 대 \2", s)  # ratios
    s = re.sub(r"(\d)\s*~\s*(\d)", r"\1에서 \2", s)
    s = re.sub(r"[\r\n]+", ". ", s)
    for pattern, repl in rules().idioms:
        s = re.sub(pattern, repl, s)

    toks = _tokens(s)
    out: list[str] = []
    seg: list[_Tok] = []

    def flush(following: str) -> None:
        if seg:
            spoken = _read_segment(seg, cmu, following)
            if spoken:
                out.append((" " if seg[0].space_before else "") + spoken)
            seg.clear()

    for t in toks:
        if t.kind in _MATH_KINDS:
            seg.append(t)
            continue
        flush(t.text if t.kind == "han" else "")
        if t.kind == "han":
            out.append((" " if t.space_before else "") + t.text)
        elif t.kind == "punct":
            out.append(t.text)
        elif t.text in ";:":
            out.append(",")
        elif t.space_before:
            out.append(" ")
    flush("")
    return _tidy("".join(out))


def _tidy(s: str) -> str:
    s = re.sub(r"[^가-힣\s.,!?…]", " ", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([.,!?…])", r"\1", s)
    s = re.sub(r"([.,!?…])(?=[가-힣])", r"\1 ", s)
    s = re.sub(r",(?:\s*,)+", ",", s)
    s = re.sub(r",\s*([.!?…])", r"\1", s)
    s = re.sub(r"^[\s.,!?…]+", "", s)
    s = re.sub(r"\.(?:\s*\.)+", ".", s)
    return s.strip()


# ---------------------------------------------------------------------------- pieces

_CODA_FIX = {
    "ᆩ": "ᆨ", "ᆪ": "ᆨ", "ᆰ": "ᆨ", "ᆿ": "ᆨ", "ᆬ": "ᆫ", "ᆭ": "ᆫ", "ᆺ": "ᆮ", "ᆻ": "ᆮ", "ᆽ": "ᆮ",
    "ᆾ": "ᆮ", "ᇀ": "ᆮ", "ᇂ": "ᆮ", "ᆲ": "ᆯ", "ᆳ": "ᆯ", "ᆴ": "ᆯ", "ᆶ": "ᆯ", "ᆱ": "ᆷ", "ᆹ": "ᆸ",
    "ᆵ": "ᆸ", "ᇁ": "ᆸ",
}  # fmt: skip


@dataclass
class Piece:
    """One sentence-sized chunk synthesised in a single model call."""

    text: str
    phones: list[str]
    syllables: list[str]  # written syllables of `text`
    phone_syllable: list[int]  # per phone: index into `syllables`, -1 for pad/punctuation


def split_sentences(text: str, max_chars: int) -> list[str]:
    pieces: list[str] = []
    for sent in re.split(r"(?<=[.!?…])\s+", text):
        sent = sent.strip()
        while len(sent) > max_chars:
            cut = max(sent.rfind(",", 0, max_chars), sent.rfind(" ", 0, max_chars))
            cut = cut if cut > max_chars // 3 else max_chars
            pieces.append(sent[: cut + 1].strip())
            sent = sent[cut + 1 :].strip()
        if _HANGUL.search(sent):
            pieces.append(sent)
    return pieces


def to_piece(sentence: str, symbols: set[str]) -> Piece:
    phones = ["_"]
    owner = [-1]
    syllables: list[str] = []
    for m in re.finditer(r"[가-힣]+|[.,!?…]", sentence):
        tok = m.group()
        if tok in PUNCT:
            if tok in symbols:
                phones.append(tok)
                owner.append(-1)
            continue
        for written, spoken in zip(tok, g2p(tok), strict=True):
            idx = len(syllables)
            syllables.append(written)
            for jamo in hangul_to_jamo(spoken):
                sym = _CODA_FIX.get(jamo, jamo)
                if sym in symbols:
                    phones.append(sym)
                    owner.append(idx)
    phones.append("_")
    owner.append(-1)
    return Piece(sentence, phones, syllables, owner)


def to_pieces(
    text: str, symbols: Iterable[str], max_chars: int = 120, cmu: Cmudict | None = None
) -> list[Piece]:
    table = set(symbols)
    return [to_piece(s, table) for s in split_sentences(normalize(text, cmu), max_chars)]
