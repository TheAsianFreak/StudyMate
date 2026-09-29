"""Korean frontend, MeloTTS synthesis, lip-sync timings and the tts/voice handlers."""

from __future__ import annotations

import base64
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterator

import numpy as np
import pytest
from fastapi.testclient import TestClient

from studymate.main import app
from studymate.services import get_services
from studymate.speech import dsp
from studymate.speech.korean import g2p, normalize
from studymate.speech.presets import BUILTIN_PRESETS
from studymate.speech.tts import MeloKorean

MODELS = get_services().settings.models_dir
MELO_DIR = MODELS / "tts" / "melo-korean"
needs_melo = pytest.mark.skipif(not (MELO_DIR / "checkpoint.pth.ok").exists(), reason="MeloTTS not installed")


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        ("먼저 3을 오른쪽으로 넘겨요.", "먼저 삼을 오른쪽으로 넘겨요."),
        ("2x + 3 = 7", "이 엑스 더하기 삼은 칠"),
        ("f(x) = x^2 + 2x + 1", "에프 엑스는 엑스 제곱 더하기 이 엑스 더하기 일"),
        (r"$\frac{x}{2} + 3 = 7$", "이 분의 엑스 더하기 삼은 칠"),
        (r"\sqrt{16} = 4", "루트 십육은 사"),
        ("3 x 4 = 12", "삼 곱하기 사는 십이"),
        ("사과 3개와 학생 2명, 그리고 1/2 조각", "사과 세개와 학생 두명, 그리고 이분의 일 조각"),
        ("3.14는 원주율 π의 근삿값", "삼 점 일사는 원주율 파이의 근삿값"),
        ("-5 + 3 = -2", "마이너스 오 더하기 삼은 마이너스 이"),
        ("넓이는 12cm²", "넓이는 십이 제곱센티미터"),
        ("2024년 6월 25일 3시 30분", "이천이십사년 유월 이십오일 세시 삼십분"),
        ("정답률 85%", "정답률 팔십오퍼센트"),
        ("x < 3", "엑스는 삼보다 작다"),
        ("음... 잘 모르겠어요ㅋㅋ", "음… 잘 모르겠어요"),
    ],
)
def test_normalize_study_content(text: str, spoken: str) -> None:
    assert normalize(text) == spoken


def test_g2p_applies_pronunciation_rules_per_word() -> None:
    assert g2p("먹었다") == "머걷따"
    assert g2p("같이") == "가치"
    assert g2p("국물") == "궁물"
    assert g2p("넓이는") == "널비는"
    assert len(g2p("삼각형의")) == 4


def test_frontend_import_never_touches_the_network() -> None:
    """g2pkk calls nltk.download('cmudict') at import time; that must be neutralised."""
    code = (
        "import socket\n"
        "class Blocked(socket.socket):\n"
        "    def __init__(self, *a, **k):\n"
        "        raise RuntimeError('network access attempted')\n"
        "socket.socket = Blocked\n"
        "from studymate.speech import korean\n"
        "assert korean.g2p('읽고') == '익꼬'\n"
        "print(korean.normalize('apple 3개'))\n"
    )
    env = {**os.environ, "NLTK_DATA": tempfile.mkdtemp(prefix="nltk-empty-"), "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, encoding="utf-8", env=env, timeout=120
    )
    assert proc.returncode == 0, proc.stderr
    assert "nltk_data" not in proc.stdout + proc.stderr
    assert "세개" in proc.stdout


def test_english_words_with_cmudict() -> None:
    from studymate.speech.korean import Cmudict

    path = MODELS / "nltk_data" / "corpora" / "cmudict" / "cmudict"
    if not path.exists():
        pytest.skip("g2p-cmudict not installed")
    assert normalize("apple은 사과", Cmudict(path)).startswith("애펄은")
    assert normalize("DNA와 OK", Cmudict(path)) == "디 엔 에이와 오케이"


@pytest.fixture(scope="module")
def melo() -> Iterator[MeloKorean]:
    if not (MELO_DIR / "checkpoint.pth.ok").exists():
        pytest.skip("MeloTTS not installed")
    yield MeloKorean(MELO_DIR)


def _syllables(text: str) -> str:
    return "".join(re.findall(r"[가-힣]", text))


