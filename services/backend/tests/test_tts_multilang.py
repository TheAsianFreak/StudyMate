"""Japanese/English speech: text normalisation, G2P units, Kokoro synthesis and timings,
per-language presets and models, language-aware handlers."""

from __future__ import annotations

import base64
import json
import os
import re
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from studymate.config import Lang
from studymate.errors import UserFacingError
from studymate.main import app
from studymate.services import get_services
from studymate.speech import dsp, english, japanese
from studymate.speech.presets import BUILTIN_PRESETS, SPEAKERS, PresetStore, lang_of, speaker_of
from studymate.speech.units import Sentence, Unit, pack, split_long
from studymate.system.downloader import load_registry

SERVICES = get_services()
MODELS = SERVICES.settings.models_dir
KOKORO = MODELS / "tts" / "kokoro-82m"
SPACY = MODELS / "tts" / "spacy" / "en_core_web_sm"
DEFAULTS = {"ko": "female_bright", "ja": "ja_bright", "en": "en_bright"}


def installed(*model_ids: str) -> bool:
    return all(SERVICES.registry.installed(m) for m in model_ids)


needs_ja = pytest.mark.skipif(
    not installed(*SERVICES.settings.tts.model_ids("ja")), reason="Kokoro ja not installed"
)
needs_en = pytest.mark.skipif(
    not installed(*SERVICES.settings.tts.model_ids("en")), reason="Kokoro en not installed"
)


# ---------------------------------------------------------------------------- English text


@pytest.mark.parametrize(
    ("n", "words"),
    [
        (0, "zero"),
        (13, "thirteen"),
        (42, "forty two"),
        (100, "one hundred"),
        (1392, "one thousand three hundred ninety two"),
        (12000, "twelve thousand"),
        (2_000_005, "two million five"),
    ],
)
def test_english_cardinal(n: int, words: str) -> None:
    assert english.cardinal(n) == words


def test_english_ordinal_year_fraction() -> None:
    assert [english.ordinal(n) for n in (1, 2, 3, 5, 12, 20, 21, 100)] == [
        "first", "second", "third", "fifth", "twelfth", "twentieth", "twenty first", "one hundredth",
    ]  # fmt: skip
    assert english.year(1392) == "thirteen ninety two"
    assert english.year(2024) == "twenty twenty four"
    assert english.year(2005) == "two thousand five"
    assert english.year(1905) == "nineteen oh five"
    assert english.fraction(1, 2) == "one half"
    assert english.fraction(3, 4) == "three quarters"
    assert english.fraction(2, 3) == "two thirds"
    assert english.fraction(5, 12) == "five over twelve"
    assert english.number("3.14") == "three point one four"
    assert english.number("007") == "zero zero seven"


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        ("First, move 3 to the right side.", "First, move three to the right side."),
        ("2x + 3 = 7", "two [x] plus three equals seven"),
        ("f(x) = x^2 + 2x + 1", "[f] of [x] equals [x] squared plus two [x] plus one"),
        (r"$\frac{x}{2} + 3 = 7$", "[x] over two plus three equals seven"),
        (r"\sqrt{16} = 4", "the square root of sixteen equals four"),
        ("3 x 4 = 12", "three times four equals twelve"),
        ("3/4 of the class", "three quarters of the class"),
        ("3.14 is close to π", "three point one four is close to pi"),
        ("-5 + 3 = -2", "negative five plus three equals negative two"),
        ("y = -2x + 1", "[y] equals negative two [x] plus one"),
        ("The area is 12 cm²", "The area is twelve square centimeters"),
        ("It was founded in 1392.", "It was founded in thirteen ninety two."),
        ("The accuracy is 85%", "The accuracy is eighty five percent"),
        ("x ≤ 5", "[x] is less than or equal to five"),
        ("Water boils at 100°C.", "Water boils at one hundred degrees Celsius."),
        ("Take a look at a triangle.", "Take a look at a triangle."),
        ("a + b = c", "[a] plus [b] equals [c]"),
        ("the x-axis is well-known", "the x axis is well known"),
        ("It costs $3.50.", "It costs three dollars and fifty cents."),
        ("the 1st and 22nd", "the first and twenty second"),
        ("2^10 = 1024", "two to the power of ten equals one thousand twenty four"),
        ("the ratio 3:4", "the ratio three to four"),
        ("12,000 students", "twelve thousand students"),
    ],
)
def test_english_normalize(text: str, spoken: str) -> None:
    assert english.normalize(text) == spoken


