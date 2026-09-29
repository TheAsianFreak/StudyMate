"""Numeric traces: I/O, opt-in recorder, synthetic sessions and the replay tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from studymate.config import DrowsyConfig
from studymate.drowsy import replay as replay_mod
from studymate.drowsy.replay import replay
from studymate.drowsy.synth import alert_session, drowsy_session
from studymate.drowsy.trace import TraceRecorder, TraceRow, decode_row, encode_row, read_trace, write_trace


def test_trace_rows_round_trip() -> None:
    rows = [
        TraceRow(t=1.25, face=True, ear=0.2812345, pitch=7.123, label="alert"),
        TraceRow(t=1.33, face=False),
        TraceRow(t=1.4, input=True),
    ]
    decoded = [decode_row(encode_row(r)) for r in rows]
    assert decoded[0] == TraceRow(t=1.25, face=True, ear=0.2812, pitch=7.12, label="alert")
    assert decoded[1] == rows[1]
    assert decoded[2] == rows[2]
    assert decode_row("  ") is None


def test_recorder_writes_numbers_only(tmp_path: Path) -> None:
    rec = TraceRecorder(tmp_path, t0=100.0)
    rec.sample(100.5, True, 0.3, 4.0)
    rec.sample(100.6, False, None, None)
    rec.input(100.55)
    rec.close()
    rec.sample(101.0, True, 0.3, 4.0)  # ignored after close
    lines = [json.loads(x) for x in rec.path.read_text(encoding="utf-8").splitlines()]
    assert lines == [
        {"t": 0.5, "face": True, "ear": 0.3, "pitch": 4.0},
        {"t": 0.6, "face": False},
        {"t": 0.55, "input": True},
    ]
    allowed = {"t", "face", "ear", "pitch", "input"}
    assert all(set(obj) <= allowed for obj in lines)


def test_alert_session_has_no_alarms() -> None:
    res = replay(alert_session(minutes=45, seed=7), DrowsyConfig(), name="alert")
    assert res.labelled and res.alert_s > 40 * 60
    assert res.alarms == []


def test_drowsy_session_is_detected_after_onset() -> None:
    res = replay(drowsy_session(seed=3, alert_min=3, drowsy_min=8, wake_min=2), DrowsyConfig(), name="drowsy")
    assert len(res.episodes) == 1
    episode = res.episodes[0]
    assert episode.detected is not None and 0 < episode.latency < 8 * 60  # type: ignore[operator]
    assert res.false_alarms == []
    # waking up with input ends the alarm
    assert res.transitions[-1].after in ("paused", "normal")


def test_replay_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "d.jsonl"
    write_trace(path, drowsy_session(seed=5, alert_min=2, drowsy_min=6, wake_min=1))
    assert sum(1 for _ in read_trace(path)) > 1000
    replay_mod.main([str(path), "--set", "candidate_hold_s=3", "--sensitivity", "high"])
    out = capsys.readouterr().out
    assert "d.jsonl:" in out and "-> drowsy" in out and "latency" in out
    with pytest.raises(SystemExit):
        replay_mod.main([str(path), "--set", "nope=1"])
