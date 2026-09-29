"""Japanese / English display titles for the model registry (models.json holds Korean)."""

from __future__ import annotations

from studymate.i18n import lang

_TITLES: dict[str, tuple[str, str]] = {
    "llama-runtime-vulkan": ("llama.cpp サーバー（Vulkan）", "llama.cpp server (Vulkan)"),
    "llama-runtime-cpu": ("llama.cpp サーバー（CPU）", "llama.cpp server (CPU)"),
    "bge-m3": ("bge-m3 埋め込み（Q8_0）", "bge-m3 embeddings (Q8_0)"),
    "melo-korean": ("MeloTTS 韓国語", "MeloTTS Korean"),
    "g2p-cmudict": ("英語発音辞書（CMUdict）", "English pronunciation dictionary (CMUdict)"),
    "kokoro-82m": ("Kokoro-82M 音声合成（日本語・英語）", "Kokoro-82M speech synthesis (Japanese, English)"),
    "kokoro-voices-ja": ("Kokoro 日本語の声（女性4種）", "Kokoro Japanese voices (4 female)"),
    "kokoro-voices-en": ("Kokoro 英語の声（女性4種）", "Kokoro English voices (4 female)"),
    "g2p-en-oov": ("英語の未登録語の発音推定（g2p_en）", "English pronunciation guesser (g2p_en)"),
    "spacy-en-core-web-sm": (
        "英語の品詞解析（spaCy en_core_web_sm）",
        "English part-of-speech tagger (spaCy en_core_web_sm)",
    ),
    "ocr-korean-rec": (
        "PaddleOCR 韓国語認識（PP-OCRv5 mobile, ONNX）",
        "PaddleOCR Korean recognition (PP-OCRv5 mobile, ONNX)",
    ),
    "ocr-pix2tex": ("pix2tex 数式認識（v0.0.1）", "pix2tex formula recognition (v0.0.1)"),
}


def model_title(model_id: str, korean_title: str) -> str:
    """Title in the request language; model names without translation stay as they are."""
    current = lang()
    if current == "ko" or model_id not in _TITLES:
        return korean_title
    ja, en = _TITLES[model_id]
    return ja if current == "ja" else en
