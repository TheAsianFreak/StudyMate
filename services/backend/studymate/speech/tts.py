"""MeloTTS Korean synthesis on CPU, BERT-free, with per-syllable timings for lip sync.

The model's duration predictor gives a frame count per input symbol (`w_ceil`); frames
are `hop_length` samples long, so each written syllable gets exact start/end times in
the synthesised audio (SPEC 7.4). Audio stays in memory; nothing is written to disk.
"""

from __future__ import annotations

import json
import logging
import threading
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from studymate.speech.korean import Cmudict, Piece, to_pieces

log = logging.getLogger(__name__)

# From MeloTTS melo/text/symbols.py: language_id_map["KR"], language_tone_start_map["KR"].
KR_LANGUAGE_ID = 4
KR_TONE_START = 11
SPEAKER_ID = 0  # spk2id {"KR": 0}
SPEAKER_NAME = "melo_kr"  # VoicePreset.speaker for the Korean voice


@dataclass
class Timing:
    char: str
    start_ms: float
    end_ms: float
    vowel: str | None = None  # a i u e o n; None for Korean (derived from the syllable)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "char": self.char,
            "start_ms": round(self.start_ms, 1),
            "end_ms": round(self.end_ms, 1),
        }
        if self.vowel is not None:
            out["vowel"] = self.vowel
        return out


@dataclass
class Synthesis:
    audio: np.ndarray  # float32 mono in [-1, 1]
    sample_rate: int
    phonemes: list[Timing] = field(default_factory=list)
    text: str = ""  # normalised text that was spoken

    @property
    def duration_ms(self) -> float:
        return 1000.0 * len(self.audio) / self.sample_rate


@dataclass
class SynthOptions:
    sdp_ratio: float = 0.2
    noise_scale: float = 0.6
    noise_scale_w: float = 0.8
    length_scale: float = 1.0
    sentence_pause_ms: int = 80
    max_piece_chars: int = 120


