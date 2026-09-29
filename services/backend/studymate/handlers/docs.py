"""doc_import / docs_get / doc_delete (RAG documents)."""

from __future__ import annotations

import asyncio

from studymate.db import get_db
from studymate.protocol.backend import DocDelete, DocImport, DocImported, DocProgress, Docs, DocsGet
from studymate.rag import store
from studymate.rag.importer import Stage, import_pdf
from studymate.router import Context, router
from studymate.services import Services, get_services


async def _docs(services: Services, request_id: str | None) -> Docs:
    db = await asyncio.to_thread(get_db, services)
    docs = await asyncio.to_thread(store.list_docs, db)
    return Docs(type="docs", id=request_id, docs=docs)


@router.on("doc_import", DocImport)
async def doc_import(ctx: Context, msg: DocImport) -> None:
    async def progress(stage: Stage, done: int, total: int) -> None:
        await ctx.send(DocProgress(type="doc_progress", id=msg.id, stage=stage, done=done, total=total))

    doc = await import_pdf(get_services(), msg.path, progress)
    await ctx.send(DocImported(type="doc_imported", id=msg.id, doc=doc))


@router.on("docs_get", DocsGet)
async def docs_get(ctx: Context, msg: DocsGet) -> None:
    await ctx.send(await _docs(get_services(), msg.id))


@router.on("doc_delete", DocDelete)
async def doc_delete(ctx: Context, msg: DocDelete) -> None:
    services = get_services()
    db = await asyncio.to_thread(get_db, services)
    await asyncio.to_thread(store.delete_doc, db, msg.doc_id)  # idempotent: unknown ids just refresh
    await ctx.send(await _docs(services, msg.id))
