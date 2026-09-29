"""Voice presets: built-in voice types per language plus user presets in the data dir.

All built-in voices are female (product decision). Korean types are post-processing of
the single MeloTTS Korean speaker; Japanese and English types use distinct native Kokoro
speakers with light post-processing. A preset's `lang` (ko when omitted) picks the TTS
engine and its `speaker` the base voice (the language's first speaker when omitted).
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from studymate.config import Lang
from studymate.errors import UserFacingError
from studymate.protocol.backend import VoicePreset
from studymate.speech.tts import SPEAKER_NAME as KO_SPEAKER
from studymate.storage import JsonStore

LANGS: tuple[Lang, ...] = ("ko", "ja", "en")

# Base voices per language; the first is the default. Kokoro ids are its voice file names
# (all female: jf_* Japanese, af_* American and bf_* British English).
SPEAKERS: dict[Lang, tuple[str, ...]] = {
    "ko": (KO_SPEAKER,),
    "ja": ("jf_alpha", "jf_nezumi", "jf_tebukuro", "jf_gongitsune"),
    "en": ("af_bella", "af_heart", "af_sarah", "bf_emma"),
}


def _p(lang: Lang, speaker: str, preset_id: str, name: str, **values: float) -> VoicePreset:
    return VoicePreset(
        preset_id=preset_id,
        name=name,
        gender="female",
        builtin=True,
        lang=lang,
        speaker=speaker,
        **values,
    )


# Median f0 of the base voices (Hz, teacher lines): melo_kr ~216; jf_alpha 264, jf_nezumi 238,
# jf_tebukuro 333, jf_gongitsune 228; af_bella 202, af_heart 199, af_sarah 186, bf_emma 183.
# ja/en presets avoid pitch/formant changes where the speaker already fits the type, so
# WORLD re-synthesis only runs for the "cute" English and "mature" Japanese types.
BUILTIN_PRESETS: tuple[VoicePreset, ...] = (
    _p("ko", KO_SPEAKER, "female_bright", "밝은 여성", pitch_semitones=1.0, formant_ratio=1.05, speed=1.05,
       brightness_db=2.0, warmth_db=0.0, reverb=0.05, volume_db=0.0),
    _p("ko", KO_SPEAKER, "female_calm", "차분한 여성", pitch_semitones=-1.5, formant_ratio=0.98, speed=0.95,
       brightness_db=-1.0, warmth_db=2.0, reverb=0.08, volume_db=0.0),
    _p("ko", KO_SPEAKER, "female_girl", "발랄한 소녀", pitch_semitones=3.5, formant_ratio=1.12, speed=1.08,
       brightness_db=3.0, warmth_db=-1.0, reverb=0.03, volume_db=0.0),
    _p("ja", "jf_alpha", "ja_bright", "明るい女性", pitch_semitones=0.0, formant_ratio=1.0, speed=1.0,
       brightness_db=1.5, warmth_db=0.0, reverb=0.04, volume_db=0.0),
    _p("ja", "jf_nezumi", "ja_calm", "落ち着いた女性", pitch_semitones=0.0, formant_ratio=1.0, speed=0.95,
       brightness_db=-0.5, warmth_db=1.5, reverb=0.06, volume_db=0.0),
    _p("ja", "jf_tebukuro", "ja_cute", "かわいい女の子", pitch_semitones=0.0, formant_ratio=1.0, speed=1.03,
       brightness_db=2.0, warmth_db=-0.5, reverb=0.03, volume_db=0.0),
    _p("ja", "jf_gongitsune", "ja_mature", "大人の女性", pitch_semitones=-1.0, formant_ratio=0.98, speed=0.95,
       brightness_db=-1.0, warmth_db=2.0, reverb=0.07, volume_db=0.0),
    _p("en", "af_bella", "en_bright", "Bright", pitch_semitones=0.0, formant_ratio=1.0, speed=1.0,
       brightness_db=1.5, warmth_db=0.0, reverb=0.04, volume_db=0.0),
    _p("en", "af_heart", "en_calm", "Calm", pitch_semitones=0.0, formant_ratio=1.0, speed=0.95,
       brightness_db=-0.5, warmth_db=1.5, reverb=0.06, volume_db=0.0),
    _p("en", "af_sarah", "en_cute", "Cute", pitch_semitones=3.0, formant_ratio=1.06, speed=1.03,
       brightness_db=2.0, warmth_db=-0.5, reverb=0.03, volume_db=0.0),
    _p("en", "bf_emma", "en_mature", "Mature", pitch_semitones=0.0, formant_ratio=1.0, speed=0.97,
       brightness_db=-1.0, warmth_db=2.0, reverb=0.07, volume_db=0.0),
)  # fmt: skip
BUILTIN_IDS = frozenset(p.preset_id for p in BUILTIN_PRESETS)

MAX_USER_PRESETS = 100


def lang_of(preset: VoicePreset) -> Lang:
    return preset.lang or "ko"


def speaker_of(preset: VoicePreset) -> str:
    """The preset's base voice, or its language's default when unset/unknown."""
    speakers = SPEAKERS[lang_of(preset)]
    return preset.speaker if preset.speaker in speakers else speakers[0]


def _canonical(preset: VoicePreset) -> VoicePreset:
    """Explicit lang/speaker so a client echoing a built-in without them still matches."""
    return preset.model_copy(update={"builtin": True, "lang": lang_of(preset), "speaker": speaker_of(preset)})


class PresetStore:
    """User presets in `voice-presets.json`:
    {"presets": [...], "default_preset_ids": {"ko": ..., "ja": ..., "en": ...}}.
    The pre-multilingual `default_preset_id` key is read as the Korean default."""

    def __init__(self, path: Path, fallback_defaults: Mapping[str, str]) -> None:
        self._store = JsonStore(path)
        self._lock = threading.Lock()
        self._fallback: dict[str, str] = {}
        for lang in LANGS:
            wanted = fallback_defaults.get(lang)
            builtin = next((p for p in BUILTIN_PRESETS if p.preset_id == wanted and lang_of(p) == lang), None)
            first = next(p for p in BUILTIN_PRESETS if lang_of(p) == lang)
            self._fallback[lang] = (builtin or first).preset_id

    def _user_presets(self, data: dict[str, Any]) -> list[VoicePreset]:
        out: list[VoicePreset] = []
        for raw in data.get("presets", []):
            try:
                preset = VoicePreset.model_validate({**raw, "builtin": False})
            except (ValidationError, TypeError):
                continue  # skip a corrupted entry rather than losing every preset
            if preset.preset_id not in BUILTIN_IDS:
                out.append(preset)
        return out

    def presets(self) -> list[VoicePreset]:
        """Every preset of every language (the shell shows the current language's)."""
        return [*BUILTIN_PRESETS, *self._user_presets(self._store.load())]

    def get(self, preset_id: str) -> VoicePreset | None:
        return next((p for p in self.presets() if p.preset_id == preset_id), None)

    def default_id(self, lang: Lang = "ko") -> str:
        data = self._store.load()
        chosen = data.get("default_preset_ids")
        wanted = chosen.get(lang) if isinstance(chosen, dict) else None
        if wanted is None and lang == "ko":
            wanted = data.get("default_preset_id")  # legacy single default (all Korean)
        langs = {p.preset_id: lang_of(p) for p in [*BUILTIN_PRESETS, *self._user_presets(data)]}
        # a removed preset (e.g. the former male built-ins) falls back to the language default
        return wanted if isinstance(wanted, str) and langs.get(wanted) == lang else self._fallback[lang]

    def default(self, lang: Lang = "ko") -> VoicePreset:
        preset = self.get(self.default_id(lang))
        assert preset is not None
        return preset

    def save(self, preset: VoicePreset, make_default: bool = False) -> None:
        """Adds or replaces a user preset. A built-in id is accepted only unchanged (so a
        client can make a built-in the default); edited built-ins must be saved as copies."""
        with self._lock:
            data = self._store.load()
            users = self._user_presets(data)
            if preset.preset_id in BUILTIN_IDS:
                builtin = next(p for p in BUILTIN_PRESETS if p.preset_id == preset.preset_id)
                if _canonical(preset) != builtin:
                    raise UserFacingError(
                        "builtin_preset", "기본 목소리는 바꿀 수 없어요. 새 이름으로 복제해서 저장해 주세요."
                    )
            else:
                if not preset.preset_id.strip() or not preset.name.strip():
                    raise UserFacingError("invalid_preset", "목소리 이름을 입력해 주세요.")
                if preset.speaker is not None and preset.speaker not in SPEAKERS[lang_of(preset)]:
                    raise UserFacingError("unknown_speaker", "이 언어에 없는 목소리 종류예요.")
                stored = preset.model_copy(update={"builtin": False})
                replaced = [p for p in users if p.preset_id != stored.preset_id]
                if len(replaced) >= MAX_USER_PRESETS:
                    raise UserFacingError("too_many_presets", "저장할 수 있는 목소리 개수를 넘었어요.")
                users = (
                    [*replaced, stored]
                    if len(replaced) == len(users)
                    else [stored if p.preset_id == stored.preset_id else p for p in users]
                )
            data["presets"] = [p.model_dump(exclude_none=True) for p in users]
            if make_default:
                defaults = self._defaults(data)
                defaults[lang_of(preset)] = preset.preset_id
                data["default_preset_ids"] = defaults
            self._store.save(data)

    def delete(self, preset_id: str) -> None:
        if preset_id in BUILTIN_IDS:
            raise UserFacingError("builtin_preset", "기본 목소리는 삭제할 수 없어요.")
        with self._lock:
            data = self._store.load()
            users = self._user_presets(data)
            kept = [p for p in users if p.preset_id != preset_id]
            if len(kept) == len(users):
                raise UserFacingError("unknown_preset", "목소리 프리셋을 찾을 수 없어요.")
            data["presets"] = [p.model_dump(exclude_none=True) for p in kept]
            data["default_preset_ids"] = {k: v for k, v in self._defaults(data).items() if v != preset_id}
            self._store.save(data)

    @staticmethod
    def _defaults(data: dict[str, Any]) -> dict[str, str]:
        """Per-language defaults, folding in (and dropping) the legacy single key."""
        chosen = data.get("default_preset_ids")
        defaults = {k: v for k, v in chosen.items() if isinstance(v, str)} if isinstance(chosen, dict) else {}
        legacy = data.pop("default_preset_id", None)
        if isinstance(legacy, str):
            defaults.setdefault("ko", legacy)
        return defaults
