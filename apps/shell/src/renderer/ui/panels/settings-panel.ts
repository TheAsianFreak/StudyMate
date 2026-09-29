import type { GpuUse, ModelInfo, Tier, VoicePreset } from '@studymate/protocol';
import { getLang, localeTag, onLangChange, t, type PlainKey } from '../../../shared/i18n';
import type { ShellSettings } from '../../../shared/ipc';
import type { AppContext } from '../../app-context';
import { errorText } from '../../backend/client';
import { missingModels, presetLang, servesLang } from '../../backend/models';
import { addressField } from '../address-field';
import { clear, formatBytes, h } from '../dom';
import { languageField } from '../language-select';
import { Panel } from '../panel';

type Tab = 'general' | 'voice' | 'drowsy' | 'character' | 'models';

const TABS: [Tab, PlainKey][] = [
  ['general', 'settings.tab.general'],
  ['voice', 'settings.tab.voice'],
  ['drowsy', 'settings.tab.drowsy'],
  ['character', 'settings.tab.character'],
  ['models', 'settings.tab.models'],
];

const TIER_LABEL: Record<Tier, string> = {
  lite: 'Lite',
  standard: 'Standard',
  pro: 'Pro',
  max: 'Max',
};
const GPU_USES: GpuUse[] = ['high', 'balanced', 'low'];

interface Slider {
  key: keyof VoicePreset;
  label: PlainKey;
  min: number;
  max: number;
  step: number;
  /** Unit shown after the value; a message key when it is a word. */
  unit: PlainKey | '×' | 'dB' | '';
}

const VOICE_SLIDERS: Slider[] = [
  {
    key: 'pitch_semitones',
    label: 'voice.slider.pitch',
    min: -12,
    max: 12,
    step: 0.5,
    unit: 'voice.unit.semitone',
  },
  {
    key: 'formant_ratio',
    label: 'voice.slider.formant',
    min: 0.7,
    max: 1.4,
    step: 0.01,
    unit: '×',
  },
  { key: 'speed', label: 'voice.slider.speed', min: 0.5, max: 2, step: 0.05, unit: '×' },
  {
    key: 'brightness_db',
    label: 'voice.slider.brightness',
    min: -12,
    max: 12,
    step: 0.5,
    unit: 'dB',
  },
  { key: 'warmth_db', label: 'voice.slider.warmth', min: -12, max: 12, step: 0.5, unit: 'dB' },
  { key: 'reverb', label: 'voice.slider.reverb', min: 0, max: 1, step: 0.05, unit: '' },
  { key: 'volume_db', label: 'voice.slider.volume', min: -24, max: 12, step: 0.5, unit: 'dB' },
];

export class SettingsPanel {
  private readonly panel: Panel;
  private readonly tabs: HTMLElement;
  private readonly content: HTMLElement;
  private tab: Tab = 'general';
  private readonly downloads = new Map<string, number>();

  constructor(private readonly app: AppContext) {
    this.panel = new Panel(app.overlay, { title: 'settings.title', icon: '⚙️', width: 460 });
    this.tabs = h('nav', { class: 'tabs' });
    this.renderTabs();
    this.content = h('div', { class: 'tab-content' });
    this.panel.body.append(this.tabs, this.content);
    app.backend.on('download_progress', (m) => {
      this.downloads.set(m.model_id, m.done ? 1 : m.total ? m.downloaded / m.total : 0);
      if (this.tab === 'models' && this.panel.isOpen) this.show('models');
    });
    app.backend.on('status', () => {
      if (this.tab === 'models' && this.panel.isOpen) this.show('models');
    });
    onLangChange(() => {
      this.renderTabs();
      if (this.panel.isOpen) this.show(this.tab);
    });
  }

  open(tab: Tab = this.tab): void {
    this.panel.open();
    this.show(tab);
  }

  private renderTabs(): void {
    this.tabs.replaceChildren(
      ...TABS.map(([id, label]) =>
        h(
          'button',
          { class: 'tab', type: 'button', 'data-tab': id, onclick: () => this.show(id) },
          t(label),
        ),
      ),
    );
  }

