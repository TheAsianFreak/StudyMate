"""Voice post-processing chain applied after synthesis (SPEC 7.6, VoicePreset).

Order: WORLD (pitch, formant, speed) -> low/high shelf EQ -> reverb -> volume ->
resample -> peak limiter. The chain is model-agnostic; lip-sync timings are rescaled for
the speed change so the audio stays the master clock (design rule 2).

WORLD via pyworld (MIT; WORLD itself is modified BSD).
"""

from __future__ import annotations

import base64
import io
import math
import wave
from collections.abc import Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from functools import lru_cache
from typing import Protocol

import numpy as np
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from scipy.signal import fftconvolve, lfilter, resample_poly

FRAME_PERIOD_MS = 5.0
LIMIT_CEILING = 0.95  # about -0.45 dBFS
WARMTH_HZ = 250.0
BRIGHTNESS_HZ = 3000.0


class Preset(Protocol):
    """Structural view of `protocol.backend.VoicePreset`."""

    pitch_semitones: float
    formant_ratio: float
    speed: float
    brightness_db: float
    warmth_db: float
    reverb: float
    volume_db: float


class _Timing(Protocol):
    char: str
    start_ms: float
    end_ms: float


@dataclass
class Processed:
    audio: np.ndarray  # float32 mono
    sample_rate: int
    timings: list[tuple[str, float, float]]  # (char, start_ms, end_ms)
    vowels: list[str | None] = field(default_factory=list)  # PhonemeTiming.vowel per timing

    @property
    def duration_ms(self) -> float:
        return 1000.0 * len(self.audio) / self.sample_rate


# ---------------------------------------------------------------------------- WORLD


def world_transform(
    audio: np.ndarray, sr: int, pitch_semitones: float = 0.0, formant_ratio: float = 1.0, speed: float = 1.0
) -> np.ndarray:
    """Pitch shift, spectral-envelope (formant) warp and time scaling in one WORLD pass."""
    import pyworld as pw

    x = np.ascontiguousarray(audio, dtype=np.float64)
    f0, t = pw.dio(x, sr, f0_floor=60.0, f0_ceil=900.0, frame_period=FRAME_PERIOD_MS)
    f0 = pw.stonemask(x, f0, t, sr)
    sp = pw.cheaptrick(x, f0, t, sr)
    ap = pw.d4c(x, f0, t, sr)

    if pitch_semitones:
        f0 = f0 * 2.0 ** (pitch_semitones / 12.0)
    if formant_ratio != 1.0:
        sp = warp_envelope(sp, formant_ratio)
    if speed != 1.0:
        f0, sp, ap = time_scale(f0, sp, ap, speed)

    y: np.ndarray = pw.synthesize(
        np.ascontiguousarray(f0), np.ascontiguousarray(sp), np.ascontiguousarray(ap), sr, FRAME_PERIOD_MS
    )
    # Keep loudness comparable to the input (warping moves energy between bands).
    rms_in = float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0
    rms_out = float(np.sqrt(np.mean(np.square(y)))) if len(y) else 0.0
    if rms_out > 1e-9 and rms_in > 0:
        y *= rms_in / rms_out
    return y.astype(np.float32)


def warp_envelope(sp: np.ndarray, ratio: float) -> np.ndarray:
    """Scales the spectral envelope along frequency: ratio > 1 moves formants up."""
    bins = sp.shape[1]
    src = np.clip(np.arange(bins) / ratio, 0, bins - 1)
    lo = np.floor(src).astype(np.int64)
    hi = np.minimum(lo + 1, bins - 1)
    frac = src - lo
    log_sp = np.log(np.maximum(sp, 1e-16))
    warped = log_sp[:, lo] * (1.0 - frac) + log_sp[:, hi] * frac
    out: np.ndarray = np.exp(warped)
    return out


