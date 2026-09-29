"""tts_request -> tts_audio: MeloTTS (ko) / Kokoro (ja, en) + the voice preset chain."""

from __future__ import annotations

import asyncio
import logging
import time

from studymate.protocol.backend import TtsRequest
from studymate.router import Context, router
from studymate.services import get_services
from studymate.speech.presets import lang_of
from studymate.speech.service import check_text, preset_store, render_tts, resolve_preset, tts_engine

log = logging.getLogger(__name__)


@router.on("tts_request", TtsRequest)
async def tts_request(ctx: Context, msg: TtsRequest) -> None:
    services = get_services()
    text = check_text(services, msg.text)
    store = preset_store(services)
    lang = services.lang
    preset = await asyncio.to_thread(resolve_preset, store, lang, msg.preset, msg.voice)
    if msg.voice and msg.preset is None and preset.preset_id != msg.voice:
        log.warning("voice preset %r is unknown or not %s, using %s", msg.voice, lang, preset.preset_id)
    engine = await tts_engine(services, lang_of(preset))
    started = time.perf_counter()
    payload = await asyncio.to_thread(render_tts, engine, text, preset, services.settings.tts.sample_rate)
    log.info(
        "tts: %d chars -> %.0f ms audio in %.2f s (%s)",
        len(text),
        payload["duration_ms"],
        time.perf_counter() - started,
        preset.preset_id,
    )
    await ctx.send({"type": "tts_audio", "id": msg.id, **payload})
