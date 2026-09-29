from __future__ import annotations

import base64
import io
import socket
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

from studymate.config import get_settings
from studymate.errors import ModelMissingError, UserFacingError
from studymate.system.registry import ModelRegistry
from studymate.vision import reader
from studymate.vision.reader import Problem, board_latex, decode_image, guess_subject, read_problem


def _png_b64(color: str = "white", size: tuple[int, int] = (120, 40)) -> str:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


class FakeLLM:
    def __init__(self, out: dict[str, Any] | Exception) -> None:
        self.out = out
        self.calls: list[dict[str, Any]] = []

    async def chat_json(
        self, messages: list[dict[str, Any]], schema: dict[str, Any], **kw: Any
    ) -> dict[str, Any]:
        self.calls.append({"messages": messages, "schema": schema, **kw})
        if isinstance(self.out, Exception):
            raise self.out
        return self.out


def _services(*, vision: bool, llm: FakeLLM, ocr_installed: bool = True) -> Any:
    settings = get_settings()
    registry = SimpleNamespace(installed=lambda model_id: ocr_installed)
    return SimpleNamespace(
        settings=settings, llm=llm, llama=SimpleNamespace(available=lambda role: vision), registry=registry
    )


@pytest.fixture
def fake_ocr(monkeypatch: pytest.MonkeyPatch) -> list[Image.Image]:
    seen: list[Image.Image] = []

    async def read_ocr(services: Any, img: Image.Image) -> Problem:
        seen.append(img)
        return Problem("다음 방정식을 푸시오.\n2x + 3 = 7", "2x + 3 = 7", "수학", "ocr")

    monkeypatch.setattr(reader, "_read_ocr", read_ocr)
    return seen


async def test_vision_tier_uses_qwen_vl(fake_ocr: list[Image.Image]) -> None:
    llm = FakeLLM(
        {
            "problem_text": "방정식 \\frac{x}{2}=4를 푸시오.",
            "problem_latex": "\\frac{x}{2}=4",
            "subject": "수학",
        }
    )
    problem = await read_problem(_services(vision=True, llm=llm), _png_b64())
    assert problem.source == "vision" and problem.latex == "\\frac{x}{2}=4" and problem.subject == "수학"
    call = llm.calls[0]
    assert call["role"] == "vision"
    assert call["schema"]["required"] == ["problem_text", "problem_latex", "subject"]
    content = call["messages"][0]["content"]
    assert content[0]["type"] == "image_url" and content[0]["image_url"]["url"].startswith(
        "data:image/png;base64,"
    )
    assert not fake_ocr


async def test_lite_tier_uses_ocr(fake_ocr: list[Image.Image]) -> None:
    llm = FakeLLM(AssertionError("VL must not be called"))
    problem = await read_problem(_services(vision=False, llm=llm), _png_b64())
    assert problem.source == "ocr" and len(fake_ocr) == 1
    assert not llm.calls


async def test_vl_failure_falls_back_to_ocr(fake_ocr: list[Image.Image]) -> None:
    llm = FakeLLM(UserFacingError("llm_start_failed", "x"))
    problem = await read_problem(_services(vision=True, llm=llm), _png_b64())
    assert problem.source == "ocr" and llm.calls


async def test_lite_tier_without_ocr_models_reports_missing_model() -> None:
    llm = FakeLLM(AssertionError("no VL"))
    with pytest.raises(ModelMissingError):
        await read_problem(_services(vision=False, llm=llm, ocr_installed=False), _png_b64())


def test_decode_image_rejects_garbage_and_flattens_alpha() -> None:
    with pytest.raises(UserFacingError):
        decode_image("not an image", 10_000_000)
    with pytest.raises(UserFacingError):
        decode_image(_png_b64(size=(4, 4)), 10_000_000)
    with pytest.raises(UserFacingError):
        decode_image(_png_b64(), 10)
    buf = io.BytesIO()
    Image.new("RGBA", (50, 20), (0, 0, 0, 0)).save(buf, format="PNG")
    img = decode_image("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), 10_000_000)
    assert img.mode == "RGB" and img.getpixel((0, 0)) == (255, 255, 255)


@pytest.mark.parametrize(
    ("text", "subject"),
    [
        ("다음 방정식을 푸시오. 2x + 3 = 7", "수학"),
        ("\\frac{1}{2} + \\frac{1}{3}을 계산하시오.", "수학"),
        ("광합성이 일어나는 세포 소기관은?", "과학"),
        ("조선을 건국한 왕은 누구인가?", "사회"),
        ("다음 시에서 화자의 정서로 알맞은 것은?", "국어"),
        ("Choose the word that best completes the sentence: She ___ to school every day.", "영어"),
    ],
)
def test_guess_subject(text: str, subject: str) -> None:
    assert guess_subject(text) == subject
    assert guess_subject(text, "과학 시간") == "과학"


def test_board_latex_prefers_math_lines() -> None:
    assert board_latex("다음 연립방정식을 푸시오.\nx + y = 5\nx - y = 1") == "x + y = 5, \\quad x - y = 1"
    assert board_latex("방정식 3(x-2) = 2x+5의 해").startswith("\\text{방정식}")
    assert board_latex("광합성이란?") == "\\text{광합성이란?}"


def _ocr_models_installed() -> bool:
    reg = ModelRegistry(get_settings())
    return reg.installed("ocr-korean-rec") and reg.installed("ocr-pix2tex")


@pytest.mark.skipif(not _ocr_models_installed(), reason="OCR models not downloaded")
def test_real_ocr_reads_rendered_problem_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """RapidOCR + pix2tex read a stacked fraction without any network access."""
    from eval.render import render_problem
    from studymate.verify import verify_answer
    from studymate.vision.mathocr import MathOcr
    from studymate.vision.ocr import TextOcr, read_image

    def no_network(*a: Any, **k: Any) -> Any:
        raise AssertionError("network access during OCR")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    reg = ModelRegistry(get_settings())
    text_ocr = TextOcr(reg.path("ocr-korean-rec"), 0.5)
    math_ocr = MathOcr(reg.path("ocr-pix2tex"), reg.path("ocr-pix2tex", 1))
    img = render_problem("다음 방정식을 푸시오.\n$\\frac{x-1}{2} = \\frac{x+2}{3}$")
    lines = read_image(img, text_ocr, math_ocr)
    assert "방정식" in lines[0]
    assert verify_answer("\n".join(lines), "x = 7").verified, lines


def test_ocr_engines_consistency_check() -> None:
    from studymate.vision.ocr import _consistent, _parses_fragment

    # line OCR may miss isolated glyphs, but pix2tex must not drop what it saw
    assert _consistent(r"\frac{x-1}{2} = \frac{x+2}{3}", "x - 1 x+2 2 3")
    assert _consistent("4x+9 =", "4x + =")
    assert not _consistent(r"x \cdot y = 1", "x - y = 1")  # '-' read as a dot
    assert not _consistent(r"x - \frac{x-1}{3} = 2", "x - x - 1 3 = 3")
    assert not _consistent("x = 1", "")
    assert _parses_fragment(r"-\ 2)\ =\ 2x\ +")
    assert _parses_fragment("4x + 9 =")
    assert not _parses_fragment(r"\frac{{\mathcal A}}{2}")
    assert not _parses_fragment("+ =")
