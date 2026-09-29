"""Installed-model lookup and tier-based model selection."""

from __future__ import annotations

from pathlib import Path

from studymate.config import Settings, Tier
from studymate.system.downloader import ModelEntry, is_installed, load_registry


class ModelRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.entries: dict[str, ModelEntry] = {m.id: m for m in load_registry()}

    @property
    def models_dir(self) -> Path:
        return self.settings.models_dir

    def installed(self, model_id: str) -> bool:
        entry = self.entries.get(model_id)
        return entry is not None and is_installed(entry, self.models_dir)

    def path(self, model_id: str, index: int = 0) -> Path:
        """Absolute path of a model file (first file by default)."""
        return self.models_dir / self.entries[model_id].files[index].path

    def dir(self, model_id: str) -> Path:
        return self.path(model_id).parent

    def pick(self, tier: Tier, kind: str) -> str | None:
        """First installed model of `kind` (llm/vision/stt/embed) configured for the tier."""
        candidates: list[str] = getattr(self.settings.tiers[tier], kind)
        return next((m for m in candidates if self.installed(m)), None)

    def llama_server_exe(self) -> Path | None:
        """llama-server.exe from the installed runtime, preferring Vulkan unless forced to CPU."""
        order = {"auto": ["vulkan", "cpu"], "vulkan": ["vulkan", "cpu"], "cpu": ["cpu"]}[
            self.settings.llama.runtime
        ]
        for flavour in order:
            model_id = f"llama-runtime-{flavour}"
            if not self.installed(model_id):
                continue
            base = self.dir(model_id)
            for candidate in (base / "llama-server.exe", *base.glob("**/llama-server.exe")):
                if candidate.exists():
                    return candidate
        return None
