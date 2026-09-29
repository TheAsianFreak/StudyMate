import {
  app,
  BrowserWindow,
  dialog,
  globalShortcut,
  ipcMain,
  powerMonitor,
  protocol,
  screen,
  shell,
  type IpcMainEvent,
  type IpcMainInvokeEvent,
} from 'electron';
import { appendFileSync, existsSync, mkdirSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import iconPath from '../../build/icon.png?asset';
import { isLang, PRODUCT_NAME, setLang, t, type Lang } from '../shared/i18n';
import {
  IPC,
  type EulaText,
  type Rect,
  type ShellAction,
  type ShellNotice,
  type UiAction,
} from '../shared/ipc';
import { APP_ORIGIN, APP_SCHEME, registerAppProtocol } from './app-protocol';
import { AvatarStore } from './avatars';
import { captureRegion } from './capture';
import { startCursorTracking } from './cursor';
import { MetricsReporter } from './metrics';
import { SettingsStore } from './settings';
import { BackendSidecar } from './sidecar';
import {
  buildAppMenu,
  createTray,
  refreshTrayTooltip,
  setTrayCameraBadge,
  SHORTCUTS,
  type AppMenuActions,
} from './tray';
import { isUninstallCleanup, runUninstallCleanup } from './uninstall';

// The product is named "Your StudyMate", but data (settings, avatars, models) stays in
// %APPDATA%/StudyMate, the folder the backend and docs use, so renames never strand it.
// Development and self-test runs get their own folder: sharing it with an installed copy
// mixes settings (e.g. a test's language) and makes the single-instance lock close the
// user's app while a test runs.
app.setPath(
  'userData',
  join(app.getPath('appData'), app.isPackaged ? 'StudyMate' : 'StudyMate-dev'),
);

// Unexpected errors are logged (logs/main.log) instead of Electron's raw
// "A JavaScript error occurred in the main process" dialog.
function logMainError(kind: string, err: unknown): void {
  const text = `${new Date().toISOString()} ${kind}: ${err instanceof Error ? (err.stack ?? err.message) : String(err)}\n`;
  console.error(text);
  try {
    const dir = join(app.getPath('userData'), 'logs');
    mkdirSync(dir, { recursive: true });
    appendFileSync(join(dir, 'main.log'), text);
  } catch {
    // log folder unavailable: the console line is all we can do
  }
}
process.on('uncaughtException', (err) => logMainError('uncaughtException', err));
process.on('unhandledRejection', (reason) => logMainError('unhandledRejection', reason));

protocol.registerSchemesAsPrivileged([
  {
    scheme: APP_SCHEME,
    // allowServiceWorkers: Godot's runtime queries the service worker registration on boot.
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      stream: true,
      allowServiceWorkers: true,
    },
  },
]);

const IDLE_REPORT_MS = 2000;
/** How often the overlay re-asserts that it sits above other windows (keepOnTop). */
const ON_TOP_INTERVAL_MS = 2000;
/** Dev-only end-to-end self test: STUDYMATE_SELFTEST=all|panels,board,ask,solve,quiz,wake */
const SELFTEST = app.isPackaged ? '' : (process.env['STUDYMATE_SELFTEST'] ?? '');

/** Self-test hooks: `SNAP name` screenshots our own window, `SELFTEST DONE` quits. */
function handleSelfTestLog(win: BrowserWindow, message: string): void {
  if (message.startsWith('SNAP ')) {
    const name = message.slice(5).replace(/[^\w-]/g, '_');
    const dir =
      process.env['STUDYMATE_SELFTEST_DIR'] ?? join(app.getPath('temp'), 'studymate-selftest');
    void win.webContents.capturePage().then(async (image) => {
      const { mkdir, writeFile } = await import('node:fs/promises');
      await mkdir(dir, { recursive: true });
      await writeFile(join(dir, `${name}.png`), image.toPNG());
    });
  } else if (message.includes('SELFTEST DONE')) {
    setTimeout(() => app.quit(), 1500);
  }
}

