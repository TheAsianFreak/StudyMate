import {
  Menu,
  nativeImage,
  Tray,
  type MenuItemConstructorOptions,
  type NativeImage,
} from 'electron';
import { getLang, LANG_NAMES, LANGS, t, type Lang, type PlainKey } from '../shared/i18n';
import type { UiAction } from '../shared/ipc';
import iconPath from '../../build/icon.png?asset';

export interface AppMenuActions {
  isHudVisible: () => boolean;
  onToggleHud: (visible: boolean) => void;
  onUi: (action: UiAction) => void;
  onImportAvatar: () => void;
  onResetAvatar: () => void;
  onSetLang: (lang: Lang) => void;
  onQuit: () => void;
}

export const SHORTCUTS = {
  quit: 'CommandOrControl+Alt+Q',
  capture: 'CommandOrControl+Shift+S',
  talk: 'CommandOrControl+Shift+Space',
} as const;

/**
 * The app menu, shared by the tray icon and the right-click menu on the character.
 * Built on every open, so labels always follow the current language.
 */
export function buildAppMenu(actions: AppMenuActions): Menu {
  const ui = (
    label: PlainKey,
    action: UiAction,
    accelerator?: string,
  ): MenuItemConstructorOptions => ({
    label: t(label),
    ...(accelerator ? { accelerator } : {}),
    click: () => actions.onUi(action),
  });
  const template: MenuItemConstructorOptions[] = [
    ui('menu.capture', 'capture', SHORTCUTS.capture),
    ui('menu.talk', 'talk', SHORTCUTS.talk),
    ui('menu.ask', 'ask'),
    { type: 'separator' },
    ui('menu.quiz', 'quiz'),
    ui('menu.notes', 'notes'),
    ui('menu.review', 'review'),
    ui('menu.docs', 'docs'),
    { type: 'separator' },
    ui('menu.settings', 'settings'),
    { label: t('menu.importAvatar'), click: actions.onImportAvatar },
    { label: t('menu.resetAvatar'), click: actions.onResetAvatar },
    {
      label: t('menu.language'),
      submenu: LANGS.map((lang): MenuItemConstructorOptions => ({
        label: LANG_NAMES[lang],
        type: 'radio',
        checked: getLang() === lang,
        click: () => actions.onSetLang(lang),
      })),
    },
    {
      label: t('menu.debugHud'),
      type: 'checkbox',
      checked: actions.isHudVisible(),
      click: (item) => actions.onToggleHud(item.checked),
    },
    ui('menu.credits', 'credits'),
    { type: 'separator' },
    { label: t('menu.quit'), accelerator: SHORTCUTS.quit, click: actions.onQuit },
  ];
  return Menu.buildFromTemplate(template);
}

// Kept at module scope so the tray icon is not garbage collected.
let tray: Tray | null = null;
let cameraBadge = false;

/** Tray icon; left or right click opens the app menu (rebuilt so checkboxes stay current). */
export function createTray(actions: AppMenuActions): Tray {
  tray = new Tray(createIcon());
  refreshTrayTooltip();
  const open = (): void => tray?.popUpContextMenu(buildAppMenu(actions));
  tray.on('click', open);
  tray.on('right-click', open);
  return tray;
}

export function setTrayCameraBadge(cameraActive: boolean): void {
  if (!tray) return;
  cameraBadge = cameraActive;
  tray.setImage(createIcon(cameraActive));
  refreshTrayTooltip();
}

/** Re-applies the tooltip in the current language (after a language switch). */
export function refreshTrayTooltip(): void {
  tray?.setToolTip(t(cameraBadge ? 'tray.tooltipCamera' : 'tray.tooltip'));
}

/** The app icon (sticker chalkboard); a red dot marks webcam use. */
function createIcon(cameraActive = false): NativeImage {
  const base = nativeImage.createFromPath(iconPath).resize({ width: 32, height: 32 });
  if (!cameraActive) return base;
  const size = base.getSize();
  const bitmap = Buffer.from(base.toBitmap());
  for (let y = 0; y < size.height; y++) {
    for (let x = 0; x < size.width; x++) {
      if (Math.hypot(x - 25, y - 7) >= 6) continue;
      const i = (y * size.width + x) * 4;
      bitmap[i] = 0x30; // B
      bitmap[i + 1] = 0x30; // G
      bitmap[i + 2] = 0xff; // R
      bitmap[i + 3] = 0xff;
    }
  }
  return nativeImage.createFromBitmap(bitmap, size);
}
