import type { Status } from '@studymate/protocol';
import { getLang, onLangChange, t } from '../../shared/i18n';
import { EULA_VERSION, type EulaText } from '../../shared/ipc';
import type { AppContext } from '../app-context';
import { missingForStatus } from '../backend/models';
import { addressField } from './address-field';
import { formatBytes, h, nodes } from './dom';
import { languageField } from './language-select';

const TIER_LABEL = { lite: 'Lite', standard: 'Standard', pro: 'Pro', max: 'Max' } as const;

/**
 * First-run onboarding (and again whenever EULA_VERSION changes): the user picks a
 * language, reads the EULA, optionally tells the character what to call them, sees what
 * will be installed, and agrees. This in-app consent is the acceptance of the EULA (the
 * installer has no license page and the Steam build has no installer); nothing is
 * downloaded and the AI features stay locked until then.
 */
export class Onboarding {
  private readonly el: HTMLElement;
  private readonly body: HTMLElement;
  private readonly footer: HTMLElement;
  private agreed = false;
  private eula: EulaText | null | undefined;
  private eulaLang: string | null = null;

  constructor(
    private readonly app: AppContext,
    parent: HTMLElement,
    /** Called once the user agreed (settings already saved). */
    private readonly onAccepted: () => void,
  ) {
    this.body = h('div', { class: 'onboarding-body' });
    this.footer = h('footer', { class: 'onboarding-footer' });
    this.el = h(
      'section',
      { class: 'onboarding', 'data-hit': true, role: 'dialog', 'aria-modal': 'true', hidden: true },
      this.body,
      this.footer,
    );
    parent.appendChild(this.el);
    onLangChange(() => {
      if (this.isOpen) void this.render();
    });
    app.backend.on('status', () => {
      if (this.isOpen) this.renderFooterAndSummary();
    });
  }

  get isOpen(): boolean {
    return !this.el.hidden;
  }

  open(): void {
    const wasOpen = this.isOpen;
    this.el.hidden = false;
    if (!wasOpen) {
      this.el.classList.remove('pop');
      void this.el.offsetWidth;
      this.el.classList.add('pop');
    }
    void this.render();
  }

  close(): void {
    this.el.hidden = true;
  }

  private async render(): Promise<void> {
    const lang = getLang();
    if (this.eulaLang !== lang) {
      this.eula = undefined;
      this.eulaLang = lang;
      this.draw();
      this.eula = await window.shell.readEula(lang).catch(() => null);
      if (getLang() !== lang) return; // switched again while loading
    }
    this.draw();
  }

  private draw(): void {
    const previous = this.app.settings().eulaAcceptedVersion;
    const eulaBox =
      this.eula === undefined
        ? h('p', { class: 'status' }, t('onboarding.eulaLoading'))
        : this.eula === null
          ? h('p', { class: 'status error' }, t('onboarding.eulaMissing'))
          : h('pre', { class: 'eula-text', lang: this.eula.lang, tabindex: 0 }, this.eula.text);
    this.body.replaceChildren(
      ...nodes(
        h(
          'div',
          { class: 'onboarding-head' },
          h('span', { class: 'onboarding-icon' }, '🌸'),
          h('h2', {}, t('welcome.title')),
        ),
        languageField(this.app),
        previous && previous !== EULA_VERSION
          ? h('p', { class: 'onboarding-note' }, t('onboarding.changed'))
          : h('p', {}, t('onboarding.intro')),
        h('h3', {}, t('onboarding.eula')),
        this.eula && this.eula.lang !== getLang()
          ? h('p', { class: 'hint' }, t('onboarding.eulaFallback'))
          : null,
        eulaBox,
        addressField(this.app, t('onboarding.optional')),
        h('h3', {}, t('onboarding.install')),
        h('div', { class: 'onboarding-install' }),
      ),
    );
    this.renderFooterAndSummary();
  }

  /** Install summary and the agree / quit buttons (they depend on the backend status). */
  private renderFooterAndSummary(): void {
    const status = this.app.backend.status;
    const summary = this.body.querySelector<HTMLElement>('.onboarding-install');
    const missing = status ? missingForStatus(status, getLang()) : [];
    if (summary) summary.replaceChildren(...this.summaryLines(status, missing.length));

    const check = h('input', { type: 'checkbox', checked: this.agreed });
    const start = h(
      'button',
      { class: 'btn primary', type: 'button' },
      t(status && missing.length === 0 ? 'onboarding.startNoInstall' : 'onboarding.start'),
    );
    // Agreeing needs the text on screen and the backend's status (what will be installed).
    const canAgree = (): boolean => this.agreed && Boolean(this.eula) && status !== null;
    start.disabled = !canAgree();
    check.addEventListener('change', () => {
      this.agreed = check.checked;
      start.disabled = !canAgree();
    });
    start.addEventListener('click', () => void this.accept(start));
    const quit = h(
      'button',
      { class: 'btn ghost', type: 'button', onclick: () => window.shell.runAction('quit') },
      t('onboarding.quit'),
    );
    this.footer.replaceChildren(
      h('label', { class: 'toggle onboarding-agree' }, check, h('span', {}, t('onboarding.agree'))),
      h('div', { class: 'row' }, quit, start),
    );
  }

  private summaryLines(status: Status | null, count: number): HTMLElement[] {
    if (!status) return [h('p', { class: 'status' }, t('onboarding.installWaiting'))];
    const missing = missingForStatus(status, getLang());
    const size = missing.reduce((a, m) => a + m.size, 0);
    return [
      h(
        'p',
        {},
        count === 0
          ? t('onboarding.installNone')
          : t('onboarding.installSummary', {
              tier: TIER_LABEL[status.tier],
              n: count,
              size: formatBytes(size),
            }),
      ),
      h('p', { class: 'hint' }, t('onboarding.installLocal')),
    ];
  }

  private async accept(button: HTMLButtonElement): Promise<void> {
    button.disabled = true;
    await this.app.patchSettings({
      eulaAcceptedVersion: EULA_VERSION,
      eulaAcceptedAt: new Date().toISOString(),
    });
    this.close();
    this.onAccepted();
  }
}
