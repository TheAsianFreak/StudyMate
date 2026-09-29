// IPC channel names and payloads shared by main, preload and renderer.

import type { Lang } from './i18n';

export const IPC = {
  /** renderer -> main: whether the window should receive mouse input. */
  setInteractive: 'shell:set-interactive',
  /** main -> renderer: tray toggled the debug HUD. */
  hudVisible: 'shell:hud-visible',
  /** main -> renderer: process metrics, sent every second while the HUD is visible. */
  metrics: 'shell:metrics',
  /** main -> renderer: cursor position in window CSS px, sent when it changes. */
  cursor: 'shell:cursor',
  /** main -> renderer: the selected avatar changed (null = built-in character). */
  avatarChanged: 'shell:avatar-changed',
  /** renderer -> main (invoke): current avatar selection. */
  avatarCurrent: 'shell:avatar-current',
  /** renderer -> main (invoke): bytes of an imported avatar. */
  avatarRead: 'shell:avatar-read',
  /** renderer -> main: open the app menu at the pointer (right-click on the character). */
  showMenu: 'shell:show-menu',
  /** renderer -> main: menu-equivalent actions triggered from in-app UI. */
  runAction: 'shell:run-action',
  /** main -> renderer: a menu item or global shortcut asked the UI to do something. */
  uiAction: 'shell:ui-action',
  /** renderer -> main (invoke) / main -> renderer: backend sidecar URL and state. */
  backendInfo: 'shell:backend-info',
  backendChanged: 'shell:backend-changed',
  /** renderer -> main (invoke): capture a window-CSS-px rect as PNG base64. */
  capture: 'shell:capture',
  /** renderer -> main (invoke) / main -> renderer: shell preferences. */
  settingsGet: 'shell:settings-get',
  settingsPatch: 'shell:settings-patch',
  settingsChanged: 'shell:settings-changed',
  /** renderer -> main (invoke): let the user pick a PDF; resolves to its path or null. */
  pickPdf: 'shell:pick-pdf',
  /** main -> renderer: milliseconds since the last system-wide keyboard/mouse input. */
  idle: 'shell:idle',
  /** renderer -> main: webcam in use (tray badge). */
  cameraActive: 'shell:camera-active',
  /** renderer -> main (invoke): open the EULA in the current language; resolves to success. */
  openEula: 'shell:open-eula',
  /** renderer -> main (invoke): the EULA text in a language (English fallback), or null. */
  readEula: 'shell:read-eula',
  /** main -> renderer: show a notification card (already localized). */
  notify: 'shell:notify',
} as const;

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface ProcessMetric {
  type: string;
  pid: number;
  /** Percent of one CPU core since the previous sample. */
  cpu: number;
  /** Working set in MB. */
  memoryMb: number;
}

/** A user-imported VRM stored in the app data folder. */
export interface AvatarSelection {
  id: string;
  name: string;
}

export interface BackendInfo {
  url: string;
  state: 'starting' | 'ready' | 'failed';
}

export type WakeIntensity = 'soft' | 'normal' | 'hard';
export type Sensitivity = 'low' | 'normal' | 'high';

export interface ShellSettings {
  /** UI, character speech and speech recognition language (default: from the OS locale). */
  lang: Lang;
  /**
   * How the character addresses the user (e.g. a name, 선배, マスター); "" = the default.
   * Only values the backend accepted (set_profile → status.profile.address) are saved.
   */
  address: string;
  /** Webcam drowsiness detection (opt-in). */
  drowsyEnabled: boolean;
  drowsySensitivity: Sensitivity;
  /** soft: talk + desk tap only; normal: + soft chalk; hard: "교탁 모드" hard chalk. */
  wakeIntensity: WakeIntensity;
  /** Suppresses wake-ups and idle chatter. */
  focusMode: boolean;
  /** After answering, listen again automatically (conversation mode). */
  conversationAutoListen: boolean;
  /** Character wanders around while idle. */
  wander: boolean;
  /** Character reminds about due review cards. */
  reviewReminders: boolean;
  /** First-run setup (models, webcam explanation) has been completed. */
  onboarded: boolean;
  /** Download the models the recommended tier needs automatically on launch. */
  autoDownloadModels: boolean;
  /**
   * EULA version the user agreed to in the in-app onboarding ("" = never). Until it equals
   * EULA_VERSION no models are installed and the AI features stay locked.
   */
  eulaAcceptedVersion: string;
  /** ISO 8601 time of that agreement. */
  eulaAcceptedAt: string;
}

/** Current EULA (apps/shell/build/eula). Bumping it asks every user to agree again. */
export const EULA_VERSION = '2026-09-25';

/** Longest address the backend accepts (UserProfile.address). */
export const ADDRESS_MAX = 20;

export const DEFAULT_SHELL_SETTINGS: ShellSettings = {
  lang: 'ko',
  address: '',
  drowsyEnabled: false,
  drowsySensitivity: 'normal',
  wakeIntensity: 'normal',
  focusMode: false,
  conversationAutoListen: true,
  wander: true,
  reviewReminders: true,
  onboarded: false,
  autoDownloadModels: true,
  eulaAcceptedVersion: '',
  eulaAcceptedAt: '',
};

/** EULA text for the onboarding screen. */
export interface EulaText {
  /** Language of the text (English when the requested translation is missing). */
  lang: Lang;
  text: string;
}

/** Actions that menus and shortcuts forward to the renderer UI. */
export type UiAction =
  'capture' | 'talk' | 'ask' | 'quiz' | 'notes' | 'review' | 'docs' | 'settings' | 'credits';

/** Actions the renderer asks the main process to perform. */
export type ShellAction = 'importAvatar' | 'resetAvatar' | 'quit';

/** A notification card raised by the main process. */
export interface ShellNotice {
  title: string;
  lines: string[];
  tone: 'info' | 'error';
}

export interface ShellApi {
  setInteractive(interactive: boolean): void;
  onHudVisible(listener: (visible: boolean) => void): void;
  onMetrics(listener: (metrics: ProcessMetric[]) => void): void;
  onCursor(listener: (x: number, y: number) => void): void;
  getCurrentAvatar(): Promise<AvatarSelection | null>;
  readAvatar(id: string): Promise<Uint8Array>;
  onAvatarChanged(listener: (selection: AvatarSelection | null) => void): void;
  showMenu(): void;
  runAction(action: ShellAction): void;
  onUiAction(listener: (action: UiAction) => void): void;
  getBackendInfo(): Promise<BackendInfo>;
  onBackendChanged(listener: (info: BackendInfo) => void): void;
  captureRegion(rect: Rect): Promise<string>;
  getSettings(): Promise<ShellSettings>;
  patchSettings(patch: Partial<ShellSettings>): Promise<ShellSettings>;
  onSettingsChanged(listener: (settings: ShellSettings) => void): void;
  pickPdf(): Promise<string | null>;
  onIdle(listener: (idleMs: number) => void): void;
  setCameraActive(active: boolean): void;
  /** Opens the EULA text file in the current language (English fallback); false if missing. */
  openEula(): Promise<boolean>;
  readEula(lang: Lang): Promise<EulaText | null>;
  onNotify(listener: (notice: ShellNotice) => void): void;
}
