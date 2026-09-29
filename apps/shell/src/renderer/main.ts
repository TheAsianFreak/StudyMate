import './styles.css';
import type { VoicePresets } from '@studymate/protocol';
import { getLang, isLang, PRODUCT_NAME, setAddress, setLang, t, type Lang } from '../shared/i18n';
import {
  DEFAULT_SHELL_SETTINGS,
  EULA_VERSION,
  type ShellSettings,
  type UiAction,
} from '../shared/ipc';
import type { AppContext } from './app-context';
import { BackendClient, localizeError } from './backend/client';
import { presetLang } from './backend/models';
import { GodotBridge } from './bridge/godot-bridge';
import { startGodot } from './bridge/godot-loader';
import { Conversation } from './director/conversation';
import { Director } from './director/director';
import { SolveFlow } from './director/solve';
import { Timeline } from './director/timeline';
import { WakeUp } from './director/wake';
import { installCharacterDrag } from './ui/character-drag';
import { ClickThrough } from './ui/click-through';
import { Dock } from './ui/dock';
import { ScreenEffects } from './ui/effects';
import { Hud } from './ui/hud';
import { ModelSetup } from './ui/model-setup';
import { Onboarding } from './ui/onboarding';
import { runSelfTest } from './selftest';
import { AskPanel } from './ui/panels/ask-panel';
import { CreditsPanel } from './ui/panels/credits-panel';
import { DocsPanel } from './ui/panels/docs-panel';
import { NotesPanel } from './ui/panels/notes-panel';
import { QuizPanel } from './ui/panels/quiz-panel';
import { ReviewPanel } from './ui/panels/review-panel';
import { SettingsPanel } from './ui/panels/settings-panel';
import { WelcomePanel } from './ui/panels/welcome-panel';
import { Sfx } from './ui/sfx';
import { SpeechBubble } from './ui/speech-bubble';
import { Toasts } from './ui/toast';

const REVIEW_CHECK_MS = 10 * 60_000;
const FIRST_REVIEW_CHECK_MS = 90_000;

const canvas = document.querySelector<HTMLCanvasElement>('#godot-canvas')!;
const stage = document.querySelector<HTMLElement>('#stage')!;
const overlay = document.querySelector<HTMLElement>('#overlay')!;

// The main process passes the language in the URL so the very first paint is localized;
// later switches arrive with the settings (applySettings → switchLanguage).
const bootLang = new URLSearchParams(location.search).get('lang');
if (isLang(bootLang)) setLang(bootLang);
document.documentElement.lang = getLang();
document.title = PRODUCT_NAME;

let settings: ShellSettings = { ...DEFAULT_SHELL_SETTINGS, lang: getLang() };
let voicePreset: string | undefined;
/** Self-test runs count as accepted so they can exercise every feature. */
const SELFTEST = new URLSearchParams(location.search).has('selftest');
/** EULA agreed in the onboarding: until then nothing is installed and AI features are locked. */
const eulaAccepted = (): boolean => SELFTEST || settings.eulaAcceptedVersion === EULA_VERSION;
let onboarding: Onboarding | null = null;

// --- core -------------------------------------------------------------------------------
const toasts = new Toasts(overlay);
let bubble: SpeechBubble | null = null;
// The bridge must exist before the engine starts: Godot looks up window.studymateHost on boot.
const bridge = new GodotBridge();
const director = new Director(
  bridge,
  {
    say: (text, ms) => bubble?.say(text, ms),
    notify: (title, lines, tone) => toasts.show(title, lines, tone),
  },
  (id) => window.shell.readAvatar(id),
);
bubble = new SpeechBubble(overlay, director);
const backend = new BackendClient();
const timeline = new Timeline(director, backend, overlay, bubble);
const sfx = new Sfx(timeline.audio.ctx);
const effects = new ScreenEffects(stage, overlay);
const voice = (): string | undefined => voicePreset;

