import type { ModelInfo, Status, Tier, VoicePreset } from '@studymate/protocol';
import type { Lang } from '../../shared/i18n';

/** Download order: what makes the character useful soonest comes first. */
const CATEGORY_ORDER = ['runtime', 'tts', 'llm', 'embed', 'face', 'ocr', 'stt', 'vision'];

/**
 * Languages a model serves (e.g. a TTS voice). Absent (older backends) or empty = every
 * language.
 */
export function modelLangs(model: ModelInfo): readonly Lang[] | undefined {
  return model.langs && model.langs.length > 0 ? model.langs : undefined;
}

export function servesLang(model: ModelInfo, lang: Lang): boolean {
  return modelLangs(model)?.includes(lang) ?? true;
}

/** Models the tier needs for this language that are not installed yet, in download order. */
export function missingModels(models: ModelInfo[], tier: Tier, lang: Lang): ModelInfo[] {
  return models
    .filter((m) => !m.installed && (m.required || m.tiers.includes(tier)) && servesLang(m, lang))
    .sort((a, b) => CATEGORY_ORDER.indexOf(a.category) - CATEGORY_ORDER.indexOf(b.category));
}

export function missingForStatus(status: Status, lang: Lang): ModelInfo[] {
  return missingModels(status.models, status.tier, lang);
}

/** Language a voice preset speaks (presets without `lang` are Korean). */
export function presetLang(preset: VoicePreset): Lang {
  return preset.lang ?? 'ko';
}
