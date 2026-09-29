"""drowsy_start / user_activity / drowsy_stop over the WebSocket with the camera and the
landmarker replaced by fakes (the real webcam is never opened in tests)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from studymate.config import DrowsyConfig
from studymate.drowsy.camera import CameraUnavailableError
from studymate.drowsy.face import FaceMetrics
from studymate.handlers import drowsy as drowsy_handler
from studymate.main import app
from studymate.services import get_services


class FakeCamera:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.opened = False
        self.released = threading.Event()

    def open(self) -> None:
        if self.fail:
            raise CameraUnavailableError()
        self.opened = True

    def grab(self) -> bool:
        time.sleep(0.004)
        return True

    def retrieve(self) -> np.ndarray | None:
        return np.zeros((4, 4, 3), dtype=np.uint8)

    def release(self) -> None:
        self.released.set()


class FakeAnalyzer:
    def __init__(self) -> None:
        self.closed = False

    def analyze(self, frame_bgr: np.ndarray, t: float) -> FaceMetrics:
        return FaceMetrics(face=True, ear=0.3, pitch=5.0)

    def close(self) -> None:
        self.closed = True


class Fakes:
    def __init__(self) -> None:
        self.cameras: list[FakeCamera] = []
        self.analyzers: list[FakeAnalyzer] = []
        self.camera_fails = False

    def camera(self, index: int, cfg: DrowsyConfig) -> FakeCamera:
        cam = FakeCamera(self.camera_fails)
        self.cameras.append(cam)
        return cam

    def analyzer(self, path: Path, cfg: DrowsyConfig) -> FakeAnalyzer:
        a = FakeAnalyzer()
        self.analyzers.append(a)
        return a


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> Iterator[Fakes]:
    f = Fakes()
    services = get_services()
    fast = DrowsyConfig(fps=100.0, calibration_s=0.3, state_interval_s=0.05, activity_hold_s=5.0)
    monkeypatch.setattr(services.settings, "drowsy", fast)
    monkeypatch.setattr(drowsy_handler, "_model_path", lambda services: Path("face_landmarker.task"))
    monkeypatch.setattr(drowsy_handler.manager, "camera_factory", f.camera)
    monkeypatch.setattr(drowsy_handler.manager, "analyzer_factory", f.analyzer)
    yield f
    drowsy_handler.manager.stop()


def receive_until(
    ws: WebSocketTestSession, pred: Callable[[dict[str, Any]], bool], limit: int = 2000
) -> dict[str, Any]:
    for _ in range(limit):
        msg: dict[str, Any] = ws.receive_json()
        if pred(msg):
            return msg
    raise AssertionError("expected message not received")


def test_start_calibrate_activity_stop(fakes: Fakes) -> None:
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "drowsy_start", "id": "d1", "sensitivity": "normal"})
        first = ws.receive_json()
        assert first == {"type": "camera_state", "active": True}
        done = receive_until(ws, lambda m: m["type"] == "drowsy_calibration" and m["done"])
        assert done["baseline_ear"] == pytest.approx(0.3)
        state = receive_until(ws, lambda m: m["type"] == "drowsy_state")
        assert state["state"] == "normal" and state["pitch"] == pytest.approx(5.0)

        ws.send_json({"type": "user_activity", "last_input_ms": 0})
        receive_until(ws, lambda m: m["type"] == "drowsy_state" and m["state"] == "paused")

        ws.send_json({"type": "drowsy_stop", "id": "s1"})
        receive_until(ws, lambda m: m["type"] == "camera_state" and m["active"] is False)
        assert drowsy_handler.manager.session is None
        cam, analyzer = fakes.cameras[0], fakes.analyzers[0]
        assert cam.opened and cam.released.is_set() and analyzer.closed


def test_restart_keeps_a_single_session(fakes: Fakes) -> None:
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "drowsy_start", "sensitivity": "low"})
        receive_until(ws, lambda m: m["type"] == "camera_state")
        ws.send_json({"type": "drowsy_start", "sensitivity": "high", "camera_index": 1})
        off = receive_until(ws, lambda m: m["type"] == "camera_state")
        on = receive_until(ws, lambda m: m["type"] == "camera_state")
        assert (off["active"], on["active"]) == (False, True)
        assert fakes.cameras[0].released.is_set() and fakes.analyzers[0].closed
        session = drowsy_handler.manager.session
        assert session is not None and session.sensitivity == "high" and session.running
    # app shutdown runs the registered cleanup, which releases the camera
    assert fakes.cameras[1].released.wait(2.0)
    assert drowsy_handler.manager.session is None


def test_camera_unavailable_is_reported(fakes: Fakes) -> None:
    fakes.camera_fails = True
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "drowsy_start", "id": "d2", "sensitivity": "normal"})
        err = ws.receive_json()
        assert err["type"] == "error" and err["id"] == "d2" and err["code"] == "camera_unavailable"
        assert "카메라" in err["message"]
    assert drowsy_handler.manager.session is None
    assert fakes.analyzers[0].closed  # model unloaded again


def test_stop_and_activity_without_session_are_noops(fakes: Fakes) -> None:
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "user_activity", "last_input_ms": 1200})
        ws.send_json({"type": "drowsy_stop"})
        ws.send_json({"type": "hello", "id": "h"})
        assert receive_until(ws, lambda m: True)["type"] == "status"
    assert not fakes.cameras