@needs_melo
def test_synthesis_and_timings(melo: MeloKorean) -> None:
    text = "먼저 3을 오른쪽으로 넘겨요. 양변에 2를 곱하면 x = 8이 돼요!"
    syn = melo.synthesize(text, seed=0)
    assert syn.sample_rate == 44100
    rms = float(np.sqrt(np.mean(np.square(syn.audio))))
    assert rms > 0.02 and float(np.max(np.abs(syn.audio))) <= 1.0
    chars = "".join(p.char for p in syn.phonemes)
    assert chars == _syllables(normalize(text))  # every written syllable, in order
    prev_end = 0.0
    for p in syn.phonemes:
        assert p.start_ms >= prev_end - 1e-6
        assert p.end_ms > p.start_ms
        prev_end = p.end_ms
    assert prev_end <= syn.duration_ms
    # the sentence gap sits between "요" and "양"
    k = chars.index("요양")
    gap = syn.phonemes[k + 1].start_ms - syn.phonemes[k].end_ms
    assert gap > 100


@needs_melo
def test_voice_presets_on_real_speech(melo: MeloKorean) -> None:
    syn = melo.synthesize("오늘은 일차방정식을 같이 풀어 볼 거예요.", seed=0)
    base = dsp.median_f0(syn.audio, syn.sample_rate)
    assert 180 < base < 260  # the single MeloTTS Korean speaker is female
    for preset in BUILTIN_PRESETS:
        if preset.lang != "ko":
            continue
        out = dsp.process(syn.audio, syn.sample_rate, preset, syn.phonemes, 44100)
        f0 = dsp.median_f0(out.audio, out.sample_rate)
        expected = base * 2 ** (preset.pitch_semitones / 12)
        assert f0 == pytest.approx(expected, rel=0.08), preset.preset_id
        assert f0 > 180, preset.preset_id  # every built-in voice is female
        assert out.duration_ms == pytest.approx(syn.duration_ms / preset.speed, rel=0.05)


# ---------------------------------------------------------------------------- handlers


@needs_melo
def test_tts_request_handler() -> None:
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "tts_request", "id": "t1", "text": "안녕하세요, 3번 문제를 풀어 볼게요."})
        msg = ws.receive_json()
        assert msg["type"] == "tts_audio" and msg["id"] == "t1", msg
        audio, sr = dsp.read_wav(base64.b64decode(msg["wav_base64"]))
        assert sr == msg["sample_rate"] == get_services().settings.tts.sample_rate
        assert msg["duration_ms"] == pytest.approx(1000 * len(audio) / sr, abs=1)
        assert "".join(p["char"] for p in msg["phonemes"]) == "안녕하세요삼번문제를풀어볼게요"
        assert msg["phonemes"][-1]["end_ms"] <= msg["duration_ms"]

        slow = {**BUILTIN_PRESETS[0].model_dump(), "preset_id": "preview", "builtin": False, "speed": 0.5}
        ws.send_json({"type": "tts_request", "id": "t2", "text": "안녕하세요", "preset": slow})
        preview = ws.receive_json()
        ws.send_json({"type": "tts_request", "id": "t3", "text": "안녕하세요", "voice": "female_girl"})
        girl = ws.receive_json()
        ws.send_json({"type": "tts_request", "id": "t4", "text": "안녕하세요", "voice": "no-such-voice"})
        fallback = ws.receive_json()
        assert {preview["id"], girl["id"], fallback["id"]} == {"t2", "t3", "t4"}
        assert preview["duration_ms"] > 1.6 * fallback["duration_ms"]
        girl_audio, girl_sr = dsp.read_wav(base64.b64decode(girl["wav_base64"]))
        base_audio, base_sr = dsp.read_wav(base64.b64decode(fallback["wav_base64"]))
        assert dsp.median_f0(girl_audio, girl_sr) > dsp.median_f0(base_audio, base_sr)
        assert all("vowel" not in p for p in msg["phonemes"])  # Korean: derived from the syllable


