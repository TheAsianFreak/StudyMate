"""FastAPI entry point: `uvicorn studymate.main:app --port 8765`.

Binds to 127.0.0.1 only. The shell starts this process as a sidecar and talks to it over
a single WebSocket (`/ws`); `/health` is used for readiness checks.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from studymate import __version__, handlers
from studymate.router import Hub, router
from studymate.services import get_services

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("studymate")

hub = Hub()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    handlers.load_all()
    services = get_services()
    router.lang_provider = lambda: services.lang
    router.address_provider = lambda: services.address
    log.info("backend %s ready (tier=%s, handlers=%d)", __version__, services.tier, len(router.types))
    try:
        yield
    finally:
        await router.shutdown()
        services.shutdown()


app = FastAPI(title="StudyMate backend", version=__version__, lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.websocket("/ws")
async def websocket(ws: WebSocket) -> None:
    await ws.accept()

    async def send_text(text: str) -> None:
        await ws.send_text(text)

    hub.add(send_text)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await send_text(
                    json.dumps({"type": "error", "code": "bad_json", "message": "잘못된 JSON입니다."})
                )
                continue
            if not isinstance(msg, dict):
                continue
            router.dispatch(msg, send_text, hub)
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(send_text)


def run() -> None:
    """Console entry for the bundled executable."""
    import uvicorn

    from studymate.config import get_settings

    s = get_settings()
    uvicorn.run(app, host=s.host, port=s.port, log_level="info", ws="websockets")


if __name__ == "__main__":
    run()
