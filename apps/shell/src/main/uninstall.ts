import { app, dialog } from 'electron';
import { existsSync, readFileSync } from 'node:fs';
import { rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { isLang, langFromLocale, PRODUCT_NAME, setLang, t, type Lang } from '../shared/i18n';

/**
 * Steam runs `Your StudyMate.exe --uninstall-cleanup` when the game is uninstalled
 * (steam/installscript.vdf), since Steam never runs the NSIS uninstaller. Same question as
 * the NSIS uninstaller (build/installer.nsh): also delete the models and the study data?
 */
export const UNINSTALL_FLAG = '--uninstall-cleanup';

export function isUninstallCleanup(): boolean {
  return process.argv.includes(UNINSTALL_FLAG);
}

/** Asks, deletes `dataDir` on yes, and exits. Call before app 'ready'. */
export async function runUninstallCleanup(dataDir: string): Promise<void> {
  // Chromium writes its own files into userData while running: point it elsewhere so the
  // real data folder has no open files when it is deleted.
  app.setPath('userData', join(tmpdir(), 'StudyMate-uninstall'));
  await app.whenReady();
  setLang(savedLang(dataDir) ?? langFromLocale(app.getLocale()));
  if (existsSync(dataDir)) {
    const { response } = await dialog.showMessageBox({
      type: 'question',
      title: PRODUCT_NAME,
      message: t('uninstall.question'),
      detail: t('uninstall.detail'),
      buttons: [t('uninstall.deleteAll'), t('uninstall.keep')],
      defaultId: 0,
      cancelId: 1,
      noLink: true,
    });
    if (response === 0) {
      await rm(dataDir, { recursive: true, force: true, maxRetries: 3 }).catch(() => undefined);
    }
  }
  await rm(app.getPath('userData'), { recursive: true, force: true }).catch(() => undefined);
  app.exit(0);
}

function savedLang(dataDir: string): Lang | null {
  try {
    const saved = JSON.parse(readFileSync(join(dataDir, 'shell-settings.json'), 'utf-8')) as {
      lang?: unknown;
    };
    return isLang(saved.lang) ? saved.lang : null;
  } catch {
    return null;
  }
}
