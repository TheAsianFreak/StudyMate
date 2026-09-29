"""Small JSON document store in the data dir (user preferences, voice presets).
Structured learning data lives in SQLite (`studymate.db`)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class JsonStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def load(self) -> dict[str, Any]:
        with self._lock:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                return {}
            return data if isinstance(data, dict) else {}

    def save(self, data: dict[str, Any]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)

    def update(self, **values: Any) -> dict[str, Any]:
        data = self.load()
        data.update(values)
        self.save(data)
        return data
