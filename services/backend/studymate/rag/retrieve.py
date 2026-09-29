"""Retrieval interface used by quiz generation and Q&A."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from studymate.db import get_db
from studymate.errors import UserFacingError
from studymate.rag import store

if TYPE_CHECKING:
    from studymate.services import Services

log = logging.getLogger(__name__)

_MAX_QUERY_CHARS = 2000
_MAX_K = 4096  # sqlite-vec KNN limit


@dataclass(frozen=True)
class RetrievedChunk:
    doc_id: str
    page: int  # 1-based
    text: str
    score: float  # cosine similarity, higher is closer (bge-m3: ~0.3 unrelated .. 1.0)


async def retrieve(
    services: Services, query: str, *, doc_id: str | None = None, k: int = 6
) -> list[RetrievedChunk]:
    """Top-k chunks most similar to `query`, optionally limited to one document.

    Returns [] when no documents are imported or the embedding model is unavailable.
    """
    query = " ".join(query.split())[:_MAX_QUERY_CHARS]
    if not query or k <= 0:
        return []
    db = await asyncio.to_thread(get_db, services)
    if await asyncio.to_thread(store.chunk_count, db, doc_id) == 0:
        return []
    if not services.llama.available("embed"):
        return []
    try:
        vectors = await services.llm.embed([query])
        blob = store.to_blob(vectors[0])
    except (UserFacingError, ValueError, IndexError) as exc:
        log.warning("query embedding failed: %s", exc)
        return []
    hits = await asyncio.to_thread(store.knn, db, blob, min(k, _MAX_K), doc_id)
    return [RetrievedChunk(doc_id=h.doc_id, page=h.page, text=h.text, score=1.0 - h.distance) for h in hits]