let askPanel: AskPanel | null = null;
const conversation = new Conversation(
  director,
  backend,
  timeline,
  {
    listening: (level, partial) => bubble?.listening(level, partial),
    heard: (text) => {
      bubble?.say(`“${text}”`, 1500);
      askPanel?.addTurn('user', text);
    },
    thinking: () => bubble?.thinking(),
    idle: () => bubble?.hide(),
    answered: (text) => askPanel?.addTurn('assistant', text),
  },
  voice,
);
const solve = new SolveFlow(director, backend, timeline, overlay, voice, {
  onSolved: (label, context, problemId) => conversation.setTopic(label, context, problemId),
  onAsk: () => askPanel?.open(),
});
const wake = new WakeUp(
  director,
  sfx,
  effects,
  () => !timeline.playing && !conversation.isListening,
);

const app: AppContext = {
  director,
  backend,
  timeline,
  conversation,
  solve,
  wake,
  sfx,
  toasts,
  overlay,
  settings: () => settings,
  patchSettings: async (patch) => {
    settings = await window.shell.patchSettings(patch);
  },
  voice,
  setVoice: (id) => {
    voicePreset = id;
  },
  eulaAccepted,
  openOnboarding: () => onboarding?.open(),
};

// --- input ----------------------------------------------------------------------------
const clickThrough = new ClickThrough(
  (x, y) => director.state === 'dragging' || director.hitTest(x, y),
);
director.onChange(() => clickThrough.refresh());
installCharacterDrag(director, () => clickThrough.refresh());

// --- panels ---------------------------------------------------------------------------
askPanel = new AskPanel(app);
const quizPanel = new QuizPanel(app);
const notesPanel = new NotesPanel(app);
const reviewPanel = new ReviewPanel(app);
const docsPanel = new DocsPanel(app);
const settingsPanel = new SettingsPanel(app);
const creditsPanel = new CreditsPanel(app);
const welcomePanel = new WelcomePanel(app, () => settingsPanel.open('models'));

/** Features that need the installed AI (and so the EULA consent); others stay open. */
const NEEDS_EULA = new Set<UiAction>(['capture', 'talk', 'ask', 'quiz', 'notes', 'review', 'docs']);

function runUiAction(action: UiAction): void {
  if (NEEDS_EULA.has(action) && !eulaAccepted()) {
    director.ui.say(t('onboarding.locked'), 2500);
    onboarding?.open();
    return;
  }
  switch (action) {
    case 'capture':
      void solve.captureAndSolve();
      break;
    case 'talk':
      conversation.toggle();
      break;
    case 'ask':
      askPanel?.open();
      break;
    case 'quiz':
      quizPanel.open();
      break;
    case 'notes':
      notesPanel.open();
      break;
    case 'review':
      reviewPanel.open();
      break;
    case 'docs':
      docsPanel.open();
      break;
    case 'settings':
      settingsPanel.open();
      break;
    case 'credits':
      creditsPanel.open();
      break;
  }
}
window.shell.onUiAction(runUiAction);
const dock = new Dock(overlay, director, runUiAction);
clickThrough.onPointer((x, y) => dock.pointer(x, y));

// --- debug HUD --------------------------------------------------------------------------
const hud = new Hud(overlay, { director, bridge, clickThrough, backend, timeline, wake });
hud.setVisible(false);
window.shell.onHudVisible((visible) => hud.setVisible(visible));
window.shell.onMetrics((metrics) => hud.setMetrics(metrics));

// --- settings -------------------------------------------------------------------------
function applySettings(next: ShellSettings): void {
  const prev = settings;
  settings = next;
  if (next.lang !== getLang()) switchLanguage(next.lang);
  applyAddress(next.address);
  director.setWander(next.wander);
  conversation.autoListen = next.conversationAutoListen;
  wake.intensity = next.wakeIntensity;
  wake.focusMode = next.focusMode;
  if (
    backend.connected &&
    (next.drowsyEnabled !== prev.drowsyEnabled || next.drowsySensitivity !== prev.drowsySensitivity)
  ) {
    syncDrowsy();
  }
}

