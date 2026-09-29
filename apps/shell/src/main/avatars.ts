import { app, dialog, type BrowserWindow } from 'electron';
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { basename, join } from 'node:path';
import { t } from '../shared/i18n';
import type { AvatarSelection } from '../shared/ipc';
import { screenAvatar, type ScreeningResult } from './avatar-screening';

const MAX_BYTES = 256 * 1024 * 1024;

/** Why an avatar was refused, as user-facing lines in the current language. */
export function screeningMessage(result: Exclude<ScreeningResult, { ok: true }>): string[] {
  if (result.reason === 'not_vrm') return [t('avatar.notVrm')];
  return [t('avatar.adult', { detail: result.detail }), t('avatar.adultEula')];
}
const ID_PATTERN = /^[0-9a-f]{16}$/;

interface Settings {
  avatar: AvatarSelection | null;
}

/**
 * User-imported VRM avatars. Files are copied into the app's userData folder and
 * never leave the PC; the app ships only its own default character.
 */
export class AvatarStore {
  private readonly dir = join(app.getPath('userData'), 'avatars');
  private readonly settingsFile = join(app.getPath('userData'), 'settings.json');
  private settings: Settings = { avatar: null };
  /**
   * Set by `init` when the saved avatar fails screening (it was imported before screening
   * existed): the selection is reset and this is reported to the user once.
   */
  private refused: Exclude<ScreeningResult, { ok: true }> | null = null;

  constructor(private readonly onChange: (selection: AvatarSelection | null) => void) {}

  async init(): Promise<void> {
    try {
      const parsed = JSON.parse(await readFile(this.settingsFile, 'utf-8')) as Partial<Settings>;
      const avatar = parsed.avatar;
      if (avatar && ID_PATTERN.test(avatar.id)) this.settings.avatar = avatar;
    } catch {
      // First run or unreadable settings: fall back to the default character.
    }
    const avatar = this.settings.avatar;
    if (!avatar) return;
    let bytes: Uint8Array;
    try {
      bytes = await readFile(join(this.dir, `${avatar.id}.vrm`));
    } catch {
      return; // missing file: the renderer reports the load failure as before
    }
    const result = screenAvatar(bytes, `${avatar.name}.vrm`);
    if (!result.ok) {
      this.refused = result;
      await this.select(null);
    }
  }

  /** The refusal found by `init`, as localized lines; returned only once. */
  takeRefusal(): string[] | null {
    const refused = this.refused;
    this.refused = null;
    return refused ? screeningMessage(refused) : null;
  }

  get current(): AvatarSelection | null {
    return this.settings.avatar;
  }

  /**
   * Opens a file picker and imports the chosen VRM. Returns the error message lines on
   * failure (nothing is copied or selected then).
   */
  async importFromDialog(parent: BrowserWindow): Promise<string[] | null> {
    const result = await dialog.showOpenDialog(parent, {
      title: t('dialog.importAvatar'),
      filters: [{ name: t('dialog.vrmFilter'), extensions: ['vrm'] }],
      properties: ['openFile'],
    });
    const file = result.filePaths[0];
    if (result.canceled || !file) return null;

    const bytes = await readFile(file);
    if (bytes.length > MAX_BYTES) return [t('avatar.tooLarge')];
    // Adult avatars can't be registered (EULA); not_vrm also covers non-glTF files.
    const screening = screenAvatar(bytes, basename(file));
    if (!screening.ok) return screeningMessage(screening);

    const id = createHash('sha256').update(bytes).digest('hex').slice(0, 16);
    await mkdir(this.dir, { recursive: true });
    await writeFile(join(this.dir, `${id}.vrm`), bytes);
    await this.select({ id, name: basename(file, '.vrm') });
    return null;
  }

  async resetToDefault(): Promise<void> {
    await this.select(null);
  }

  async read(id: unknown): Promise<Uint8Array> {
    if (typeof id !== 'string' || !ID_PATTERN.test(id)) throw new Error('invalid avatar id');
    return readFile(join(this.dir, `${id}.vrm`));
  }

  private async select(selection: AvatarSelection | null): Promise<void> {
    this.settings.avatar = selection;
    await writeFile(this.settingsFile, JSON.stringify(this.settings, null, 2));
    this.onChange(selection);
  }
}
