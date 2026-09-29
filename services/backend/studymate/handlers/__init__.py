"""Message handlers. Every module in this package registers its routes on import."""

from __future__ import annotations

import importlib
import pkgutil


def load_all() -> None:
    for info in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{info.name}")
