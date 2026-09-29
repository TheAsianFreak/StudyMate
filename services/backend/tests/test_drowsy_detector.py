"""Detector rules on synthetic numeric time series (no camera, no model)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from studymate.config import DrowsyConfig
from studymate.drowsy.detector import DrowsyDetector, Event, Sample, Thresholds
from studymate.protocol.backend import DrowsyCalibration, DrowsyStateMessage

FPS = 12.0
EAR0 = 0.30
PITCH0 = 5.0


def feed(
    det: DrowsyDetector,
    t0: float,
    t1: float,
    ear: Callable[[float], float] = lambda t: EAR0,
    pitch: Callable[[float], float] = lambda t: PITCH0,
    face: Callable[[float], bool] = lambda t: True,
) -> tuple[list[Event], list[str]]:
    """Feeds samples in [t0, t1) at FPS; returns events and the state after each sample."""
    events: list[Event] = []
    states: list[str] = []
    n = int(round((t1 - t0) * FPS))
    for i in range(n):
        t = t0 + i / FPS
        f = face(t)
        events += det.update(Sample(t=t, face=f, ear=ear(t) if f else None, pitch=pitch(t) if f else None))
        states.append(str(det.state))
    return events, states


def blinking(period: float = 3.5, dur: float = 0.25) -> Callable[[float], float]:
    return lambda t: EAR0 * 0.15 if (t % period) < dur else EAR0


def dozing(t: float) -> float:
    """Eyes closed 7 s of every 10 s."""
    return EAR0 * 0.2 if (t % 10.0) < 7.0 else EAR0


def nodding(t: float) -> float:
    """Head sinks 25 degrees for 4 s of every closure."""
    return PITCH0 + 25.0 if 2.0 < (t % 10.0) < 6.0 else PITCH0


def calibrated(cfg: DrowsyConfig | None = None, sensitivity: str = "normal") -> DrowsyDetector:
    det = DrowsyDetector(cfg or DrowsyConfig(), sensitivity)
    feed(det, 0.0, 6.0, ear=blinking())
    assert det.calibrated
    return det


def states_of(events: list[Event]) -> list[DrowsyStateMessage]:
    return [e for e in events if isinstance(e, DrowsyStateMessage)]


def test_calibration_progress_and_blink_robust_baseline() -> None:
    det = DrowsyDetector(DrowsyConfig())
    events, _ = feed(det, 0.0, 6.0, ear=blinking(period=2.0, dur=0.3))
    calib = [e for e in events if isinstance(e, DrowsyCalibration)]
    progress = [c.progress for c in calib if not c.done]
    assert progress == sorted(progress) and progress[0] == 0.0 and progress[-1] < 1.0
    done = [c for c in calib if c.done]
    assert len(done) == 1 and done[0].progress == 1.0
    assert done[0].baseline_ear == pytest.approx(EAR0, rel=0.01)  # blinks rejected
    assert states_of(events)[0].state == "normal"


def test_calibration_counts_only_face_time() -> None:
    det = DrowsyDetector(DrowsyConfig())
    events, states = feed(det, 0.0, 8.0, face=lambda t: False)
    assert not det.calibrated
    assert states[-1] == "no_face"
    events, _ = feed(det, 8.0, 12.0)
    assert not det.calibrated  # 4 s of face so far
    events, _ = feed(det, 12.0, 14.0)
    assert det.calibrated
    assert any(isinstance(e, DrowsyCalibration) and e.done for e in events)


def test_blinks_and_glances_do_not_trigger() -> None:
    det = calibrated()
    glance = lambda t: PITCH0 + 25.0 if (t % 20.0) < 1.5 else PITCH0  # noqa: E731
    lids = lambda t: blinking()(t) * (0.85 if (t % 20.0) < 1.5 else 1.0)  # noqa: E731
    _, states = feed(det, 6.0, 606.0, ear=lids, pitch=glance)
    assert set(states) == {"normal"}
    assert det.perclos < 0.15


def test_long_head_down_reading_is_not_closed_eyes() -> None:
    # Lids drop ~25 % when reading on the desk; the pitch compensation keeps them "open".
    det = calibrated()
    _, states = feed(
        det,
        6.0,
        306.0,
        ear=lambda t: blinking()(t) * 0.75,
        pitch=lambda t: PITCH0 + 28.0 if (t % 30.0) > 4.0 else PITCH0,
    )
    assert "candidate" not in states and "drowsy" not in states
    assert det.perclos < 0.15


def test_sustained_closure_with_nods_triggers() -> None:
    cfg = DrowsyConfig()
    det = calibrated(cfg)
    feed(det, 6.0, 36.0, ear=blinking())
    events, states = feed(det, 36.0, 136.0, ear=dozing, pitch=nodding)
    assert "candidate" in states and "drowsy" in states
    first_candidate = states.index("candidate")
    first_drowsy = states.index("drowsy")
    assert (first_drowsy - first_candidate) / FPS == pytest.approx(cfg.candidate_hold_s, abs=0.2)
    drowsy_msgs = [m for m in states_of(events) if m.state == "drowsy"]
    assert drowsy_msgs[0].perclos >= cfg.perclos_threshold


def test_closure_without_head_drops_stays_normal() -> None:
    det = calibrated()
    _, states = feed(det, 6.0, 126.0, ear=dozing)
    assert det.perclos >= 0.4
    assert set(states) == {"normal"}  # SPEC needs both PERCLOS and repeated pitch drops


def test_drowsy_recovers_when_eyes_open_and_head_steady() -> None:
    det = calibrated()
    _, states = feed(det, 6.0, 106.0, ear=dozing, pitch=nodding)
    assert states[-1] == "drowsy"
    _, states = feed(det, 106.0, 196.0, ear=blinking())
    assert states[-1] == "normal"


def test_activity_pauses_and_clears_evidence() -> None:
    cfg = DrowsyConfig()
    det = calibrated(cfg)
    _, states = feed(det, 6.0, 106.0, ear=dozing, pitch=nodding)
    assert states[-1] == "drowsy"
    det.note_input(106.0)
    events, states = feed(det, 106.0, 106.0 + cfg.activity_hold_s - 0.5, ear=dozing, pitch=nodding)
    assert set(states) == {"paused"}
    assert states_of(events)[0].state == "paused"
    # after the hold, evidence restarts from the input, so there is no instant re-alarm
    _, states = feed(det, 116.0, 120.0, ear=dozing, pitch=nodding)
    assert set(states) == {"normal"}
    # ...but continued dozing is detected again once the window has filled
    _, states = feed(det, 120.0, 160.0, ear=dozing, pitch=nodding)
    assert "drowsy" in states


def test_repeated_report_of_same_input_is_not_a_new_input() -> None:
    det = calibrated()
    det.note_input(10.0)
    feed(det, 6.0, 7.0)
    det.note_input(10.1)  # same input, transport jitter
    assert not det._input_pending


def test_no_face_after_timeout_and_back() -> None:
    cfg = DrowsyConfig()
    det = calibrated(cfg)
    _, states = feed(det, 6.0, 10.0, face=lambda t: False)
    assert states[int((cfg.no_face_s - 0.5) * FPS)] == "normal"
    assert states[-1] == "no_face"
    _, states = feed(det, 10.0, 11.0)
    assert states[-1] == "normal"


def test_face_lost_while_drowsy_keeps_state() -> None:
    det = calibrated()
    _, states = feed(det, 6.0, 106.0, ear=dozing, pitch=nodding)
    assert states[-1] == "drowsy"
    _, states = feed(det, 106.0, 116.0, face=lambda t: False)  # head down on the desk
    assert set(states) == {"drowsy"}


def test_state_is_reported_about_twice_a_second() -> None:
    det = calibrated()
    events, _ = feed(det, 6.0, 16.0)
    assert 15 <= len(states_of(events)) <= 22
    msg = states_of(events)[-1]
    assert msg.ear == pytest.approx(EAR0) and msg.pitch == pytest.approx(PITCH0)


def test_sensitivity_scales_thresholds() -> None:
    cfg = DrowsyConfig()
    low, normal, high = (Thresholds.from_config(cfg, s) for s in ("low", "normal", "high"))
    assert low.perclos > normal.perclos > high.perclos
    assert low.pitch_drop_deg > normal.pitch_drop_deg > high.pitch_drop_deg
    assert low.closed_ratio < normal.closed_ratio < high.closed_ratio
    assert normal.closed_ratio == pytest.approx(cfg.ear_closed_ratio)
    assert normal.perclos == pytest.approx(cfg.perclos_threshold)
