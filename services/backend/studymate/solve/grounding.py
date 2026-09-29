"""RAG context for ask / quiz. Retrieval problems never break the answer: no context instead."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import studymate.rag.retrieve as rag
from studymate.i18n import tr

if TYPE_CHECKING:
    from studymate.rag.retrieve import RetrievedChunk
    from studymate.services import Services

log = logging.getLogger(__name__)

EXCERPT_CHARS = 600


async def retrieve_safe(
    services: Services, query: str, *, doc_id: str | None = None, k: int = 6
) -> list[RetrievedChunk]:
    if not query.strip():
        return []
    try:
        return list(await rag.retrieve(services, query, doc_id=doc_id, k=k))
    except NotImplementedError:
        log.warning("retrieve() not implemented yet; answering without document context")
    except Exception as exc:  # embedding model missing, DB error, ...
        log.warning("retrieval failed (%s); answering without document context", exc)
    return []


def format_chunks(chunks: list[RetrievedChunk], limit: int = EXCERPT_CHARS) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        text = " ".join(c.text.split())[:limit]
        label = tr(f"자료 {i} · {c.page}쪽", f"資料 {i} · {c.page}ページ", f"Source {i} · p. {c.page}")
        parts.append(f"[{label}] {text}")
    return "\n".join(parts)
