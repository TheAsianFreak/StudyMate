"""PDF validation and per-page text extraction (pypdfium2; no OCR)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from studymate.errors import UserFacingError

_HEADER_SCAN = 1024  # the spec allows junk before %PDF- within the first KiB


def validate_pdf_path(raw_path: str, max_mb: int) -> Path:
    """Checks that `raw_path` is an absolute path to a readable PDF file."""
    path = Path(raw_path.strip().strip('"'))
    if not path.is_absolute():
        raise UserFacingError("bad_path", "PDF 파일의 전체 경로가 필요합니다.")
    if path.suffix.lower() != ".pdf":
        raise UserFacingError("not_pdf", "PDF 파일만 가져올 수 있습니다.")
    try:
        if not path.is_file():
            raise UserFacingError("file_not_found", "파일을 찾을 수 없습니다.")
        size = path.stat().st_size
        with path.open("rb") as f:
            head = f.read(_HEADER_SCAN)
    except OSError as exc:
        raise UserFacingError("file_unreadable", "파일을 읽을 수 없습니다.") from exc
    if b"%PDF-" not in head:
        raise UserFacingError("not_pdf", "PDF 파일이 아니거나 손상되었습니다.")
    if size > max_mb * 1024 * 1024:
        raise UserFacingError(
            "pdf_too_large", f"PDF가 너무 큽니다. {max_mb}MB 이하의 파일만 가져올 수 있습니다."
        )
    return path


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def extract_pages(path: Path, on_page: Callable[[int, int], None] | None = None) -> list[str]:
    """Raw text of every page (index 0 = page 1). Pages without a text layer yield ""."""
    try:
        pdf = pdfium.PdfDocument(path)
    except pdfium.PdfiumError as exc:
        if exc.err_code == pdfium_c.FPDF_ERR_PASSWORD:
            raise UserFacingError("pdf_encrypted", "암호가 걸린 PDF는 가져올 수 없습니다.") from exc
        raise UserFacingError("pdf_invalid", "PDF를 열 수 없습니다. 파일이 손상되었을 수 있습니다.") from exc
    try:
        total = len(pdf)
        pages: list[str] = []
        for index in range(total):
            pages.append(_page_text(pdf, index))
            if on_page is not None:
                on_page(index + 1, total)
        return pages
    finally:
        pdf.close()


def _page_text(pdf: pdfium.PdfDocument, index: int) -> str:
    try:
        page = pdf[index]
    except pdfium.PdfiumError:
        return ""  # one broken page should not fail the whole import
    try:
        textpage = page.get_textpage()
        try:
            return str(textpage.get_text_range(errors="replace"))
        finally:
            textpage.close()
    except pdfium.PdfiumError:
        return ""
    finally:
        page.close()
