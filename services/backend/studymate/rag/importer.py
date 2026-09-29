"""PDF import: validate -> extract -> clean/chunk -> embed (batched) -> store."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from studymate.db import Database, get_db, iso, utc_now
from studymate.errors import ModelMissingError, UserFacingError
from studymate.protocol.backend import DocInfo
from studymate.rag import store
from studymate.rag.pdf import extract_pages, file_sha256, validate_pdf_path
from studymate.rag.text import chunk_document, clean_document

if TYPE_CHECKING:
    from studymate.services import Services

log = logging.getLogger(__name__)

Stage = Literal["extract", "embed"]
Progress = Callable[[Stage, int, int], Coroutine[Any, Any, None]]

_PROGRESS_STEPS = 50  # at most ~50 progress events per stage
_importing: set[str] = set()


def require_embedder(services: Services) -> None:
    if services.registry.llama_server_exe() is None:
        raise ModelMissingError("llama.cpp 런타임")
    if not services.llama.available("embed"):
        raise ModelMissingError("임베딩")


async def embed_texts(services: Services, texts: list[str]) -> list[bytes]:
    vectors = await services.llm.embed(texts)
    if len(vectors) != len(texts):
        raise UserFacingError("embed_failed", "임베딩 결과가 올바르지 않습니다.")
    try:
        return [store.to_blob(v) for v in vectors]
    except ValueError as exc:
        log.error("bad embedding: %s", exc)
        raise UserFacingError("embed_failed", "임베딩 결과가 올바르지 않습니다.") from exc


async def import_pdf(services: Services, raw_path: str, progress: Progress | None = None) -> DocInfo:
    cfg = services.settings.rag
    path = validate_pdf_path(raw_path, cfg.max_pdf_mb)
    require_embedder(services)
    db = await asyncio.to_thread(get_db, services)

    sha256 = await asyncio.to_thread(file_sha256, path)
    existing = await asyncio.to_thread(store.find_by_sha256, db, sha256)
    if existing is not None:
        log.info("pdf already imported as %s", existing.doc_id)
        return existing
    if sha256 in _importing:
        raise UserFacingError("already_importing", "이미 가져오는 중인 문서입니다.")
    _importing.add(sha256)
    try:
        return await _import(services, db, path, sha256, progress)
    finally:
        _importing.discard(sha256)


async def _import(
    services: Services, db: Database, path: Path, sha256: str, progress: Progress | None
) -> DocInfo:
    cfg = services.settings.rag
    loop = asyncio.get_running_loop()
    started = time.perf_counter()

    def on_page(done: int, total: int) -> None:
        if progress is None or not _should_report(done, total):
            return
        future = asyncio.run_coroutine_threadsafe(progress("extract", done, total), loop)
        try:
            future.result(timeout=10)  # keeps events in order
        except Exception:  # a slow or closed socket must not break the import
            log.debug("extract progress not delivered", exc_info=True)

    raw_pages = await asyncio.to_thread(extract_pages, path, on_page)
    pages = await asyncio.to_thread(clean_document, raw_pages)
    empty_pages = [
        i
        for i, paras in enumerate(pages, start=1)
        if sum(len(p.replace(" ", "")) for p in paras) < cfg.min_page_chars
    ]
    chunks = chunk_document(pages, cfg.chunk_chars, cfg.chunk_overlap, cfg.min_chunk_chars)
    extracted = time.perf_counter()
    log.info(
        "%s: %d pages (%d without text layer), %d chunks in %.2fs",
        path.name,
        len(raw_pages),
        len(empty_pages),
        len(chunks),
        extracted - started,
    )
    if not chunks:
        if raw_pages and len(empty_pages) == len(raw_pages):
            raise UserFacingError(
                "pdf_no_text", "PDF에서 글자를 찾지 못했습니다. 스캔한 PDF(이미지)는 아직 지원하지 않습니다."
            )
        raise UserFacingError("pdf_no_text", "PDF에서 가져올 내용을 찾지 못했습니다.")

    blobs: list[bytes] = []
    total = len(chunks)
    if progress is not None:
        await progress("embed", 0, total)
    for start in range(0, total, max(1, cfg.embed_batch)):
        batch = chunks[start : start + cfg.embed_batch]
        blobs += await embed_texts(services, [c.text for c in batch])
        if progress is not None and _should_report(len(blobs), total):
            await progress("embed", len(blobs), total)
    log.info("%s: embedded %d chunks in %.2fs", path.name, total, time.perf_counter() - extracted)

    doc = await asyncio.to_thread(
        store.insert_document,
        db,
        doc_id=f"d_{uuid.uuid4().hex[:12]}",
        title=path.stem,
        path=str(path),
        sha256=sha256,
        pages=len(raw_pages),
        empty_pages=empty_pages,
        imported_at=iso(utc_now()),
        chunks=chunks,
        blobs=blobs,
    )
    return doc


def _should_report(done: int, total: int) -> bool:
    step = max(1, total // _PROGRESS_STEPS)
    return done == total or done % step == 0
