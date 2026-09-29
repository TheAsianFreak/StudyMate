"""Webcam capture on a background thread (opt-in only).

Privacy: every frame is handed to the `on_frame` callback and the loop drops its reference
right after; frames are never queued, stored, written to disk or logged. Frames beyond the
target rate are grabbed but never decoded.

Only the Media Foundation backend (DirectShow as fallback) is requested explicitly, so
OpenCV never loads its FFmpeg plugin (opencv_videoio_ffmpeg*.dll, LGPL); the packaged app
can leave that DLL out.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Any, Protocol

import numpy as np

from studymate.errors import UserFacingError

log = logging.getLogger(__name__)

# Read by OpenCV when the MSMF backend is first used: hardware transforms make opening
# some webcams take many seconds and are useless at 640x480.
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

CAMERA_UNAVAILABLE = (
    "카메라를 열 수 없습니다. 카메라 연결, 다른 앱의 사용 여부, Windows 카메라 권한을 확인해주세요."
)
CAMERA_LOST = "카메라 연결이 끊겨 졸음 감지를 멈췄습니다."


class CameraUnavailableError(UserFacingError):
    def __init__(self) -> None:
        super().__init__("camera_unavailable", CAMERA_UNAVAILABLE)


class Camera(Protocol):
    def open(self) -> None: ...
    def grab(self) -> bool: ...
    def retrieve(self) -> np.ndarray | None: ...
    def release(self) -> None: ...


class OpenCvCamera:
    """cv2.VideoCapture restricted to MSMF, then DirectShow."""

    def __init__(self, index: int, width: int, height: int) -> None:
        self.index = index
        self.width = width
        self.height = height
        self.backend: str | None = None
        self._cap: Any = None

    def open(self) -> None:
        import cv2

        for api, name in ((cv2.CAP_MSMF, "msmf"), (cv2.CAP_DSHOW, "dshow")):
            cap = cv2.VideoCapture(self.index, api)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                if cap.grab():  # the first frame is grabbed only to prove the device works
                    self._cap = cap
                    self.backend = name
                    log.info("camera %d opened (%s)", self.index, name)
                    return
            cap.release()
        raise CameraUnavailableError()

    def grab(self) -> bool:
        return self._cap is not None and bool(self._cap.grab())

    def retrieve(self) -> np.ndarray | None:
        if self._cap is None:
            return None
        ok, frame = self._cap.retrieve()
        return frame if ok else None

    def release(self) -> None:
        cap, self._cap = self._cap, None
        if cap is not None:
            cap.release()
            log.info("camera %d released", self.index)


class CameraWorker:
    """Grabs frames from an opened camera at `fps` and hands each one to `on_frame`.

    `on_closed(error)` runs once on the worker thread after the camera is released;
    `error` is None for a normal stop or a Korean message when the camera was lost.
    """

    def __init__(
        self,
        camera: Camera,
        fps: float,
        on_frame: Callable[[np.ndarray, float], None],
        on_closed: Callable[[str | None], None],
        fail_s: float = 3.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._camera = camera
        self._period = 1.0 / max(fps, 0.1)
        self._on_frame = on_frame
        self._on_closed = on_closed
        self._fail_s = fail_s
        self._clock = clock
        self._stop = threading.Event()
        self.finished = threading.Event()  # set once the camera is released and on_closed ran
        self._thread = threading.Thread(target=self._run, name="drowsy-camera", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout)

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()

    def _run(self) -> None:
        error: str | None = None
        next_due = 0.0
        last_ok = self._clock()
        try:
            while not self._stop.is_set():
                if not self._camera.grab():
                    if self._clock() - last_ok > self._fail_s:
                        error = CAMERA_LOST
                        break
                    self._stop.wait(0.05)
                    continue
                now = last_ok = self._clock()
                if now < next_due:
                    continue  # over the target rate: skip without decoding
                next_due = next_due + self._period if now - next_due < self._period else now + self._period
                frame = self._camera.retrieve()
                if frame is None:
                    continue
                try:
                    self._on_frame(frame, now)
                except Exception as exc:  # never let one bad frame kill the session
                    log.warning("frame analysis failed: %s", type(exc).__name__)
                finally:
                    del frame
        finally:
            try:
                self._camera.release()
            finally:
                try:
                    self._on_closed(error)
                finally:
                    self.finished.set()