def test_english_syllables_and_vowels() -> None:
    # "problem": the lips close on p, b and m
    ps = "pɹˈɑbləm"
    units = [(ps[a:b], v) for a, b, v in english.syllables(ps)]
    assert units == [("p", "n"), ("ɹˈɑ", "a"), ("b", "n"), ("lə", "a"), ("m", "n")]
    assert [v for _, _, v in english.syllables("ˈikwᵊlz")] == ["i", "u"]
    three_plus = "θɹˈiplˈʌs"
    assert "".join(three_plus[a:b] for a, b, _ in english.syllables(three_plus)) == three_plus
    assert english.syllables("") == []
    assert english.arpabet_to_misaki(["HH", "AH0", "L", "OW1"]) == "həlˈO"
    assert english.romaji("Tsukuyomi") == "tsˌukujˈOmi"
    assert english.romaji("Street") is None


# ---------------------------------------------------------------------------- Japanese text


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        ("まず3を右辺に移項します。", "まず3を右辺に移項します。"),
        ("2x + 3 = 7", "2xたす3イコール7"),
        ("f(x) = x^2 + 2x + 1", "fxイコールxの2乗たす2xたす1"),
        (r"$\frac{x}{2} + 3 = 7$", "2分のxたす3イコール7"),
        ("(x+1)/2 = 3", "2分のxたす1イコール3"),
        (r"\sqrt{16} = 4", "ルート16イコール4"),
        ("3 x 4 = 12", "3かける4イコール12"),
        ("りんご3個と1/2切れ", "りんご3個と2分の1切れ"),
        ("-5 + 3 = -2", "マイナス5たす3イコールマイナス2"),
        ("面積は12cm²です", "面積は12平方センチメートルです"),
        ("正答率85%", "正答率85パーセント"),
        ("x < 3", "x小なり3"),
        ("12,000人", "12000人"),
        ("水は100℃で沸騰します", "水は100度で沸騰します"),
        ("比は3:4です", "比は3対4です"),
        ("ｘ＝－２", "xイコールマイナス2"),
    ],
)
def test_japanese_normalize(text: str, spoken: str) -> None:
    assert japanese.normalize(text) == spoken


def test_japanese_morae() -> None:
    assert japanese.moras("きょうは") == ["きょ", "う", "は"]
    assert japanese.moras("がっこう") == ["が", "っ", "こ", "う"]
    assert japanese.mora_ipa("きょ", "") == "kʲo"
    assert [japanese.mora_ipa("ん", nxt) for nxt in ("pa", "ka", "ta", "ʨi", "a", "")] == [
        "m", "ŋ", "n", "ɲ", "ɴ", "ɴ",
    ]  # fmt: skip


def test_japanese_frontend_units() -> None:
    fe = japanese.JapaneseFrontend()
    sentences = fe.sentences("3本の鉛筆。今日は二次関数を勉強しましょう！")
    assert len(sentences) == 2
    first = sentences[0]
    assert first.phonemes.startswith("sambon")  # the counter reading survives normalisation
    assert "".join(u.char for u in first.units) == "サンボンノエンピツ"
    second = sentences[1]
    assert second.phonemes.endswith("!")
    for s in sentences:
        for u in s.units:
            assert u.vowel in ("a", "i", "u", "e", "o", "n")
            assert 0 <= u.start < u.end <= len(s.phonemes)
    long_vowel = next(u for u in second.units if u.char == "ー")
    assert long_vowel.vowel == "o"  # キョー keeps the o mouth


# ---------------------------------------------------------------------------- units


def _sentence(words: list[str]) -> Sentence:
    ps, units = "", []
    for w in words:
        if ps:
            ps += " "
        units.append(Unit(w, "a", len(ps), len(ps) + len(w)))
        ps += w
    return Sentence(ps, units)


def test_pack_and_split_keep_units_aligned() -> None:
    long = _sentence(["abcde"] * 30)  # 179 phonemes
    parts = split_long(long, 50)
    assert all(len(p.phonemes) <= 50 for p in parts)
    assert sum(len(p.units) for p in parts) == 30
    for p in parts:
        assert all(p.phonemes[u.start : u.end] == "abcde" for u in p.units)
    chunks = pack([_sentence(["ab", "cd"]), _sentence(["ef"]), long], 60)
    assert chunks[0].phonemes == "ab cd ef"
    for c in chunks:
        assert len(c.phonemes) <= 60
        assert all(c.phonemes[u.start : u.end] == u.char for u in c.units)


