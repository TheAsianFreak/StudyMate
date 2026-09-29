import { app } from 'electron';
import { readFileSync } from 'node:fs';
import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { isLang, langFromLocale, type Lang } from '../shared/i18n';
import { ADDRESS_MAX, DEFAULT_SHELL_SETTINGS, type ShellSettings } from '../shared/ipc';

/** Shell preferences persisted as JSON in the app data folder. */
export class SettingsStore {
  private readonly file = join(app.getPath('userData'), 'shell-settings.json');
  /** First run: the language follows the OS locale (ko → ko, ja → ja, anything else → en). */
  private readonly defaults: ShellSettings = {
    ...structuredClone(DEFAULT_SHELL_SETTINGS),
    lang: langFromLocale(app.getLocale()),
  };
  private value: ShellSettings;
  /**
   * STUDYMATE_LANG=ko|ja|en (development / self-test): overrides the saved language without
   * persisting it, until the user picks a language in the app.
   */
  private langOverride: Lang | null = isLang(process.env['STUDYMATE_LANG'])
    ? (process.env['STUDYMATE_LANG'] as Lang)
    : null;

  constructor(private readonly onChange: (settings: ShellSettings) => void) {
    this.value = structuredClone(this.defaults);
    try {
      const saved = JSON.parse(readFileSync(this.file, 'utf-8')) as Partial<ShellSettings>;
      this.value = mergeDefaults(saved, this.defaults);
    } catch {
      // first run or unreadable: defaults
    }
  }

  get(): ShellSettings {
    const out = structuredClone(this.value);
    if (this.langOverride) out.lang = this.langOverride;
    return out;
  }

  async patch(patch: unknown): Promise<ShellSettings> {
    if (typeof patch !== 'object' || patch === null) return this.get();
    if ('lang' in patch) this.langOverride = null;
    this.value = mergeDefaults(
      { ...this.value, ...(patch as Partial<ShellSettings>) },
      this.defaults,
    );
    await writeFile(this.file, JSON.stringify(this.value, null, 2));
    this.onChange(this.get());
    return this.get();
  }
}

/** Keeps only known keys with the right primitive types (and a supported language). */
function mergeDefaults(input: Partial<ShellSettings>, defaults: ShellSettings): ShellSettings {
  const out = structuredClone(defaults);
  for (const key of Object.keys(out) as (keyof ShellSettings)[]) {
    const v = input[key];
    if (v !== undefined && typeof v === typeof out[key]) {
      (out as unknown as Record<string, unknown>)[key] = v;
    }
  }
  if (!isLang(out.lang)) out.lang = defaults.lang;
  out.address = out.address.trim().slice(0, ADDRESS_MAX);
  return out;
}
