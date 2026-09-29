"""llama-server process management.

One llama-server process per role (chat / vision / embed), started lazily on first use
and stopped after `idle_unload_s` without requests, so models only occupy RAM/VRAM while
they are needed. When a model would not fit in GPU memory next to the ones already
running (Max tier: Qwen3 14B + Qwen2.5-VL 7B on a 16 GB card), the least recently used
other role is stopped first, once its in-flight requests are done.
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import httpx

from studymate.config import GpuUse, Settings, Tier
from studymate.errors import ModelMissingError, UserFacingError
from studymate.system.registry import ModelRegistry

log = logging.getLogger(__name__)

Role = Literal["chat", "vision", "embed"]
_ROLE_OFFSET: dict[Role, int] = {"chat": 0, "vision": 1, "embed": 2}
_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_DEVICE_LINE = re.compile(r"^\s*(\S+): (.+?) \((\d+) MiB, (\d+) MiB free\)")
_INTEGRATED = re.compile(
    r"Radeon\(TM\) Graphics|Radeon Graphics|Intel\(R\) (UHD|Iris|Graphics)|Vega \d+ Graphics", re.I
)


# Injected when a reasoning pass runs out of budget, so the model wraps up instead of stopping mid-thought.
REASONING_BUDGET_MESSAGE = " Time is up, so I will write the answer from the work so far."
# gpu_use "balanced": share of the card llama.cpp leaves free for the rest of the PC
BALANCED_FREE_PERCENT = 50


@dataclass(frozen=True)
class Device:
    name: str  # llama.cpp device id, e.g. "Vulkan0"
    total_mib: int
    free_mib: int


def pick_device(list_devices_output: str) -> Device | None:
    """Chooses the discrete GPU from `llama-server --list-devices`; None means CPU only.

    Integrated GPUs report shared system RAM as VRAM, so they are only used when
    nothing else is available.
    """
    devices = []
    for line in list_devices_output.splitlines():
        if m := _DEVICE_LINE.match(line):
            devices.append((Device(m.group(1), int(m.group(3)), int(m.group(4))), m.group(2)))
    discrete = [d for d, desc in devices if not _INTEGRATED.search(desc)]
    pool = discrete or [d for d, _ in devices]
    if not pool:
        return None
    return max(pool, key=lambda d: d.total_mib)


@dataclass
class _Instance:
    model_id: str
    port: int
    process: subprocess.Popen[bytes]
    last_used: float = field(default_factory=time.monotonic)


class LlamaServerManager:
    def __init__(
        self, settings: Settings, registry: ModelRegistry, tier: Tier, gpu_use: GpuUse = "high"
    ) -> None:
        self.settings = settings
        self.registry = registry
        self.tier: Tier = tier
        self.gpu_use: GpuUse = gpu_use
        self._instances: dict[Role, _Instance] = {}
        self._locks: dict[Role, asyncio.Lock] = {r: asyncio.Lock() for r in _ROLE_OFFSET}
        self._start_lock = asyncio.Lock()  # one start at a time, so the GPU budget stays true
        self._busy: dict[Role, int] = dict.fromkeys(_ROLE_OFFSET, 0)  # requests in flight
        self._idle: dict[Role, asyncio.Event] = {r: asyncio.Event() for r in _ROLE_OFFSET}
        self._open: dict[Role, asyncio.Event] = {r: asyncio.Event() for r in _ROLE_OFFSET}
        for r in _ROLE_OFFSET:
            self._idle[r].set()
            self._open[r].set()  # cleared while the role drains to make room for another
        self._reaper: asyncio.Task[None] | None = None
        self._device: Device | None | Literal[False] = False  # False = not probed yet

    def set_tier(self, tier: Tier) -> None:
        if tier != self.tier:
            self.tier = tier
            for role in list(self._instances):
                self._stop(role)

    def set_gpu_use(self, gpu_use: GpuUse) -> None:
        """The servers restart with the new placement on their next use."""
        if gpu_use != self.gpu_use:
            self.gpu_use = gpu_use
            for role in list(self._instances):
                self._stop(role)

    def model_for(self, role: Role) -> str | None:
        kind = {"chat": "llm", "vision": "vision", "embed": "embed"}[role]
        return self.registry.pick(self.tier, kind)

    def available(self, role: Role) -> bool:
        return self.model_for(role) is not None and self.registry.llama_server_exe() is not None

    @asynccontextmanager
    async def session(self, role: Role) -> AsyncIterator[str]:
        """Base URL of the role's server, started if needed, for one request. While the
        session is open the server is never stopped to make room for another model."""
        base = await self._acquire(role)
        try:
            yield base
        finally:
            self._release(role)

    async def _acquire(self, role: Role) -> str:
        await self._open[role].wait()
        async with self._locks[role]:
            model_id = self.model_for(role)
            if model_id is None:
                raise ModelMissingError({"chat": "언어", "vision": "비전", "embed": "임베딩"}[role])
            inst = self._instances.get(role)
            if inst and (inst.model_id != model_id or inst.process.poll() is not None):
                self._stop(role)
                inst = None
            if inst is None:
                async with self._start_lock:
                    await self._make_room(role, model_id)
                    inst = await self._start(role, model_id)
                self._instances[role] = inst
            inst.last_used = time.monotonic()
            self._busy[role] += 1
            self._idle[role].clear()
            self._ensure_reaper()
            return f"http://127.0.0.1:{inst.port}"

    def _release(self, role: Role) -> None:
        self._busy[role] -= 1
        if inst := self._instances.get(role):
            inst.last_used = time.monotonic()
        if self._busy[role] == 0:
            self._idle[role].set()

    def _on_cpu(self, role: Role) -> bool:
        """Embeddings always run on the CPU (small model, frees the GPU); the language model
        too with gpu_use "low". The vision model stays on the GPU: on the CPU reading one
        screenshot takes about a minute."""
        return role == "embed" or (role == "chat" and self.gpu_use == "low")

    def _device_args(self, role: Role, device: Device | None) -> list[str]:
        if device is None or self._on_cpu(role):
            return ["-dev", "none", "-ngl", "0"]
        if role == "chat" and self.gpu_use == "balanced":
            # llama.cpp keeps as many layers on the GPU as leave half the card free; the rest
            # run on the CPU (slower answers, lighter GPU load)
            margin = device.total_mib * BALANCED_FREE_PERCENT // 100
            return ["-dev", device.name, "-ngl", "auto", "--fit", "on", "--fit-target", str(margin)]
        return ["-dev", device.name, "-ngl", str(self.settings.llama.gpu_layers)]

    def footprint_mib(self, role: Role, model_id: str) -> int:
        """Estimated GPU memory of a role's server: weights plus context and compute buffers."""
        if self._on_cpu(role):
            return 0
        size = self.registry.entries[model_id].total_size / 2**20
        full = int(size) + self.settings.llama.vram_overhead_mib.get(role, 0)
        if role == "chat" and self.gpu_use == "balanced" and self._device:
            return min(full, self._device.total_mib * (100 - BALANCED_FREE_PERCENT) // 100)
        return full

    async def _make_room(self, role: Role, model_id: str) -> None:
        """Stops other roles (least recently used first) until `role` fits in GPU memory.
        The budget is the free memory seen before any of our servers ran, less a margin."""
        exe = self.registry.llama_server_exe()
        if exe is None:
            return
        device = (
            self._device if self._device is not False else await asyncio.to_thread(self._probe_device, exe)
        )
        if device is None:
            return  # CPU: system RAM, no budget
        budget = device.free_mib - self.settings.llama.vram_margin_mib
        need = self.footprint_mib(role, model_id)
        while True:
            running = [r for r in self._instances if r != role]
            used = sum(self.footprint_mib(r, self._instances[r].model_id) for r in running)
            if not running or used + need <= budget:
                return
            victim = min(running, key=lambda r: self._instances[r].last_used)
            log.info(
                "stopping llama-server %s for %s (%d + %d MiB > %d MiB)", victim, role, used, need, budget
            )
            self._open[victim].clear()
            try:
                await self._idle[victim].wait()
                self._stop(victim)
            finally:
                self._open[victim].set()

    @property
    def on_gpu(self) -> bool:
        """The language model runs on a GPU (known once a server has started)."""
        return bool(self._device) and not self._on_cpu("chat")

    def _probe_device(self, exe: Path) -> Device | None:
        if self._device is False:
            try:
                out = subprocess.run(
                    [str(exe), "--list-devices"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    creationflags=_CREATE_NO_WINDOW,
                    cwd=str(exe.parent),
                )
                self._device = pick_device(out.stdout + out.stderr)
            except (OSError, subprocess.TimeoutExpired):
                self._device = None
            log.info("llama.cpp device: %s", self._device or "CPU")
        return self._device or None

    async def _start(self, role: Role, model_id: str) -> _Instance:
        exe = self.registry.llama_server_exe()
        if exe is None:
            raise ModelMissingError("llama.cpp 런타임")
        device = await asyncio.to_thread(self._probe_device, exe)
        cfg = self.settings.llama
        port = cfg.base_port + _ROLE_OFFSET[role]
        args = [
            str(exe),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "-m",
            str(self.registry.path(model_id)),
            "--no-webui",
        ]
        args += self._device_args(role, device)
        if cfg.threads:
            args += ["-t", str(cfg.threads)]
        if role == "chat":
            args += [
                "-c",
                str(cfg.chat_ctx),
                "--jinja",
                "-fa",
                "auto",
                "-ctk",
                "q8_0",
                "-ctv",
                "q8_0",
                # thinking only when a request asks for it (chat_json(think=True)); every
                # other request turns it off in the chat template
                "--reasoning",
                "auto",
                "--reasoning-budget",
                str(cfg.reasoning_budget),
                "--reasoning-budget-message",
                REASONING_BUDGET_MESSAGE,
            ]
        elif role == "vision":
            args += ["-c", str(cfg.vision_ctx), "--jinja", "--reasoning", "off"]
            args += ["--mmproj", str(self.registry.path(model_id, 1))]
        else:
            args += ["-c", str(cfg.embed_ctx), "--embedding", "--pooling", "cls", "-ub", str(cfg.embed_ctx)]

        log.info("starting llama-server %s (%s) on :%d", role, model_id, port)
        log_path = self.settings.data_dir / "logs" / f"llama-{role}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("wb") as log_file:
            process = subprocess.Popen(
                args,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=_CREATE_NO_WINDOW,
                cwd=str(Path(exe).parent),
            )
        inst = _Instance(model_id, port, process)
        await self._wait_healthy(inst, log_path)
        return inst

    async def _wait_healthy(self, inst: _Instance, log_path: Path) -> None:
        deadline = time.monotonic() + self.settings.llama.startup_timeout_s
        async with httpx.AsyncClient(timeout=2.0) as client:
            while time.monotonic() < deadline:
                if inst.process.poll() is not None:
                    tail = log_path.read_text(encoding="utf-8", errors="replace")[-800:]
                    log.error("llama-server exited early:\n%s", tail)
                    raise UserFacingError(
                        "llm_start_failed", "언어 모델을 시작하지 못했습니다. 로그를 확인해주세요."
                    )
                try:
                    r = await client.get(f"http://127.0.0.1:{inst.port}/health")
                    if r.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.5)
        inst.process.kill()
        raise UserFacingError("llm_start_timeout", "언어 모델 시작 시간이 초과되었습니다.")

    def _ensure_reaper(self) -> None:
        if self._reaper is None or self._reaper.done():
            self._reaper = asyncio.create_task(self._reap_idle())

    async def _reap_idle(self) -> None:
        idle = self.settings.llama.idle_unload_s
        while self._instances:
            await asyncio.sleep(min(30.0, idle))
            now = time.monotonic()
            for role, inst in list(self._instances.items()):
                if now - inst.last_used > idle and self._busy[role] == 0 and not self._locks[role].locked():
                    log.info("unloading idle llama-server %s", role)
                    self._stop(role)

    def _stop(self, role: Role) -> None:
        inst = self._instances.pop(role, None)
        if inst and inst.process.poll() is None:
            inst.process.terminate()
            try:
                inst.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                inst.process.kill()

    def shutdown(self) -> None:
        for role in list(self._instances):
            self._stop(role)
        if self._reaper:
            self._reaper.cancel()