const APP_USER_MODEL_ID = 'app.studymate.desktop';
let overlay: BrowserWindow | null = null;
let hudVisible = !app.isPackaged;

function createOverlayWindow(lang: Lang): BrowserWindow {
  const { workArea } = screen.getPrimaryDisplay();
  const win = new BrowserWindow({
    ...workArea,
    title: PRODUCT_NAME,
    transparent: true,
    backgroundColor: '#00000000',
    frame: false,
    hasShadow: false,
    resizable: false,
    movable: false,
    // A taskbar button like any app: clicking it hides/shows the character (minimize), and
    // its "Close window" quits. The window itself stays frameless, transparent and on top.
    minimizable: true,
    maximizable: false,
    fullscreenable: false,
    skipTaskbar: false,
    icon: iconPath,
    alwaysOnTop: true,
    show: false,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      // The character keeps animating while other apps have focus.
      backgroundThrottling: false,
      autoplayPolicy: 'no-user-gesture-required',
    },
  });

  win.once('ready-to-show', () => {
    win.showInactive();
    // Click-through by default; the renderer turns input on over the character or UI.
    win.setIgnoreMouseEvents(true, { forward: true });
    win.webContents.send(IPC.hudVisible, hudVisible);
    keepOnTop(win);
  });
  // Godot's web runtime sets the page title to its project name; the taskbar shows the product.
  win.on('page-title-updated', (event) => event.preventDefault());

  if (!app.isPackaged) {
    win.webContents.on('console-message', (details) => {
      console.log(`[renderer:${details.level}] ${details.message}`);
      if (SELFTEST) handleSelfTestLog(win, details.message);
    });
  }
  // The microphone and webcam are used by the backend; the renderer needs no permissions.
  win.webContents.session.setPermissionRequestHandler((_wc, _permission, callback) =>
    callback(false),
  );

  const devUrl = process.env['ELECTRON_RENDERER_URL'];
  // Dev-only diagnostics: STUDYMATE_QUERY="profile" | "nogodot" is appended to the page URL.
  const params = new URLSearchParams(app.isPackaged ? '' : (process.env['STUDYMATE_QUERY'] ?? ''));
  if (SELFTEST) params.set('selftest', SELFTEST);
  // The first paint is already in the right language; later switches arrive as settings.
  params.set('lang', lang);
  const query = params.size ? `?${params.toString()}` : '';
  void win.loadURL((!app.isPackaged && devUrl ? devUrl : `${APP_ORIGIN}/index.html`) + query);
  return win;
}

function fitToWorkArea(): void {
  overlay?.setBounds(screen.getPrimaryDisplay().workArea);
  raiseOverlay();
}

/** Puts the overlay back at the top of the always-on-top windows, without activating it. */
function raiseOverlay(): void {
  const win = overlay;
  if (!win || win.isDestroyed() || win.isMinimized() || !win.isVisible()) return;
  // 'screen-saver': above other topmost windows ('floating' is placed behind the taskbar).
  win.setAlwaysOnTop(true, 'screen-saver');
  win.moveTop();
}

/**
 * On Windows the character can end up behind other windows: always-on-top windows opened
 * later (task manager, messengers, video players), full-screen apps, sleep or a display
 * change. The topmost state is re-asserted on those events and every few seconds; the
 * window is click-through outside the character, so staying on top never blocks clicks.
 */
function keepOnTop(win: BrowserWindow): void {
  raiseOverlay();
  const timer = setInterval(raiseOverlay, ON_TOP_INTERVAL_MS);
  win.on('closed', () => clearInterval(timer));
  win.on('restore', raiseOverlay);
  powerMonitor.on('resume', raiseOverlay);
  powerMonitor.on('unlock-screen', raiseOverlay);
}

/**
 * EULA.<lang>.txt, or the English one when that translation is missing.
 * Packaged: resources/eula/ (electron-builder extraResources); dev: apps/shell/build/eula/.
 */