  private show(tab: Tab): void {
    this.tab = tab;
    this.tabs
      .querySelectorAll('.tab')
      .forEach((b) => b.classList.toggle('active', (b as HTMLElement).dataset['tab'] === tab));
    clear(this.content);
    ({
      general: () => this.general(),
      voice: () => void this.voice(),
      drowsy: () => this.drowsy(),
      character: () => this.character(),
      models: () => this.models(),
    })[tab]();
  }

  private toggle(key: keyof ShellSettings, label: PlainKey, hint?: PlainKey): HTMLElement {
    const s = this.app.settings();
    const input = h('input', { type: 'checkbox', checked: Boolean(s[key]) });
    input.addEventListener('change', () => void this.app.patchSettings({ [key]: input.checked }));
    return h(
      'label',
      { class: 'toggle' },
      input,
      h('span', {}, t(label)),
      hint ? h('small', {}, t(hint)) : null,
    );
  }

  private general(): void {
    this.content.append(
      languageField(this.app, true),
      addressField(this.app),
      this.toggle('wander', 'settings.wander'),
      this.toggle('conversationAutoListen', 'settings.autoListen', 'settings.autoListenHint'),
      this.toggle('reviewReminders', 'settings.reviewReminders', 'settings.reviewRemindersHint'),
      this.toggle('focusMode', 'settings.focusMode', 'settings.focusModeHint'),
      this.toggle('autoDownloadModels', 'settings.autoDownload', 'settings.autoDownloadHint'),
      h(
        'div',
        { class: 'shortcuts' },
        h('h3', {}, t('settings.shortcuts')),
        h('p', {}, h('kbd', {}, 'Ctrl+Shift+S'), t('settings.shortcut.capture')),
        h('p', {}, h('kbd', {}, 'Ctrl+Shift+Space'), t('settings.shortcut.talk')),
        h('p', {}, h('kbd', {}, 'Ctrl+Alt+Q'), t('settings.shortcut.quit')),
        h('p', {}, t('settings.shortcut.mouse')),
      ),
    );
  }

