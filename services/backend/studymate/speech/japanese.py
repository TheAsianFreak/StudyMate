"""Japanese text frontend for Kokoro: normalisation, readings and per-mora lip-sync units.

- `normalize()` rewrites math the way a Japanese teacher reads it (`2x+3=7` ->
  2x たす 3 イコール 7, `3/4` -> 4分の3, `x^2` -> xの2乗, `-5` -> マイナス5) and leaves
  numbers with counters to OpenJTalk, which reads 3本 / 1つ / 10分 correctly.
- Readings come from pyopenjtalk-plus (MIT; NAIST-jdic/UniDic-based dictionary bundled
  in the wheel, so nothing is downloaded). Its optional Sudachi homograph pass is off: it
  needs a ~200 MB dictionary we don't ship.
- Kana are mapped to the IPA the Kokoro v1.0 Japanese voices were trained with (misaki's
  first-gen table, `kokoro/ja_kana.py`), one `Unit` per mora (`char` = katakana mora).
"""

from __future__ import annotations

import re
import threading
import unicodedata
from dataclasses import dataclass
from typing import Any

from studymate.speech.kokoro.ja_kana import HEPBURN
from studymate.speech.mathtext import FULLWIDTH, Tok, latex, mark_math, read_group, tokens
from studymate.speech.units import Sentence, Unit

# ---------------------------------------------------------------------------- normalize

FUNCS = {
    "sin": "サイン", "cos": "コサイン", "tan": "タンジェント", "sec": "セカント", "csc": "コセカント",
    "cot": "コタンジェント", "log": "ログ", "ln": "エルエヌ", "exp": "エクスポネンシャル",
    "lim": "リミット", "max": "マックス", "min": "ミニマム",
}  # fmt: skip
UNITS = {
    "mm": "ミリメートル", "cm": "センチメートル", "km": "キロメートル", "kg": "キログラム",
    "mg": "ミリグラム", "ml": "ミリリットル", "mL": "ミリリットル", "kcal": "キロカロリー",
    "Hz": "ヘルツ", "min": "分", "sec": "秒",
}  # fmt: skip
_RELATIONS = {
    "=": "イコール", "<": "小なり", ">": "大なり", "≤": "小なりイコール", "≥": "大なりイコール",
    "≠": "ノットイコール", "≈": "ニアリーイコール",
}  # fmt: skip
_BINARY = {
    "+": "たす",
    "-": "ひく",
    "×": "かける",
    "*": "かける",
    "÷": "わる",
    "/": "わる",
    "±": "プラスマイナス",
}
_SYMBOLS = {
    "−": "-", "–": "-", "⋅": "×", "·": "×", "∙": "×", "≦": "≤", "≧": "≥", "²": "^2", "³": "^3",
    "℃": "°C", "〜": "~", "∶": ":",
}  # fmt: skip