function eulaFile(lang: Lang): { lang: Lang; file: string } | null {
  const dir = app.isPackaged
    ? join(process.resourcesPath, 'eula')
    : join(app.getAppPath(), 'build', 'eula');
  for (const candidate of [lang, 'en'] as const) {
    const file = join(dir, `EULA.${candidate}.txt`);
    if (existsSync(file)) return { lang: candidate, file };
  }
  return null;
}

/** Opens the EULA with the default text viewer. */
async function openEula(lang: Lang): Promise<boolean> {
  const eula = eulaFile(lang);
  return eula !== null && (await shell.openPath(eula.file)) === '';
}

/** The EULA text for the onboarding screen (the files are UTF-8 with a BOM). */
async function readEula(lang: unknown): Promise<EulaText | null> {
  const eula = eulaFile(isLang(lang) ? lang : 'en');
  if (!eula) return null;
  const text = await readFile(eula.file, 'utf-8');
  return { lang: eula.lang, text: text.charCodeAt(0) === 0xfeff ? text.slice(1) : text };
}

/** Registers an IPC handler that only accepts calls from the overlay window. */
function handle(channel: string, fn: (...args: unknown[]) => unknown): void {
  ipcMain.handle(channel, (event: IpcMainInvokeEvent, ...args: unknown[]) => {
    if (event.sender !== overlay?.webContents) throw new Error('unexpected sender');
    return fn(...args);
  });
}

function on(channel: string, fn: (...args: unknown[]) => void): void {
  ipcMain.on(channel, (event: IpcMainEvent, ...args: unknown[]) => {
    if (event.sender !== overlay?.webContents) return;
    fn(...args);
  });
}

function isRect(v: unknown): v is Rect {
  if (typeof v !== 'object' || v === null) return false;
  const r = v as Record<string, unknown>;
  return ['x', 'y', 'w', 'h'].every((k) => typeof r[k] === 'number' && Number.isFinite(r[k]));
}

