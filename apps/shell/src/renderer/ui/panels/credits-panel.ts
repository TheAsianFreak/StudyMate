import notices from '../../../../../../THIRD_PARTY_NOTICES.md?raw';
import { getLang, onLangChange, PRODUCT_NAME, t } from '../../../shared/i18n';
import type { AppContext } from '../../app-context';
import { h, nodes } from '../dom';
import { Panel } from '../panel';

const TSUKUYOMI_SITE = 'https://tyc.rei-yumesaki.net/';
const TSUKUYOMI_TERMS = 'https://tyc.rei-yumesaki.net/material/avatar/3d-a/';

/** About / credits / open-source notices / EULA (SPEC P0: 오픈소스 고지 화면). */
export class CreditsPanel {
  private readonly panel: Panel;

  constructor(private readonly app: AppContext) {
    this.panel = new Panel(app.overlay, { title: 'credits.title', icon: 'ℹ️', width: 520 });
    this.render();
    onLangChange(() => this.render());
  }

  open(): void {
    this.panel.open();
  }

  private render(): void {
    const lang = getLang();
    const eula = h('button', { class: 'btn', type: 'button' }, t('credits.eula'));
    eula.addEventListener('click', async () => {
      if (!(await window.shell.openEula())) {
        this.app.toasts.show(t('credits.eulaMissing'), [], 'error');
      }
    });
    this.panel.body.replaceChildren(
      ...nodes(
        h('h3', {}, PRODUCT_NAME),
        h('p', {}, t('credits.tagline')),
        h('div', { class: 'row' }, eula),
        h(
          'section',
          { class: 'credit' },
          h('h3', {}, t('credits.character')),
          // Credit required by the Tsukuyomi-chan 3D model Type A terms (app template). The
          // Japanese lines are the official wording and stay verbatim in every language.
          lang === 'ja' ? null : h('p', {}, t('credits.usesCharacter')),
          h(
            'p',
            { lang: 'ja' },
            '本ソフトウェアでは、フリー素材キャラクター「つくよみちゃん」（© Rei Yumesaki）を使用しています。',
          ),
          h('p', { lang: 'ja' }, `■つくよみちゃん公式サイト ${TSUKUYOMI_SITE}`),
          h('p', {}, '3D Character by Rei Yumesaki — 「つくよみちゃん公式3Dモデル タイプA」'),
          h('p', {}, t('credits.modelTerms')),
          // Obligation the terms put on users who publish what they make with the character.
          h('p', { class: 'duty' }, t('credits.publishDuty')),
          h('p', {}, t('credits.termsUrl', { url: TSUKUYOMI_TERMS })),
          h('p', { class: 'hint' }, t('credits.unofficial')),
        ),
        h(
          'section',
          { class: 'credit' },
          h('h3', {}, t('credits.voices')),
          h('p', {}, t('credits.voicesText')),
          // CC BY 3.0 attribution for the recordings three Japanese Kokoro voices were trained on.
          h(
            'p',
            { lang: 'ja' },
            '音声 © テレビ西日本 (https://www.tnc.co.jp/forchildren/roudoku), CC BY 3.0',
          ),
        ),
        h(
          'section',
          { class: 'credit' },
          h('h3', {}, t('credits.licenses')),
          lang === 'ko' ? null : h('p', { class: 'hint' }, t('credits.licensesNote')),
          h('pre', { class: 'notices', lang: 'ko' }, notices),
        ),
      ),
    );
  }
}
