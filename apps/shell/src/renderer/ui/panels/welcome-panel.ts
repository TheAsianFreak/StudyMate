import { onLangChange, t } from '../../../shared/i18n';
import type { AppContext } from '../../app-context';
import { h, nodes } from '../dom';
import { Panel } from '../panel';

/**
 * First-run introduction after the onboarding (EULA consent): shortcuts, model check,
 * webcam opt-in (off by default).
 */
export class WelcomePanel {
  private readonly panel: Panel;

  constructor(
    private readonly app: AppContext,
    private readonly openModels: () => void,
  ) {
    this.panel = new Panel(app.overlay, { title: 'welcome.title', icon: '🌸', width: 440 });
    onLangChange(() => {
      if (this.panel.isOpen) this.open();
    });
  }

  open(): void {
    const caps = this.app.backend.status?.capabilities;
    const missing = caps && !caps.solve;
    const body = this.panel.body;
    body.replaceChildren(
      ...nodes(
        h('p', {}, t('welcome.intro')),
        h(
          'ul',
          { class: 'welcome-list' },
          h('li', {}, h('kbd', {}, 'Ctrl+Shift+S'), t('welcome.capture')),
          h('li', {}, h('kbd', {}, 'Ctrl+Shift+Space'), t('welcome.talk')),
          h('li', {}, t('welcome.mouse')),
          h('li', {}, h('kbd', {}, 'Ctrl+Alt+Q'), t('welcome.quit')),
        ),
        missing
          ? h(
              'div',
              { class: 'privacy' },
              h('strong', {}, t('welcome.needModels')),
              h('p', {}, t('welcome.needModelsHint')),
              h(
                'button',
                { class: 'btn primary', type: 'button', onclick: () => this.openModels() },
                t('welcome.openModels'),
              ),
            )
          : null,
        h(
          'div',
          { class: 'privacy' },
          h('strong', {}, t('welcome.drowsyTitle')),
          h('p', {}, t('welcome.drowsyHint')),
          h(
            'div',
            { class: 'row' },
            h(
              'button',
              { class: 'btn', type: 'button', onclick: () => void this.finish(true) },
              t('welcome.enableDrowsy'),
            ),
            h(
              'button',
              { class: 'btn primary', type: 'button', onclick: () => void this.finish(false) },
              t('welcome.later'),
            ),
          ),
        ),
      ),
    );
    this.panel.open();
  }

  private async finish(drowsy: boolean): Promise<void> {
    await this.app.patchSettings({ onboarded: true, drowsyEnabled: drowsy });
    this.panel.close();
    this.app.director.ui.say(t(drowsy ? 'welcome.byeDrowsy' : 'welcome.bye'), 3000);
  }
}