# ---------------------------------------------------------------------------- presets


def test_builtin_voices_per_language() -> None:
    for lang in ("ko", "ja", "en"):
        mine = [p for p in BUILTIN_PRESETS if lang_of(p) == lang]
        assert mine, lang
        assert {p.gender for p in mine} == {"female"}
        assert all(p.speaker in SPEAKERS[lang] for p in mine)
        assert DEFAULTS[lang] in {p.preset_id for p in mine}
    ja_speakers = {p.speaker for p in BUILTIN_PRESETS if p.lang == "ja"}
    en_speakers = {p.speaker for p in BUILTIN_PRESETS if p.lang == "en"}
    assert len(ja_speakers) >= 3 and len(en_speakers) >= 3  # distinct native voices
    assert all(s.startswith("jf_") for s in SPEAKERS["ja"])
    assert all(s[1] == "f" for s in SPEAKERS["en"])  # af_*/bf_*: female speakers only
    # names are in their own language
    assert all(re.search(r"[ぁ-んァ-ヶ一-龯]", p.name) for p in BUILTIN_PRESETS if p.lang == "ja")
    assert all(p.name.isascii() for p in BUILTIN_PRESETS if p.lang == "en")


def test_preset_defaults_are_per_language(tmp_path: Path) -> None:
    path = tmp_path / "voice-presets.json"
    # a pre-multilingual file whose default was a (now removed) male built-in
    path.write_text(json.dumps({"presets": [], "default_preset_id": "male_soft"}), encoding="utf-8")
    store = PresetStore(path, DEFAULTS)
    assert [store.default_id(lang) for lang in ("ko", "ja", "en")] == [
        "female_bright",
        "ja_bright",
        "en_bright",
    ]

    ja_copy = next(p for p in BUILTIN_PRESETS if p.preset_id == "ja_calm").model_copy(
        update={"preset_id": "mine-ja", "name": "わたし", "builtin": False, "pitch_semitones": 2.0}
    )
    store.save(ja_copy, make_default=True)
    assert store.default_id("ja") == "mine-ja"
    assert store.default_id("ko") == "female_bright"  # other languages untouched
    got = store.get("mine-ja")
    assert got is not None and got.lang == "ja" and got.speaker == ja_copy.speaker

    store.save(next(p for p in BUILTIN_PRESETS if p.preset_id == "en_calm"), make_default=True)
    assert store.default_id("en") == "en_calm"
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert "default_preset_id" not in stored and stored["default_preset_ids"]["ja"] == "mine-ja"

    store.delete("mine-ja")
    assert store.default_id("ja") == "ja_bright"

    # a legacy Korean default that still exists is honoured
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps({"presets": [], "default_preset_id": "female_calm"}), encoding="utf-8")
    assert PresetStore(legacy, DEFAULTS).default_id("ko") == "female_calm"


def test_preset_speaker_validation(tmp_path: Path) -> None:
    store = PresetStore(tmp_path / "voice-presets.json", DEFAULTS)
    base = next(p for p in BUILTIN_PRESETS if p.preset_id == "en_bright")
    wrong = base.model_copy(update={"preset_id": "x", "name": "x", "builtin": False, "speaker": "jf_alpha"})
    with pytest.raises(UserFacingError) as err:
        store.save(wrong)
    assert err.value.code == "unknown_speaker"
    # a built-in echoed back without lang/speaker (older client) is still "unchanged"
    bare = next(p for p in BUILTIN_PRESETS if p.preset_id == "female_bright").model_copy(
        update={"lang": None, "speaker": None}
    )
    store.save(bare, make_default=True)
    assert store.default_id("ko") == "female_bright"
    # an omitted speaker means the language's default voice
    assert speaker_of(base.model_copy(update={"speaker": None})) == SPEAKERS["en"][0]


# ---------------------------------------------------------------------------- registry / status