if (isUninstallCleanup()) {
  void runUninstallCleanup(app.getPath('userData'));
} else if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  // Same id as the installer's shortcuts (electron-builder appId): the taskbar button groups
  // with a pinned shortcut and shows the app icon.
  if (process.platform === 'win32') app.setAppUserModelId(APP_USER_MODEL_ID);
  void app.whenReady().then(async () => {
    registerAppProtocol();
    // Timers (idle, metrics, cursor) may still fire while the app quits: skip a closed window.
    const send = (channel: string, ...args: unknown[]): void => {
      if (overlay && !overlay.isDestroyed()) overlay.webContents.send(channel, ...args);
    };

    // Everything the renderer may invoke is registered before the window exists.
    const settings = new SettingsStore((s) => {
      setLang(s.lang);
      refreshTrayTooltip(); // the menus are rebuilt on every open
      send(IPC.settingsChanged, s);
    });
    setLang(settings.get().lang);
    const avatars = new AvatarStore((selection) => send(IPC.avatarChanged, selection));
    await avatars.init();
    const backend = new BackendSidecar((info) => send(IPC.backendChanged, info));

    handle(IPC.avatarCurrent, () => avatars.current);
    handle(IPC.avatarRead, (id) => avatars.read(id));
    handle(IPC.backendInfo, () => backend.info);
    handle(IPC.settingsGet, () => settings.get());
    handle(IPC.settingsPatch, (patch) => settings.patch(patch));
    handle(IPC.capture, (rect) => {
      if (!overlay || !isRect(rect)) throw new Error('invalid capture rect');
      return captureRegion(overlay, rect);
    });
    handle(IPC.pickPdf, async () => {
      if (!overlay) return null;
      const result = await dialog.showOpenDialog(overlay, {
        title: t('dialog.pickPdf'),
        filters: [{ name: 'PDF', extensions: ['pdf'] }],
        properties: ['openFile'],
      });
      return result.canceled ? null : (result.filePaths[0] ?? null);
    });
    handle(IPC.openEula, () => openEula(settings.get().lang));
    handle(IPC.readEula, (lang) => readEula(lang));

    overlay = createOverlayWindow(settings.get().lang);
    const win = overlay;
    // A saved avatar refused by screening was reset in avatars.init(): say so once.
    win.webContents.once('did-finish-load', () => {
      const refusal = avatars.takeRefusal();
      if (refusal) {
        const notice: ShellNotice = {
          title: t('avatar.blockedTitle'),
          lines: refusal,
          tone: 'error',
        };
        send(IPC.notify, notice);
      }
    });
    const metrics = new MetricsReporter((m) => send(IPC.metrics, m));
    if (hudVisible) metrics.start();
    startCursorTracking(win, (x, y) => send(IPC.cursor, x, y));

    on(IPC.setInteractive, (interactive) => {
      if (typeof interactive === 'boolean') {
        win.setIgnoreMouseEvents(!interactive, { forward: true });
      }
    });
    on(IPC.cameraActive, (active) => setTrayCameraBadge(active === true));

    const importAvatar = (): void => {
      avatars.importFromDialog(win).then(
        (error) => {
          if (error) dialog.showErrorBox(t('dialog.avatarFailed'), error.join('\n'));
        },
        (err: unknown) => dialog.showErrorBox(t('dialog.avatarFailed'), String(err)),
      );
    };
    const uiAction = (action: UiAction): void => {
      // Tray, menu and shortcuts act on the character: bring it back if hidden from the taskbar.
      if (overlay?.isMinimized()) overlay.restore();
      send(IPC.uiAction, action);
    };
    const menuActions: AppMenuActions = {
      isHudVisible: () => hudVisible,
      onToggleHud: (visible) => {
        hudVisible = visible;
        send(IPC.hudVisible, visible);
        if (visible) metrics.start();
        else metrics.stop();
      },
      onUi: uiAction,
      onImportAvatar: importAvatar,
      onResetAvatar: () => void avatars.resetToDefault(),
      onSetLang: (lang) => void settings.patch({ lang }),
      onQuit: () => app.quit(),
    };
    createTray(menuActions);
    on(IPC.showMenu, () => buildAppMenu(menuActions).popup({ window: win }));
    on(IPC.runAction, (action) => {
      const actions: Record<ShellAction, () => void> = {
        importAvatar,
        resetAvatar: () => void avatars.resetToDefault(),
        quit: () => app.quit(),
      };
      if (typeof action === 'string' && action in actions) actions[action as ShellAction]();
    });

    // Always-available global shortcuts (the tray icon may sit in the hidden overflow).
    const shortcuts: [string, () => void][] = [
      [SHORTCUTS.quit, () => app.quit()],
      [SHORTCUTS.capture, () => uiAction('capture')],
      [SHORTCUTS.talk, () => uiAction('talk')],
    ];
    for (const [accelerator, fn] of shortcuts) {
      if (!globalShortcut.register(accelerator, fn)) {
        console.warn(`[shell] could not register ${accelerator}`);
      }
    }

    // System-wide input idle time, used to hold drowsiness judgement while the user types.
    setInterval(() => send(IPC.idle, powerMonitor.getSystemIdleTime() * 1000), IDLE_REPORT_MS);

    screen.on('display-metrics-changed', fitToWorkArea);
    screen.on('display-added', fitToWorkArea);
    screen.on('display-removed', fitToWorkArea);

    app.on('before-quit', () => backend.stop());
    try {
      await backend.start();
    } catch (err) {
      console.error('[shell] backend failed to start', err);
      backend.info = { url: '', state: 'failed' };
      send(IPC.backendChanged, backend.info);
    }
  });

  // The overlay has no close button: quit via tray, character right-click or Ctrl+Alt+Q.
  app.on('window-all-closed', () => app.quit());
  app.on('will-quit', () => globalShortcut.unregisterAll());
}
