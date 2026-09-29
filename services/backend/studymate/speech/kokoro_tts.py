"""Kokoro-82M synthesis for Japanese and English with per-unit timings for lip sync.

The model predicts a duration (in 600-sample frames at 24 kHz) for every phoneme token, so
each frontend unit (kana mora / English syllable) gets exact start/end times in the audio
(SPEC 7.4). Speed is applied inside the model (durations / speed), which sounds better
than stretching afterwards. Audio stays in memory; nothing is written to disk.
"""

from __future__ import annotations

import json
import logging
import threading
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from studymate.speech.tts import Synthesis, Timing
from studymate.speech.units import Sentence, pack

log = logging.getLogger(__name__)

SAMPLE_RATE = 24000
FRAME = 600  # samples per predicted duration unit
MAX_TOKENS = 510  # context 512 minus BOS/EOS


class Frontend(Protocol):
    def sentences(self, text: str) -> list[Sentence]: ...


@dataclass
class KokoroOptions:
    max_phonemes: int = 300
    chunk_pause_ms: int = 60


class KokoroModel:
    """The shared Kokoro weights (one instance for ja and en); inference is serialised."""

    def __init__(self, model_dir: Path, threads: int | None = None) -> None:
        import torch

        from studymate.speech.kokoro.model import KModel

        if threads:
            torch.set_num_threads(threads)
        config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)  # torch weight_norm deprecation
            warnings.simplefilter("ignore", UserWarning)  # LSTM dropout with one layer
            net = KModel(config, model_dir / "kokoro-v1_0.pth")
        net.eval()
        self.net = net
        self.vocab: dict[str, int] = config["vocab"]
        self._torch = torch
        self._lock = threading.Lock()
        self._voices: dict[Path, Any] = {}
        log.info("Kokoro-82M loaded")

    def voice(self, path: Path) -> Any:
        with self._lock:
            if path not in self._voices:
                self._voices[path] = self._torch.load(path, map_location="cpu", weights_only=True)
            return self._voices[path]

    def infer(
        self, ids: list[int], voice: Any, speed: float, seed: int | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """(audio float32 at 24 kHz, frames per token incl. BOS/EOS) for token ids."""
        torch = self._torch
        n = len(ids)
        ref = voice[min(n, MAX_TOKENS) - 1]
        with self._lock, torch.inference_mode():
            if seed is not None:
                torch.manual_seed(seed)
            audio, dur = self.net.forward_with_tokens(torch.LongTensor([[0, *ids, 0]]), ref, speed)
        return audio.float().cpu().numpy().astype(np.float32), dur.cpu().numpy().reshape(-1)


class KokoroTts:
    """One language on the shared Kokoro model. `frontend_for(speaker)` picks the G2P
    (English uses the British lexicon for bf_* voices)."""

    native_speed = True
    sample_rate = SAMPLE_RATE

    def __init__(
        self,
        model: KokoroModel,
        voices_dir: Path,
        speakers: tuple[str, ...],
        frontend_for: Callable[[str], Frontend],
        options: KokoroOptions | None = None,
    ) -> None:
        self.model = model
        self.voices_dir = voices_dir
        self.speakers = speakers
        self.frontend_for = frontend_for
        self.options = options or KokoroOptions()

    def speaker(self, speaker: str | None) -> str:
        return speaker if speaker in self.speakers else self.speakers[0]

    def chunks(self, text: str, speaker: str | None = None) -> list[Sentence]:
        sentences = self.frontend_for(self.speaker(speaker)).sentences(text)
        return pack(sentences, min(self.options.max_phonemes, MAX_TOKENS))

    def synthesize(
        self, text: str, *, speaker: str | None = None, speed: float = 1.0, seed: int | None = None
    ) -> Synthesis:
        name = self.speaker(speaker)
        voice = self.model.voice(self.voices_dir / f"{name}.pt")
        chunks = self.chunks(text, name)
        pause = np.zeros(int(SAMPLE_RATE * self.options.chunk_pause_ms / 1000), dtype=np.float32)
        parts: list[np.ndarray] = []
        timings: list[Timing] = []
        offset = 0
        for k, chunk in enumerate(chunks):
            ids, token_of = self._tokens(chunk.phonemes)
            if not ids:
                continue
            if k and parts:
                parts.append(pause)
                offset += len(pause)
            audio, frames = self.model.infer(ids, voice, speed, seed)
            starts = np.concatenate([[0], np.cumsum(frames)]) * FRAME  # sample where token t starts
            for u in chunk.units:
                a, b = token_of[u.start], token_of[u.end]
                if b <= a:
                    continue
                start = offset + float(starts[a])
                end = offset + float(min(starts[b], len(audio)))
                if end > start:
                    timings.append(
                        Timing(u.char, 1000.0 * start / SAMPLE_RATE, 1000.0 * end / SAMPLE_RATE, u.vowel)
                    )
            parts.append(audio)
            offset += len(audio)
        out = np.concatenate(parts) if parts else np.zeros(SAMPLE_RATE // 10, dtype=np.float32)
        return Synthesis(out, SAMPLE_RATE, timings, " ".join(c.phonemes for c in chunks))

    def _tokens(self, phonemes: str) -> tuple[list[int], list[int]]:
        """Token ids (unknown symbols dropped) and, for every phoneme index 0..len, the
        token index (BOS = 0) where that phoneme starts."""
        ids: list[int] = []
        token_of: list[int] = []
        for ch in phonemes:
            token_of.append(len(ids) + 1)
            idx = self.model.vocab.get(ch)
            if idx is not None and len(ids) < MAX_TOKENS:
                ids.append(idx)
        token_of.append(len(ids) + 1)
        return ids, token_of