def time_scale(
    f0: np.ndarray, sp: np.ndarray, ap: np.ndarray, speed: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Resamples WORLD frames so the output is `1/speed` as long (t_out = t_in / speed)."""
    n = len(f0)
    m = max(1, int(round(n / speed)))
    pos = np.minimum(np.arange(m) * speed, n - 1)
    lo = np.floor(pos).astype(np.int64)
    hi = np.minimum(lo + 1, n - 1)
    frac = (pos - lo)[:, None]
    nearest = np.minimum(np.round(pos).astype(np.int64), n - 1)
    sp_out = np.exp(np.log(np.maximum(sp[lo], 1e-16)) * (1 - frac) + np.log(np.maximum(sp[hi], 1e-16)) * frac)
    # Voiced/unvoiced decisions must not be averaged; interpolate f0 only inside voiced runs.
    f0_out = f0[nearest].copy()
    both = (f0[lo] > 0) & (f0[hi] > 0)
    f0_out[both] = f0[lo][both] * (1 - frac[both, 0]) + f0[hi][both] * frac[both, 0]
    return f0_out, sp_out, ap[nearest]


def median_f0(audio: np.ndarray, sr: int) -> float:
    """Median f0 (Hz) over voiced frames, analysed at 16 kHz with WORLD Harvest."""
    import pyworld as pw

    x = resample(audio, sr, 16000).astype(np.float64)
    f0, _ = pw.harvest(x, 16000, f0_floor=50.0, f0_ceil=800.0, frame_period=10.0)
    voiced = f0[f0 > 0]
    return float(np.median(voiced)) if len(voiced) else 0.0


# ---------------------------------------------------------------------------- filters


def shelf_coeffs(sr: int, freq: float, gain_db: float, kind: str) -> tuple[np.ndarray, np.ndarray]:
    """RBJ Audio EQ Cookbook shelving biquad (slope S = 1)."""
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * freq / sr
    cos_w0 = math.cos(w0)
    alpha = math.sin(w0) / 2.0 * math.sqrt(2.0)
    sq = 2.0 * math.sqrt(a) * alpha
    if kind == "low":
        b = [
            a * ((a + 1) - (a - 1) * cos_w0 + sq),
            2 * a * ((a - 1) - (a + 1) * cos_w0),
            a * ((a + 1) - (a - 1) * cos_w0 - sq),
        ]
        den = [
            (a + 1) + (a - 1) * cos_w0 + sq,
            -2 * ((a - 1) + (a + 1) * cos_w0),
            (a + 1) + (a - 1) * cos_w0 - sq,
        ]
    elif kind == "high":
        b = [
            a * ((a + 1) + (a - 1) * cos_w0 + sq),
            -2 * a * ((a - 1) + (a + 1) * cos_w0),
            a * ((a + 1) + (a - 1) * cos_w0 - sq),
        ]
        den = [
            (a + 1) - (a - 1) * cos_w0 + sq,
            2 * ((a - 1) - (a + 1) * cos_w0),
            (a + 1) - (a - 1) * cos_w0 - sq,
        ]
    else:
        raise ValueError(kind)
    b_arr, a_arr = np.array(b), np.array(den)
    return b_arr / a_arr[0], a_arr / a_arr[0]


def shelf(audio: np.ndarray, sr: int, freq: float, gain_db: float, kind: str) -> np.ndarray:
    if abs(gain_db) < 1e-3 or freq >= sr / 2:
        return audio
    b, a = shelf_coeffs(sr, freq, gain_db, kind)
    y: np.ndarray = lfilter(b, a, audio)
    return y.astype(np.float32)


# ---------------------------------------------------------------------------- reverb

# Freeverb tunings at 44.1 kHz (Jezar's public-domain design), scaled to other rates.
_COMBS = (1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617)
_ALLPASSES = (556, 441, 341, 225)
_ROOM_FEEDBACK = 0.78  # small room
_DAMPING = 0.35
_ALLPASS_FEEDBACK = 0.5
_IR_SECONDS = 1.2


def _comb(x: np.ndarray, delay: int, feedback: float, damp: float) -> np.ndarray:
    """Lowpass-feedback comb, processed block-wise (block = delay, so each block only
    depends on the previous one)."""
    n = len(x)
    buf = np.zeros(n + delay)
    y = np.zeros(n)
    lp = 0.0
    for start in range(0, n, delay):
        stop = min(start + delay, n)
        out = buf[start:stop]  # buf[k] holds the value written `delay` samples earlier
        y[start:stop] = out
        low, _ = lfilter([1 - damp], [1, -damp], out, zi=[damp * lp])
        lp = float(low[-1]) if len(low) else lp
        buf[start + delay : stop + delay] = x[start:stop] + feedback * low
    return y


def _allpass(x: np.ndarray, delay: int, feedback: float) -> np.ndarray:
    n = len(x)
    buf = np.zeros(n + delay)
    y = np.zeros(n)
    for start in range(0, n, delay):
        stop = min(start + delay, n)
        out = buf[start:stop]
        y[start:stop] = out - x[start:stop]
        buf[start + delay : stop + delay] = x[start:stop] + feedback * out
    return y


@lru_cache(maxsize=4)
def reverb_ir(sr: int) -> np.ndarray:
    """Freeverb impulse response (mono), normalised to unit energy."""
    n = int(_IR_SECONDS * sr)
    scale = sr / 44100.0
    impulse = np.zeros(n)
    impulse[0] = 1.0
    wet = np.zeros(n)
    for d in _COMBS:
        wet += _comb(impulse, max(1, int(d * scale)), _ROOM_FEEDBACK, _DAMPING)
    for d in _ALLPASSES:
        wet = _allpass(wet, max(1, int(d * scale)), _ALLPASS_FEEDBACK)
    fade = np.linspace(1.0, 0.0, n) ** 2  # avoid a hard cut at the IR end
    wet *= fade
    energy = float(np.sqrt(np.sum(np.square(wet))))
    return (wet / energy).astype(np.float32) if energy > 0 else wet.astype(np.float32)


def reverb(audio: np.ndarray, sr: int, mix: float) -> np.ndarray:
    """Adds a small-room reverb; the returned audio is longer by the (trimmed) tail."""
    if mix <= 0 or len(audio) == 0:
        return audio
    ir = reverb_ir(sr)
    wet = fftconvolve(audio, ir)
    dry = np.concatenate([audio, np.zeros(len(wet) - len(audio), dtype=audio.dtype)])
    out: np.ndarray = (1.0 - 0.5 * mix) * dry + mix * wet
    # Trim the tail once it falls below -60 dBFS.
    tail = np.abs(out[len(audio) :])
    loud = np.nonzero(tail > 1e-3)[0]
    end = len(audio) + (int(loud[-1]) + 1 if len(loud) else 0)
    return out[:end].astype(np.float32)


# ---------------------------------------------------------------------------- level


def limit(
    audio: np.ndarray, sr: int, ceiling: float = LIMIT_CEILING, lookahead_ms: float = 3.0
) -> np.ndarray:
    """Look-ahead peak limiter: gain never exceeds what the loudest nearby peak allows."""
    if len(audio) == 0 or float(np.max(np.abs(audio))) <= ceiling:
        return audio
    w = max(1, int(sr * lookahead_ms / 1000))
    need = np.minimum(1.0, ceiling / np.maximum(np.abs(audio), 1e-9))
    gain = minimum_filter1d(need, size=2 * w + 1, mode="nearest")
    gain = uniform_filter1d(gain, size=2 * w + 1, mode="nearest")
    limited: np.ndarray = np.clip(audio * gain, -ceiling, ceiling)
    return limited.astype(np.float32)


def resample(audio: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out or len(audio) == 0:
        return audio.astype(np.float32, copy=False)
    ratio = Fraction(sr_out, sr_in).limit_denominator(1000)
    y: np.ndarray = resample_poly(audio, ratio.numerator, ratio.denominator)
    return y.astype(np.float32)


# ---------------------------------------------------------------------------- chain


def needs_world(preset: Preset) -> bool:
    return (
        abs(preset.pitch_semitones) > 1e-3
        or abs(preset.formant_ratio - 1.0) > 1e-3
        or abs(preset.speed - 1.0) > 1e-3
    )


def process(
    audio: np.ndarray, sr: int, preset: Preset, timings: Sequence[_Timing], out_rate: int
) -> Processed:
    y = audio.astype(np.float32, copy=False)
    speed = float(preset.speed)
    if needs_world(preset):
        y = world_transform(y, sr, preset.pitch_semitones, preset.formant_ratio, speed)
    else:
        speed = 1.0
    y = shelf(y, sr, WARMTH_HZ, preset.warmth_db, "low")
    y = shelf(y, sr, BRIGHTNESS_HZ, preset.brightness_db, "high")
    y = reverb(y, sr, float(preset.reverb))
    if preset.volume_db:
        y = y * np.float32(10.0 ** (preset.volume_db / 20.0))
    y = resample(y, sr, out_rate)
    y = limit(y, out_rate)
    scaled = [(t.char, t.start_ms / speed, t.end_ms / speed) for t in timings]
    vowels = [getattr(t, "vowel", None) for t in timings]
    return Processed(y.astype(np.float32), out_rate, scaled, vowels)


def wav_bytes(audio: np.ndarray, sr: int) -> bytes:
    pcm = np.clip(audio, -1.0, 1.0)
    pcm16 = np.round(pcm * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16.tobytes())
    return buf.getvalue()


def wav_base64(audio: np.ndarray, sr: int) -> str:
    return base64.b64encode(wav_bytes(audio, sr)).decode("ascii")


def read_wav(data: bytes) -> tuple[np.ndarray, int]:
    """16-bit mono WAV bytes -> (float32 audio, sample rate). Used by tests and tools."""
    with wave.open(io.BytesIO(data), "rb") as wf:
        sr = wf.getframerate()
        pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype="<i2")
    return (pcm.astype(np.float32) / 32767.0), sr
