"""Document, chunk and vector tables."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from studymate.db import EMBED_DIM, Database
from studymate.protocol.backend import DocInfo
from studymate.rag.text import Chunk

_DOC_COLUMNS = "doc_id, title, pages, chunks, imported_at, empty_pages"


@dataclass(frozen=True)
class ChunkHit:
    chunk_id: int
    doc_id: str
    page: int
    text: str
    distance: float


def to_blob(vector: Sequence[float] | np.ndarray) -> bytes:
    """Unit-normalised float32 blob for vec0 (cosine distance)."""
    arr = np.asarray(vector, dtype=np.float32)
    if arr.shape != (EMBED_DIM,):
        raise ValueError(f"embedding has shape {arr.shape}, expected ({EMBED_DIM},)")
    norm = float(np.linalg.norm(arr))
    if not np.isfinite(norm) or norm == 0.0:
        raise ValueError("embedding is zero or not finite")
    return (arr / norm).astype(np.float32).tobytes()


def _doc(row: sqlite3.Row) -> DocInfo:
    return DocInfo(
        doc_id=row["doc_id"],
        title=row["title"],
        pages=row["pages"],
        chunks=row["chunks"],
        imported_at=row["imported_at"],
        empty_pages=json.loads(row["empty_pages"] or "[]"),
    )


def find_by_sha256(db: Database, sha256: str) -> DocInfo | None:
    with db.read() as conn:
        row = conn.execute(f"SELECT {_DOC_COLUMNS} FROM documents WHERE sha256 = ?", (sha256,)).fetchone()
    return _doc(row) if row else None


def insert_document(
    db: Database,
    *,
    doc_id: str,
    title: str,
    path: str,
    sha256: str,
    pages: int,
    empty_pages: list[int],
    imported_at: str,
    chunks: list[Chunk],
    blobs: list[bytes],
) -> DocInfo:
    if len(chunks) != len(blobs):
        raise ValueError("chunks and embeddings differ in length")
    with db.write() as conn:
        conn.execute(
            "INSERT INTO documents (doc_id, title, path, sha256, pages, chunks, empty_pages, imported_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (doc_id, title, path, sha256, pages, len(chunks), json.dumps(empty_pages), imported_at),
        )
        for chunk, blob in zip(chunks, blobs, strict=True):
            cur = conn.execute(
                "INSERT INTO chunks (doc_id, page, ord, text) VALUES (?, ?, ?, ?)",
                (doc_id, chunk.page, chunk.ord, chunk.text),
            )
            conn.execute(
                "INSERT INTO chunk_vecs (chunk_id, doc_id, embedding) VALUES (?, ?, ?)",
                (cur.lastrowid, doc_id, blob),
            )
    return DocInfo(
        doc_id=doc_id,
        title=title,
        pages=pages,
        chunks=len(chunks),
        imported_at=imported_at,
        empty_pages=empty_pages,
    )


def list_docs(db: Database) -> list[DocInfo]:
    with db.read() as conn:
        rows = conn.execute(f"SELECT {_DOC_COLUMNS} FROM documents ORDER BY imported_at DESC").fetchall()
    return [_doc(r) for r in rows]


def delete_doc(db: Database, doc_id: str) -> bool:
    """Deletes the document; chunks cascade and a trigger removes their vectors."""
    with db.write() as conn:
        return conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,)).rowcount > 0


def chunk_count(db: Database, doc_id: str | None = None) -> int:
    with db.read() as conn:
        if doc_id is None:
            row = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) FROM chunks WHERE doc_id = ?", (doc_id,)).fetchone()
    return int(row[0])


def knn(db: Database, blob: bytes, k: int, doc_id: str | None = None) -> list[ChunkHit]:
    """Nearest chunks by cosine distance (0 = same direction, 2 = opposite)."""
    where = "embedding MATCH ? AND k = ?" + (" AND doc_id = ?" if doc_id is not None else "")
    params: tuple[object, ...] = (blob, k) if doc_id is None else (blob, k, doc_id)
    sql = (
        f"WITH knn AS (SELECT chunk_id, distance FROM chunk_vecs WHERE {where})"
        " SELECT c.chunk_id, c.doc_id, c.page, c.text, knn.distance"
        " FROM knn JOIN chunks c ON c.chunk_id = knn.chunk_id ORDER BY knn.distance"
    )
    with db.read() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [ChunkHit(r["chunk_id"], r["doc_id"], r["page"], r["text"], float(r["distance"])) for r in rows]


def doc_empty_pages(db: Database, doc_id: str) -> list[int]:
    with db.read() as conn:
        row = conn.execute("SELECT empty_pages FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    return list(json.loads(row[0])) if row else []
