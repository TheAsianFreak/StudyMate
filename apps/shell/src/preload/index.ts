import { contextBridge, ipcRenderer } from 'electron';
import {
  IPC,
  type AvatarSelection,
  type BackendInfo,
  type ProcessMetric,
  type ShellApi,
  type ShellNotice,
  type ShellSettings,
  type UiAction,
} from '../shared/ipc';

const api: ShellApi = {
  setInteractive: (interactive) => ipcRenderer.send(IPC.setInteractive, interactive),
  onHudVisible: (listener) => {
    ipcRenderer.on(IPC.hudVisible, (_event, visible: boolean) => listener(visible));
  },
  onMetrics: (listener) => {
    ipcRenderer.on(IPC.metrics, (_event, metrics: ProcessMetric[]) => listener(metrics));
  },
  onCursor: (listener) => {
    ipcRenderer.on(IPC.cursor, (_event, x: number, y: number) => listener(x, y));
  },
  getCurrentAvatar: () => ipcRenderer.invoke(IPC.avatarCurrent),
  readAvatar: (id) => ipcRenderer.invoke(IPC.avatarRead, id),
  onAvatarChanged: (listener) => {
    ipcRenderer.on(IPC.avatarChanged, (_event, selection: AvatarSelection | null) =>
      listener(selection),
    );
  },
  showMenu: () => ipcRenderer.send(IPC.showMenu),
  runAction: (action) => ipcRenderer.send(IPC.runAction, action),
  onUiAction: (listener) => {
    ipcRenderer.on(IPC.uiAction, (_event, action: UiAction) => listener(action));
  },
  getBackendInfo: () => ipcRenderer.invoke(IPC.backendInfo),
  onBackendChanged: (listener) => {
    ipcRenderer.on(IPC.backendChanged, (_event, info: BackendInfo) => listener(info));
  },
  captureRegion: (rect) => ipcRenderer.invoke(IPC.capture, rect),
  getSettings: () => ipcRenderer.invoke(IPC.settingsGet),
  patchSettings: (patch) => ipcRenderer.invoke(IPC.settingsPatch, patch),
  onSettingsChanged: (listener) => {
    ipcRenderer.on(IPC.settingsChanged, (_event, settings: ShellSettings) => listener(settings));
  },
  pickPdf: () => ipcRenderer.invoke(IPC.pickPdf),
  onIdle: (listener) => {
    ipcRenderer.on(IPC.idle, (_event, idleMs: number) => listener(idleMs));
  },
  setCameraActive: (active) => ipcRenderer.send(IPC.cameraActive, active),
  openEula: () => ipcRenderer.invoke(IPC.openEula),
  readEula: (lang) => ipcRenderer.invoke(IPC.readEula, lang),
  onNotify: (listener) => {
    ipcRenderer.on(IPC.notify, (_event, notice: ShellNotice) => listener(notice));
  },
};

contextBridge.exposeInMainWorld('shell', api);