def _read_math(toks: list[Tok]) -> str:
    out: list[str] = []
    prev = "start"  # start | operand | op
    groups: list[int] = []  # len(out) at each open "("
    last_group = -1  # start in `out` of the group closed by the previous ")"
    i = 0
    n = len(toks)
    while i < n:
        t = toks[i]
        nxt = toks[i + 1] if i + 1 < n else None
        if t.kind == "num":
            if nxt is not None and nxt.text == "/" and i + 2 < n and toks[i + 2].kind == "num":
                out.append(f"{toks[i + 2].text.replace(',', '')}分の{t.text.replace(',', '')}")
                i += 3
                prev = "operand"
                continue
            out.append(t.text.replace(",", ""))
            prev = "operand"
            if nxt is not None and nxt.kind == "word" and nxt.text in UNITS:
                square = i + 3 < n and toks[i + 2].text == "^" and toks[i + 3].text in ("2", "3")
                prefix = ("平方" if toks[i + 3].text == "2" else "立方") if square else ""
                out.append(prefix + UNITS[nxt.text])
                i += 4 if square else 2
                continue
        elif t.kind == "word":
            low = t.text.lower()
            if low in FUNCS and len(t.text) > 1:
                out.append(FUNCS[low])
                prev = "op"
            elif (
                t.text == "x"
                and prev == "operand"
                and nxt is not None
                and nxt.kind == "num"
                and t.space_before
            ):
                out.append("かける")  # 3 x 4
                prev = "op"
            else:
                out.append(t.text)
                prev = "operand"
        elif t.kind == "greek":
            out.append(t.text)  # OpenJTalk reads π, θ, α, ...
            prev = "operand"
        elif t.kind == "op":
            op = t.text
            if op in _RELATIONS:
                out.append(_RELATIONS[op])
                prev = "op"
            elif op == "/" and prev == "operand" and out:
                # a/b is read denominator first: x/2 -> 2分のx, (x+1)/2 -> 2分のxたす1
                start = last_group if toks[i - 1].text == ")" and last_group >= 0 else len(out) - 1
                numerator = "".join(out[start:])
                del out[start:]
                group, j = read_group(toks, i + 1)
                out.append(f"{_read_math(group)}分の{numerator}")
                i = j
                prev = "operand"
                continue
            elif op in "+-" and prev != "operand":
                out.append("プラス" if op == "+" else "マイナス")
                prev = "op"
            elif op in _BINARY:
                out.append(_BINARY[op])
                prev = "op"
            elif op == "^":
                group, j = read_group(toks, i + 1)
                if group:
                    out.append(f"の{_read_math(group)}乗")
                i = j
                prev = "operand"
                continue
            elif op == "√":
                group, j = read_group(toks, i + 1)
                out.append("ルート" + _read_math(group))
                i = j
                prev = "operand"
                continue
            elif op == "∞":
                out.append("無限大")
                prev = "operand"
            elif op == "%":
                out.append("パーセント")
            elif op == "°":
                out.append("度")
                if nxt is not None and nxt.text in ("C", "F") and not nxt.space_before:
                    i += 1
            elif op == "(":
                groups.append(len(out))
            elif op == ")":
                last_group = groups.pop() if groups else -1
                prev = "operand"
        i += 1
    return "".join(w for w in out if w)


def normalize(text: str) -> str:
    """The character's line -> text OpenJTalk reads the way a Japanese teacher would."""
    s = unicodedata.normalize("NFC", text).translate(FULLWIDTH)
    for a, b in _SYMBOLS.items():
        s = s.replace(a, b)
    s = latex(s)
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)  # 12,000 -> 12000 (OpenJTalk reads the comma)
    s = re.sub(r"(?<=\d)\s*:\s*(?=\d)", "対", s)  # ratio 3:4
    s = re.sub(r"(?<=\d)\s*~\s*(?=\d)", "から", s)
    s = re.sub(r"\s*[\r\n]+\s*", "。", s)
    toks = tokens(s)
    mark_math(toks)
    out: list[str] = []
    run: list[Tok] = []

    def flush() -> None:
        # No spaces around or inside math: OpenJTalk treats a space as a word break, which
        # would stop it from reading 3本 as さんぼん.
        if run:
            out.append(_read_math(run))
            run.clear()

    for t in toks:
        if t.math:
            run.append(t)
            continue
        flush()
        if t.kind == "op" and t.text in "()|":
            continue
        spaced = t.space_before and t.kind == "word" and bool(out) and out[-1][-1:].isascii()
        out.append((" " if spaced else "") + t.text)  # keep spaces only between Latin words
    flush()
    return "".join(out).strip()


# ---------------------------------------------------------------------------- readings

SUTEGANA = frozenset("ゃゅょぁぃぅぇぉ")
_PUNCT = {
    "。": ".", "．": ".", ".": ".", "、": ",", "，": ",", ",": ",", "！": "!", "!": "!",
    "？": "?", "?": "?", "…": "…", "「": "“", "『": "“", "」": "”", "』": "”", "：": ",", ":": ",",
    "；": ",", ";": ",", "～": "—", "~": "—",
}  # fmt: skip
_SENTENCE_END = frozenset(".!?")
_VOWEL = {"a": "a", "i": "i", "ɯ": "u", "ɨ": "u", "u": "u", "e": "e", "o": "o"}


def kata2hira(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def hira2kata(s: str) -> str:
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)


def moras(hira: str) -> list[str]:
    """Hiragana -> morae; small kana join the previous kana (きゃ, ふぁ)."""
    out: list[str] = []
    for ch in hira:
        if ch in SUTEGANA and out and out[-1] not in ("っ", "ん", "ー") and len(out[-1]) == 1:
            out[-1] += ch
        elif ch in HEPBURN or ch in ("っ", "ん", "ー"):
            out.append(ch)
    return out


