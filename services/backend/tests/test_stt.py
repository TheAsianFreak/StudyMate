"""STT without a microphone: TTS audio is fed to the transcriber, the recorder and the
stt_start/stt_stop handlers through a fake audio source."""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

import studymate.handlers.stt as stt_handler
from studymate.config import SttConfig
from studymate.main import app
from studymate.services import get_services
from studymate.speech.korean import normalize
from studymate.speech.stt import MicrophoneError, Recorder, StreamingVad, Transcriber, resample

MODELS = get_services().settings.models_dir
MELO_DIR = MODELS / "tts" / "melo-korean"
SMALL_DIR = MODELS / "stt" / "faster-whisper-small"
SENTENCE = "틀린 문제는 오답 노트에 저장해 둘게요."
needs_models = pytest.mark.skipif(
    not ((MELO_DIR / "checkpoint.pth.ok").exists() and (SMALL_DIR / "model.bin.ok").exists()),
    reason="MeloTTS and whisper-small are required",
)
pytestmark = needs_models


def cer(ref: str, hyp: str) -> float:
    a = re.sub(r"[^가-힣]", "", normalize(ref))
    b = re.sub(r"[^가-힣]", "", normalize(hyp))
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, cb in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (ca != cb))
    return row[len(b)] / len(a)


@pytest.fixture(scope="module")
def speech16k() -> np.ndarray:
    from studymate.speech.tts import MeloKorean

    syn = MeloKorean(MELO_DIR).synthesize(SENTENCE, seed=0)
    return resample(syn.audio, syn.sample_rate, 16000)


@pytest.fixture(scope="module")
def small() -> Transcriber:
    return Transcriber(SMALL_DIR)


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(16000 * seconds), dtype=np.float32)


def test_transcribe_synthesized_speech(small: Transcriber, speech16k: np.ndarray) -> None:
    text = small.transcribe(speech16k)
    assert cer(SENTENCE, text) <= 0.15, text
    assert small.transcribe(silence(0.05)) == ""


def test_streaming_vad_matches_batched(speech16k: np.ndarray) -> None:
    from faster_whisper.vad import get_vad_model

    audio = np.concatenate([silence(0.5), speech16k, silence(0.5)])
    audio = audio[: len(audio) // 512 * 512]
    batched = get_vad_model()(audio.copy()).reshape(-1)
    vad = StreamingVad()
    probs: list[float] = []
    rng = np.random.default_rng(0)
    i = 0
    while i < len(audio):
        step = int(rng.integers(100, 3000))
        probs += vad.push(audio[i : i + step])
        i += step
    assert np.allclose(batched, np.array(probs), atol=1e-5)


def _run(rec: Recorder, audio: np.ndarray, chunk: int) -> tuple[str | None, float]:
    for start in range(0, len(audio), chunk):
        rec.feed(audio[start : start + chunk])
        tick = rec.poll()
        if tick.stop_reason:
            return tick.stop_reason, rec.samples / 16000
    return None, rec.samples / 16000


def test_recorder_stops_after_trailing_silence(speech16k: np.ndarray) -> None:
    cfg = SttConfig(vad_silence_ms=600)
    rec = Recorder(16000, cfg)
    lead = 0.3
    reason, at = _run(rec, np.concatenate([silence(lead), speech16k, silence(3.0)]), 1600)
    speech_end = lead + len(speech16k) / 16000
    assert reason == "silence"
    assert rec.speech_started
    # The TTS clip ends with a little silence of its own, so allow some slack before the end.
    assert speech_end - 0.4 < at < speech_end + 0.6 + 0.3
    assert len(rec.audio()) == rec.samples
    rec.clear()
    assert len(rec.audio()) == 0


def test_recorder_no_speech_and_max_length(speech16k: np.ndarray) -> None:
    reason, at = _run(Recorder(16000, SttConfig(no_speech_timeout_s=1.0)), silence(3.0), 1600)
    assert reason == "no_speech" and at == pytest.approx(1.0, abs=0.11)
    looped = np.tile(speech16k, 4)
    reason, at = _run(Recorder(16000, SttConfig(max_record_s=2.0, vad_silence_ms=5000)), looped, 1600)
    assert reason == "max_length" and at == pytest.approx(2.0, abs=0.11)


def test_recorder_resamples_device_rate(speech16k: np.ndarray) -> None:
    audio48 = resample(np.concatenate([speech16k, silence(2.0)]), 16000, 48000)
    rec = Recorder(48000, SttConfig(vad_silence_ms=600))
    reason, _ = _run(rec, audio48, 4800)
    assert reason == "silence"
    assert rec.samples == pytest.approx(len(rec.audio()))


# ---------------------------------------------------------------------------- handlers


class FakeSource:
    """Plays a 16 kHz clip into the recorder from a thread, `speed`x faster than real time."""

    def __init__(self, audio: np.ndarray, speed: float = 3.0, fail: bool = False) -> None:
        self.audio = audio
        self.speed = speed
        self.fail = fail
        self.sample_rate = 16000
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.stopped = False

    def start(self, on_audio: Callable[[np.ndarray], None]) -> None:
        if self.fail:
            raise MicrophoneError("no input device")

        def run() -> None:
            chunk = 800
            for i in range(0, len(self.audio), chunk):
                if self._stop.wait(chunk / 16000 / self.speed):
                    return
                on_audio(self.audio[i : i + chunk].copy())

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        self.stopped = True


def _use(monkeypatch: pytest.MonkeyPatch, source: FakeSource) -> None:
    monkeypatch.setattr(stt_handler, "source_factory", lambda rate: source)
    monkeypatch.setattr(stt_handler, "stt_model_id", lambda services: "whisper-small")


def _until_final(ws: Any, request_id: str) -> list[dict[str, Any]]:
    msgs: list[dict[str, Any]] = []
    while True:
        msg = ws.receive_json()
        msgs.append(msg)
        if msg["type"] == "stt_final" and msg["id"] == request_id:
            return msgs
        assert msg["type"] != "error" or msg.get("id") != request_id, msg


def test_stt_handler_auto_stops_and_transcribes(
    monkeypatch: pytest.MonkeyPatch, speech16k: np.ndarray
) -> None:
    source = FakeSource(np.concatenate([silence(0.3), speech16k, silence(4.0)]))
    _use(monkeypatch, source)
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "stt_start", "id": "r1"})
        msgs = _until_final(ws, "r1")
    levels = [m["level"] for m in msgs if m["type"] == "stt_level"]
    assert len(levels) >= 5
    assert all(0.0 <= v <= 1.0 for v in levels) and max(levels) > 0.3
    assert all(m["id"] == "r1" for m in msgs)
    assert cer(SENTENCE, msgs[-1]["text"]) <= 0.15, msgs[-1]
    assert source.stopped  # stopped by VAD, well before the 4 s of trailing silence ran out
    assert stt_handler._active is None


