"""hello / status / set_tier / set_gpu_use / set_language / set_profile / download_model."""

from __future__ import annotations

import asyncio
from typing import Any

from studymate import __version__
from studymate.errors import UserFacingError
from studymate.protocol.backend import (
    DownloadModel,
    Hello,
    SetGpuUse,
    SetLanguage,
    SetProfile,
    SetTier,
)
from studymate.router import Context, router
from studymate.services import Services, get_services
from studymate.system import hardware
from studymate.system.downloader import ChecksumError, Progress, install
from studymate.system.titles import model_title

_downloading: set[str] = set()


def build_status(services: Services, request_id: str | None = None) -> dict[str, Any]:
    reg = services.registry
    tier = services.tier
    lang = services.lang
    models = [
        {
            "model_id": m.id,
            "title": model_title(m.id, m.title),
            "category": m.category,
            "tiers": list(m.tiers),
            "size": m.total_size,
            "installed": reg.installed(m.id),
            "required": m.required,
            **({"langs": list(m.langs)} if m.langs is not None else {}),
            "license": m.license,
            "license_url": m.license_url,
        }
        for m in reg.entries.values()
    ]
    runtime = reg.llama_server_exe() is not None
    tts_models = services.settings.tts.model_ids(lang)
    status: dict[str, Any] = {
        "type": "status",
        "version": __version__,
        "tier": tier,
        "gpu_use": services.gpu_use,
        "lang": lang,
        "hardware": hardware.localized(services.hardware),
        "models": models,
        "capabilities": {
            "solve": runtime and reg.pick(tier, "llm") is not None,
            "vision": runtime and reg.pick(tier, "vision") is not None,
            "tts": all(reg.installed(m) for m in tts_models),  # the current language's voices
            "stt": reg.pick(tier, "stt") is not None,
            "drowsy": reg.installed("face-landmarker"),
            "rag": runtime and reg.pick(tier, "embed") is not None,
        },
    }
    if request_id:
        status["id"] = request_id
    return status


@router.on("hello", Hello)
async def hello(ctx: Context, msg: Hello) -> None:
    services = get_services()
    if msg.lang is not None:
        services.set_lang(msg.lang)
    if msg.profile is not None:
        try:
            services.set_address(msg.profile.address)
        except UserFacingError:
            services.set_address("")  # a saved address that no longer passes: fall back to default
    status = await asyncio.to_thread(build_status, services, msg.id)
    await ctx.send(status)


@router.on("set_tier", SetTier)
async def set_tier(ctx: Context, msg: SetTier) -> None:
    services = get_services()
    services.set_tier(msg.tier)
    status = await asyncio.to_thread(build_status, services)
    if msg.id:
        await ctx.send({**status, "id": msg.id})
    await ctx.broadcast(status)


@router.on("set_gpu_use", SetGpuUse)
async def set_gpu_use(ctx: Context, msg: SetGpuUse) -> None:
    services = get_services()
    services.set_gpu_use(msg.gpu_use)
    status = await asyncio.to_thread(build_status, services)
    if msg.id:
        await ctx.send({**status, "id": msg.id})
    await ctx.broadcast(status)


@router.on("set_language", SetLanguage)
async def set_language(ctx: Context, msg: SetLanguage) -> None:
    services = get_services()
    services.set_lang(msg.lang)
    status = await asyncio.to_thread(build_status, services)
    if msg.id:
        await ctx.send({**status, "id": msg.id})
    await ctx.broadcast(status)


@router.on("set_profile", SetProfile)
async def set_profile(ctx: Context, msg: SetProfile) -> None:
    services = get_services()
    services.set_address(msg.profile.address)  # UserFacingError -> error {code} to the shell
    status = await asyncio.to_thread(build_status, services)
    if msg.id:
        await ctx.send({**status, "id": msg.id})
    await ctx.broadcast(status)


@router.on("download_model", DownloadModel)
async def download_model(ctx: Context, msg: DownloadModel) -> None:
    services = get_services()
    entry = services.registry.entries.get(msg.model_id)
    if entry is None:
        raise UserFacingError("unknown_model", "알 수 없는 모델입니다.")
    if msg.model_id in _downloading:
        raise UserFacingError("already_downloading", "이미 받는 중입니다.")
    loop = asyncio.get_running_loop()

    def on_progress(p: Progress) -> None:
        payload = {
            "type": "download_progress",
            "id": msg.id,
            "model_id": p.model_id,
            "file": p.file,
            "downloaded": p.downloaded,
            "done": p.done,
        }
        if p.total is not None:
            payload["total"] = p.total
        asyncio.run_coroutine_threadsafe(ctx.send(payload), loop)

    _downloading.add(msg.model_id)
    try:
        await asyncio.to_thread(install, entry, services.settings.models_dir, on_progress)
    except ChecksumError as exc:
        raise UserFacingError("checksum", f"파일 검증에 실패했습니다: {exc}") from exc
    except OSError as exc:
        raise UserFacingError("download_failed", "다운로드에 실패했습니다. 네트워크를 확인해주세요.") from exc
    finally:
        _downloading.discard(msg.model_id)
    status = await asyncio.to_thread(build_status, services)
    await ctx.send({**status, "id": msg.id})  # reply to the requester
    await ctx.broadcast(status)