def test_voice_preset_handlers() -> None:
    mine = {
        **BUILTIN_PRESETS[1].model_dump(),
        "preset_id": "test-mine",
        "name": "테스트 목소리",
        "builtin": True,
    }
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "voice_presets_get", "id": "g"})
        got = ws.receive_json()
        assert got["type"] == "voice_presets" and got["id"] == "g"
        assert got["default_preset_id"] == "female_bright"
        ids = {p["preset_id"] for p in got["presets"]}
        assert ids >= {"female_bright", "female_calm", "ja_bright", "en_bright"}
        assert {p["gender"] for p in got["presets"] if p["builtin"]} == {"female"}

        ws.send_json({"type": "voice_preset_save", "id": "s", "preset": mine, "make_default": True})
        saved = ws.receive_json()
        assert saved["default_preset_id"] == "test-mine"
        stored = next(p for p in saved["presets"] if p["preset_id"] == "test-mine")
        assert stored["builtin"] is False  # user presets are never built-in

        ws.send_json({"type": "voice_preset_delete", "id": "d1", "preset_id": "female_bright"})
        err = ws.receive_json()
        assert err["type"] == "error" and err["code"] == "builtin_preset" and err["id"] == "d1"

        edited = {**BUILTIN_PRESETS[0].model_dump(), "pitch_semitones": 4.0}
        ws.send_json({"type": "voice_preset_save", "id": "s2", "preset": edited})
        assert ws.receive_json()["code"] == "builtin_preset"

        ws.send_json({"type": "voice_preset_save", "id": "s3", "preset": {**mine, "speed": 9.0}})
        assert ws.receive_json()["code"] == "invalid_message"  # schema range check

        ws.send_json({"type": "voice_preset_delete", "id": "d2", "preset_id": "test-mine"})
        after = ws.receive_json()
        assert after["default_preset_id"] == "female_bright"
        assert "test-mine" not in {p["preset_id"] for p in after["presets"]}


# ---------------------------------------------------------------------------- slow

SENTENCES = [
    "안녕하세요, 오늘은 일차방정식을 같이 풀어 볼 거예요.",
    "먼저 3을 오른쪽으로 넘겨요.",
    "양변에 2를 곱하면 x는 8이 돼요.",
    "삼각형의 넓이는 밑변 곱하기 높이 나누기 2예요.",
    "광합성은 식물이 빛 에너지를 이용해 양분을 만드는 과정이에요.",
    "조선은 1392년에 이성계가 세웠어요.",
    "틀린 문제는 오답 노트에 저장해 둘게요.",
    "졸리면 잠깐 스트레칭을 하고 다시 시작해요.",
    "이 문제의 정답은 3번이에요.",
    "다음 단원은 이차함수의 그래프예요.",
    "물은 섭씨 100도에서 끓어요.",
    "집중력이 떨어질 때는 물을 한 잔 마셔 보세요.",
]


def edit_distance(a: str, b: str) -> int:
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, cb in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (ca != cb))
    return row[len(b)]


def cer(refs: list[str], hyps: list[str]) -> float:
    """Character error rate over Hangul after normalising both sides (digits -> Hangul)."""
    errors = total = 0
    for r, h in zip(refs, hyps, strict=True):
        ref, hyp = _syllables(normalize(r)), _syllables(normalize(h))
        errors += edit_distance(ref, hyp)
        total += len(ref)
    return errors / total


@pytest.mark.slow
@pytest.mark.skipif(not os.environ.get("STUDYMATE_SLOW_TESTS"), reason="set STUDYMATE_SLOW_TESTS=1")
@pytest.mark.parametrize("preset_id", ["female_bright", "female_girl"])
def test_roundtrip_intelligibility(melo: MeloKorean, preset_id: str) -> None:
    """TTS -> voice chain -> Whisper (tier model) and back; BERT-free MeloTTS must stay clear."""
    from studymate.speech.stt import Transcriber, resample

    services = get_services()
    model_id = services.registry.pick(services.tier, "stt")
    if model_id is None:
        pytest.skip("no whisper model installed")
    stt = Transcriber(services.registry.dir(model_id))
    preset = next(p for p in BUILTIN_PRESETS if p.preset_id == preset_id)
    hyps = []
    for text in SENTENCES:
        syn = melo.synthesize(text, seed=0)
        out = dsp.process(syn.audio, syn.sample_rate, preset, syn.phonemes, 44100)
        hyps.append(stt.transcribe(resample(out.audio, 44100, 16000)))
    limit = 0.08 if "large" in model_id else 0.2
    assert cer(SENTENCES, hyps) <= limit, list(zip(SENTENCES, hyps, strict=True))
