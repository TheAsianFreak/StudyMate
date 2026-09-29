"""GPU-memory swapping in LlamaServerManager: a model that does not fit next to the running
ones stops the least recently used other role, but never one with a request in flight."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from studymate.config import Settings
from studymate.llm.server import Device, LlamaServerManager, Role, _Instance
from studymate.system.registry import ModelRegistry

MIB = 2**20


class _Proc:
    def __init__(self) -> None:
        self.stopped = False

    def poll(self) -> int | None:
        return 0 if self.stopped else None

    def terminate(self) -> None:
        self.stopped = True

    def wait(self, timeout: float | None = None) -> int:
        return 0

    def kill(self) -> None:
        self.stopped = True


def _manager(tmp_path: Path, tier: Any = "max", free_mib: int = 13_800) -> LlamaServerManager:
    settings = Settings(data_dir=tmp_path, models_dir=tmp_path)
    registry = ModelRegistry(settings)
    registry.installed = lambda model_id: True  # type: ignore[method-assign]
    registry.llama_server_exe = lambda: tmp_path / "llama-server.exe"  # type: ignore[method-assign]
    manager = LlamaServerManager(settings, registry, tier)
    manager._device = Device("Vulkan0", 15_977, free_mib)
    started: list[Role] = []

    async def fake_start(role: Role, model_id: str) -> _Instance:
        started.append(role)
        return _Instance(model_id, 9000, _Proc())  # type: ignore[arg-type]

    manager._start = fake_start  # type: ignore[method-assign]
    manager.started = started  # type: ignore[attr-defined]
    return manager


async def _use(manager: LlamaServerManager, role: Role) -> None:
    async with manager.session(role):
        pass


def test_footprint_counts_weights_and_overhead(tmp_path: Path) -> None:
    m = _manager(tmp_path)
    size = m.registry.entries["qwen3-14b"].total_size // MIB
    assert m.footprint_mib("chat", "qwen3-14b") == size + m.settings.llama.vram_overhead_mib["chat"]


async def test_max_tier_swaps_chat_and_vision(tmp_path: Path) -> None:
    m = _manager(tmp_path)
    await _use(m, "chat")
    await _use(m, "embed")
    assert set(m._instances) == {"chat", "embed"}  # 14B + bge-m3 fit together
    await _use(m, "vision")
    assert "chat" not in m._instances and "vision" in m._instances
    await _use(m, "chat")
    assert "vision" not in m._instances and "chat" in m._instances


async def test_pro_tier_keeps_everything_loaded(tmp_path: Path) -> None:
    m = _manager(tmp_path, tier="pro")
    for role in ("chat", "vision", "embed"):
        await _use(m, role)  # type: ignore[arg-type]
    assert set(m._instances) == {"chat", "vision", "embed"}


async def test_cpu_has_no_budget(tmp_path: Path) -> None:
    m = _manager(tmp_path)
    m._device = None
    await _use(m, "chat")
    await _use(m, "vision")
    assert set(m._instances) == {"chat", "vision"}


async def test_busy_role_is_stopped_only_after_its_request(tmp_path: Path) -> None:
    m = _manager(tmp_path)
    await _use(m, "chat")
    order: list[str] = []
    release = asyncio.Event()

    async def long_chat() -> None:
        async with m.session("chat"):
            order.append("chat start")
            await release.wait()
            order.append("chat end")

    async def vision() -> None:
        await asyncio.sleep(0.01)
        async with m.session("vision"):
            order.append("vision")

    chat_task = asyncio.create_task(long_chat())
    vision_task = asyncio.create_task(vision())
    await asyncio.sleep(0.05)
    assert order == ["chat start"]  # vision waits for the chat request
    assert "chat" in m._instances
    release.set()
    await asyncio.gather(chat_task, vision_task)
    assert order == ["chat start", "chat end", "vision"]
    assert set(m._instances) == {"vision"}


async def test_new_requests_wait_while_a_role_drains(tmp_path: Path) -> None:
    m = _manager(tmp_path)
    await _use(m, "chat")
    release = asyncio.Event()

    async def long_chat() -> None:
        async with m.session("chat"):
            await release.wait()

    first = asyncio.create_task(long_chat())
    await asyncio.sleep(0.01)
    vision = asyncio.create_task(_use(m, "vision"))
    await asyncio.sleep(0.01)
    late_chat = asyncio.create_task(_use(m, "chat"))  # must not keep chat alive forever
    await asyncio.sleep(0.01)
    assert m._busy["chat"] == 1
    release.set()
    await asyncio.wait_for(asyncio.gather(first, vision, late_chat), timeout=2)
    assert m.started == ["chat", "vision", "chat"]  # type: ignore[attr-defined]


@pytest.mark.parametrize("tier", ["lite", "standard", "pro", "max"])
def test_every_tier_has_models(tmp_path: Path, tier: str) -> None:
    m = _manager(tmp_path, tier=tier)
    assert m.model_for("chat") is not None


@pytest.mark.parametrize(
    ("vram", "ram", "tier"),
    [
        (15.9, 61.7, "max"),
        (24.0, 64.0, "max"),
        (12.0, 32.0, "pro"),
        (15.9, 16.0, "standard"),
        (0.0, 16.0, "lite"),
    ],
)
def test_recommendation(vram: float, ram: float, tier: str) -> None:
    from studymate.i18n import use_lang
    from studymate.system.hardware import recommend

    gpus: list[dict[str, object]] = [{"name": "AMD Radeon(TM) Graphics", "vram_gb": 2.0}]
    if vram:
        gpus.append({"name": "NVIDIA GeForce RTX", "vram_gb": vram})
    with use_lang("en"):
        got, reason = recommend(ram, gpus)
    assert got == tier
    assert ("swaps" in reason) == (tier == "max" and vram < 20)


def test_lone_surrogates_are_dropped_from_model_output() -> None:
    import json

    from studymate.llm.client import strip_surrogates

    backslash = chr(92)
    # half an emoji escaped by the model; a full pair (party popper) must survive
    raw = '{"say": "good' + backslash + 'ud83c!", "steps": ["a' + backslash + "ud83c" + backslash + 'udf89"]}'
    parsed = strip_surrogates(json.loads(raw))
    assert parsed == {"say": "good!", "steps": ["a" + chr(0x1F389)]}
    json.dumps(parsed, ensure_ascii=False).encode("utf-8")  # no UnicodeEncodeError


def test_gpu_use_levels_place_models(tmp_path: Path) -> None:
    m = _manager(tmp_path)
    gpu = m._device
    assert gpu
    # embeddings always on the CPU, taking no GPU memory
    assert m._device_args("embed", gpu) == ["-dev", "none", "-ngl", "0"]
    assert m.footprint_mib("embed", "bge-m3") == 0
    assert m._device_args("chat", gpu)[:2] == ["-dev", "Vulkan0"] and m.on_gpu
    m.set_gpu_use("balanced")
    args = m._device_args("chat", gpu)
    assert args[args.index("--fit-target") + 1] == str(gpu.total_mib // 2)
    assert m.footprint_mib("chat", "qwen3-14b") <= gpu.total_mib // 2
    m.set_gpu_use("low")
    assert m._device_args("chat", gpu) == ["-dev", "none", "-ngl", "0"]
    assert not m.on_gpu  # no reasoning pass when the language model runs on the CPU
    assert m._device_args("vision", gpu)[:2] == ["-dev", "Vulkan0"]  # vision stays on the GPU


async def test_changing_gpu_use_restarts_servers(tmp_path: Path) -> None:
    m = _manager(tmp_path)
    await _use(m, "chat")
    m.set_gpu_use("low")
    assert m._instances == {}


def test_ws_set_gpu_use_is_saved_and_reported() -> None:
    from fastapi.testclient import TestClient

    from studymate.main import app
    from studymate.services import get_services

    with TestClient(app) as client, client.websocket_connect("/ws") as ws:

        def reply(msg_id: str) -> dict[str, object]:
            while (msg := ws.receive_json()).get("id") != msg_id:  # skip the broadcast copies
                pass
            return dict(msg)

        ws.send_json({"type": "set_gpu_use", "id": "g1", "gpu_use": "balanced"})
        status = reply("g1")
        assert status["type"] == "status" and status["gpu_use"] == "balanced"
        assert get_services().llama.gpu_use == "balanced"
        ws.send_json({"type": "set_gpu_use", "id": "g2", "gpu_use": "high"})
        assert reply("g2")["gpu_use"] == "high"
