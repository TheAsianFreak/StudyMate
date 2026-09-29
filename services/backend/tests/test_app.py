from __future__ import annotations

from fastapi.testclient import TestClient

from studymate.llm.server import Device, pick_device
from studymate.main import app


def test_health_and_hello() -> None:
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "hello", "id": "h1"})
            status = ws.receive_json()
            assert status["type"] == "status"
            assert status["id"] == "h1"
            assert status["tier"] in ("lite", "standard", "pro", "max")
            assert {"solve", "tts", "stt", "drowsy", "rag", "vision"} <= status["capabilities"].keys()


def test_unknown_and_invalid_messages() -> None:
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "nope", "id": "x"})
        assert ws.receive_json()["code"] == "unknown_type"
        ws.send_json({"type": "set_tier", "id": "y", "tier": "ultra"})
        assert ws.receive_json()["code"] == "invalid_message"


def test_pick_device_prefers_discrete_gpu() -> None:
    out = (
        "Available devices:\n"
        "  Vulkan0: NVIDIA GeForce RTX 5080 (15977 MiB, 15209 MiB free)\n"
        "  Vulkan1: AMD Radeon(TM) Graphics (48799 MiB, 46359 MiB free)\n"
    )
    assert pick_device(out) == Device("Vulkan0", 15977, 15209)
    igpu = pick_device("  Vulkan0: AMD Radeon(TM) Graphics (4000 MiB, 3000 MiB free)")
    assert igpu is not None and igpu.name == "Vulkan0"
    assert pick_device("no devices") is None
