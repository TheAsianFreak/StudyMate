"""English text frontend for Kokoro: normalisation and G2P with per-syllable lip-sync units.

- `normalize()` turns the character's line into speakable English: numbers (cardinal,
  decimal, negative, ordinal, year, fraction, percent, degree, money) and simple math
  (`2x + 3 = 7`, `x^2`, `3/4`, `f(x)`, `√2`, `<`, ...). Single-letter math variables are
  written `[x]` so the G2P spells them instead of reading `a` as the article.
- `EnglishFrontend` runs misaki's lexicons + spaCy tagger (vendored, without espeak-ng and
  num2words; see `kokoro/misaki_en.py`) and splits every word into syllable units whose
  vowel drives the mouth shape (`PhonemeTiming.vowel`).

Everything is local: the spaCy model is loaded from the models dir, never downloaded.
"""

from __future__ import annotations

import json
import re
import threading
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from studymate.speech.g2p_en_oov import OovG2p
from studymate.speech.mathtext import FULLWIDTH, Tok, latex, mark_math, read_group, tokens
from studymate.speech.units import Sentence, Unit

# ---------------------------------------------------------------------------- numbers

_ONES = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = ["_", "_", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_SCALES = ((10**12, "trillion"), (10**9, "billion"), (10**6, "million"), (1000, "thousand"))
_ORDINAL_WORDS = {
    "one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth",
    "nine": "ninth", "twelve": "twelfth",
}  # fmt: skip
_FRACTION_WORDS = {2: ("half", "halves"), 4: ("quarter", "quarters")}


def cardinal(n: int) -> str:
    """American cardinal without "and" or hyphens: 1392 -> one thousand three hundred ninety two."""
    if n < 0:
        return "minus " + cardinal(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] + (" " + _ONES[ones] if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        return _ONES[hundreds] + " hundred" + (" " + cardinal(rest) if rest else "")
    for value, name in _SCALES:
        if n >= value:
            head, rest = divmod(n, value)
            return cardinal(head) + " " + name + (" " + cardinal(rest) if rest else "")
    raise AssertionError(n)


def ordinal(n: int) -> str:
    words = cardinal(n).split(" ")
    last = words[-1]
    if last in _ORDINAL_WORDS:
        words[-1] = _ORDINAL_WORDS[last]
    elif last.endswith("y"):
        words[-1] = last[:-1] + "ieth"
    else:
        words[-1] = last + "th"
    return " ".join(words)


def year(n: int) -> str:
    """1392 -> thirteen ninety two, 2024 -> twenty twenty four, 1905 -> nineteen oh five."""
    if n % 1000 == 0 or (2000 <= n < 2010):
        return cardinal(n)
    head, tail = divmod(n, 100)
    if tail == 0:
        return cardinal(head) + " hundred"
    return cardinal(head) + " " + (cardinal(tail) if tail >= 10 else "oh " + _ONES[tail])


def digits(s: str) -> str:
    return " ".join(_ONES[int(d)] for d in s if d.isdigit())


def number(num: str) -> str:
    """A written numeral (commas and decimals allowed) as words."""
    num = num.replace(",", "")
    if num.startswith("."):
        return "point " + digits(num[1:])
    if "." in num:
        whole, frac = num.split(".", 1)
        return f"{number(whole)} point {digits(frac)}"
    if len(num) > 1 and num.startswith("0"):
        return digits(num)
    if len(num) > 15:
        return digits(num)
    return cardinal(int(num))


def fraction(num: int, den: int) -> str:
    """3/4 -> three quarters, 2/3 -> two thirds, 5/12 -> five over twelve."""
    if den in _FRACTION_WORDS:
        one, many = _FRACTION_WORDS[den]
        return f"{cardinal(num)} {one if num == 1 else many}"
    if 3 <= den <= 10 and den != 4:
        word = ordinal(den)
        return f"{cardinal(num)} {word if num == 1 else word + 's'}"
    return f"{cardinal(num)} over {cardinal(den)}"


# ---------------------------------------------------------------------------- math words

FUNCS = {
    "sin": "sine", "cos": "cosine", "tan": "tangent", "sec": "secant", "csc": "cosecant",
    "cot": "cotangent", "log": "log", "ln": "natural log", "exp": "exp", "lim": "the limit of",
    "max": "the max of", "min": "the min of",
}  # fmt: skip
GREEK = {
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon", "θ": "theta",
    "λ": "lambda", "μ": "mu", "π": "pi", "ρ": "rho", "σ": "sigma", "τ": "tau", "φ": "phi",
    "ω": "omega", "Δ": "delta", "Σ": "sigma", "Ω": "omega",
}  # fmt: skip
UNITS = {
    "mm": ("millimeter", "millimeters"), "cm": ("centimeter", "centimeters"),
    "km": ("kilometer", "kilometers"), "kg": ("kilogram", "kilograms"),
    "mg": ("milligram", "milligrams"), "ml": ("milliliter", "milliliters"),
    "mL": ("milliliter", "milliliters"), "kcal": ("kilocalorie", "kilocalories"),
    "Hz": ("hertz", "hertz"), "min": ("minute", "minutes"), "sec": ("second", "seconds"),
}  # fmt: skip
_RELATIONS = {
    "=": "equals", "<": "is less than", ">": "is greater than", "≤": "is less than or equal to",
    "≥": "is greater than or equal to", "≠": "is not equal to", "≈": "is approximately",
}  # fmt: skip
_BINARY = {
    "+": "plus",
    "-": "minus",
    "×": "times",
    "*": "times",
    "÷": "divided by",
    "/": "over",
    "±": "plus or minus",
}
_YEAR_CUES = {"in", "year", "since", "by", "from", "until", "till", "before", "after", "around", "circa"}


def _read_math(toks: list[Tok], before: str) -> str:
    """One run of math tokens -> words. `before` is the preceding prose word (year cue)."""
    out: list[str] = []
    prev = "start"  # start | operand | op
    i = 0
    n = len(toks)
    while i < n:
        t = toks[i]
        nxt = toks[i + 1] if i + 1 < n else None
        if t.kind == "num":
            if prev == "operand" and out:
                out.append("times")  # 2(3) or x 3: rare, but keep it readable
            if (
                nxt is not None
                and nxt.text == "/"
                and i + 2 < n
                and toks[i + 2].kind == "num"
                and ("." not in t.text + toks[i + 2].text)
            ):
                out.append(fraction(int(t.text.replace(",", "")), int(toks[i + 2].text.replace(",", ""))))
                i += 3
                prev = "operand"
                continue
            plain = t.text.replace(",", "")
            if (
                n == 1
                and plain.isdigit()
                and len(plain) == 4
                and 1000 <= int(plain) < 2100
                and "," not in t.text
                and before.lower() in _YEAR_CUES
            ):
                out.append(year(int(plain)))
            else:
                out.append(number(t.text))
            prev = "operand"
            if nxt is not None and nxt.kind == "word" and nxt.text in UNITS:
                one, many = UNITS[nxt.text]
                square = i + 3 < n and toks[i + 2].text == "^" and toks[i + 3].text in ("2", "3")
                word = one if plain in ("1", "1.0") else many
                out.append(
                    ("square " if square and toks[i + 3].text == "2" else "cubic " if square else "") + word
                )
                i += 4 if square else 2
                continue
        elif t.kind == "word":
            low = t.text.lower()
            if low in FUNCS and len(t.text) > 1:
                out.append(FUNCS[low])
                prev = "op"
                i += 1
                continue
            if (
                t.text == "x"
                and prev == "operand"
                and nxt is not None
                and nxt.kind == "num"
                and t.space_before
            ):
                out.append("times")  # 3 x 4
                prev = "op"
                i += 1
                continue
            out.append(f"[{t.text}]" if len(t.text) == 1 else t.text)
            prev = "operand"
            if nxt is not None and nxt.text == "(" and not nxt.space_before and len(t.text) == 1:
                out.append("of")  # f(x) -> f of x
                prev = "op"
        elif t.kind == "greek":
            out.append(GREEK.get(t.text, ""))
            prev = "operand"
        elif t.kind == "op":
            op = t.text
            if op in _RELATIONS:
                out.append(_RELATIONS[op])
                prev = "op"
            elif op == "-" and prev != "operand":
                out.append("negative")
                prev = "op"
            elif op == "+" and prev != "operand":
                out.append("positive")
                prev = "op"
            elif op in _BINARY:
                out.append(_BINARY[op])
                prev = "op"
            elif op == "^":
                group, j = read_group(toks, i + 1)
                exp = "".join(x.text for x in group)
                if exp == "2":
                    out.append("squared")
                elif exp == "3":
                    out.append("cubed")
                elif group:
                    out.append("to the power of " + _read_math(group, ""))
                i = j
                prev = "operand"
                continue
            elif op == "√":
                group, j = read_group(toks, i + 1)
                out.append("the square root of " + _read_math(group, ""))
                i = j
                prev = "operand"
                continue
            elif op == "∞":
                out.append("infinity")
                prev = "operand"
            elif op == "%":
                out.append("percent")
            elif op == "°":
                out.append("degrees" if not out or out[-1] != "one" else "degree")
                if nxt is not None and nxt.text in ("C", "F") and not nxt.space_before:
                    out.append("Celsius" if nxt.text == "C" else "Fahrenheit")
                    i += 1
            elif op == ")":
                prev = "operand"
            elif op == "(":
                if prev == "operand" and out and out[-1] != "of":
                    out.append("times")
                prev = "op"
        i += 1
    return " ".join(w for w in out if w)


# ---------------------------------------------------------------------------- normalize

_SYMBOLS = {
    "−": "-", "–": "-", "—": ", ", "⋅": "×", "·": "×", "∙": "×", "≦": "≤", "≧": "≥",
    "²": "^2", "³": "^3", "⁴": "^4", "℃": "°C", "…": "...", "→": ", ", "⇒": ", ",
    "“": '"', "”": '"', "‘": "'", "’": "'",
}  # fmt: skip


def normalize(text: str) -> str:
    """The character's line -> words, punctuation and `[x]` math variables."""
    s = unicodedata.normalize("NFC", text).translate(FULLWIDTH)
    for a, b in _SYMBOLS.items():
        s = s.replace(a, b)
    s = re.sub(r"\$(\d+(?:,\d{3})*)(?:\.(\d\d))?\b", _money, s)  # before LaTeX: `$` isn't math mode here
    s = latex(s)
    s = re.sub(r"\b(\d+)(st|nd|rd|th)\b", lambda m: ordinal(int(m.group(1))), s)
    s = re.sub(r"\b(\d{1,2}):(\d{2})\s*([ap])\.?m\.?\b", _clock, s, flags=re.I)
    s = re.sub(r"(?<=\d)\s*:\s*(?=\d)", " to ", s)  # ratios 3:4
    s = re.sub(r"(?<=\d)\s*~\s*(?=\d)", " to ", s)
    s = re.sub(r"\s*[\r\n]+\s*", ". ", s)

    toks = tokens(s)
    mark_math(toks)
    out: list[str] = []
    run: list[Tok] = []
    last_word = ""

    def flush() -> None:
        if run:
            spoken = _read_math(run, last_word)
            if spoken:
                out.append((" " if run[0].space_before else "") + spoken)
            run.clear()

    for t in toks:
        if t.math:
            run.append(t)
            continue
        flush()
        prefix = " " if t.space_before else ""
        if t.kind == "word":
            out.append(prefix + t.text)
            last_word = t.text
        elif t.kind == "op":
            out.append(prefix + ({"&": "and", "%": "percent", "/": " or "}.get(t.text, " ")))
        else:
            out.append(prefix + t.text)
    flush()
    return _tidy("".join(out))


def _money(m: re.Match[str]) -> str:
    dollars = int(m.group(1).replace(",", ""))
    words = f"{cardinal(dollars)} dollar{'' if dollars == 1 else 's'}"
    if m.group(2) and int(m.group(2)):
        cents = int(m.group(2))
        words += f" and {cardinal(cents)} cent{'' if cents == 1 else 's'}"
    return words


def _clock(m: re.Match[str]) -> str:
    hour, minute = int(m.group(1)), int(m.group(2))
    mins = "" if minute == 0 else (" oh " + _ONES[minute] if minute < 10 else " " + cardinal(minute))
    return f"{cardinal(hour)}{mins} {m.group(3).upper()} M"


def _tidy(s: str) -> str:
    s = re.sub(r"[^\x20-\x7e]", " ", s)  # the model's English vocab is ASCII + punctuation
    s = re.sub(r"[#*_~`<>{}|\\^@]", " ", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([.,!?;:])", r"\1", s)
    s = re.sub(r"([.,!?;:])(?=[A-Za-z\[])", r"\1 ", s)
    s = re.sub(r",(?:\s*,)+", ",", s)
    s = re.sub(r"\.{3,}", "...", s)
    return s.strip(" ,")


# ---------------------------------------------------------------------------- G2P

# misaki vowels (US + GB) -> lip-sync vowel. Diphthongs use their first target.
VOWEL_OF = {
    "æ": "a", "ɑ": "a", "ʌ": "a", "ɐ": "a", "ə": "a", "ɜ": "a", "I": "a", "W": "a",
    "ɔ": "o", "ɒ": "o", "O": "o", "Q": "o", "Y": "o",
    "ɛ": "e", "A": "e",
    "i": "i", "ɪ": "i", "ᵻ": "i",
    "u": "u", "ʊ": "u", "ᵊ": "u",
}  # fmt: skip
BILABIAL = frozenset("mbp")

# ARPAbet (CMUdict) -> misaki US phonemes, for words the lexicons don't know.
_ARPA = {
    "AA": "ɑ", "AE": "æ", "AO": "ɔ", "AW": "W", "AY": "I", "EH": "ɛ", "EY": "A", "IH": "ɪ",
    "IY": "i", "OW": "O", "OY": "Y", "UH": "ʊ", "UW": "u", "B": "b", "CH": "ʧ", "D": "d",
    "DH": "ð", "F": "f", "G": "ɡ", "HH": "h", "JH": "ʤ", "K": "k", "L": "l", "M": "m",
    "N": "n", "NG": "ŋ", "P": "p", "R": "ɹ", "S": "s", "SH": "ʃ", "T": "t", "TH": "θ",
    "V": "v", "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}  # fmt: skip


def arpabet_to_misaki(arpa: list[str], british: bool = False) -> str:
    out: list[str] = []
    for ph in arpa:
        base, stress = ph.rstrip("012"), ph[len(ph.rstrip("012")) :]
        if base == "AH":
            sym = "ə" if stress in ("0", "") else "ʌ"
        elif base == "ER":
            sym = "əɹ" if stress in ("0", "") else "ɜɹ"
        else:
            sym = _ARPA.get(base, "")
        if british and sym == "O":
            sym = "Q"
        mark = "ˈ" if stress == "1" else "ˌ" if stress == "2" else ""
        out.append(mark + sym)
    return "".join(out)


_ROMAJI = re.compile(
    r"(?:(?:ky|gy|sh|ch|ts|ny|hy|by|py|my|ry|[kgsztdnhbpmrwyjf])?[aiueo]|n(?![aiueoy])|([kstpgdbz])(?=\1))+"
)
_ROMAJI_SYL = re.compile(r"(ky|gy|sh|ch|ts|ny|hy|by|py|my|ry|[kgsztdnhbpmrwyjf])?([aiueo])|n|([kstpgdbz])")
_ROMAJI_CONS = {"sh": "ʃ", "ch": "ʧ", "j": "ʤ", "g": "ɡ", "r": "ɹ", "y": "j"}
_ROMAJI_VOWEL = {"a": "ɑ", "i": "i", "u": "u", "e": "ɛ", "o": "O"}


def romaji(word: str) -> str | None:
    """Japanese names written in romaji (Tsukuyomi, Hinata) read with Japanese vowels and
    English-style penultimate stress; None when the word isn't plausible romaji."""
    low = word.lower()
    if len(low) < 4 or not _ROMAJI.fullmatch(low):
        return None
    sylls: list[str] = []
    for m in _ROMAJI_SYL.finditer(low):
        cons, vowel, geminate = m.group(1), m.group(2), m.group(3)
        if geminate:
            continue  # sokuon: the doubled consonant is spoken once
        if vowel is None:
            if sylls:
                sylls[-1] += "n"
            continue
        c = cons or ""
        c = _ROMAJI_CONS.get(c[0], c[0]) + "j" if len(c) == 2 and c[1] == "y" else _ROMAJI_CONS.get(c, c)
        sylls.append(c + "\0" + _ROMAJI_VOWEL[vowel])
    if len(sylls) < 2:
        return None
    stressed = len(sylls) - 2
    out = []
    for k, syl in enumerate(sylls):
        mark = "ˈ" if k == stressed else "ˌ" if k == 0 and stressed >= 2 else ""
        out.append(syl.replace("\0", mark))
    return "".join(out)


class OovFallback:
    """Words misaki's lexicons don't know: CMUdict (optional model `g2p-cmudict`, strong on
    names), romaji names, then the g2p_en neural model (`g2p-en-oov`), else spelled letter
    by letter."""

    def __init__(
        self,
        cmudict: Path | None,
        neural: OovG2p | None,
        letters: Callable[[str], str | None],
        british: bool,
    ) -> None:
        self.cmudict = cmudict
        self.neural = neural if neural is not None and neural.available else None
        self.letters = letters
        self.british = british
        self._dict: dict[str, list[str]] | None = None
        self._lock = threading.Lock()

    def _load(self) -> dict[str, list[str]]:
        with self._lock:
            if self._dict is None:
                self._dict = {}
                if self.cmudict is not None and self.cmudict.is_file():
                    for line in self.cmudict.read_text(encoding="latin-1").splitlines():
                        parts = line.split()
                        if len(parts) >= 3 and parts[0].lower() not in self._dict:
                            self._dict[parts[0].lower()] = parts[2:]
            return self._dict

    def __call__(self, token: Any) -> tuple[str | None, int | None]:
        word = str(token.text).strip("'’")
        arpa = self._load().get(word.lower())
        if not arpa and word.isascii() and word.isalpha():
            japanese = romaji(word)
            if japanese:
                return japanese, 2
        if not arpa and self.neural is not None and word.isascii() and word.isalpha() and len(word) > 1:
            arpa = self.neural.predict(word)
        if arpa:
            return arpabet_to_misaki(arpa, self.british), 2
        spelled = [self.letters(c) for c in word if c.isalpha()]
        if spelled and all(spelled):
            return "".join(p for p in spelled if p), 1
        return None, None


@dataclass
class _Word:
    phonemes: str
    whitespace: bool


def syllables(ps: str) -> list[tuple[int, int, str | None]]:
    """Splits one word's phonemes into (start, end, vowel) groups: the consonants before a
    vowel go with it (maximal onset); bilabials (m b p) in an onset or coda get their own
    closed ("n") unit so the lips shut on them."""
    nuclei = [k for k, c in enumerate(ps) if c in VOWEL_OF]
    if not nuclei:
        return [(0, len(ps), "n" if any(c in BILABIAL for c in ps) else None)] if ps else []
    out: list[tuple[int, int, str | None]] = []
    start = 0
    for idx, k in enumerate(nuclei):
        end = len(ps)
        if idx + 1 < len(nuclei):
            # the next syllable starts at the consonant(s)/stress mark right before its vowel
            end = nuclei[idx + 1]
            while end - 1 > k and ps[end - 1] not in VOWEL_OF:
                end -= 1
        onset = [q for q in range(start, k) if ps[q] in BILABIAL]
        if onset:
            out.append((start, onset[-1] + 1, "n"))
            start = onset[-1] + 1
        coda = next((q for q in range(k + 1, end) if ps[q] in BILABIAL), None)
        if coda is not None:
            out.append((start, coda, VOWEL_OF[ps[k]]))
            out.append((coda, end, "n"))
        else:
            out.append((start, end, VOWEL_OF[ps[k]]))
        start = end
    return out


class EnglishFrontend:
    """Text -> Kokoro phoneme sentences with syllable units. Thread-safe (one lock)."""

    def __init__(
        self,
        spacy_dir: Path,
        *,
        british: bool = False,
        cmudict: Path | None = None,
        oov_checkpoint: Path | None = None,
    ) -> None:
        import spacy

        from studymate.speech.kokoro.misaki_en import G2P

        nlp = spacy.load(spacy_dir, enable=["tok2vec", "tagger", "attribute_ruler"])
        self.british = british
        golds = _letters(british)
        self._letters = golds
        neural = OovG2p(oov_checkpoint) if oov_checkpoint is not None else None
        fallback = OovFallback(cmudict, neural, golds.get, british)
        self.g2p = G2P(nlp, british=british, fallback=fallback)  # type: ignore[no-untyped-call]
        self._lock = threading.Lock()

    def sentences(self, text: str) -> list[Sentence]:
        spoken = normalize(text)
        spoken = re.sub(
            r"\[([A-Za-z])\](?!\()",
            lambda m: f"[{m.group(1)}](/{self._letters.get(m.group(1)) or m.group(1)}/)",
            spoken,
        )
        if not spoken:
            return []
        with self._lock:
            _, tokens = self.g2p(spoken)
        return _to_sentences([_Word(tk.phonemes or "", bool(tk.whitespace)) for tk in tokens])


def _to_sentences(words: list[_Word]) -> list[Sentence]:
    out: list[Sentence] = []
    ps = ""
    units: list[Unit] = []
    for word in words:
        p = word.phonemes
        if p and all(c in ".!?…" for c in p.strip()):
            ps += p
            out.append(Sentence(ps.strip(), units, text=""))
            ps, units = "", []
            continue
        base = len(ps)
        if p and not all(c in ',;:—"“”()' for c in p):
            for start, end, vowel in syllables(p):
                units.append(Unit(p[start:end], vowel, base + start, base + end))
        ps += p
        if word.whitespace and ps and not ps.endswith(" "):
            ps += " "
    if ps.strip():
        out.append(Sentence(ps.rstrip(), units, text=""))
    return [s for s in out if s.units]


_LETTER_CACHE: dict[bool, dict[str, str]] = {}


def _letters(british: bool) -> dict[str, str]:
    """Letter names (A-Z, a-z) from misaki's gold lexicon: `x` -> ˈɛks."""
    if british not in _LETTER_CACHE:
        from misaki import data

        name = f"{'gb' if british else 'us'}_gold.json"
        gold = json.loads(resources.files(data).joinpath(name).read_text(encoding="utf-8"))
        table: dict[str, str] = {}
        for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            v = gold.get(c)
            if isinstance(v, dict):
                v = v.get("DEFAULT")
            if isinstance(v, str):
                table[c] = table[c.lower()] = v
        _LETTER_CACHE[british] = table
    return _LETTER_CACHE[british]