  private async voice(): Promise<void> {
    const box = this.content;
    box.append(h('p', { class: 'status' }, t('common.loading')));
    let allPresets: VoicePreset[];
    let defaultId: string;
    try {
      const reply = await this.app.backend.request(
        { type: 'voice_presets_get', id: this.app.backend.newId('vp') },
        'voice_presets',
      );
      allPresets = reply.presets;
      defaultId = reply.default_preset_id;
    } catch (err) {
      clear(box);
      box.append(h('p', { class: 'status error' }, errorText(err)));
      return;
    }
    if (this.tab !== 'voice') return;
    clear(box);
    // Only voices that speak the current language.
    const lang = getLang();
    const presets = allPresets.filter((p) => presetLang(p) === lang);
    if (presets.length === 0) {
      box.append(h('p', { class: 'status' }, t('voice.none')));
      return;
    }
    const current =
      [this.app.voice(), defaultId].find((id) => presets.some((p) => p.preset_id === id)) ??
      presets[0]!.preset_id;
    const select = h(
      'select',
      { class: 'field' },
      ...presets.map((p) =>
        h(
          'option',
          { value: p.preset_id, selected: p.preset_id === current },
          `${p.name}${p.builtin ? '' : t('voice.mine')}`,
        ),
      ),
    );
    const editor = h('div', { class: 'voice-editor' });
    let working: VoicePreset = structuredClone(
      presets.find((p) => p.preset_id === current) ?? presets[0]!,
    );

    const renderEditor = (): void => {
      clear(editor);
      for (const s of VOICE_SLIDERS) {
        const value = h('output', {}, fmt(working[s.key] as number, s));
        const input = h('input', {
          type: 'range',
          min: s.min,
          max: s.max,
          step: s.step,
          value: String(working[s.key]),
        });
        input.addEventListener('input', () => {
          (working as unknown as Record<string, number>)[s.key] = Number(input.value);
          value.textContent = fmt(Number(input.value), s);
        });
        editor.append(h('label', { class: 'slider' }, h('span', {}, t(s.label)), input, value));
      }
    };
    renderEditor();
    select.addEventListener('change', () => {
      working = structuredClone(presets.find((p) => p.preset_id === select.value)!);
      this.app.setVoice(select.value);
      renderEditor();
    });

    const preview = h('button', { class: 'btn', type: 'button' }, t('voice.preview'));
    preview.addEventListener('click', async () => {
      preview.disabled = true;
      try {
        const reply = await this.app.backend.request(
          {
            type: 'tts_request',
            id: this.app.backend.newId('pv'),
            text: t('voice.previewText'),
            preset: working,
          },
          'tts_audio',
        );
        const voice = await this.app.timeline.audio.decodeWav(reply.wav_base64);
        await this.app.timeline.audio.play(voice).done;
      } catch (err) {
        this.app.toasts.show(t('voice.previewFailed'), [errorText(err)], 'error');
      } finally {
        preview.disabled = false;
      }
    });
    const name = h('input', {
      class: 'field',
      placeholder: t('voice.namePlaceholder'),
      value: working.builtin ? '' : working.name,
    });
    const save = h('button', { class: 'btn primary', type: 'button' }, t('voice.save'));
    save.addEventListener('click', async () => {
      const label =
        name.value.trim() ||
        t('voice.defaultName', { date: new Date().toLocaleDateString(localeTag()) });
      const preset: VoicePreset = {
        ...working,
        builtin: false,
        // Every character voice is female now; user voices are saved as such too.
        gender: 'female',
        // A copy keeps speaking the language of the voice it was made from.
        lang: presetLang(working),
        name: label,
        preset_id: working.builtin ? `user_${Date.now().toString(36)}` : working.preset_id,
      };
      try {
        await this.app.backend.request(
          {
            type: 'voice_preset_save',
            id: this.app.backend.newId('vs'),
            preset,
            make_default: true,
          },
          'voice_presets',
        );
        this.app.setVoice(preset.preset_id);
        this.app.toasts.show(t('voice.saved'), [t('voice.savedDetail', { name: label })]);
        this.show('voice');
      } catch (err) {
        this.app.toasts.show(t('voice.saveFailed'), [errorText(err)], 'error');
      }
    });
    const del = h(
      'button',
      { class: 'btn ghost', type: 'button', disabled: working.builtin },
      t('common.delete'),
    );
    del.addEventListener('click', async () => {
      if (working.builtin) return;
      await this.app.backend.request(
        {
          type: 'voice_preset_delete',
          id: this.app.backend.newId('vd'),
          preset_id: working.preset_id,
        },
        'voice_presets',
      );
      this.app.setVoice(defaultId);
      this.show('voice');
    });
    box.append(
      h('label', {}, t('voice.type'), select),
      h('p', { class: 'hint' }, t('voice.hint')),
      editor,
      h('div', { class: 'row' }, preview, del),
      h('div', { class: 'row' }, name, save),
    );
  }