def test_registry_tts_entries() -> None:
    entries = {m.id: m for m in load_registry()}
    cfg = SERVICES.settings.tts
    for lang in ("ko", "ja", "en"):
        for model_id in cfg.model_ids(lang):
            entry = entries[model_id]
            assert entry.category == "tts" and entry.required, model_id
            assert entry.langs is not None and lang in entry.langs, model_id
            for f in entry.files:
                assert f.size and f.sha256 and len(f.sha256) == 64, f.path
    assert entries["melo-korean"].langs == ("ko",)
    assert entries["kokoro-82m"].langs == ("ja", "en")
    for lang in ("ja", "en"):
        files = {Path(f.path).stem for f in entries[cfg.kokoro_voices_ids[lang]].files}
        assert files == set(SPEAKERS[lang]), lang  # exactly the voices the presets can use
    all_paths = [f.path for m in entries.values() for f in m.files]
    assert not any(re.search(r"/[abj]m_\w+\.pt$", p) for p in all_paths)  # no male speakers
    assert entries[cfg.g2p_oov_id].langs == ("en",)
    assert set(entries[cfg.cmudict_id].langs or ()) == {"ko", "en"}
    assert all(m.langs is None for m in entries.values() if m.category != "tts")


@pytest.fixture
def lang_switch() -> Iterator[None]:
    before = SERVICES.lang
    yield
    SERVICES.set_lang(before)


def test_status_reports_langs_and_tts_per_language(lang_switch: None) -> None:
    from studymate.handlers.system import build_status

    for lang in ("ko", "ja", "en"):
        SERVICES.set_lang(lang)  # type: ignore[arg-type]
        status = build_status(SERVICES)
        models = {m["model_id"]: m for m in status["models"]}
        assert models["kokoro-voices-ja"]["langs"] == ["ja"]
        assert "langs" not in models["whisper-small"]
        expected = installed(*SERVICES.settings.tts.model_ids(lang))
        assert status["capabilities"]["tts"] is expected


# ---------------------------------------------------------------------------- synthesis


@pytest.fixture(scope="module")
def kokoro_ja() -> object:
    if not installed(*SERVICES.settings.tts.model_ids("ja")):
        pytest.skip("Kokoro ja not installed")
    import asyncio

    from studymate.speech.service import tts_engine

    return asyncio.run(tts_engine(SERVICES, "ja"))


@pytest.fixture(scope="module")
def kokoro_en() -> object:
    if not installed(*SERVICES.settings.tts.model_ids("en")):
        pytest.skip("Kokoro en not installed")
    import asyncio

    from studymate.speech.service import tts_engine

    return asyncio.run(tts_engine(SERVICES, "en"))


def _check_timings(syn: object) -> None:
    phonemes = syn.phonemes  # type: ignore[attr-defined]
    duration = syn.duration_ms  # type: ignore[attr-defined]
    assert phonemes
    prev = 0.0
    for p in phonemes:
        assert p.vowel in ("a", "i", "u", "e", "o", "n")
        assert p.end_ms > p.start_ms >= prev - 1e-6
        prev = p.end_ms
    assert prev <= duration + 1e-6


@needs_ja
def test_kokoro_japanese_synthesis(kokoro_ja: object) -> None:
    syn = kokoro_ja.synthesize("こんにちは。まず、3を右辺に移項します。", speaker="jf_alpha", seed=0)  # type: ignore[attr-defined]
    assert syn.sample_rate == 24000
    rms = float(np.sqrt(np.mean(np.square(syn.audio))))
    assert rms > 0.02 and float(np.max(np.abs(syn.audio))) <= 1.0
    _check_timings(syn)
    assert "".join(p.char for p in syn.phonemes).startswith("コンニチワマズサンヲ")
    # native speed: faster speech, same units, timings scale with it
    fast = kokoro_ja.synthesize(
        "こんにちは。まず、3を右辺に移項します。", speaker="jf_alpha", speed=1.5, seed=0
    )  # type: ignore[attr-defined]
    assert fast.duration_ms < 0.8 * syn.duration_ms
    assert [p.char for p in fast.phonemes] == [p.char for p in syn.phonemes]


@needs_en
def test_kokoro_english_synthesis(kokoro_en: object) -> None:
    text = "Hello! If we multiply both sides by 2, we get x = 8."
    for speaker in SPEAKERS["en"]:
        syn = kokoro_en.synthesize(text, speaker=speaker, seed=0)  # type: ignore[attr-defined]
        _check_timings(syn)
        assert 150 < dsp.median_f0(syn.audio, syn.sample_rate) < 330, speaker  # female voices
    assert {p.vowel for p in syn.phonemes} >= {"a", "e", "i", "o", "n"}


