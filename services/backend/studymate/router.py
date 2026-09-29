"""WebSocket message routing.

Handler modules under `studymate.handlers` register with `@router.on(<type>, <Model>)`.
Each incoming message is validated against its generated pydantic model and handled
in its own task, so a long solve never blocks TTS or drowsiness events.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from studymate import i18n
from studymate.errors import UserFacingError

log = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)
Handler = Callable[["Context", Any], Awaitable[None]]


class Hub:
    """Connected clients; broadcast is used for pushed state (drowsy, camera, status)."""

    def __init__(self) -> None:
        self._clients: set[Callable[[str], Awaitable[None]]] = set()
        self._on_empty: list[Callable[[], None]] = []

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def on_empty(self, callback: Callable[[], None]) -> None:
        """Registers a callback run when the last client disconnects (e.g. release the webcam)."""
        if callback not in self._on_empty:
            self._on_empty.append(callback)

    def add(self, send: Callable[[str], Awaitable[None]]) -> None:
        self._clients.add(send)

    def remove(self, send: Callable[[str], Awaitable[None]]) -> None:
        self._clients.discard(send)
        if not self._clients:
            for callback in list(self._on_empty):
                try:
                    callback()
                except Exception:
                    log.exception("on_empty callback failed")

    async def broadcast(self, msg: BaseModel | dict[str, Any]) -> None:
        text = _encode(msg)
        for send in list(self._clients):
            try:
                await send(text)
            except Exception:  # client went away mid-broadcast
                self._clients.discard(send)


class Context:
    """Per-message handle given to handlers."""

    def __init__(self, send_text: Callable[[str], Awaitable[None]], hub: Hub, request_id: str | None) -> None:
        self._send_text = send_text
        self.hub = hub
        self.request_id = request_id

    async def send(self, msg: BaseModel | dict[str, Any]) -> None:
        await self._send_text(_encode(msg))

    async def broadcast(self, msg: BaseModel | dict[str, Any]) -> None:
        await self.hub.broadcast(msg)

    async def error(self, code: str, message: str) -> None:
        payload: dict[str, Any] = {"type": "error", "code": code, "message": message}
        if self.request_id:
            payload["id"] = self.request_id
        await self.send(payload)


class Router:
    def __init__(self) -> None:
        self._routes: dict[str, tuple[type[BaseModel], Handler]] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        # Language every handler runs in (set by main to the backend's saved language).
        self.lang_provider: Callable[[], i18n.Lang] | None = None
        # How the character addresses the user, set with the language.
        self.address_provider: Callable[[], str] | None = None

    def on(self, msg_type: str, model: type[M]) -> Callable[[Callable[[Context, M], Awaitable[None]]], Any]:
        def decorator(fn: Callable[[Context, M], Awaitable[None]]) -> Any:
            if msg_type in self._routes:
                raise RuntimeError(f"duplicate handler for {msg_type}")
            self._routes[msg_type] = (model, fn)
            return fn

        return decorator

    @property
    def types(self) -> set[str]:
        return set(self._routes)

    def dispatch(self, raw: dict[str, Any], send_text: Callable[[str], Awaitable[None]], hub: Hub) -> None:
        msg_type = raw.get("type")
        request_id = raw.get("id") if isinstance(raw.get("id"), str) else None
        ctx = Context(send_text, hub, request_id)
        route = self._routes.get(msg_type) if isinstance(msg_type, str) else None
        task = asyncio.create_task(self._run(ctx, route, raw))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(
        self, ctx: Context, route: tuple[type[BaseModel], Handler] | None, raw: dict[str, Any]
    ) -> None:
        if route is None:
            await ctx.error("unknown_type", f"알 수 없는 메시지 종류입니다: {raw.get('type')}")
            return
        model, handler = route
        if self.lang_provider is not None:
            i18n.set_lang(self.lang_provider())
        if self.address_provider is not None:
            i18n.set_address(self.address_provider())
        try:
            msg = model.model_validate(raw)
        except ValidationError as exc:
            log.warning("invalid %s: %s", raw.get("type"), exc)
            await ctx.error("invalid_message", "메시지 형식이 올바르지 않습니다.")
            return
        try:
            await handler(ctx, msg)
        except UserFacingError as exc:
            await ctx.error(exc.code, exc.message)
        except Exception:
            log.exception("handler %s failed", raw.get("type"))
            await ctx.error("internal", "처리 중 오류가 발생했습니다.")

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)


def _encode(msg: BaseModel | dict[str, Any]) -> str:
    if isinstance(msg, BaseModel):
        return msg.model_dump_json(exclude_none=True)
    import json

    return json.dumps(msg, ensure_ascii=False)


router = Router()
