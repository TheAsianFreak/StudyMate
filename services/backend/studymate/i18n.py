"""Language of the current request (ko / ja / en).

The router sets it for every incoming message from `Services.lang`, so prompts, safety
lines and verifier hints can pick their language without threading a parameter through
every call. Context variables follow asyncio tasks and `asyncio.to_thread`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal

Lang = Literal["ko", "ja", "en"]
LANGS: tuple[Lang, ...] = ("ko", "ja", "en")

_current: ContextVar[Lang] = ContextVar("studymate_lang", default="ko")
# How the character addresses the user ("" = the character's default), set with the language.
_address: ContextVar[str] = ContextVar("studymate_address", default="")


def address() -> str:
    return _address.get()


def set_address(value: str) -> None:
    _address.set(value)


@contextmanager
def use_address(value: str) -> Iterator[None]:
    token = _address.set(value)
    try:
        yield
    finally:
        _address.reset(token)


def lang() -> Lang:
    return _current.get()


def set_lang(value: Lang) -> None:
    _current.set(value)


@contextmanager
def use_lang(value: Lang) -> Iterator[None]:
    token = _current.set(value)
    try:
        yield
    finally:
        _current.reset(token)


def tr(ko: str, ja: str, en: str) -> str:
    """The string for the current language."""
    current = _current.get()
    return ja if current == "ja" else en if current == "en" else ko