def _receive(ws: object, kind: str) -> dict[str, object]:
    """Next message of `kind`, skipping `status` broadcasts (set_language sends two)."""
    while True:
        msg: dict[str, object] = ws.receive_json()  # type: ignore[attr-defined]
        if msg["type"] == kind or msg["type"] == "error":
            return msg


@pytest.mark.parametrize("lang", ["ja", "en"])
def test_tts_request_follows_language(lang: Lang, lang_switch: None) -> None:
    if not installed(*SERVICES.settings.tts.model_ids(lang)):
        pytest.skip(f"Kokoro {lang} not installed")
    text = {"ja": "今日は二次関数を勉強しましょう。", "en": "Today we'll study quadratic functions."}[lang]
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "set_language", "id": "l", "lang": lang})
        status = ws.receive_json()
        assert status["type"] == "status" and status["lang"] == lang and status["capabilities"]["tts"]
        ws.send_json({"type": "voice_presets_get", "id": "g"})
        presets = _receive(ws, "voice_presets")
        assert presets["default_preset_id"] == DEFAULTS[lang]
        ws.send_json({"type": "tts_request", "id": "t1", "text": text})
        msg = _receive(ws, "tts_audio")
        assert msg["type"] == "tts_audio" and msg["id"] == "t1", msg
        audio, sr = dsp.read_wav(base64.b64decode(msg["wav_base64"]))
        assert sr == msg["sample_rate"] and msg["duration_ms"] == pytest.approx(1000 * len(audio) / sr, abs=1)
        assert msg["phonemes"] and all(p["vowel"] in "aiueon" for p in msg["phonemes"])
        assert msg["phonemes"][-1]["end_ms"] <= msg["duration_ms"]
        # a Korean voice id left over in the shell settings falls back to this language
        ws.send_json({"type": "tts_request", "id": "t2", "text": text, "voice": "female_girl"})
        other = _receive(ws, "tts_audio")
        assert other["type"] == "tts_audio" and other["phonemes"][0]["vowel"]
        # the post-processing chain applies to every language
        slow = {**next(p for p in BUILTIN_PRESETS if p.preset_id == DEFAULTS[lang]).model_dump(),
                "preset_id": "preview", "builtin": False, "speed": 0.6}  # fmt: skip
        ws.send_json({"type": "tts_request", "id": "t3", "text": text, "preset": slow})
        preview = _receive(ws, "tts_audio")
        assert preview["duration_ms"] > 1.4 * msg["duration_ms"]


def test_ja_en_speech_never_touches_the_network() -> None:
    """Frontends and Kokoro load only local files (CLAUDE.md rule 7)."""
    if not (
        installed(*SERVICES.settings.tts.model_ids("ja"))
        and installed(*SERVICES.settings.tts.model_ids("en"))
    ):
        pytest.skip("Kokoro ja/en not installed")
    import subprocess
    import sys

    code = (
        "import asyncio, socket\n"
        "loop = asyncio.new_event_loop()  # its self-pipe is a local socketpair; create it first\n"
        "class Blocked(socket.socket):\n"
        "    def __init__(self, *a, **k):\n"
        "        raise RuntimeError('network access attempted')\n"
        "def no_dns(*a, **k):\n"
        "    raise RuntimeError('network access attempted')\n"
        "socket.socket = Blocked\n"
        "socket.getaddrinfo = no_dns\n"
        "from studymate.services import get_services\n"
        "from studymate.speech.service import tts_engine\n"
        "s = get_services()\n"
        "ja = loop.run_until_complete(tts_engine(s, 'ja')).synthesize('3本の鉛筆です。')\n"
        "en = loop.run_until_complete(tts_engine(s, 'en'))\n"
        "en = en.synthesize('Tsukuyomi solved 2x + 3 = 7.', speaker='bf_emma')\n"
        "print(len(ja.phonemes), len(en.phonemes))\n"
    )
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "HF_HUB_OFFLINE": "", "TRANSFORMERS_OFFLINE": ""}
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, encoding="utf-8", env=env, timeout=300
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    ja_units, en_units = map(int, proc.stdout.split()[-2:])
    assert ja_units > 5 and en_units > 5


