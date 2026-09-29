"""Database layer tests. Also hosts helpers shared by test_rag*/test_learning* (imported
by name; conftest.py belongs to another area)."""

from __future__ import annotations

import ctypes
import sqlite3
import threading
import zlib
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
import pytest

from studymate.config import Settings
from studymate.db import EMBED_DIM, MIGRATIONS, Database, connect, get_db, iso, parse_iso, utc_now
from studymate.rag import store as rag_store
from studymate.rag.text import Chunk
from studymate.services import Services

KOREAN_FONT = Path("C:/Windows/Fonts/malgun.ttf")

# --- shared helpers -----------------------------------------------------------------


def fake_vector(text: str) -> list[float]:
    """Deterministic bag-of-character-bigrams embedding: texts sharing words are close."""
    v = np.zeros(EMBED_DIM, dtype=np.float64)
    t = "".join(text.lower().split())
    for i in range(len(t) - 1):
        v[zlib.crc32(t[i : i + 2].encode("utf-8")) % EMBED_DIM] += 1.0
    if not v.any():
        v[0] = 1.0
    return [float(x) for x in v]


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [fake_vector(t) for t in texts]


def make_services(tmp_path: Path, *, embed: bool = True) -> tuple[Services, FakeEmbedder]:
    """Services on a fresh data dir; the embedding model is faked (or reported missing)."""
    services = Services(Settings(data_dir=tmp_path, tier="lite"))
    embedder = FakeEmbedder()
    services.llm.embed = embedder  # type: ignore[method-assign]
    services.llama.available = lambda role: embed  # type: ignore[method-assign]
    services.registry.llama_server_exe = lambda: tmp_path / "llama-server.exe"  # type: ignore[method-assign]
    return services, embedder


def make_pdf(path: Path, pages: list[list[str]], font_path: Path | None = None) -> Path:
    """Writes a PDF with one text line per list entry (an empty page list = blank page)."""
    pdf = pdfium.PdfDocument.new()
    if font_path is not None:
        data = font_path.read_bytes()
        buf = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
        font = pdfium_c.FPDFText_LoadFont(pdf, buf, len(data), pdfium_c.FPDF_FONT_TRUETYPE, 1)
    else:
        font = pdfium_c.FPDFText_LoadStandardFont(pdf, b"Helvetica")
    assert font
    try:
        for lines in pages:
            page = pdf.new_page(595, 842)
            y = 800.0
            for line in lines:
                obj = pdfium_c.FPDFPageObj_CreateTextObj(pdf, font, 11.0)
                wide = ctypes.create_string_buffer((line + "\x00").encode("utf-16-le"))
                assert pdfium_c.FPDFText_SetText(obj, ctypes.cast(wide, ctypes.POINTER(pdfium_c.FPDF_WCHAR)))
                pdfium_c.FPDFPageObj_Transform(obj, 1, 0, 0, 1, 40, y)
                pdfium_c.FPDFPage_InsertObject(page, obj)
                y -= 16
            assert pdfium_c.FPDFPage_GenerateContent(page)
            page.close()
    finally:
        pdfium_c.FPDFFont_Close(font)
    pdf.save(str(path))
    pdf.close()
    return path


# --- tests --------------------------------------------------------------------------


def test_connect_applies_migrations_once(tmp_path: Path) -> None:
    path = tmp_path / "a.db"
    conn = connect(path)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == len(MIGRATIONS)
        tables = {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'trigger')")
        }
        assert {
            "documents",
            "chunks",
            "chunk_vecs",
            "quiz_items",
            "attempts",
            "wrong_notes",
            "review_cards",
            "review_logs",
            "chunks_after_delete",
        } <= tables
        assert conn.execute("SELECT vec_version()").fetchone()[0].startswith("v")
    finally:
        conn.close()
    conn = connect(path)  # second open: nothing re-applied
    try:
        assert conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == len(MIGRATIONS)
    finally:
        conn.close()


def test_newer_schema_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "b.db"
    connect(path).close()
    raw = sqlite3.connect(path)
    raw.execute("INSERT INTO schema_version VALUES (999, 'x')")
    raw.commit()
    raw.close()
    with pytest.raises(RuntimeError, match="newer"):
        connect(path)


def test_write_rolls_back_on_error(tmp_path: Path) -> None:
    db = Database(tmp_path / "c.db")
    with pytest.raises(ValueError), db.write() as conn:
        conn.execute("INSERT INTO quiz_items VALUES ('q1', '{}', 'now')")
        raise ValueError("boom")
    with db.read() as conn:
        assert conn.execute("SELECT COUNT(*) FROM quiz_items").fetchone()[0] == 0
    db.close()
    with db.read() as conn:  # reconnects after close
        assert conn.execute("SELECT COUNT(*) FROM quiz_items").fetchone()[0] == 0
    db.close()


def test_concurrent_writers(tmp_path: Path) -> None:
    db = Database(tmp_path / "d.db")

    def work(n: int) -> None:
        for i in range(25):
            with db.write() as conn:
                conn.execute("INSERT INTO quiz_items VALUES (?, '{}', 'now')", (f"q{n}_{i}",))

    threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with db.read() as conn:
        assert conn.execute("SELECT COUNT(*) FROM quiz_items").fetchone()[0] == 200
    db.close()


def test_delete_document_removes_chunks_and_vectors(tmp_path: Path) -> None:
    db = Database(tmp_path / "e.db")
    for doc_id, sha in (("d1", "s1"), ("d2", "s2")):
        chunks = [Chunk(page=1, ord=i, text=f"{doc_id} chunk {i}") for i in range(3)]
        rag_store.insert_document(
            db,
            doc_id=doc_id,
            title=doc_id,
            path=f"C:/{doc_id}.pdf",
            sha256=sha,
            pages=1,
            empty_pages=[],
            imported_at=iso(utc_now()),
            chunks=chunks,
            blobs=[rag_store.to_blob(fake_vector(c.text)) for c in chunks],
        )
    assert rag_store.chunk_count(db) == 6
    assert rag_store.delete_doc(db, "d1")
    assert not rag_store.delete_doc(db, "d1")
    with db.read() as conn:
        assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM chunk_vecs").fetchone()[0] == 3
    hits = rag_store.knn(db, rag_store.to_blob(fake_vector("d1 chunk 0")), 10)
    assert {h.doc_id for h in hits} == {"d2"}
    db.close()


def test_to_blob_validates_shape() -> None:
    with pytest.raises(ValueError):
        rag_store.to_blob([1.0, 2.0])
    with pytest.raises(ValueError):
        rag_store.to_blob([0.0] * EMBED_DIM)
    blob = rag_store.to_blob([3.0] + [0.0] * (EMBED_DIM - 1))
    assert np.frombuffer(blob, dtype=np.float32)[0] == pytest.approx(1.0)


def test_get_db_is_shared_and_closed_on_shutdown(tmp_path: Path) -> None:
    services, _ = make_services(tmp_path)
    db = get_db(services)
    assert get_db(services) is db
    assert db.path == tmp_path / "studymate.db"
    services.shutdown()
    with db.read() as conn:  # a late caller still works (reconnect)
        assert conn.execute("SELECT 1").fetchone()[0] == 1
    db.close()


def test_iso_round_trip() -> None:
    now = utc_now()
    text = iso(now)
    assert text.endswith("Z") and len(text) == len("2026-01-01T00:00:00.000Z")
    assert abs((parse_iso(text) - now).total_seconds()) < 0.001
