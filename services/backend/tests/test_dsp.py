"""Voice post-processing chain and preset store (synthetic signals, no TTS model)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest
from scipy.signal import freqz

from studymate.errors import UserFacingError
from studymate.protocol.backend import VoicePreset
from studymate.speech import dsp
from studymate.speech.presets import BUILTIN_IDS, BUILTIN_PRESETS, PresetStore

DEFAULTS = {"ko": "female_bright", "ja": "ja_bright", "en": "en_bright"}

SR = 22050


@dataclass
class T:
    char: str
    start_ms: float
    end_ms: float


def vowel(f0: float = 220.0, seconds: float = 1.5, sr: int = SR) -> np.ndarray:
    """Harmonic tone with a slight vibrato and formant-like harmonic weights."""
    t = np.arange(int(seconds * sr)) / sr
    inst = f0 * (1 + 0.01 * np.sin(2 * np.pi * 5 * t))
    phase = 2 * np.pi * np.cumsum(inst) / sr
    y = np.zeros_like(t)
    for h in range(1, 25):
        freq = f0 * h
        if freq > sr / 2 - 500:
            break
        weight = np.exp(-(((freq - 700) / 300) ** 2)) + 0.6 * np.exp(-(((freq - 1200) / 400) ** 2)) + 0.05
        y += weight * np.sin(h * phase)
    y *= 0.3 / np.max(np.abs(y))
    fade = np.minimum(1, np.minimum(t, t[-1] - t) / 0.02)
    return (y * fade).astype(np.float32)


def preset(**overrides: float) -> VoicePreset:
    values: dict[str, float] = {
        "pitch_semitones": 0.0,
        "formant_ratio": 1.0,
        "speed": 1.0,
        "brightness_db": 0.0,
        "warmth_db": 0.0,
        "reverb": 0.0,
        "volume_db": 0.0,
    }
    values.update(overrides)
    return VoicePreset(preset_id="t", name="테스트", gender="neutral", builtin=False, **values)


@pytest.mark.parametrize("semitones", [-12.0, -8.0, 3.0, 7.0])
def test_pitch_shift_moves_f0(semitones: float) -> None:
    x = vowel(200.0)
    base = dsp.median_f0(x, SR)
    assert base == pytest.approx(200.0, rel=0.03)
    y = dsp.world_transform(x, SR, pitch_semitones=semitones)
    assert dsp.median_f0(y, SR) == pytest.approx(base * 2 ** (semitones / 12), rel=0.04)


def test_formant_warp_moves_envelope_peak() -> None:
    bins = 513
    freqs = np.arange(bins)
    env = np.exp(-(((freqs - 100) / 10.0) ** 2)) + 1e-6
    sp = np.tile(env, (4, 1))
    assert int(np.argmax(dsp.warp_envelope(sp, 1.2)[0])) == 120
    assert int(np.argmax(dsp.warp_envelope(sp, 0.8)[0])) == 80


def test_formant_only_keeps_pitch() -> None:
    x = vowel(220.0)
    y = dsp.world_transform(x, SR, formant_ratio=0.85)
    assert dsp.median_f0(y, SR) == pytest.approx(220.0, rel=0.04)


@pytest.mark.parametrize("speed", [0.5, 0.8, 1.25, 2.0])
def test_speed_changes_duration_and_timings(speed: float) -> None:
    x = vowel(200.0, seconds=2.0)
    timings = [T("가", 100.0, 400.0), T("나", 400.0, 900.0), T("다", 900.0, 1800.0)]
    out = dsp.process(x, SR, preset(speed=speed), timings, SR)
    assert out.duration_ms == pytest.approx(2000.0 / speed, rel=0.02)
    for (char, start, end), src in zip(out.timings, timings, strict=True):
        assert char == src.char
        assert start == pytest.approx(src.start_ms / speed)
        assert end == pytest.approx(src.end_ms / speed)
    # pitch is untouched by a pure tempo change
    assert dsp.median_f0(out.audio, SR) == pytest.approx(200.0, rel=0.04)


def test_neutral_preset_skips_world_and_resamples() -> None:
    x = vowel(200.0, seconds=1.0, sr=44100)
    out = dsp.process(x, 44100, preset(), [T("가", 0.0, 500.0)], 24000)
    assert out.sample_rate == 24000
    assert len(out.audio) == pytest.approx(24000, abs=2)
    assert out.timings == [("가", 0.0, 500.0)]


def test_shelves_hit_their_gain() -> None:
    b, a = dsp.shelf_coeffs(44100, 250.0, 6.0, "low")
    _, h = freqz(b, a, worN=[10.0, 20000.0], fs=44100)
    assert 20 * np.log10(abs(h[0])) == pytest.approx(6.0, abs=0.2)
    assert 20 * np.log10(abs(h[1])) == pytest.approx(0.0, abs=0.2)
    b, a = dsp.shelf_coeffs(44100, 3000.0, -6.0, "high")
    _, h = freqz(b, a, worN=[50.0, 20000.0], fs=44100)
    assert 20 * np.log10(abs(h[0])) == pytest.approx(0.0, abs=0.2)
    assert 20 * np.log10(abs(h[1])) == pytest.approx(-6.0, abs=0.3)


def test_reverb_adds_a_decaying_tail() -> None:
    click = np.zeros(SR // 2, dtype=np.float32)
    click[-110:-100] = 0.5
    wet = dsp.reverb(click, SR, 0.5)
    assert len(wet) > len(click) + SR // 20  # the tail outlives the input
    late = wet[len(click) + SR // 50 : len(click) + SR // 20]
    assert float(np.max(np.abs(late))) > 1e-3  # energy long after the click
    assert dsp.reverb(click, SR, 0.0) is click


def test_limiter_and_volume() -> None:
    x = vowel(200.0)
    out = dsp.process(x, SR, preset(volume_db=12.0), [], SR)
    assert float(np.max(np.abs(out.audio))) <= dsp.LIMIT_CEILING + 1e-6
    quiet = dsp.process(x, SR, preset(volume_db=-12.0), [], SR)
    ratio = float(np.max(np.abs(quiet.audio))) / float(np.max(np.abs(x)))
    assert ratio == pytest.approx(10 ** (-12 / 20), rel=0.02)


def test_wav_roundtrip() -> None:
    x = vowel(200.0, seconds=0.5)
    data = dsp.wav_bytes(x, SR)
    assert data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    y, sr = dsp.read_wav(data)
    assert sr == SR and len(y) == len(x)
    assert float(np.max(np.abs(y - x))) < 1e-4


# ---------------------------------------------------------------------------- presets


def test_builtin_presets_are_valid_and_varied() -> None:
    ids = [p.preset_id for p in BUILTIN_PRESETS]
    assert len(ids) == len(set(ids))
    for p in BUILTIN_PRESETS:
        assert p.builtin
        VoicePreset.model_validate(p.model_dump())  # within schema ranges
    # product decision: every built-in voice is female, in every language
    assert {p.gender for p in BUILTIN_PRESETS} == {"female"}
    assert BUILTIN_IDS.isdisjoint({"male_soft", "male_low", "male_boy"})
    by_lang = {lang: [p for p in BUILTIN_PRESETS if p.lang == lang] for lang in ("ko", "ja", "en")}
    assert len(by_lang["ko"]) == 3 and len(by_lang["ja"]) >= 3 and len(by_lang["en"]) >= 3
    assert "female_bright" in BUILTIN_IDS


def test_female_presets_stay_in_female_range() -> None:
    """The Korean base speaker is female (~215 Hz); its presets must stay clearly female."""
    x = vowel(215.0)
    for p in BUILTIN_PRESETS:
        if p.lang != "ko":
            continue
        y = dsp.world_transform(x, SR, p.pitch_semitones, p.formant_ratio, 1.0)
        assert dsp.median_f0(y, SR) > 180, p.preset_id


def test_preset_store_roundtrip(tmp_path: Path) -> None:
    store = PresetStore(tmp_path / "voice-presets.json", DEFAULTS)
    assert store.default_id() == "female_bright"
    mine = preset(pitch_semitones=-2.0).model_copy(update={"preset_id": "user-1", "name": "내 목소리"})
    store.save(mine, make_default=True)
    assert store.default_id() == "user-1"
    got = store.get("user-1")
    assert got is not None and got.pitch_semitones == -2.0 and not got.builtin

    # replace keeps one entry
    store.save(mine.model_copy(update={"speed": 1.2}))
    assert [p.preset_id for p in store.presets()].count("user-1") == 1
    assert store.get("user-1") is not None and store.get("user-1").speed == 1.2  # type: ignore[union-attr]

    # a fresh store reads the same file
    again = PresetStore(tmp_path / "voice-presets.json", DEFAULTS)
    assert again.default_id() == "user-1"

    store.delete("user-1")
    assert store.get("user-1") is None
    assert store.default_id() == "female_bright"  # default falls back when deleted


def test_builtins_are_protected(tmp_path: Path) -> None:
    store = PresetStore(tmp_path / "voice-presets.json", DEFAULTS)
    with pytest.raises(UserFacingError) as err:
        store.delete("female_calm")
    assert err.value.code == "builtin_preset"
    edited = BUILTIN_PRESETS[0].model_copy(update={"pitch_semitones": 5.0})
    with pytest.raises(UserFacingError):
        store.save(edited)
    # an unchanged built-in may be saved to make it the default
    store.save(next(p for p in BUILTIN_PRESETS if p.preset_id == "female_calm"), make_default=True)
    assert store.default_id() == "female_calm"
    assert store.get("female_bright") == BUILTIN_PRESETS[0]
    with pytest.raises(UserFacingError):
        store.delete("does-not-exist")


def test_corrupt_store_is_tolerated(tmp_path: Path) -> None:
    path = tmp_path / "voice-presets.json"
    path.write_text('{"presets": [{"preset_id": "x"}], "default_preset_id": "x"}', encoding="utf-8")
    store = PresetStore(path, DEFAULTS)
    assert [p.preset_id for p in store.presets()] == [p.preset_id for p in BUILTIN_PRESETS]
    assert store.default_id() == "female_bright"
