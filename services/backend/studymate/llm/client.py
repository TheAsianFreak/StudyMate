"""OpenAI-compatible calls to llama-server.

Structured output is always constrained with a JSON schema (llama.cpp turns it into a
grammar), so callers never parse free text (CLAUDE.md rule 6).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from studymate.errors import UserFacingError
from studymate.llm.server import LlamaServerManager, Role

log = logging.getLogger(__name__)


class LlmClient:
    def __init__(self, manager: LlamaServerManager, timeout_s: float) -> None:
        self.manager = manager
        self.timeout_s = timeout_s

    async def chat_json(
        self,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
        *,
        role: Role = "chat",
        name: str = "output",
        temperature: float = 0.2,
        max_tokens: int = 2048,
        seed: int | None = None,
        sampling: dict[str, Any] | None = None,
        think: bool = False,
    ) -> dict[str, Any]:
        """Chat completion whose content is guaranteed to match `schema`. `sampling` adds
        llama-server sampler options (e.g. the DRY repetition penalty). With `think` the model
        reasons first (Qwen3 thinking, capped by llama.reasoning_budget); the reasoning comes
        back apart from the content and is not used: the schema-constrained content follows it."""
        body: dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": name, "schema": schema, "strict": True},
            },
            "chat_template_kwargs": {"enable_thinking": think},
        }
        if seed is not None:
            body["seed"] = seed
        if sampling:
            body.update(sampling)
        data = await self._post("/v1/chat/completions", body, role)
        content = data["choices"][0]["message"].get("content") or ""
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            log.warning("schema-constrained output was not JSON: %.200s", content)
            raise UserFacingError("llm_bad_output", "모델 출력이 올바르지 않습니다.") from exc
        if not isinstance(parsed, dict):
            raise UserFacingError("llm_bad_output", "모델 출력이 올바르지 않습니다.")
        result: dict[str, Any] = strip_surrogates(parsed)
        return result

    async def embed(self, texts: list[str]) -> list[list[float]]:
        data = await self._post("/v1/embeddings", {"input": texts}, "embed")
        items = sorted(data["data"], key=lambda d: d["index"])
        return [item["embedding"] for item in items]

    async def _post(self, path: str, body: dict[str, Any], role: Role) -> dict[str, Any]:
        async with self.manager.session(role) as base:
            try:
                async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                    r = await client.post(base + path, json=body)
                    r.raise_for_status()
                    result: dict[str, Any] = r.json()
                    return result
            except httpx.HTTPError as exc:
                log.error("llama-server %s request failed: %s", role, exc)
                raise UserFacingError("llm_request_failed", "언어 모델 요청에 실패했습니다.") from exc


_LONE_SURROGATE = re.compile(f"[{chr(0xD800)}-{chr(0xDFFF)}]")


def strip_surrogates(value: Any) -> Any:
    """Drops lone UTF-16 surrogates. The model sometimes escapes half an emoji, which
    json.loads keeps as is and which then cannot be encoded as UTF-8 (WebSocket, files)."""
    if isinstance(value, str):
        return _LONE_SURROGATE.sub("", value)
    if isinstance(value, list):
        return [strip_surrogates(v) for v in value]
    if isinstance(value, dict):
        return {k: strip_surrogates(v) for k, v in value.items()}
    return value


def image_message(text: str, png_base64: str) -> dict[str, Any]:
    """User message with an inline image for the vision role."""
    return {
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{png_base64}"}},
            {"type": "text", "text": text},
        ],
    }