/**
 * The saved address fills `{address}` in canned lines and goes to the backend (hello, or
 * set_profile when it differs from what the backend has, e.g. settings loaded late).
 */
function applyAddress(address: string): void {
  setAddress(address);
  if (address === backend.address) return;
  backend.address = address;
  const current = backend.status?.profile?.address;
  if (backend.connected && current !== undefined && current !== address) {
    backend.send({ type: 'set_profile', id: backend.newId('profile'), profile: { address } });
  }
}

function syncDrowsy(): void {
  // The webcam check is an AI feature: only after the EULA was accepted.
  if (settings.drowsyEnabled && eulaAccepted() && backend.status?.capabilities.drowsy) {
    backend.send({
      type: 'drowsy_start',
      id: backend.newId('drowsy'),
      sensitivity: settings.drowsySensitivity,
    });
  } else {
    backend.send({ type: 'drowsy_stop', id: backend.newId('drowsy') });
  }
}

/**
 * Language switch (settings panel, welcome panel or tray menu → main process → here):
 * static labels re-render through onLangChange listeners, the voice and conversation reset
 * (they belong to the old language), and the backend follows with set_language; its reply
 * status may list models the new language still needs (e.g. its TTS voice).
 */
function switchLanguage(lang: Lang): void {
  setLang(lang);
  document.documentElement.lang = lang;
  voicePreset = undefined;
  conversation.forget();
  if (!backend.connected) return; // the next hello carries the language
  backend
    .request({ type: 'set_language', id: backend.newId('lang'), lang }, 'status', undefined, 15_000)
    .then((status) => {
      if (lang !== getLang()) return;
      if (!director.busy) director.ui.say(t('lang.switched'), 3500);
      if (settings.autoDownloadModels && eulaAccepted()) void modelSetup.run(status, 'language');
    })
    .catch((err: unknown) => console.warn('[shell] set_language failed', err));
}

// First launch (or a new EULA version): the onboarding card asks for consent; installing
// starts only from its "agree" button. Later launches resume downloads on their own.
onboarding = new Onboarding(app, overlay, () => {
  const status = backend.status;
  if (status) void modelSetup.run(status);
  if (settings.drowsyEnabled) syncDrowsy();
  if (!settings.onboarded) setTimeout(() => welcomePanel.open(), 1500);
});

const settingsReady = window.shell.getSettings().then((s) => {
  applySettings(s);
  if (!eulaAccepted()) onboarding?.open();
  else if (!s.onboarded) setTimeout(() => welcomePanel.open(), 2500);
});
window.shell.onSettingsChanged(applySettings);

