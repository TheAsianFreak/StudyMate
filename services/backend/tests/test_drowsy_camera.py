"""Capture loop and session wiring with a fake camera (no real device)."""

from __future__ import annotations

import threading
import time
from typing import Any

import numpy as np

from studymate.config import DrowsyConfig
from studymate.drowsy.camera import CAMERA_LOST, CameraWorker
from studymate.drowsy.face import FaceMetrics
from studymate.drowsy.session import DrowsySession


class StreamCamera:
    """Delivers a frame every `interval` seconds; stops delivering after `fail_after` frames."""

    def __init__(self, interval: float = 0.005, fail_after: int | None = None) -> None:
        self.interval = interval
        self.fail_after = fail_after
        self.grabs = 0
        self.retrieves = 0
        self.released = False

    def open(self) -> None:
        pass

    def grab(self) -> bool:
        time.sleep(self.interval)
        self.grabs += 1
        return self.fail_after is None or self.grabs <= self.fail_after

    def retrieve(self) -> np.ndarray | None:
        self.retrieves += 1
        return np.zeros((2, 2, 3), dtype=np.uint8)

    def release(self) -> None:
        self.released = True


def test_worker_limits_rate_and_decodes_only_used_frames() -> None:
    cam = StreamCamera(interval=0.004)
    frames: list[float] = []
    closed = threading.Event()
    worker = CameraWorker(cam, 20.0, lambda f, t: frames.append(t), lambda e: closed.set())
    worker.start()
    time.sleep(0.6)
    worker.stop()
    assert closed.is_set() and cam.released and worker.finished.is_set()
    assert 6 <= len(frames) <= 16  # ~20 fps (12 in 0.6 s) out of a faster stream
    assert cam.retrieves == len(frames) < cam.grabs


def test_worker_reports_lost_camera() -> None:
    cam = StreamCamera(fail_after=3)
    errors: list[str | None] = []
    worker = CameraWorker(cam, 50.0, lambda f, t: None, errors.append, fail_s=0.2)
    worker.start()
    assert worker.finished.wait(3.0)
    assert errors == [CAMERA_LOST] and cam.released


def test_session_emits_numbers_only_and_cleans_up_when_camera_is_lost() -> None:
    emitted: list[Any] = []
    closed: list[bool] = []

    class Analyzer:
        def analyze(self, frame_bgr: np.ndarray, t: float) -> FaceMetrics:
            return FaceMetrics(face=True, ear=0.28, pitch=3.0)

        def close(self) -> None:
            closed.append(True)

    cfg = DrowsyConfig(fps=100.0, calibration_s=0.1, state_interval_s=0.05, camera_fail_s=0.2)
    session = DrowsySession(cfg, "normal", StreamCamera(fail_after=60), Analyzer, emitted.append)
    session.start()
    deadline = time.monotonic() + 5.0
    while session.running and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not session.running
    session.stop()
    dumped = [m if isinstance(m, dict) else m.model_dump() for m in emitted]
    types = [m["type"] for m in dumped]
    assert types[0] == "camera_state" and dumped[0]["active"] is True
    assert "drowsy_calibration" in types and "drowsy_state" in types
    assert dumped[-2] == {"type": "error", "code": "camera_lost", "message": CAMERA_LOST}
    assert dumped[-1] == {"type": "camera_state", "active": False}
    assert closed == [True]
    for m in dumped:  # nothing but scalars ever leaves the session
        assert all(isinstance(v, str | int | float | bool | type(None)) for v in m.values())
