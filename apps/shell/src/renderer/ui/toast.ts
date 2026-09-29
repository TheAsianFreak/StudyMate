import { t } from '../../shared/i18n';

const TOAST_MS = 9000;

/** Stack of dismissable notification cards in the bottom-right corner. */
export class Toasts {
  private readonly el: HTMLElement;

  constructor(parent: HTMLElement) {
    this.el = document.createElement('div');
    this.el.className = 'toasts';
    parent.appendChild(this.el);
  }

  show(title: string, lines: string[], tone: 'info' | 'error' = 'info'): void {
    const card = document.createElement('section');
    card.className = `toast toast-${tone}`;
    card.dataset['hit'] = '';

    const heading = document.createElement('h2');
    heading.textContent = title;
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'toast-close';
    close.textContent = '×';
    close.setAttribute('aria-label', t('common.close'));
    close.addEventListener('click', () => card.remove());
    heading.appendChild(close);
    card.appendChild(heading);

    for (const line of lines) {
      const p = document.createElement('p');
      p.textContent = line;
      card.appendChild(p);
    }
    this.el.appendChild(card);
    setTimeout(() => card.remove(), TOAST_MS);
  }
}
