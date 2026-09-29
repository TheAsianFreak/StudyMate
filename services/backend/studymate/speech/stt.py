"""Speech-to-text: faster-whisper transcription and a push-to-talk recorder.

Privacy: microphone audio lives only in memory (numpy buffers) and is dropped as soon as
the final transcript is produced. Nothing is written to disk or logged, and neither are
transcripts.
"""

from __future__ import annotations

import logging
import math
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from scipy.signal import resample_poly

from studymate.config import SttConfig

log = logging.getLogger(__name__)

VAD_RATE = 16000
VAD_WINDOW = 512  # samples at 16 kHz (32 ms), what Silero expects
VAD_CONTEXT = 64


def resample(audio: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out or len(audio) == 0:
        return audio.astype(np.float32, copy=False)
    ratio = Fraction(sr_out, sr_in).limit_denominator(1000)
    y: np.ndarray = resample_poly(audio, ratio.numerator, ratio.denominator)
    return y.astype(np.float32)


class Transcriber:
    """One faster-whisper model (CPU int8 by default); safe to call from worker threads."""

    def __init__(
        self,
        model_dir: Path,
        *,
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int = 0,
        language: str | None = None,
        beam_size: int = 5,
    ) -> None:
        from faster_whisper import WhisperModel

        self.language = language
        self.beam_size = beam_size
        self.model = WhisperModel(
            str(model_dir),
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
            local_files_only=True,
        )
        log.info("whisper model loaded: %s (%s, %s)", model_dir.name, device, compute_type)

    def transcribe(
        self,
        audio: np.ndarray,
        *,
        vad_filter: bool = True,
        beam_size: int | None = None,
        language: str | None = None,
    ) -> str:
        """`audio`: float32 mono at 16 kHz. `language` (ko/ja/en) overrides the default so
        one loaded model serves every app language."""
        if len(audio) < VAD_RATE // 10:
            return ""
        segments, _ = self.model.transcribe(
            audio.astype(np.float32, copy=False),
            language=language or self.language,
            beam_size=beam_size or self.beam_size,
            vad_filter=vad_filter,
            condition_on_previous_text=False,
            without_timestamps=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()


class StreamingVad:
    """Silero VAD bundled with faster-whisper, run window by window with carried state.

    Equivalent to `faster_whisper.vad.SileroVADModel.__call__` on the whole buffer.
    """

    def __init__(self) -> None:
        from faster_whisper.vad import get_vad_model

        self._session = get_vad_model().session
        self._h = np.zeros((1, 1, 128), dtype=np.float32)
        self._c = np.zeros((1, 1, 128), dtype=np.float32)
        self._ctx = np.zeros((1, VAD_CONTEXT), dtype=np.float32)
        self._pending = np.zeros(0, dtype=np.float32)

    def push(self, audio16k: np.ndarray) -> list[float]:
        """Speech probability for every completed 32 ms window."""
        buf = np.concatenate([self._pending, audio16k.astype(np.float32, copy=False)])
        probs: list[float] = []
        n = len(buf) // VAD_WINDOW
        for k in range(n):
            window = buf[k * VAD_WINDOW : (k + 1) * VAD_WINDOW][None, :]
            out, self._h, self._c = self._session.run(
                None, {"input": np.concatenate([self._ctx, window], axis=1), "h": self._h, "c": self._c}
            )
            probs.append(float(np.asarray(out).reshape(-1)[0]))
            self._ctx = window[:, -VAD_CONTEXT:]
        self._pending = buf[n * VAD_WINDOW :]
        return probs


class AudioSource(Protocol):
    sample_rate: int

    def start(self, on_audio: Callable[[np.ndarray], None]) -> None: ...

    def stop(self) -> None: ...


class MicrophoneError(Exception):
    pass


class MicrophoneSource:
    """Default input device via sounddevice (PortAudio). 16 kHz mono when supported."""

    def __init__(self, sample_rate: int = VAD_RATE, device: int | str | None = None) -> None:
        self.device = device
        self.sample_rate = sample_rate
        self._stream: Any = None

    def start(self, on_audio: Callable[[np.ndarray], None]) -> None:
        try:
            import sounddevice as sd

            info = sd.query_devices(self.device, kind="input")
        except Exception as exc:  # PortAudio missing or no default input device
            raise MicrophoneError(str(exc)) from exc

        def callback(indata: np.ndarray, frames: int, time: Any, status: Any) -> None:
            on_audio(indata[:, 0].copy())

        last: Exception | None = None
        for rate in (self.sample_rate, int(info["default_samplerate"])):
            try:
                stream = sd.InputStream(
                    samplerate=rate, channels=1, dtype="float32", device=self.device, callback=callback
                )
                stream.start()
            except Exception as exc:  # rate not supported by this host API: retry at native rate
                last = exc
                continue
            self._stream = stream
            self.sample_rate = rate
            return
        raise MicrophoneError(str(last))

    def stop(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()


@dataclass
class Tick:
    level: float  # 0..1 for the UI meter
    speech_started: bool
    stop_reason: str | None  # "silence" | "max_length" | "no_speech" | None


class Recorder:
    """Accumulates microphone audio in memory and decides when an utterance is over.

    `feed()` is called from the audio thread; `poll()` from the handler loop.
    """

    def __init__(self, source_rate: int, cfg: SttConfig) -> None:
        self.cfg = cfg
        self.source_rate = source_rate
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._chunks: list[np.ndarray] = []  # 16 kHz
        self._vad = StreamingVad()
        self._lock = threading.Lock()
        self.samples = 0
        self.speech_windows = 0
        self.speech_started = False
        self._silence_run = 0  # consecutive non-speech windows after speech started

    def feed(self, chunk: np.ndarray) -> None:
        self._queue.put(chunk)

    def poll(self) -> Tick:
        raw: list[np.ndarray] = []
        while True:
            try:
                raw.append(self._queue.get_nowait())
            except queue.Empty:
                break
        level = 0.0
        if raw:
            block = resample(np.concatenate(raw), self.source_rate, VAD_RATE)
            with self._lock:
                self._chunks.append(block)
                self.samples += len(block)
            level = _level(block)
            threshold = self.cfg.vad_threshold
            for p in self._vad.push(block):
                if p >= threshold:
                    self.speech_windows += 1
                    self._silence_run = 0
                    if self.speech_windows >= 3:  # ~100 ms of speech
                        self.speech_started = True
                elif self.speech_started:
                    self._silence_run += 1
        return Tick(level, self.speech_started, self._stop_reason())

    def _stop_reason(self) -> str | None:
        seconds = self.samples / VAD_RATE
        if seconds >= self.cfg.max_record_s:
            return "max_length"
        if (
            self.speech_started
            and self._silence_run * VAD_WINDOW * 1000 / VAD_RATE >= self.cfg.vad_silence_ms
        ):
            return "silence"
        if not self.speech_started and seconds >= self.cfg.no_speech_timeout_s:
            return "no_speech"
        return None

    def audio(self) -> np.ndarray:
        with self._lock:
            return np.concatenate(self._chunks) if self._chunks else np.zeros(0, dtype=np.float32)

    def clear(self) -> None:
        """Drops every buffered sample (privacy: nothing outlives the transcription)."""
        with self._lock:
            self._chunks.clear()
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break


def _level(block: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(np.square(block)))) if len(block) else 0.0
    db = 20 * math.log10(max(rms, 1e-6))
    return min(1.0, max(0.0, (db + 60.0) / 50.0))  # -60 dBFS -> 0, -10 dBFS -> 1