  private drowsy(): void {
    const s = this.app.settings();
    const enabled = h('input', { type: 'checkbox', checked: s.drowsyEnabled });
    enabled.addEventListener(
      'change',
      () => void this.app.patchSettings({ drowsyEnabled: enabled.checked }),
    );
    const sens = h(
      'select',
      { class: 'field' },
      h('option', { value: 'low', selected: s.drowsySensitivity === 'low' }, t('drowsy.sens.low')),
      h(
        'option',
        { value: 'normal', selected: s.drowsySensitivity === 'normal' },
        t('drowsy.sens.normal'),
      ),
      h(
        'option',
        { value: 'high', selected: s.drowsySensitivity === 'high' },
        t('drowsy.sens.high'),
      ),
    );
    sens.addEventListener(
      'change',
      () =>
        void this.app.patchSettings({
          drowsySensitivity: sens.value as ShellSettings['drowsySensitivity'],
        }),
    );
    const intensity = h(
      'select',
      { class: 'field' },
      h(
        'option',
        { value: 'soft', selected: s.wakeIntensity === 'soft' },
        t('drowsy.intensity.soft'),
      ),
      h(
        'option',
        { value: 'normal', selected: s.wakeIntensity === 'normal' },
        t('drowsy.intensity.normal'),
      ),
      h(
        'option',
        { value: 'hard', selected: s.wakeIntensity === 'hard' },
        t('drowsy.intensity.hard'),
      ),
    );
    intensity.addEventListener(
      'change',
      () =>
        void this.app.patchSettings({
          wakeIntensity: intensity.value as ShellSettings['wakeIntensity'],
        }),
    );
    const test = h(
      'button',
      { class: 'btn', type: 'button', onclick: () => this.app.wake.test() },
      t('drowsy.preview'),
    );
    this.content.append(
      h(
        'div',
        { class: 'privacy' },
        h('strong', {}, t('drowsy.privacyTitle')),
        h('p', {}, t('drowsy.privacy')),
      ),
      h('label', { class: 'toggle' }, enabled, h('span', {}, t('drowsy.enable'))),
      h('label', {}, t('drowsy.sensitivity'), sens),
      h('label', {}, t('drowsy.intensity'), intensity),
      h('p', { class: 'hint' }, t('drowsy.howItWorks')),
      test,
    );
  }

  private character(): void {
    this.content.append(
      h('p', {}, t('character.default')),
      h(
        'div',
        { class: 'row' },
        h(
          'button',
          {
            class: 'btn primary',
            type: 'button',
            onclick: () => window.shell.runAction('importAvatar'),
          },
          t('character.import'),
        ),
        h(
          'button',
          { class: 'btn', type: 'button', onclick: () => window.shell.runAction('resetAvatar') },
          t('character.reset'),
        ),
      ),
      h('p', { class: 'hint' }, t('character.hint')),
    );
  }

  private models(): void {
    const status = this.app.backend.status;
    if (!status) {
      this.content.append(h('p', { class: 'status' }, t('models.waiting')));
      return;
    }
    const hw = status.hardware;
    const tier = h(
      'select',
      { class: 'field' },
      ...(['lite', 'standard', 'pro', 'max'] as Tier[]).map((tr) =>
        h(
          'option',
          { value: tr, selected: status.tier === tr },
          `${TIER_LABEL[tr]}${hw.recommended_tier === tr ? t('models.recommended') : ''}`,
        ),
      ),
    );
    tier.addEventListener('change', () =>
      this.app.backend.send({
        type: 'set_tier',
        id: this.app.backend.newId('tier'),
        tier: tier.value as Tier,
      }),
    );
    const current = status.gpu_use ?? 'high';
    const gpuUse = h(
      'select',
      { class: 'field' },
      ...GPU_USES.map((g) =>
        h('option', { value: g, selected: current === g }, t(`models.gpuUse.${g}`)),
      ),
    );
    gpuUse.addEventListener('change', () =>
      this.app.backend.send({
        type: 'set_gpu_use',
        id: this.app.backend.newId('gpu'),
        gpu_use: gpuUse.value as GpuUse,
      }),
    );
    const gpus = hw.gpus.map((g) => `${g.name} (${g.vram_gb}GB)`).join(', ') || t('models.noGpu');
    // Models of other languages (e.g. another language's voice) are listed apart, folded.
    const lang = getLang();
    const mine = status.models.filter((m) => servesLang(m, lang));
    const others = status.models.filter((m) => !servesLang(m, lang));
    this.content.append(
      h(
        'div',
        { class: 'hw' },
        h('p', {}, t('models.cpu', { cpu: hw.cpu, cores: hw.cores, ram: hw.ram_gb })),
        h('p', {}, t('models.gpu', { gpus })),
        h('p', { class: 'hint' }, hw.reason),
      ),
      h('label', {}, t('models.tier'), tier),
      h('label', {}, t('models.gpuUse'), gpuUse),
      h('p', { class: 'hint' }, t('models.gpuUseHint')),
      this.recommendedButton(status.models, status.tier),
      h('div', { class: 'model-list' }, ...mine.map((m) => this.modelRow(m, status.tier))),
    );
    if (others.length > 0) {
      this.content.append(
        h(
          'details',
          { class: 'model-others' },
          h('summary', {}, t('models.otherLangs', { n: others.length })),
          h('div', { class: 'model-list' }, ...others.map((m) => this.modelRow(m, status.tier))),
        ),
      );
    }
  }

