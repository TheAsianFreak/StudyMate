// UI localization shared by the main process and the renderer (each keeps its own current
// language). Tables: ko.ts (source of keys and placeholders), ja.ts, en.ts.

import { en } from './en';
import { ja } from './ja';
import { ko, type MessageKey, type Messages } from './ko';

export type { MessageKey, Messages };

/** App language (same values as the protocol's `Lang`). */
export type Lang = 'ko' | 'ja' | 'en';
export const LANGS: readonly Lang[] = ['ko', 'ja', 'en'];
/** Each language's own name, shown untranslated in language pickers. */
export const LANG_NAMES: Record<Lang, string> = { ko: '한국어', ja: '日本語', en: 'English' };
export const PRODUCT_NAME = 'Your StudyMate';
/** GPL-3.0 section 7(b) attribution (NOTICE): kept on the credits screen of any derived work. */
export const AUTHOR = 'TheAsianFreak (NBBANGSOFT)';

const TABLES: Record<Lang, Messages> = { ko, ja, en };
/** BCP 47 tags for Intl formatting. */
const LOCALE_TAGS: Record<Lang, string> = { ko: 'ko-KR', ja: 'ja-JP', en: 'en-US' };

let current: Lang = 'ko';
const listeners = new Set<(lang: Lang) => void>();

export function isLang(value: unknown): value is Lang {
  return typeof value === 'string' && (LANGS as readonly string[]).includes(value);
}

/** Maps an OS/browser locale ("ko", "ja-JP", "en-US", "fr") to an app language. */
export function langFromLocale(locale: string): Lang {
  const base = locale.toLowerCase().split(/[-_]/)[0];
  return base === 'ko' ? 'ko' : base === 'ja' ? 'ja' : 'en';
}

export function getLang(): Lang {
  return current;
}

export function localeTag(lang: Lang = current): string {
  return LOCALE_TAGS[lang];
}

/** Switches the language and notifies `onLangChange` listeners (no-op when unchanged). */
export function setLang(lang: Lang): void {
  if (lang === current) return;
  current = lang;
  for (const listener of listeners) listener(lang);
}

/** Called after every language switch, e.g. to re-render static labels. */
export function onLangChange(listener: (lang: Lang) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// --- how the character addresses the user -------------------------------------------------

let address = '';

/** The user's chosen address ("선배", "マスター", "Alex"); empty = the character's default. */
export function setAddress(value: string): void {
  address = value.trim();
}

/**
 * `{address}` in canned lines: the address as a vocative with its own punctuation, so a line
 * reads naturally with or without one — ko/ja lead the clause ("선배, 일어나세요~!",
 * "先輩、起きてくださーい！"), en trails it ("Time to wake up, Alex~!").
 */
function vocative(): string {
  if (!address) return '';
  return current === 'ko' ? `${address}, ` : current === 'ja' ? `${address}、` : `, ${address}`;
}

/** `{name}` placeholders of a message template (`{address}` is filled in automatically). */
type Placeholders<S extends string> = S extends `${string}{${infer P}}${infer Rest}`
  ? P | Placeholders<Rest>
  : never;
type ParamNames<K extends MessageKey> = Exclude<Placeholders<(typeof ko)[K]>, 'address'>;
type ParamsOf<K extends MessageKey> = [ParamNames<K>] extends [never]
  ? []
  : [params: Record<ParamNames<K>, string | number>];
/** Keys whose messages take no parameters (usable where a key is chosen at runtime). */
export type PlainKey = {
  [K in MessageKey]: [ParamNames<K>] extends [never] ? K : never;
}[MessageKey];

/** The message for `key` in the current language, with `{placeholders}` filled in. */
export function t<K extends MessageKey>(key: K, ...params: ParamsOf<K>): string {
  return format(TABLES[current][key] ?? ko[key], params[0]);
}

/** Like `t` for keys built at runtime (e.g. from a backend error code); undefined if unknown. */
export function tryT(key: string, params?: Record<string, string | number>): string | undefined {
  if (!(key in ko)) return undefined;
  const k = key as MessageKey;
  return format(TABLES[current][k] ?? ko[k], params);
}

function format(template: string, params?: Record<string, string | number>): string {
  if (!template.includes('{')) return template;
  const values: Record<string, string | number> = { address: vocative(), ...params };
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in values ? String(values[name]) : match,
  );
}

// --- compile-time checks: every translation uses exactly the Korean placeholders -------------

type PlaceholderMismatch<T extends Messages> = {
  [K in MessageKey]: [Placeholders<T[K]>] extends [Placeholders<(typeof ko)[K]>]
    ? [Placeholders<(typeof ko)[K]>] extends [Placeholders<T[K]>]
      ? never
      : K
    : K;
}[MessageKey];
/** Resolves to `true`, or to the offending keys, which fails the assignment below. */
type PlaceholdersMatch<T extends Messages> = [PlaceholderMismatch<T>] extends [never]
  ? true
  : PlaceholderMismatch<T>;

export const PLACEHOLDER_CHECK: [PlaceholdersMatch<typeof ja>, PlaceholdersMatch<typeof en>] = [
  true,
  true,
];
