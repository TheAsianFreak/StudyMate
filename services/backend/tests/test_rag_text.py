from __future__ import annotations

import unicodedata

from studymate.rag.text import (
    chunk_document,
    chunk_page,
    clean_document,
    normalize_text,
    page_lines,
    paragraphs,
    split_sentences,
    strip_page_furniture,
)


def test_normalize_korean_and_width() -> None:
    decomposed = unicodedata.normalize("NFD", "이차방정식")
    assert decomposed != "이차방정식"
    assert normalize_text(decomposed) == "이차방정식"
    assert normalize_text("ＡＢＣ　１２３") == "ABC 123"
    assert normalize_text("근​의­ 공식﻿") == "근의 공식"
    assert normalize_text("a\r\nb\rc") == "a\nb\nc"
    assert normalize_text("ﬁnd “it”") == 'find "it"'


def test_letter_spaced_korean_is_joined() -> None:
    assert page_lines("이 차 방 정 식 의 근 의 공 식")[0] == "이차방정식의근의공식"
    normal = "이 두 수 중 큰 수는 무엇인가"
    assert page_lines(normal)[0] == normal


def test_page_numbers_and_repeated_headers_removed() -> None:
    pages = [["중학 수학 2학년", "본문 내용 페이지 " + str(i) + " 입니다.", f"- {i} -"] for i in range(1, 6)]
    cleaned = strip_page_furniture(pages)
    for i, lines in enumerate(cleaned, start=1):
        assert [line for line in lines if line] == [f"본문 내용 페이지 {i} 입니다."]


def test_paragraphs_join_layout_lines() -> None:
    lines = [
        "이차방정식 ax^2+bx+c=0의 근은 근의 공식을 이용하여 구할 수 있으며 이 공식은",
        "판별식의 부호에 따라 실근의 개수를 알려준다. 판별식이 양수이면 서로 다른 두",
        "실근을 가진다.",
        "",
        "1. 판별식이 0이면 중근을 가진다.",
        "2. 판별식이 음수이면 실근이 없다.",
    ]
    paras = paragraphs(lines)
    assert paras[0].startswith("이차방정식") and paras[0].endswith("실근을 가진다.")
    assert "이 공식은 판별식의" in paras[0]
    assert paras[1:] == ["1. 판별식이 0이면 중근을 가진다.", "2. 판별식이 음수이면 실근이 없다."]
    english = paragraphs(["The quadratic formula gives the solutions of every equa-", "tion of degree two."])
    assert english == ["The quadratic formula gives the solutions of every equation of degree two."]
    assert paragraphs(["pdfium marks soft hyphens like equa\x02", "tion"]) == [
        "pdfium marks soft hyphens like equation"
    ]


def test_split_sentences_keeps_decimals_and_quotes() -> None:
    assert split_sentences('원주율은 약 3.14이다. 그는 "좋아." 라고 했다! 끝') == [
        "원주율은 약 3.14이다.",
        '그는 "좋아."',
        "라고 했다!",
        "끝",
    ]


def test_chunk_page_limits_and_overlap() -> None:
    sentences = [f"문장 번호 {i}번은 청크 분할을 시험하기 위한 긴 한국어 문장입니다." for i in range(40)]
    para = " ".join(sentences)
    chunks = chunk_page([para], limit=200, overlap=60)
    assert len(chunks) > 5
    assert all(len(c) <= 200 for c in chunks)
    # every sentence survives, and consecutive chunks share the overlap sentence
    joined = " ".join(chunks)
    assert all(s in joined for s in sentences)
    for prev, nxt in zip(chunks, chunks[1:], strict=False):
        assert nxt.split(". ")[0].rstrip(".") in prev


def test_chunk_page_prefers_paragraph_boundaries_without_overlap() -> None:
    p1 = "가" * 130 + "."
    p2 = "나" * 50 + "."
    chunks = chunk_page([p1, p2], limit=200, overlap=60)
    assert chunks == [p1, p2]  # p1 is >= 60% of the limit, so p2 starts a new chunk
    short = chunk_page(["짧은 문단.", "두 번째 문단."], limit=200, overlap=60)
    assert short == ["짧은 문단.\n두 번째 문단."]


def test_chunk_page_hard_splits_long_sentence() -> None:
    long_sentence = " ".join(["단어"] * 300)
    chunks = chunk_page([long_sentence], limit=100, overlap=20)
    assert all(len(c) <= 100 for c in chunks)
    assert "".join(c.replace(" ", "") for c in chunks).count("단어") >= 300


def test_chunk_document_pages_and_small_chunks() -> None:
    pages = clean_document(
        [
            "제1장 방정식\n이차방정식의 근의 공식은 판별식과 함께 배운다. 판별식이 음수이면 실근이 없다.",
            "3",  # page number only
            "",  # blank / scanned page
            "피타고라스 정리는 직각삼각형에서 빗변의 제곱이 나머지 두 변의 제곱의 합과 같다는 정리이다.",
        ]
    )
    chunks = chunk_document(pages, limit=700, overlap=120, min_chars=20)
    assert [c.page for c in chunks] == [1, 4]
    assert [c.ord for c in chunks] == [0, 1]
    assert chunks[0].text.startswith("제1장 방정식")