class MeloKorean:
    """Lazily constructed by the service container; thread-safe (inference is serialised).

    One (female) speaker; voice types are DSP presets. Speed is applied by the DSP chain
    (`native_speed = False`) so Korean output stays exactly as before.
    """

    native_speed = False
    speakers: tuple[str, ...] = (SPEAKER_NAME,)

    def __init__(
        self,
        model_dir: Path,
        *,
        cmudict_path: Path | None = None,
        options: SynthOptions | None = None,
        threads: int | None = None,
    ) -> None:
        import torch

        from studymate.speech.melo.models import SynthesizerTrn

        self.options = options or SynthOptions()
        if threads:
            torch.set_num_threads(threads)
        hps = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
        data = hps["data"]
        self.sample_rate: int = int(data["sampling_rate"])
        self.hop_length: int = int(data["hop_length"])
        self.add_blank: bool = bool(data.get("add_blank", True))
        self.symbols: list[str] = list(hps["symbols"])
        self.symbol_to_id = {s: i for i, s in enumerate(self.symbols)}
        self.cmudict = Cmudict(cmudict_path)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)  # torch.nn.utils.weight_norm deprecation
            net = SynthesizerTrn(  # type: ignore[no-untyped-call]
                len(self.symbols),
                data["filter_length"] // 2 + 1,
                hps["train"]["segment_size"] // self.hop_length,
                n_speakers=data["n_speakers"],
                num_tones=hps["num_tones"],
                num_languages=hps["num_languages"],
                **hps["model"],
            )
            checkpoint = torch.load(model_dir / "checkpoint.pth", map_location="cpu", weights_only=True)
            net.load_state_dict(checkpoint["model"], strict=True)
        del checkpoint
        net.eval()
        self.net = net
        self._torch = torch
        self._lock = threading.Lock()
        log.info("MeloTTS Korean loaded (%d Hz, BERT-free)", self.sample_rate)

    def pieces(self, text: str) -> list[Piece]:
        return to_pieces(text, self.symbols, self.options.max_piece_chars, self.cmudict)

    def synthesize(
        self, text: str, *, speaker: str | None = None, speed: float = 1.0, seed: int | None = None
    ) -> Synthesis:
        """`speaker` and `speed` exist for the common engine interface: there is one Korean
        speaker, and speed is left to the DSP chain."""
        pieces = self.pieces(text)
        sr = self.sample_rate
        pause = np.zeros(int(sr * self.options.sentence_pause_ms / 1000), dtype=np.float32)
        chunks: list[np.ndarray] = []
        timings: list[Timing] = []
        offset = 0
        with self._lock:
            if seed is not None:
                self._torch.manual_seed(seed)
            for k, piece in enumerate(pieces):
                if k:
                    chunks.append(pause)
                    offset += len(pause)
                audio, frames = self._infer(piece)
                timings.extend(self._timings(piece, frames, offset))
                chunks.append(audio)
                offset += len(audio)
        audio = np.concatenate(chunks) if chunks else np.zeros(int(sr * 0.1), dtype=np.float32)
        return Synthesis(audio.astype(np.float32), sr, timings, " ".join(p.text for p in pieces))

    def _infer(self, piece: Piece) -> tuple[np.ndarray, np.ndarray]:
        """Returns (audio, frames per interspersed symbol)."""
        torch = self._torch
        ids = [self.symbol_to_id[p] for p in piece.phones]
        tones = [KR_TONE_START] * len(ids)
        langs = [KR_LANGUAGE_ID] * len(ids)
        if self.add_blank:
            ids, tones, langs = _intersperse(ids), _intersperse(tones), _intersperse(langs)
        n = len(ids)
        opts = self.options
        with torch.inference_mode():
            x = torch.LongTensor(ids).unsqueeze(0)
            # BERT-free: kykim/bert-kor-base is not licensed for us; zero features as in
            # MeloTTS's `disable_bert` path (Korean BERT goes to ja_bert: 768 dims).
            bert = torch.zeros(1, 1024, n)
            ja_bert = torch.zeros(1, 768, n)
            o, attn, _, _ = self.net.infer(  # type: ignore[no-untyped-call]
                x,
                torch.LongTensor([n]),
                torch.LongTensor([SPEAKER_ID]),
                torch.LongTensor(tones).unsqueeze(0),
                torch.LongTensor(langs).unsqueeze(0),
                bert,
                ja_bert,
                sdp_ratio=opts.sdp_ratio,
                noise_scale=opts.noise_scale,
                noise_scale_w=opts.noise_scale_w,
                length_scale=opts.length_scale,
            )
            audio = o[0, 0].float().cpu().numpy()
            frames = attn[0, 0].sum(0).round().long().cpu().numpy()  # [T_x]
        return audio, frames

    def _timings(self, piece: Piece, frames: np.ndarray, offset: int) -> list[Timing]:
        """Written-syllable spans from symbol frame counts (blanks follow their phone)."""
        hop = self.hop_length
        starts = np.concatenate([[0], np.cumsum(frames)])  # frame index where token k starts
        step = 2 if self.add_blank else 1
        first: dict[int, int] = {}
        last: dict[int, int] = {}
        for p, syl in enumerate(piece.phone_syllable):
            if syl < 0:
                continue
            tok = 2 * p + 1 if self.add_blank else p
            first.setdefault(syl, tok)
            last[syl] = tok
        out: list[Timing] = []
        for syl, char in enumerate(piece.syllables):
            if syl not in first:
                continue
            end_tok = min(last[syl] + step, len(frames))
            start = offset + starts[first[syl]] * hop
            end = offset + starts[end_tok] * hop
            out.append(Timing(char, 1000.0 * start / self.sample_rate, 1000.0 * end / self.sample_rate))
        return out


def _intersperse(seq: list[int], item: int = 0) -> list[int]:
    out = [item] * (len(seq) * 2 + 1)
    out[1::2] = seq
    return out
