"""drowsy_start / drowsy_stop / user_activity: webcam drowsiness detection (opt-in).

One session at a time; a new drowsy_start restarts it. Session events (camera_state,
drowsy_calibration, drowsy_state, camera_lost errors) come from the camera thread and are
broadcast to every client, in order, by one pump task on the event loop.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from studymate.config import DrowsyConfig
from studymate.drowsy.camera import Camera, OpenCvCamera
from studymate.drowsy.session import Analyzer, DrowsySession
from studymate.errors import ModelMissingError
from studymate.protocol.backend import DrowsyStart, DrowsyStop, UserActivity
from studymate.router import Context, Hub, router
from studymate.services import Services, get_services

log = logging.getLogger(__name__)

Message = BaseModel | dict[str, Any]


def _open_cv_camera(index: int, cfg: DrowsyConfig) -> Camera:
    return OpenCvCamera(index, cfg.frame_width, cfg.frame_height)


def _face_analyzer(model_path: Path, cfg: DrowsyConfig) -> Analyzer:
    from studymate.drowsy.face import FaceAnalyzer

    return FaceAnalyzer(model_path, cfg.min_face_confidence)


class _Broadcaster:
    """Thread-safe emit() that broadcasts messages in order on one event loop."""

    def __init__(self, hub: Hub, loop: asyncio.AbstractEventLoop) -> None:
        self.hub = hub
        self.loop = loop
        self._queue: asyncio.Queue[Message] = asyncio.Queue()
        self._task = loop.create_task(self._pump())

    @property
    def usable(self) -> bool:
        return not self.loop.is_closed() and not self._task.done()

    def emit(self, msg: Message) -> None:
        with contextlib.suppress(RuntimeError):  # loop already closed during shutdown
            self.loop.call_soon_threadsafe(self._queue.put_nowait, msg)

    async def _pump(self) -> None:
        while True:
            msg = await self._queue.get()
            try:
                await self.hub.broadcast(msg)
            except Exception:
                log.exception("drowsy broadcast failed")


class DrowsyManager:
    def __init__(self) -> None:
        self.camera_factory: Callable[[int, DrowsyConfig], Camera] = _open_cv_camera
        self.analyzer_factory: Callable[[Path, DrowsyConfig], Analyzer] = _face_analyzer
        self._lock = threading.Lock()
        self._session: DrowsySession | None = None
        self._broadcaster: _Broadcaster | None = None  # touched on the event loop only
        self._cleanup_owner: Services | None = None

    @property
    def session(self) -> DrowsySession | None:
        return self._session

    def broadcaster(self, hub: Hub) -> _Broadcaster:
        """The ordered broadcaster for the running loop (call on the event loop)."""
        loop = asyncio.get_running_loop()
        b = self._broadcaster
        if b is None or b.loop is not loop or b.hub is not hub or not b.usable:
            b = self._broadcaster = _Broadcaster(hub, loop)
        return b

    def register_cleanup(self, services: Services) -> None:
        if self._cleanup_owner is not services:
            services.cleanups.append(self._release_on_exit)
            self._cleanup_owner = services

    def start(
        self,
        cfg: DrowsyConfig,
        sensitivity: str,
        camera_index: int,
        model_path: Path,
        emit: Callable[[Message], None],
        trace_dir: Path | None,
    ) -> None:
        """Blocking: stops any running session, then opens the camera and starts a new one."""
        with self._lock:
            self._stop_locked()
            session = DrowsySession(
                cfg,
                sensitivity,
                self.camera_factory(camera_index, cfg),
                lambda: self.analyzer_factory(model_path, cfg),
                emit,
                trace_dir,
            )
            self._session = session  # visible before camera_state arrives at the client
            try:
                session.start()
            except BaseException:
                self._session = None
                raise
            log.info("drowsiness session started (camera %d, %s)", camera_index, sensitivity)

    def _release_on_exit(self) -> None:
        self.stop()

    def stop(self) -> bool:
        """Blocking: stops the session if any. Returns whether one was running."""
        with self._lock:
            return self._stop_locked()

    def _stop_locked(self) -> bool:
        session, self._session = self._session, None
        if session is None:
            return False
        session.stop()
        log.info("drowsiness session stopped")
        return True

    def note_input(self, last_input_ms: float) -> None:
        session = self._session  # no lock: start() may hold it while a camera opens
        if session is not None:
            session.note_input(last_input_ms)


manager = DrowsyManager()


def _model_path(services: Services) -> Path:
    if not services.registry.installed("face-landmarker"):
        raise ModelMissingError("얼굴 인식")
    return services.registry.path("face-landmarker")


def _trace_dir(services: Services) -> Path | None:
    cfg = services.settings.drowsy
    if not cfg.record_trace:
        return None
    return cfg.trace_dir or services.settings.data_dir / "drowsy-traces"


def _stop_when_unattended() -> None:
    threading.Thread(target=manager.stop, name="drowsy-stop", daemon=True).start()


@router.on("drowsy_start", DrowsyStart)
async def drowsy_start(ctx: Context, msg: DrowsyStart) -> None:
    services = get_services()
    model_path = _model_path(services)
    manager.register_cleanup(services)
    # Privacy: never leave the webcam running once the shell has gone away.
    ctx.hub.on_empty(_stop_when_unattended)
    emit = manager.broadcaster(ctx.hub).emit
    await asyncio.to_thread(
        manager.start,
        services.settings.drowsy,
        msg.sensitivity,
        msg.camera_index or 0,
        model_path,
        emit,
        _trace_dir(services),
    )


@router.on("drowsy_stop", DrowsyStop)
async def drowsy_stop(ctx: Context, msg: DrowsyStop) -> None:
    await asyncio.to_thread(manager.stop)


@router.on("user_activity", UserActivity)
async def user_activity(ctx: Context, msg: UserActivity) -> None:
    manager.note_input(msg.last_input_ms)