  /** Downloads every missing model the current tier and language need, one after another. */
  private recommendedButton(models: ModelInfo[], tier: Tier): HTMLElement {
    const missing = missingModels(models, tier, getLang());
    if (missing.length === 0) return h('p', { class: 'hint' }, t('models.allInstalled'));
    // Installing needs the EULA consent first (onboarding).
    if (!this.app.eulaAccepted()) {
      return h(
        'div',
        { class: 'privacy' },
        h('p', {}, t('models.needsEula')),
        h(
          'button',
          { class: 'btn primary', type: 'button', onclick: () => this.app.openOnboarding() },
          t('models.openOnboarding'),
        ),
      );
    }
    const total = missing.reduce((a, m) => a + m.size, 0);
    const btn = h(
      'button',
      { class: 'btn primary', type: 'button' },
      t('models.downloadAll', { size: formatBytes(total) }),
    );
    btn.addEventListener('click', async () => {
      btn.setAttribute('disabled', '');
      for (const m of missing) {
        this.downloads.set(m.model_id, 0);
        try {
          await this.app.backend.request(
            { type: 'download_model', id: this.app.backend.newId('dl'), model_id: m.model_id },
            'status',
            undefined,
            6 * 3600_000,
          );
        } catch (err) {
          this.app.toasts.show(t('models.downloadFailed'), [m.title, errorText(err)], 'error');
          break;
        } finally {
          this.downloads.delete(m.model_id);
        }
      }
      if (this.tab === 'models' && this.panel.isOpen) this.show('models');
    });
    return btn;
  }

  private modelRow(m: ModelInfo, tier: Tier): HTMLElement {
    const progress = this.downloads.get(m.model_id);
    let action: HTMLElement;
    if (m.installed) {
      action = h('span', { class: 'installed' }, t('models.installed'));
    } else if (progress !== undefined && progress < 1) {
      action = h(
        'span',
        { class: 'progress small' },
        h('span', { style: `width:${(progress * 100).toFixed(0)}%` }),
      );
    } else if (!this.app.eulaAccepted()) {
      action = h('span', {}); // no installs before the EULA consent (see recommendedButton)
    } else {
      action = h('button', { class: 'btn small', type: 'button' }, t('models.get'));
      action.addEventListener('click', () => {
        this.downloads.set(m.model_id, 0);
        this.app.backend
          .request(
            { type: 'download_model', id: this.app.backend.newId('dl'), model_id: m.model_id },
            'status',
            undefined,
            6 * 3600_000,
          )
          .catch((err: unknown) =>
            this.app.toasts.show(t('models.downloadFailed'), [errorText(err)], 'error'),
          )
          .finally(() => this.downloads.delete(m.model_id));
        this.show('models');
      });
    }
    const forTier = m.tiers.includes(tier);
    return h(
      'div',
      { class: `model ${forTier ? 'for-tier' : ''}` },
      h(
        'div',
        {},
        h('strong', {}, m.title),
        h(
          'small',
          {},
          ` ${formatBytes(m.size)} · ${m.license}${m.required ? t('models.required') : ''}${forTier ? t('models.currentTier') : ''}`,
        ),
      ),
      action,
    );
  }
}

function fmt(v: number, s: Slider): string {
  const digits = s.step < 0.1 ? 2 : s.step < 1 ? 1 : 0;
  const unit = s.unit === '×' || s.unit === 'dB' || s.unit === '' ? s.unit : t(s.unit);
  return `${v > 0 && s.unit !== '×' && s.unit !== '' ? '+' : ''}${v.toFixed(digits)}${unit ? ` ${unit}` : ''}`;
}
