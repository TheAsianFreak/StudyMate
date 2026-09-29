import type { PhonemeTiming } from '@studymate/protocol';

/** Mouth shape weights sent to Godot as `viseme`. */
export interface Visemes {
  aa: number;
  ih: number;
  ou: number;
  ee: number;
  oh: number;
}

type Shape = keyof Visemes;
type Vowel = NonNullable<PhonemeTiming['vowel']>;

// Jungseong (medial vowel) order in the Hangul syllable block.
const JUNGSEONG = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ';

// SPEC 7.4 mapping of Korean vowels to VRM mouth shapes.
const VOWEL_SHAPE: Record<string, Shape> = {
  ㅏ: 'aa',
  ㅑ: 'aa',
  ㅘ: 'aa',
  ㅣ: 'ih',
  ㅟ: 'ih',
  ㅢ: 'ih',
  ㅜ: 'ou',
  ㅠ: 'ou',
  ㅡ: 'ou',
  ㅔ: 'ee',
  ㅐ: 'ee',
  ㅖ: 'ee',
  ㅒ: 'ee',
  ㅞ: 'ee',
  ㅙ: 'ee',
  ㅗ: 'oh',
  ㅛ: 'oh',
  ㅓ: 'oh',
  ㅕ: 'oh',
  ㅝ: 'oh',
  ㅚ: 'oh',
};

// Language-independent `PhonemeTiming.vowel` -> VRM shape; `n` (m/b/p, silence) is closed.
const VOWEL_VISEME: Record<Vowel, Shape | null> = {
  a: 'aa',
  i: 'ih',
  u: 'ou',
  e: 'ee',
  o: 'oh',
  n: null,
};

// Kana vowel rows (hiragana and katakana) for the text-only fallback.
const KANA_ROWS: [string, Vowel][] = [
  ['あかがさざただなはばぱまやらわぁゃゎアカガサザタダナハバパマヤラワァャヮ', 'a'],
  ['いきぎしじちぢにひびぴみりぃゐイキギシジチヂニヒビピミリィヰ', 'i'],
  ['うくぐすずつづぬふぶぷむゆるぅゅゔウクグスズツヅヌフブプムユルゥュヴ', 'u'],
  ['えけげせぜてでねへべぺめれぇゑエケゲセゼテデネヘベペメレェヱ', 'e'],
  ['おこごそぞとどのほぼぽもよろをぉょオコゴソゾトドノホボポモヨロヲォョ', 'o'],
  ['んっンッ', 'n'],
];
const KANA_VOWEL = new Map<string, Vowel>(
  KANA_ROWS.flatMap(([chars, vowel]) => [...chars].map((c): [string, Vowel] => [c, vowel])),
);
const LATIN_VOWEL: Record<string, Vowel> = { a: 'a', e: 'e', i: 'i', o: 'o', u: 'u', y: 'i' };

export const CLOSED: Visemes = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };

/** Shape of a Hangul syllable's vowel (null for anything else). */
export function shapeOf(char: string): Shape | null {
  const code = char.codePointAt(0) ?? 0;
  if (code < 0xac00 || code > 0xd7a3) return null;
  const jung = JUNGSEONG[Math.floor(((code - 0xac00) % 588) / 28)];
  return jung ? (VOWEL_SHAPE[jung] ?? null) : null;
}

/** Shape of a timeline unit: its `vowel` when the backend sent one, else its Hangul vowel. */
export function unitShape(unit: PhonemeTiming): Shape | null {
  return unit.vowel ? VOWEL_VISEME[unit.vowel] : shapeOf(unit.char);
}

/** Vowel for the text-only fallback: kana rows, CJK ideographs (unknown reading, open), Latin vowels. */
function fallbackVowel(char: string): Vowel | null {
  const kana = KANA_VOWEL.get(char);
  if (kana) return kana;
  const code = char.codePointAt(0) ?? 0;
  if (code >= 0x4e00 && code <= 0x9fff) return 'a';
  return LATIN_VOWEL[char.toLowerCase()] ?? null;
}

/**
 * Syllable timeline for a line. Uses the backend's phoneme timings when present;
 * otherwise spreads the audio duration evenly over the Hangul syllables (SPEC 7.4 fallback),
 * or, for text without Hangul (ja/en), over kana, kanji and Latin vowels.
 */
export function syllableTimeline(
  text: string,
  durationMs: number,
  phonemes?: PhonemeTiming[],
): PhonemeTiming[] {
  if (phonemes && phonemes.length > 0) return phonemes;
  const chars = [...text];
  const hangul = chars.filter((c) => shapeOf(c) !== null);
  const units: PhonemeTiming[] =
    hangul.length > 0
      ? hangul.map((char) => ({ char, start_ms: 0, end_ms: 0 }))
      : chars.flatMap((char) => {
          const vowel = fallbackVowel(char);
          return vowel ? [{ char, start_ms: 0, end_ms: 0, vowel }] : [];
        });
  if (units.length === 0) return [];
  const step = durationMs / units.length;
  return units.map((u, i) => ({ ...u, start_ms: i * step, end_ms: (i + 1) * step }));
}

/**
 * Viseme weights at audio time `t` (ms): the active syllable's vowel shape with a
 * short attack/release envelope, scaled by the voice loudness so pauses close the mouth.
 */
export function visemesAt(timeline: PhonemeTiming[], t: number, level: number): Visemes {
  const out: Visemes = { ...CLOSED };
  const loudness = Math.min(1, Math.max(0, (level - 0.01) / 0.12));
  if (loudness === 0) return out;
  for (const syl of timeline) {
    if (t < syl.start_ms - 40 || t > syl.end_ms + 60) continue;
    const shape = unitShape(syl);
    if (!shape) continue;
    const len = Math.max(syl.end_ms - syl.start_ms, 1);
    const attack = Math.min(1, (t - syl.start_ms + 40) / Math.min(60, len * 0.4));
    const release = Math.min(1, (syl.end_ms + 60 - t) / Math.min(80, len * 0.5));
    const w = Math.max(0, Math.min(attack, release)) * loudness;
    out[shape] = Math.max(out[shape], w);
  }
  return out;
}
