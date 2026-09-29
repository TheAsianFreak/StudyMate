from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_db import KOREAN_FONT, make_pdf, make_services

from studymate.db import get_db
from studymate.errors import ModelMissingError, UserFacingError
from studymate.rag import store
from studymate.rag.importer import import_pdf
from studymate.rag.pdf import validate_pdf_path
from studymate.rag.retrieve import retrieve

ENGLISH_PAGES = [
    [
        "Chapter 1. Quadratic equations",
        "A quadratic equation ax^2 + bx + c = 0 is solved with the quadratic formula.",
        "The discriminant b^2 - 4ac tells how many real roots the equation has.",
    ],
    [
        "Chapter 2. The Pythagorean theorem",
        "In a right triangle the square of the hypotenuse equals the sum of the squares",
        "of the other two sides: a^2 + b^2 = c^2.",
    ],
    [
        "Chapter 3. Probability",
        "Rolling two dice gives 36 equally likely outcomes; the probability of a sum",
        "of seven is 6/36 = 1/6.",
    ],
    [],  # blank page, like a scanned image without a text layer
]


def _events() -> tuple[list[tuple[str, int, int]], Any]:
    events: list[tuple[str, int, int]] = []

    async def progress(stage: str, done: int, total: int) -> None:
        events.append((stage, done, total))

    return events, progress


def test_validate_pdf_path(tmp_path: Path) -> None:
    with pytest.raises(UserFacingError) as e:
        validate_pdf_path("relative/file.pdf", 10)
    assert e.value.code == "bad_path"
    with pytest.raises(UserFacingError) as e:
        validate_pdf_path(str(tmp_path / "notes.txt"), 10)
    assert e.value.code == "not_pdf"
    with pytest.raises(UserFacingError) as e:
        validate_pdf_path(str(tmp_path / "missing.pdf"), 10)
    assert e.value.code == "file_not_found"
    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"PK\x03\x04 this is a zip")
    with pytest.raises(UserFacingError) as e:
        validate_pdf_path(str(fake), 10)
    assert e.value.code == "not_pdf"
    real = make_pdf(tmp_path / "real.PDF", [["hello"]])
    assert validate_pdf_path(f'"{real}"', 10) == real
    with pytest.raises(UserFacingError) as e:
        validate_pdf_path(str(real), 0)
    assert e.value.code == "pdf_too_large"


async def test_import_retrieve_delete(tmp_path: Path) -> None:
    services, embedder = make_services(tmp_path)
    pdf = make_pdf(tmp_path / "math notes.pdf", ENGLISH_PAGES)
    events, progress = _events()

    doc = await import_pdf(services, str(pdf), progress)
    assert doc.title == "math notes"
    assert doc.pages == 4
    assert doc.chunks == 3
    assert doc.doc_id.startswith("d_")
    assert [e for e in events if e[0] == "extract"][-1] == ("extract", 4, 4)
    assert events[-1] == ("embed", 3, 3)
    assert [e[0] for e in events] == sorted((e[0] for e in events), key=["extract", "embed"].index)
    db = get_db(services)
    assert store.doc_empty_pages(db, doc.doc_id) == [4]
    assert store.list_docs(db) == [doc]

    hits = await retrieve(services, "hypotenuse of a right triangle", k=3)
    assert [h.page for h in hits][0] == 2
    assert hits[0].doc_id == doc.doc_id
    assert "hypotenuse" in hits[0].text
    assert hits[0].score > hits[-1].score
    assert all(-1.0 <= h.score <= 1.0 for h in hits)
    assert (await retrieve(services, "dice probability", k=1))[0].page == 3

    # re-importing the same file returns the existing document without embedding again
    calls = len(embedder.calls)
    again = await import_pdf(services, str(pdf))
    assert again == doc and len(embedder.calls) == calls

    # doc filter
    other = await import_pdf(
        services, str(make_pdf(tmp_path / "other.pdf", [["dice dice dice probability"]]))
    )
    only_first = await retrieve(services, "dice probability", doc_id=doc.doc_id, k=5)
    assert only_first and {h.doc_id for h in only_first} == {doc.doc_id}
    assert (await retrieve(services, "dice probability", k=1))[0].doc_id == other.doc_id
    assert await retrieve(services, "dice", doc_id="d_missing") == []

    assert store.delete_doc(db, doc.doc_id)
    assert await retrieve(services, "hypotenuse", doc_id=doc.doc_id) == []
    assert [d.doc_id for d in store.list_docs(db)] == [other.doc_id]
    services.shutdown()


