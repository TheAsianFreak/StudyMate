import { onLangChange, t } from '../../../shared/i18n';
import type { AppContext } from '../../app-context';
import { h, tex } from '../dom';
import { Panel } from '../panel';

/** Typed questions / "solve this" input, plus a mic button for voice conversation. */
export class AskPanel {
  private readonly panel: Panel;
  private readonly input: HTMLTextAreaElement;
  private readonly log: HTMLElement;
  private readonly controls: HTMLElement;

  constructor(private readonly app: AppContext) {
    this.panel = new Panel(app.overlay, { title: 'ask.title', icon: '💬', width: 380 });
    this.input = h('textarea', { class: 'ask-input', rows: 3, placeholder: t('ask.placeholder') });
    this.input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        void this.send('ask');
      }
    });
    this.log = h('div', { class: 'ask-log' });
    this.controls = h('div');
    this.renderControls();
    this.panel.body.append(this.log, this.input, this.controls);
    // The conversation log stays; labels and the topic bar follow the language.
    onLangChange(() => {
      this.renderControls();
      this.showTopic();
    });
  }

  open(): void {
    this.panel.open();
    this.showTopic();
    this.input.focus();
  }

  private renderControls(): void {
    this.controls.replaceChildren(
      h(
        'div',
        { class: 'row' },
        h(
          'button',
          { class: 'btn primary', type: 'button', onclick: () => void this.send('ask') },
          t('ask.send'),
        ),
        h(
          'button',
          { class: 'btn', type: 'button', onclick: () => void this.send('solve') },
          t('ask.solve'),
        ),
        h(
          'button',
          {
            class: 'btn mic',
            type: 'button',
            title: t('ask.mic'),
            onclick: () => this.app.conversation.toggle(),
          },
          '🎤',
        ),
      ),
      h('p', { class: 'hint' }, t('ask.keys')),
    );
  }

  /** Shows which problem follow-up questions refer to (with a way to drop it). */
  private showTopic(): void {
    this.panel.body.querySelector('.ask-topic')?.remove();
    const topic = this.app.conversation.currentTopic();
    if (!topic) {
      this.input.placeholder = t('ask.placeholder');
      return;
    }
    this.input.placeholder = t('ask.placeholderTopic');
    const clear = h('button', { class: 'btn small ghost', type: 'button' }, t('ask.otherQuestion'));
    const bar = h('div', { class: 'ask-topic' }, h('span', {}, '📌 '), tex(topic.label), clear);
    clear.addEventListener('click', () => {
      this.app.conversation.clearTopic();
      this.showTopic();
    });
    this.panel.body.prepend(bar);
  }

  addTurn(role: 'user' | 'assistant', text: string): void {
    this.log.append(h('p', { class: `turn ${role}` }, text));
    while (this.log.childElementCount > 30) this.log.firstElementChild?.remove();
    this.log.scrollTop = this.log.scrollHeight;
  }

  private async send(kind: 'ask' | 'solve'): Promise<void> {
    const text = this.input.value.trim();
    if (!text) return;
    this.input.value = '';
    this.addTurn('user', text);
    if (kind === 'solve') await this.app.solve.solveText(text);
    else await this.app.conversation.ask(text);
  }
}
