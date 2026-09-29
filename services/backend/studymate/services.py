"""Process-wide service container.

Core services are created at startup; heavy domain services (OCR, TTS, STT, drowsiness,
RAG) are created lazily through `lazy()` so a model is loaded only when first needed.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Callable
from typing import Any, TypeVar, cast

from studymate.config import GpuUse, Lang, Settings, Tier, get_settings
from studymate.llm.client import LlmClient
from studymate.llm.server import LlamaServerManager
from studymate.solve.memory import SolvedProblems
from studymate.storage import JsonStore
from studymate.system import hardware
from studymate.system.registry import ModelRegistry

T = TypeVar("T")


class Services:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.prefs = JsonStore(settings.data_dir / "backend-prefs.json")
        self.registry = ModelRegistry(settings)
        self._hardware: dict[str, Any] | None = None
        self.llama = LlamaServerManager(settings, self.registry, self.tier, self.gpu_use)
        self.llm = LlmClient(self.llama, settings.llama.request_timeout_s)
        self._lazy: dict[str, Any] = {}
        self._lazy_lock = threading.Lock()
        self.cleanups: list[Callable[[], None]] = []
        # follow-up questions work from the full text of these (solve/memory.py)
        self.solved = SolvedProblems()

    @property
    def hardware(self) -> dict[str, Any]:
        if self._hardware is None:
            self._hardware = hardware.detect()
        return self._hardware

    @property
    def tier(self) -> Tier:
        if self.settings.tier:
            return self.settings.tier
        saved = self.prefs.load().get("tier")
        if saved in ("lite", "standard", "pro", "max"):
            return cast(Tier, saved)
        return cast(Tier, self.hardware["recommended_tier"])

    def set_tier(self, tier: Tier) -> None:
        self.prefs.update(tier=tier)
        self.llama.set_tier(tier)

    @property
    def gpu_use(self) -> GpuUse:
        saved = self.prefs.load().get("gpu_use")
        return cast(GpuUse, saved) if saved in ("high", "balanced", "low") else "high"

    def set_gpu_use(self, gpu_use: GpuUse) -> None:
        self.prefs.update(gpu_use=gpu_use)
        self.llama.set_gpu_use(gpu_use)

    @property
    def lang(self) -> Lang:
        """Language of the character's speech, speech recognition and curriculum."""
        saved = self.prefs.load().get("lang")
        if saved in ("ko", "ja", "en"):
            return cast(Lang, saved)
        return self.settings.lang

    def set_lang(self, lang: Lang) -> None:
        self.prefs.update(lang=lang)

    @property
    def address(self) -> str:
        """How the character addresses the user ("" = default); already screened when saved."""
        saved = self.prefs.load().get("address")
        return saved if isinstance(saved, str) else ""

    def set_address(self, raw: str | None) -> str:
        """Screens and saves the address; raises UserFacingError when it is not acceptable."""
        from studymate.profile import clean_address

        value = clean_address(raw)
        self.prefs.update(address=value)
        return value

    def lazy(self, key: str, factory: Callable[[], T]) -> T:
        """Returns the singleton for `key`, creating it on first use (thread-safe)."""
        with self._lazy_lock:
            if key not in self._lazy:
                self._lazy[key] = factory()
            return cast(T, self._lazy[key])

    async def lazy_async(self, key: str, factory: Callable[[], T]) -> T:
        """Like `lazy` but builds in a worker thread (model loading blocks)."""
        if key in self._lazy:
            return cast(T, self._lazy[key])
        return await asyncio.to_thread(self.lazy, key, factory)

    def shutdown(self) -> None:
        for cleanup in reversed(self.cleanups):
            with contextlib.suppress(Exception):  # best effort on exit
                cleanup()
        self.llama.shutdown()


_services: Services | None = None


def get_services() -> Services:
    global _services
    if _services is None:
        _services = Services(get_settings())
    return _services