// --- backend --------------------------------------------------------------------------
// One-click experience: the first status after connecting starts downloading whatever
// the recommended tier still needs (resumes interrupted downloads too).
const modelSetup = new ModelSetup(overlay, backend, director);
let firstStatusSeen = false;
backend.onConnection((connected) => {
  if (!connected) {
    firstStatusSeen = false;
    toasts.show(t('backend.disconnectedTitle'), [t('backend.reconnecting')], 'error');
  }
});
backend.on('status', (status) => {
  if (firstStatusSeen) return;
  firstStatusSeen = true;
  // The reply to hello. The backend screens the address it was sent: when it keeps another
  // one (normalized, or "" if refused), that is the one in effect, so save it.
  const sent = backend.helloAddress;
  const echoed = status.profile?.address;
  void settingsReady.then(() => {
    if (echoed !== undefined && echoed !== sent && settings.address === sent) {
      backend.address = echoed;
      void app.patchSettings({ address: echoed });
    } else if (echoed !== undefined && echoed !== settings.address) {
      // hello went out before the settings were loaded
      const address = settings.address;
      backend.send({ type: 'set_profile', id: backend.newId('profile'), profile: { address } });
    }
    // Restore drowsiness monitoring if opted in; resume missing downloads (once agreed).
    if (!eulaAccepted()) return;
    if (settings.drowsyEnabled) syncDrowsy();
    if (settings.autoDownloadModels) void modelSetup.run(status);
  });
});
backend.on('voice_presets', (m) => {
  voicePreset ??= voiceForLang(m, getLang());
});
backend.on('drowsy_state', (m) => wake.onDrowsyState(m));
backend.on('drowsy_calibration', (m) => {
  if (m.progress === 0) director.ui.say(t('drowsy.calibrating'), 4000);
  if (m.done) director.ui.say(t('drowsy.ready'), 2500);
});
// Webcam errors come from drowsy_start (fire-and-forget) or mid-session: nothing awaits them.
const DROWSY_ERRORS = new Set(['camera_unavailable', 'camera_lost', 'face_model_failed']);
backend.on('error', (m) => {
  if (DROWSY_ERRORS.has(m.code)) {
    toasts.show(t('drowsy.errorTitle'), [localizeError(m.code, m.message)], 'error');
  }
});
// Notices from the main process (e.g. a saved avatar that failed screening was reset).
window.shell.onNotify((notice) => toasts.show(notice.title, notice.lines, notice.tone));
backend.on('camera_state', (m) => window.shell.setCameraActive(m.active));
window.shell.onIdle((idleMs) => {
  wake.onIdle(idleMs);
  if (settings.drowsyEnabled && backend.connected) {
    backend.send({ type: 'user_activity', last_input_ms: idleMs });
  }
});
void window.shell.getBackendInfo().then((info) => backend.setInfo(info));
window.shell.onBackendChanged((info) => {
  backend.setInfo(info);
  if (info.state === 'failed') {
    toasts.show(t('backend.failedTitle'), [t('backend.failedHint')], 'error');
  }
});

// Scene B: the character brings up due reviews on its own (SPEC 2).
async function reviewReminder(): Promise<void> {
  if (
    !settings.reviewReminders ||
    settings.focusMode ||
    director.busy ||
    !backend.connected ||
    !eulaAccepted()
  )
    return;
  const due = await reviewPanel.dueCount();
  if (due > 0) {
    director.emotion('happy', 0.5);
    director.gesture('point', 1200);
    director.ui.say(t('reminder.say', { n: due }), 5000);
    toasts.show(t('reminder.title'), [t('reminder.cards', { n: due }), t('reminder.how')]);
  }
}

/** The backend's default voice if it speaks `lang`, else the first voice that does. */
function voiceForLang(m: VoicePresets, lang: Lang): string | undefined {
  const voices = m.presets.filter((p) => presetLang(p) === lang);
  return (voices.find((p) => p.preset_id === m.default_preset_id) ?? voices[0])?.preset_id;
}
setTimeout(() => void reviewReminder(), FIRST_REVIEW_CHECK_MS);
setInterval(() => void reviewReminder(), REVIEW_CHECK_MS);

// --- avatar & character ----------------------------------------------------------------
void window.shell.getCurrentAvatar().then((selection) => director.setAvatar(selection));
window.shell.onAvatarChanged((selection) => director.setAvatar(selection));

if (new URLSearchParams(location.search).has('selftest')) {
  void runSelfTest(app, {
    openPanel: (name) => runUiAction(name as UiAction),
    switchLanguage,
    closeOnboarding: () => onboarding?.close(),
  });
}

const diagnostics = new URLSearchParams(location.search);
// Godot prints per-section frame timings to the console (see character/scripts/frame_profiler.gd).
if (diagnostics.has('profile'))
  (window as unknown as { studymateProfile: boolean }).studymateProfile = true;
// `avatar=placeholder` swaps to the chibi fallback once Godot is up (A/B cost checks).
if (diagnostics.get('avatar') === 'placeholder') {
  director.onGodotEvent((e) => {
    if (e.type === 'ready') director.send({ type: 'load_avatar', id: 'placeholder' });
  });
}
if (!diagnostics.has('nogodot')) {
  startGodot(canvas)
    .then((engine) => bridge.attachEngine(engine))
    .catch((err: unknown) => {
      console.error(err);
      hud.showError(err instanceof Error ? err.message : String(err));
    });
}