def test_stt_handler_busy_and_manual_stop(monkeypatch: pytest.MonkeyPatch, speech16k: np.ndarray) -> None:
    source = FakeSource(np.tile(speech16k, 6), speed=1.0)
    _use(monkeypatch, source)
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "stt_start", "id": "r2"})
        assert ws.receive_json()["type"] == "stt_level"
        ws.send_json({"type": "stt_start", "id": "r3"})
        ws.send_json({"type": "stt_stop", "id": "r2"})
        msgs: list[dict[str, Any]] = []
        while not any(m["type"] == "stt_final" for m in msgs):
            msgs.append(ws.receive_json())
    busy = [m for m in msgs if m["type"] == "error"]
    assert busy and busy[0]["id"] == "r3" and busy[0]["code"] == "stt_busy"
    final = next(m for m in msgs if m["type"] == "stt_final")
    assert final["id"] == "r2"
    assert source.stopped


def test_stt_handler_without_microphone(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, FakeSource(silence(1.0), fail=True))
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "stt_start", "id": "r4"})
        msg = ws.receive_json()
    assert msg["type"] == "error" and msg["code"] == "no_microphone" and msg["id"] == "r4"
    assert "마이크" in msg["message"]
    assert stt_handler._active is None


def test_stt_handler_silence_gives_empty_final(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, FakeSource(silence(20.0), speed=8.0))
    monkeypatch.setattr(get_services().settings.stt, "no_speech_timeout_s", 1.5)
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "stt_start", "id": "r5"})
        msgs = _until_final(ws, "r5")
    assert msgs[-1]["text"] == ""


def test_stt_handler_sends_partials(monkeypatch: pytest.MonkeyPatch, speech16k: np.ndarray) -> None:
    if not get_services().registry.installed("whisper-small"):
        pytest.skip("partials use whisper-small")
    _use(monkeypatch, FakeSource(np.concatenate([speech16k, silence(3.0)]), speed=1.0))
    monkeypatch.setattr(get_services().settings.stt, "partial_interval_s", 0.6)
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "stt_start", "id": "r6"})
        msgs = _until_final(ws, "r6")
    partials = [m["text"] for m in msgs if m["type"] == "stt_partial"]
    assert partials and all(partials)
    assert cer(SENTENCE, msgs[-1]["text"]) <= 0.15, msgs[-1]