def mora_ipa(mora: str, next_ipa: str) -> str:
    """One mora -> IPA (the misaki/cutlet mapping, including ん assimilation)."""
    if mora in HEPBURN:
        return HEPBURN[mora]
    if len(mora) == 2 and mora[0] in HEPBURN and mora[1] in HEPBURN:
        return HEPBURN[mora[0]][:-1] + HEPBURN[mora[1]]
    if mora == "ー":
        return "ː"
    if mora == "っ":
        return "ʔ"
    if mora == "ん":
        if next_ipa[:1] in ("m", "p", "b"):
            return "m"
        if next_ipa[:1] in ("k", "ɡ"):
            return "ŋ"
        if next_ipa.startswith(("ɲ", "ʨ", "ʥ")):
            return "ɲ"
        if next_ipa[:1] in ("n", "t", "d", "ɾ", "z"):
            return "n"
        return "ɴ"
    return ""


@dataclass
class _Item:
    kind: str  # "mora" | "punct" | "space"
    text: str  # hiragana mora / phoneme punctuation


def _items(features: list[Any]) -> list[_Item]:
    """OpenJTalk words -> morae with word spaces the way misaki's cutlet spaced them."""
    items: list[_Item] = []
    prev_numeral = False
    for f in features:
        string, pron, size = str(f["string"]), str(f["pron"]), int(f["mora_size"])
        if size <= 0:
            punct = _PUNCT.get(string)
            if punct is not None:
                while items and items[-1].kind == "space":
                    items.pop()
                items.append(_Item("punct", punct))
                if punct not in "“":
                    items.append(_Item("space", " "))
            prev_numeral = False
            continue
        ms = moras(kata2hira(pron.replace("’", "").replace("'", "")))
        if not ms:
            continue
        numeral = f.get("pos_group1") == "数"
        joined = ms[0] in ("ー", "っ") or (prev_numeral and (numeral or f.get("pos_group1") == "接尾"))
        if items and items[-1].kind == "mora" and not joined:
            items.append(_Item("space", " "))
        items.extend(_Item("mora", m) for m in ms)
        prev_numeral = numeral
    while items and items[-1].kind == "space":
        items.pop()
    return items


def _sentences(items: list[_Item]) -> list[Sentence]:
    out: list[Sentence] = []
    ps = ""
    units: list[Unit] = []
    last_vowel = "a"
    for k, item in enumerate(items):
        if item.kind == "space":
            # cutlet drops the space around a geminate (っ) and before a long-vowel mark
            nxt = items[k + 1] if k + 1 < len(items) else None
            if ps and not ps.endswith((" ", "ʔ", "“")) and not (nxt and nxt.text in ("っ", "ー")):
                ps += " "
            continue
        if item.kind == "punct":
            ps = ps.rstrip() + item.text
            if item.text in _SENTENCE_END:
                if units:
                    out.append(Sentence(ps.strip(), units))
                ps, units = "", []
            continue
        nxt_ipa = ""
        for later in items[k + 1 :]:
            if later.kind == "mora":
                nxt_ipa = mora_ipa(later.text, "")
                break
            if later.kind == "punct":
                break
        ipa = mora_ipa(item.text, nxt_ipa)
        if not ipa:
            continue
        if item.text == "ー":
            vowel = last_vowel
        elif item.text in ("っ", "ん"):
            vowel = "n"
        else:
            vowel = _VOWEL.get(ipa[-1], "a")
            last_vowel = vowel
        units.append(Unit(hira2kata(item.text), vowel, len(ps), len(ps) + len(ipa)))
        ps += ipa
    if units:
        out.append(Sentence(ps.strip(), units))
    return out


class JapaneseFrontend:
    """Text -> Kokoro phoneme sentences with mora units. Thread-safe (one lock)."""

    def __init__(self) -> None:
        import pyopenjtalk

        self._pyopenjtalk = pyopenjtalk
        self._lock = threading.Lock()

    def features(self, text: str) -> list[Any]:
        """OpenJTalk NJD features (dicts: string, pron, mora_size, pos_group1, ...)."""
        with self._lock:
            result: list[Any] = self._pyopenjtalk.run_frontend(text, use_sudachi_kanji_yomi=False)
        return result

    def sentences(self, text: str) -> list[Sentence]:
        spoken = normalize(text)
        if not spoken:
            return []
        return _sentences(_items(self.features(spoken)))
