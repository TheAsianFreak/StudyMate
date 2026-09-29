"""stt_start / stt_stop: push-to-talk recording with VAD auto-stop, then faster-whisper.

While recording: `stt_level` (~10 Hz) and, if a small partial model is installed,
`stt_partial` every ~1.5 s. Finally `stt_final` (empty text when nothing was said).
One recording at a time; audio is kept in memory only and discarded after transcription.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from studymate.errors import UserFacingError
from studymate.protocol.backend import SttStart, SttStop
from studymate.router import Context, router
from studymate.services import Services, get_services
from studymate.speech.service import partial_model_id, stt_language, stt_model_id, transcriber
from studymate.speech.stt import AudioSource, MicrophoneError, MicrophoneSource, Recorder

log = logging.getLogger(__name__)

# Replaced in tests (no real microphone there).
source_factory: Callable[[int], AudioSource] = MicrophoneSource


@dataclass
class _Session:
    id: str
    stop: asyncio.Event = field(default_factory=asyncio.Event)
    done: bool = False


_active: _Session | None = None


@router.on("stt_start", SttStart)
async def stt_start(ctx: Context, msg: SttStart) -> None:
    global _active
    if _active is not None:
        raise UserFacingError("stt_busy", "이미 듣고 있어요.")
    services = get_services()
    model_id = stt_model_id(services)  # fail fast when no model is installed
    session = _Session(msg.id)
    _active = session
    try:
        await _record_and_transcribe(ctx, services, session, model_id)
    finally:
        session.done = True
        if _active is session:
            _active = None


@router.on("stt_stop", SttStop)
async def stt_stop(ctx: Context, msg: SttStop) -> None:
    session = _active
    if session is not None and session.id == msg.id:
        session.stop.set()


async def _record_and_transcribe(ctx: Context, services: Services, session: _Session, model_id: str) -> None:
    cfg = services.settings.stt
    # Load the final model while the user speaks (large-v3 takes a few seconds).
    loading = asyncio.create_task(transcriber(services, model_id))
    loading.add_done_callback(_consume)  # errors surface where it is awaited, never as a warning
    partial_id = partial_model_id(services)
    source = source_factory(cfg.sample_rate)
    recorder = Recorder(cfg.sample_rate, cfg)
    try:
        await asyncio.to_thread(source.start, recorder.feed)
    except MicrophoneError as exc:
        log.warning("microphone unavailable: %s", exc)
        raise UserFacingError(
            "no_microphone",
            "마이크를 찾을 수 없어요. 마이크 연결과 Windows 설정의 마이크 권한을 확인해 주세요.",
        ) from exc
    recorder.source_rate = source.sample_rate
    try:
        reason = await _record(ctx, services, session, recorder, source, partial_id)
        recorder.poll()  # drain what arrived before the stream closed
        spoke = recorder.speech_started
        audio = recorder.audio()
        recorder.clear()
        session.done = True  # late partials are dropped from here on
        text = ""
        if spoke:
            model = await loading
            text = await asyncio.to_thread(model.transcribe, audio, language=stt_language(services))
        del audio
    finally:
        session.done = True
        recorder.clear()  # privacy: no audio outlives the request, whatever happened
    log.info("stt: stopped (%s), %d chars", reason, len(text))
    await ctx.send({"type": "stt_final", "id": session.id, "text": text})


async def _record(
    ctx: Context,
    services: Services,
    session: _Session,
    recorder: Recorder,
    source: AudioSource,
    partial_id: str | None,
) -> str:
    """Streams levels (and partials) until VAD, the time limits or stt_stop end the take."""
    cfg = services.settings.stt
    partial: asyncio.Task[None] | None = None
    last_partial = time.monotonic()
    try:
        while True:
            tick = recorder.poll()
            await ctx.send({"type": "stt_level", "id": session.id, "level": round(tick.level, 3)})
            if tick.stop_reason:
                return tick.stop_reason
            now = time.monotonic()
            if (
                partial_id
                and tick.speech_started
                and now - last_partial >= cfg.partial_interval_s
                and (partial is None or partial.done())
            ):
                last_partial = now
                partial = asyncio.create_task(_partial(ctx, services, session, partial_id, recorder))
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(session.stop.wait(), timeout=cfg.level_interval_s)
            if session.stop.is_set():
                return "stopped"
    finally:
        await asyncio.to_thread(source.stop)


def _consume(task: asyncio.Task[object]) -> None:
    if not task.cancelled():
        task.exception()


async def _partial(
    ctx: Context, services: Services, session: _Session, model_id: str, recorder: Recorder
) -> None:
    try:
        model = await transcriber(services, model_id)
        audio = recorder.audio()
        text = await asyncio.to_thread(
            model.transcribe, audio, vad_filter=False, beam_size=1, language=stt_language(services)
        )
        del audio
        if text and not session.done:
            await ctx.send({"type": "stt_partial", "id": session.id, "text": text})
    except Exception:  # a failed preview must not break the recording
        log.exception("partial transcription failed")