# ---------------------------------------------------------------------------- STT


@pytest.mark.parametrize("lang", ["ja", "en"])
def test_whisper_follows_language(lang: Lang, lang_switch: None) -> None:
    """Kokoro speech -> whisper-small decoding in the app language."""
    small = MODELS / "stt" / "faster-whisper-small"
    if not ((small / "model.bin.ok").exists() and installed(*SERVICES.settings.tts.model_ids(lang))):
        pytest.skip("whisper-small and Kokoro are required")
    import asyncio

    from studymate.speech.service import stt_language, tts_engine
    from studymate.speech.stt import Transcriber, resample

    SERVICES.set_lang(lang)
    assert stt_language(SERVICES) == lang
    engine = asyncio.run(tts_engine(SERVICES, lang))
    text = {
        "ja": "間違えた問題は復習ノートに保存しておきますね。",
        "en": "I will save the questions you missed.",
    }[lang]
    syn = engine.synthesize(text, seed=0)
    heard = Transcriber(small).transcribe(resample(syn.audio, syn.sample_rate, 16000), language=lang)
    if lang == "ja":
        assert re.search(r"[ぁ-んァ-ヶ一-龯]", heard) and "ノート" in heard, heard
    else:
        assert "save" in heard.lower() and "questions" in heard.lower(), heard


# ---------------------------------------------------------------------------- slow

EN_LINES = [
    "Hi! Today we're going to solve a linear equation together.",
    "First, move 3 to the right side.",
    "If we multiply both sides by 2, we get x = 8.",
    "The area of a triangle is the base times the height divided by 2.",
    "Photosynthesis is how plants use light energy to make food.",
    "I'll save the questions you missed in your review notes.",
]
JA_LINES = [
    "こんにちは、今日は一次方程式を一緒に解いてみましょう。",
    "まず、3を右辺に移項します。",
    "両辺に2をかけると、xは8になります。",
    "三角形の面積は、底辺かける高さ割る2です。",
    "光合成は、植物が光のエネルギーを使って養分を作る仕組みです。",
    "間違えた問題は、復習ノートに保存しておきますね。",
]


def _edit(a: list[str] | str, b: list[str] | str) -> int:
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, cb in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (ca != cb))
    return row[len(b)]


@pytest.mark.slow
@pytest.mark.skipif(not os.environ.get("STUDYMATE_SLOW_TESTS"), reason="set STUDYMATE_SLOW_TESTS=1")
@pytest.mark.parametrize("preset_id", [p.preset_id for p in BUILTIN_PRESETS if p.lang in ("ja", "en")])
def test_roundtrip_intelligibility(preset_id: str) -> None:
    """Preset voice -> Whisper (tier model): WER (en) / kana CER (ja) must stay low."""
    import asyncio

    from studymate.speech.service import render_tts, tts_engine
    from studymate.speech.stt import Transcriber, resample

    preset = next(p for p in BUILTIN_PRESETS if p.preset_id == preset_id)
    lang = lang_of(preset)
    if not installed(*SERVICES.settings.tts.model_ids(lang)):
        pytest.skip("Kokoro not installed")
    model_id = SERVICES.registry.pick(SERVICES.tier, "stt")
    if model_id is None:
        pytest.skip("no whisper model installed")
    stt = Transcriber(SERVICES.registry.dir(model_id))
    engine = asyncio.run(tts_engine(SERVICES, lang))
    fe = japanese.JapaneseFrontend()

    def units(text: str) -> list[str] | str:
        if lang == "en":
            return re.sub(
                r"[^a-z0-9' ]", " ", english.normalize(text).lower().replace("[", "").replace("]", "")
            ).split()
        return "".join(
            f["pron"].replace("’", "") for f in fe.features(japanese.normalize(text)) if f["mora_size"]
        )

    errors = total = 0
    for text in JA_LINES if lang == "ja" else EN_LINES:
        payload = render_tts(engine, text, preset, 44100)
        audio, sr = dsp.read_wav(base64.b64decode(payload["wav_base64"]))
        heard = stt.transcribe(resample(audio, sr, 16000), language=lang)
        ref = units(text)
        errors += _edit(ref, units(heard))
        total += len(ref)
    assert errors / total <= (0.1 if "large" in model_id else 0.2), (preset_id, errors / total)
