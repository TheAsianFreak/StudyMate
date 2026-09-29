"""One live drowsiness session: camera thread -> face metrics -> detector -> messages.

Only numbers leave the camera thread: the frame goes into `FaceAnalyzer.analyze` and is
dropped; the detector and the optional trace recorder see (t, ear, pitch, face) only.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from pydantic import BaseModel

from studymate.config import DrowsyConfig
from studymate.drowsy.camera import Camera, CameraWorker
from studymate.drowsy.detector import DrowsyDetector, Sample
from studymate.drowsy.face import FaceMetrics
from studymate.drowsy.trace import TraceRecorder
from studymate.errors import UserFacingError
from studymate.protocol.backend import CameraState

log = logging.getLogger(__name__)

Emit = Callable[[BaseModel | dict[str, Any]], None]


class Analyzer(Protocol):
    def analyze(self, frame_bgr: np.ndarray, t: float) -> FaceMetrics: ...
    def close(self) -> None: ...


class DrowsySession:
    def __init__(
        self,
        cfg: DrowsyConfig,
        sensitivity: str,
        camera: Camera,
        analyzer_factory: Callable[[], Analyzer],
        emit: Emit,
        trace_dir: Path | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cfg = cfg
        self.sensitivity = sensitivity
        self._camera = camera
        self._analyzer_factory = analyzer_factory
        self._emit = emit
        self._trace_dir = trace_dir
        self._clock = clock
        self._detector = DrowsyDetector(cfg, sensitivity)
        self._lock = threading.Lock()
        self._analyzer: Analyzer | None = None
        self._worker: CameraWorker | None = None
        self._recorder: TraceRecorder | None = None

    @property
    def running(self) -> bool:
        return self._worker is not None and not self._worker.finished.is_set()

    def start(self) -> None:
        """Loads the landmarker and opens the camera (blocking); raises UserFacingError."""
        try:
            analyzer = self._analyzer_factory()
        except UserFacingError:
            raise
        except Exception as exc:
            log.warning("face landmarker failed to load: %s", exc)
            raise UserFacingError(
                "face_model_failed", "얼굴 인식 모델을 불러오지 못했습니다. 설정 > 모델에서 다시 받아주세요."
            ) from exc
        try:
            self._camera.open()
        except BaseException:
            analyzer.close()
            raise
        self._analyzer = analyzer
        if self._trace_dir is not None:
            try:
                self._recorder = TraceRecorder(self._trace_dir, self._clock())
                log.info("recording numeric drowsiness trace to %s", self._recorder.path)
            except OSError as exc:
                log.warning("trace recorder disabled: %s", exc)
        self._worker = CameraWorker(
            self._camera, self.cfg.fps, self._on_frame, self._on_closed, self.cfg.camera_fail_s, self._clock
        )
        self._emit(CameraState(type="camera_state", active=True))
        self._worker.start()

    def stop(self) -> None:
        """Stops the camera thread; it releases the camera and unloads the model (blocking)."""
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.stop()
            if worker.alive:
                log.warning("camera thread did not stop in time; it cleans up when it exits")

    def note_input(self, last_input_ms: float) -> None:
        """`user_activity`: the last keyboard/mouse/pen input was `last_input_ms` ago."""
        t = self._clock() - max(last_input_ms, 0.0) / 1000.0
        with self._lock:
            self._detector.note_input(t)
        recorder = self._recorder
        if recorder is not None:
            recorder.input(t)

    # ---- camera thread ------------------------------------------------------------------

    def _on_frame(self, frame: np.ndarray, t: float) -> None:
        analyzer = self._analyzer
        if analyzer is None:
            return
        m = analyzer.analyze(frame, t)
        recorder = self._recorder
        if recorder is not None:
            recorder.sample(t, m.face, m.ear, m.pitch)
        with self._lock:
            events = self._detector.update(Sample(t=t, face=m.face, ear=m.ear, pitch=m.pitch))
        for event in events:
            self._emit(event)

    def _on_closed(self, error: str | None) -> None:
        # Runs on the camera thread after its loop ended, so nothing else uses the analyzer.
        analyzer, self._analyzer = self._analyzer, None
        recorder, self._recorder = self._recorder, None
        try:
            if analyzer is not None:
                analyzer.close()
            if recorder is not None:
                recorder.close()
        finally:
            if error is not None:
                self._emit({"type": "error", "code": "camera_lost", "message": error})
            self._emit(CameraState(type="camera_state", active=False))
