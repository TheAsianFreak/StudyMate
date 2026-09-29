"""Speech services wired into the process container (lazy, one instance each)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from studymate.config import Lang
from studymate.errors import ModelMissingError, UserFacingError
from studymate.protocol.backend import VoicePreset
from studymate.services import Services
from studymate.speech import dsp
from studymate.speech.presets import SPEAKERS, PresetStore, lang_of, speaker_of
from studymate.speech.stt import Transcriber
from studymate.speech.tts import MeloKorean, Synthesis, SynthOptions


class TtsEngine(Protocol):
    """MeloKorean (ko) or KokoroTts (ja/en)."""

    native_speed: bool

    def synthesize(
        self, text: str, *, speaker: str | None = None, speed: float = 1.0, seed: int | None = None
    ) -> Synthesis: ...


def preset_store(services: Services) -> PresetStore:
    s = services.settings
    return services.lazy(
        "voice_presets", lambda: PresetStore(s.data_dir / "voice-presets.json", s.tts.default_preset_ids)
    )


def cmudict_path(services: Services) -> Path | None:
    cmudict_id = services.settings.tts.cmudict_id
    if not services.registry.installed(cmudict_id):
        return None
    return services.registry.dir(cmudict_id) / "cmudict" / "cmudict"


def _optional_file(services: Services, model_id: str, relative: str) -> Path | None:
    if not services.registry.installed(model_id):
        return None
    path = services.registry.models_dir / relative
    return path if path.exists() else None


async def tts_engine(services: Services, lang: Lang = "ko") -> TtsEngine:
    cfg = services.settings.tts
    if not all(services.registry.installed(m) for m in cfg.model_ids(lang)):
        raise ModelMissingError("음성 합성(TTS)")
    if lang == "ko":
        return await _melo(services)
    return await _kokoro(services, lang)


async def _melo(services: Services) -> MeloKorean:
    cfg = services.settings.tts

    def build() -> MeloKorean:
        options = SynthOptions(
            sdp_ratio=cfg.sdp_ratio,
            noise_scale=cfg.noise_scale,
            noise_scale_w=cfg.noise_scale_w,
            length_scale=cfg.length_scale,
            sentence_pause_ms=cfg.sentence_pause_ms,
            max_piece_chars=cfg.max_piece_chars,
        )
        return MeloKorean(
            services.registry.dir(cfg.model_id),
            cmudict_path=cmudict_path(services),
            options=options,
            threads=cfg.threads,
        )

    return await services.lazy_async("tts", build)


async def _kokoro(services: Services, lang: Lang) -> TtsEngine:
    from studymate.speech.kokoro_tts import Frontend, KokoroModel, KokoroOptions, KokoroTts

    cfg = services.settings.tts
    reg = services.registry
    model = await services.lazy_async(
        "kokoro", lambda: KokoroModel(reg.dir(cfg.kokoro_model_id), threads=cfg.threads)
    )

    def frontend_for(speaker: str) -> Frontend:
        """Built on first use in the synthesis worker thread (spaCy/OpenJTalk load)."""
        if lang == "ja":
            from studymate.speech.japanese import JapaneseFrontend

            return services.lazy("g2p:ja", JapaneseFrontend)
        from studymate.speech.english import EnglishFrontend

        british = speaker.startswith("b")  # bf_* voices were trained on British phonemes
        spacy_dir = next((reg.dir(cfg.spacy_en_id) / "en_core_web_sm").glob("en_core_web_sm-*"))
        oov = _optional_file(services, cfg.g2p_oov_id, "tts/g2p-en/g2p_en/checkpoint20.npz")
        return services.lazy(
            f"g2p:en-{'gb' if british else 'us'}",
            lambda: EnglishFrontend(
                spacy_dir, british=british, cmudict=cmudict_path(services), oov_checkpoint=oov
            ),
        )

    options = KokoroOptions(max_phonemes=cfg.kokoro_max_phonemes, chunk_pause_ms=cfg.kokoro_chunk_pause_ms)
    voices_dir = reg.dir(cfg.kokoro_voices_ids[lang])
    return services.lazy(
        f"tts:{lang}", lambda: KokoroTts(model, voices_dir, SPEAKERS[lang], frontend_for, options)
    )


def stt_model_id(services: Services) -> str:
    model_id = services.registry.pick(services.tier, "stt")
    if model_id is None:
        raise ModelMissingError("음성 인식(STT)")
    return model_id


def partial_model_id(services: Services) -> str | None:
    wanted = services.settings.stt.partial_model
    return wanted if wanted and services.registry.installed(wanted) else None


def stt_language(services: Services) -> str:
    """Whisper decodes in the app language unless config pins one."""
    return services.settings.stt.language or services.lang


async def transcriber(services: Services, model_id: str) -> Transcriber:
    cfg = services.settings.stt

    def build() -> Transcriber:
        return Transcriber(
            services.registry.dir(model_id),
            device=cfg.device,
            compute_type=cfg.compute_type,
            cpu_threads=cfg.cpu_threads,
            language=cfg.language,
            beam_size=cfg.beam_size,
        )

    return await services.lazy_async(f"stt:{model_id}", build)


def resolve_preset(
    store: PresetStore, lang: Lang, preset: VoicePreset | None, voice: str | None
) -> VoicePreset:
    """The preset a tts_request speaks with. An inline `preset` (editor preview) is used
    as is; a saved `voice` of another language, or an unknown one, falls back to the
    current language's default so stale shell settings never read text in the wrong
    language."""
    if preset is not None:
        return preset
    if voice:
        found = store.get(voice)
        if found is not None and lang_of(found) == lang:
            return found
    return store.default(lang)


def render_tts(engine: TtsEngine, text: str, preset: VoicePreset, out_rate: int) -> dict[str, Any]:
    """Blocking: synthesis + voice chain -> `tts_audio` fields (without type/id)."""
    speaker = speaker_of(preset)
    if engine.native_speed:
        # Kokoro scales its predicted durations: cleaner than time-stretching afterwards.
        synthesis = engine.synthesize(text, speaker=speaker, speed=preset.speed)
        chain = preset.model_copy(update={"speed": 1.0})
    else:
        synthesis = engine.synthesize(text, speaker=speaker)
        chain = preset
    out = dsp.process(synthesis.audio, synthesis.sample_rate, chain, synthesis.phonemes, out_rate)
    phonemes: list[dict[str, Any]] = []
    for (char, start, end), vowel in zip(out.timings, out.vowels, strict=True):
        item: dict[str, Any] = {"char": char, "start_ms": round(start, 1), "end_ms": round(end, 1)}
        if vowel is not None:
            item["vowel"] = vowel
        phonemes.append(item)
    return {
        "wav_base64": dsp.wav_base64(out.audio, out.sample_rate),
        "sample_rate": out.sample_rate,
        "duration_ms": round(out.duration_ms, 1),
        "phonemes": phonemes,
    }


def check_text(services: Services, text: str) -> str:
    text = text.strip()
    if len(text) > services.settings.tts.max_text_chars:
        raise UserFacingError("text_too_long", "읽을 문장이 너무 길어요. 나눠서 요청해 주세요.")
    return text
