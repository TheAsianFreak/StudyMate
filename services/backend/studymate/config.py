"""Backend configuration. Every path and threshold lives here, overridable via
STUDYMATE_* environment variables (nested fields use `__`, e.g. STUDYMATE_DROWSY__FPS=10)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from studymate.i18n import Lang

__all__ = ["GpuUse", "Lang", "Settings", "Tier", "get_settings"]

Tier = Literal["lite", "standard", "pro", "max"]
# How much of the language model runs on the GPU (llm/server.py); the user picks it in settings
GpuUse = Literal["high", "balanced", "low"]

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _default_models_dir() -> Path:
    return _REPO_ROOT / "models"


def _default_data_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / ".config"
    return base / "StudyMate"


class LlamaConfig(BaseModel):
    runtime: Literal["auto", "vulkan", "cpu"] = "auto"
    base_port: int = 8790
    # Long reading passages (국어 비문학, 영어 지문) + a full lesson need ~12k tokens; the KV cache
    # is q8_0 (llm/server.py) so 16k stays around 1.2 GB.
    chat_ctx: int = 16384
    vision_ctx: int = 12288
    embed_ctx: int = 8192
    gpu_layers: int = 999
    # GPU memory beyond the weights (context, compute buffers), measured on an RTX 5080:
    # 14B chat 16k +1.1 GB, Qwen2.5-VL with a 1920px screenshot +1.5 GB, bge-m3 below its file.
    # A model that does not fit next to the running ones stops the least recently used.
    vram_overhead_mib: dict[str, int] = {"chat": 1024, "vision": 1536, "embed": 0}
    vram_margin_mib: int = 512  # kept free below what other apps left at the first start
    # Qwen3 reasoning (thinking) tokens per request before it must answer (solve.think)
    reasoning_budget: int = 6144
    threads: int | None = None
    startup_timeout_s: float = 180.0
    idle_unload_s: float = 600.0
    request_timeout_s: float = 300.0


class TierModels(BaseModel):
    """Model ids from system/models.json used by each tier (first installed wins)."""

    llm: list[str]
    vision: list[str]
    stt: list[str]
    embed: list[str] = ["bge-m3"]


class SolveConfig(BaseModel):
    max_attempts: int = 3
    temperature: float = 0.2
    max_tokens: int = 3072  # a full lesson: intro, concept, up to 8 working lines, check, summary
    analysis_max_tokens: int = 1536  # extra budget for the hidden scratch field (CSAT-level problems)
    # DRY repetition penalty for lesson generation: stops a scratch field from looping
    # ("\text{ }\text{ }…") without a tight length cap. Mild so repeated LaTeX stays possible.
    dry_multiplier: float = 0.3
    dry_allowed_length: int = 4
    dry_penalty_last_n: int = 1024
    resolve_temperature: float = 0.3  # independent re-solve used for confidence "medium"
    # Reasoning (thinking) pass before the lesson: "math" = high-school / CSAT math units,
    # "all" = every advanced unit (reading passages too, slower), "off". GPU only: on the CPU
    # thousands of reasoning tokens take minutes.
    think: Literal["off", "math", "all"] = "math"
    think_max_tokens: int = 8192  # reasoning (reasoning_budget) + the outline and answer
    think_temperature: float = 0.6  # Qwen3's recommendation for thinking mode
    vision_max_tokens: int = 3072  # a whole reading passage transcribed
    vision_max_side: int = 1920  # screenshots are downscaled to this before Qwen2.5-VL (small passage text)
    max_image_bytes: int = 12_000_000
    ocr_rec_model: str = "ocr-korean-rec"  # models.json ids; det/cls come with the rapidocr wheel
    math_ocr_model: str = "ocr-pix2tex"
    ocr_text_score: float = 0.5
    ask_max_tokens: int = 1024
    ask_retrieve_k: int = 4
    ask_history_chars: int = 600  # per history turn sent to the LLM


class QuizConfig(BaseModel):
    max_attempts: int = 3
    temperature: float = 0.7
    retrieve_k: int = 6
    max_tokens: int = 1536


class TtsConfig(BaseModel):
    sample_rate: int = 44100
    # Built-in preset used when the user hasn't picked one for the language.
    default_preset_ids: dict[str, str] = {"ko": "female_bright", "ja": "ja_bright", "en": "en_bright"}
    use_bert: bool = False  # kykim/bert-kor-base needs a commercial MOU; off by default
    # ko: MeloTTS Korean (models.json ids)
    model_id: str = "melo-korean"
    cmudict_id: str = "g2p-cmudict"  # optional: English words -> Hangul (ko), OOV names (en)
    threads: int | None = None  # torch intra-op threads; None = torch default
    sdp_ratio: float = 0.2
    noise_scale: float = 0.6
    noise_scale_w: float = 0.8
    length_scale: float = 1.0  # model-side tempo; presets change speed after synthesis
    sentence_pause_ms: int = 80
    max_piece_chars: int = 120
    max_text_chars: int = 2000
    # ja/en: Kokoro-82M, one weight file plus per-language voice files
    kokoro_model_id: str = "kokoro-82m"
    kokoro_voices_ids: dict[str, str] = {"ja": "kokoro-voices-ja", "en": "kokoro-voices-en"}
    spacy_en_id: str = "spacy-en-core-web-sm"  # English POS tagger for misaki's lexicons
    g2p_oov_id: str = "g2p-en-oov"  # optional: English words no lexicon knows
    kokoro_max_phonemes: int = 300  # per model call; the model is weak on very short inputs
    kokoro_chunk_pause_ms: int = 60

    def model_ids(self, lang: str) -> list[str]:
        """Models that must be installed to speak `lang` (optional helpers excluded)."""
        if lang == "ko":
            return [self.model_id]
        ids = [self.kokoro_model_id, self.kokoro_voices_ids[lang]]
        return [*ids, self.spacy_en_id] if lang == "en" else ids


class SttConfig(BaseModel):
    sample_rate: int = 16000
    max_record_s: float = 30.0
    vad_silence_ms: int = 900
    language: str | None = None  # None = follow the app language (Services.lang)
    compute_type: str = "int8"
    device: str = "cpu"
    cpu_threads: int = 0  # 0 = CTranslate2 default
    beam_size: int = 5
    vad_threshold: float = 0.5
    no_speech_timeout_s: float = 8.0  # give up when nothing was said after starting
    partial_interval_s: float = 1.5
    partial_model: str | None = "whisper-small"  # None disables stt_partial
    level_interval_s: float = 0.1


class DrowsyConfig(BaseModel):
    fps: float = 12.0
    calibration_s: float = 5.0
    ear_closed_ratio: float = 0.70
    perclos_window_s: float = 30.0
    perclos_threshold: float = 0.40
    pitch_drop_deg: float = 15.0
    pitch_drops_required: int = 2
    activity_hold_s: float = 10.0
    candidate_hold_s: float = 5.0
    sensitivity_scale: dict[str, float] = {"low": 1.25, "normal": 1.0, "high": 0.8}
    # Details used by studymate/drowsy (see detector.py for the exact rules).
    frame_width: int = 640
    frame_height: int = 480
    min_face_confidence: float = 0.5
    camera_fail_s: float = 3.0  # consecutive read failures before "camera lost"
    no_face_s: float = 3.0
    state_interval_s: float = 0.5  # periodic drowsy_state / calibration progress (~2 Hz)
    perclos_min_coverage: float = 0.5  # fraction of the window with face data before judging
    perclos_release_ratio: float = 0.75  # candidate/drowsy -> normal below threshold * ratio
    pitch_baseline_s: float = 60.0  # rolling median window for the upright head pitch
    pitch_drop_window_s: float = 60.0  # "repeated" pitch drops are counted over this window
    ear_pitch_comp_per_deg: float = 0.008  # closed-eye ratio lowered per degree looking down
    ear_pitch_comp_max: float = 0.2
    min_baseline_ear: float = 0.12
    record_trace: bool = False  # opt-in numeric trace (t, ear, pitch, face) for tuning; no images
    trace_dir: Path | None = None  # default: <data_dir>/drowsy-traces


class RagConfig(BaseModel):
    chunk_chars: int = 700
    chunk_overlap: int = 120
    embed_batch: int = 16
    min_chunk_chars: int = 20  # shorter chunks (page numbers, lone headings) are dropped
    min_page_chars: int = 10  # a page with fewer text chars counts as having no text layer
    max_pdf_mb: int = 300


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STUDYMATE_", env_nested_delimiter="__")

    host: str = "127.0.0.1"
    port: int = 8765
    models_dir: Path = Field(default_factory=_default_models_dir)
    data_dir: Path = Field(default_factory=_default_data_dir)
    tier: Tier | None = None  # None = hardware recommendation or saved choice
    lang: Lang = "ko"  # until the shell says otherwise (hello / set_language), then saved

    llama: LlamaConfig = LlamaConfig()
    tiers: dict[str, TierModels] = {
        "lite": TierModels(llm=["qwen3-4b", "qwen3-8b"], vision=[], stt=["whisper-small", "whisper-medium"]),
        "standard": TierModels(
            llm=["qwen3-8b", "qwen3-4b"], vision=["qwen2.5-vl-7b"], stt=["whisper-medium", "whisper-small"]
        ),
        "pro": TierModels(
            llm=["qwen3-8b", "qwen3-4b"],
            vision=["qwen2.5-vl-7b"],
            stt=["whisper-large-v3", "whisper-medium", "whisper-small"],
        ),
        "max": TierModels(
            llm=["qwen3-14b", "qwen3-8b", "qwen3-4b"],
            vision=["qwen2.5-vl-7b"],
            stt=["whisper-large-v3", "whisper-medium", "whisper-small"],
        ),
    }
    solve: SolveConfig = SolveConfig()
    quiz: QuizConfig = QuizConfig()
    tts: TtsConfig = TtsConfig()
    stt: SttConfig = SttConfig()
    drowsy: DrowsyConfig = DrowsyConfig()
    rag: RagConfig = RagConfig()

    @property
    def db_path(self) -> Path:
        return self.data_dir / "studymate.db"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    # No network at runtime (CLAUDE.md rule 7): stop libraries from phoning home.
    # g2pkk would fetch NLTK cmudict at import time, albumentations checks PyPI for updates,
    # Hugging Face / transformers would try the hub.
    os.environ.setdefault("NLTK_DATA", str(s.models_dir / "nltk_data"))
    os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    return s