@pytest.mark.skipif(not KOREAN_FONT.exists(), reason="needs a Korean TrueType font")
async def test_import_korean_pdf(tmp_path: Path) -> None:
    services, _ = make_services(tmp_path)
    pdf = make_pdf(
        tmp_path / "수학노트.pdf",
        [
            ["이차방정식의 근의 공식", "판별식 D = b² - 4ac 가 음수이면 실근이 없다."],
            ["피타고라스 정리", "직각삼각형에서 빗변의 제곱은 나머지 두 변의 제곱의 합과 같다."],
        ],
        KOREAN_FONT,
    )
    doc = await import_pdf(services, str(pdf))
    assert doc.title == "수학노트" and doc.pages == 2
    hits = await retrieve(services, "직각삼각형 빗변", k=2)
    assert hits[0].page == 2
    assert "빗변의 제곱은" in hits[0].text
    first = await retrieve(services, "판별식이 음수", k=1)
    assert first[0].page == 1 and "b² - 4ac" in first[0].text
    services.shutdown()


async def test_retrieve_is_empty_without_docs_or_model(tmp_path: Path) -> None:
    services, embedder = make_services(tmp_path)
    assert await retrieve(services, "anything") == []
    assert embedder.calls == []  # no docs -> the embed server is never started
    await import_pdf(services, str(make_pdf(tmp_path / "a.pdf", ENGLISH_PAGES[:1])))
    assert await retrieve(services, "   ") == []
    services.llama.available = lambda role: False  # type: ignore[method-assign]
    assert await retrieve(services, "quadratic") == []

    async def broken(texts: list[str]) -> list[list[float]]:
        raise UserFacingError("llm_request_failed", "x")

    services.llama.available = lambda role: True  # type: ignore[method-assign]
    services.llm.embed = broken  # type: ignore[method-assign]
    assert await retrieve(services, "quadratic") == []
    services.shutdown()


async def test_import_errors(tmp_path: Path) -> None:
    services, _ = make_services(tmp_path, embed=False)
    pdf = make_pdf(tmp_path / "a.pdf", ENGLISH_PAGES[:1])
    with pytest.raises(ModelMissingError):
        await import_pdf(services, str(pdf))
    services.shutdown()

    services, _ = make_services(tmp_path / "2")
    blank = make_pdf(tmp_path / "scan.pdf", [[], []])
    with pytest.raises(UserFacingError) as e:
        await import_pdf(services, str(blank))
    assert e.value.code == "pdf_no_text" and "스캔" in e.value.message
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.7\n garbage without objects")
    with pytest.raises(UserFacingError) as e:
        await import_pdf(services, str(broken))
    assert e.value.code == "pdf_invalid"

    async def bad_dims(texts: list[str]) -> list[list[float]]:
        return [[1.0, 2.0] for _ in texts]

    services.llm.embed = bad_dims  # type: ignore[method-assign]
    with pytest.raises(UserFacingError) as e:
        await import_pdf(services, str(pdf))
    assert e.value.code == "embed_failed"
    assert store.list_docs(get_db(services)) == []  # nothing half-stored
    services.shutdown()


def test_doc_handlers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    services, _ = make_services(tmp_path)
    monkeypatch.setattr("studymate.services._services", services)
    pdf = make_pdf(tmp_path / "notes.pdf", ENGLISH_PAGES)
    from studymate.main import app

    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "doc_import", "id": "i1", "path": str(pdf)})
        progress = []
        while True:
            msg = ws.receive_json()
            if msg["type"] != "doc_progress":
                break
            progress.append(msg)
        assert msg["type"] == "doc_imported" and msg["id"] == "i1"
        doc = msg["doc"]
        assert doc["pages"] == 4 and doc["chunks"] == 3
        assert {p["stage"] for p in progress} == {"extract", "embed"}
        assert all(p["id"] == "i1" for p in progress)

        ws.send_json({"type": "docs_get", "id": "g1"})
        docs = ws.receive_json()
        assert docs == {"type": "docs", "id": "g1", "docs": [doc]}

        ws.send_json({"type": "doc_import", "id": "i2", "path": str(tmp_path / "nope.pdf")})
        err = ws.receive_json()
        assert err["type"] == "error" and err["id"] == "i2" and err["code"] == "file_not_found"

        ws.send_json({"type": "doc_delete", "id": "d1", "doc_id": doc["doc_id"]})
        assert ws.receive_json() == {"type": "docs", "id": "d1", "docs": []}
