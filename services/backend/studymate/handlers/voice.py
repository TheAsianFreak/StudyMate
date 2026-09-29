"""voice_presets_get / voice_preset_save / voice_preset_delete -> voice_presets."""

from __future__ import annotations

import asyncio

from studymate.protocol.backend import VoicePresetDelete, VoicePresets, VoicePresetSave, VoicePresetsGet
from studymate.router import Context, router
from studymate.services import get_services
from studymate.speech.presets import PresetStore
from studymate.speech.service import preset_store


def _payload(store: PresetStore, request_id: str | None) -> VoicePresets:
    """Every language's presets; the default is the current language's."""
    lang = get_services().lang
    return VoicePresets(
        type="voice_presets", id=request_id, presets=store.presets(), default_preset_id=store.default_id(lang)
    )


@router.on("voice_presets_get", VoicePresetsGet)
async def voice_presets_get(ctx: Context, msg: VoicePresetsGet) -> None:
    store = preset_store(get_services())
    await ctx.send(await asyncio.to_thread(_payload, store, msg.id))


@router.on("voice_preset_save", VoicePresetSave)
async def voice_preset_save(ctx: Context, msg: VoicePresetSave) -> None:
    store = preset_store(get_services())
    await asyncio.to_thread(store.save, msg.preset, bool(msg.make_default))
    await ctx.send(await asyncio.to_thread(_payload, store, msg.id))


@router.on("voice_preset_delete", VoicePresetDelete)
async def voice_preset_delete(ctx: Context, msg: VoicePresetDelete) -> None:
    store = preset_store(get_services())
    await asyncio.to_thread(store.delete, msg.preset_id)
    await ctx.send(await asyncio.to_thread(_payload, store, msg.id))
