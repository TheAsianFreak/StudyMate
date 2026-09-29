import { onLangChange, t, type PlainKey } from '../../shared/i18n';
import type { UiAction } from '../../shared/ipc';
import type { Director } from '../director/director';
import { h } from './dom';

const SHOW_DELAY_MS = 350;
const HIDE_DELAY_MS = 1200;

const BUTTONS: [UiAction, string, PlainKey][] = [
  ['capture', '📷', 'dock.capture'],
  ['talk', '🎤', 'dock.talk'],
  ['ask', '💬', 'dock.ask'],
  ['quiz', '✏️', 'dock.quiz'],
  ['review', '🔁', 'dock.review'],
  ['notes', '📒', 'dock.notes'],
  ['docs', '📚', 'dock.docs'],
  ['settings', '⚙️', 'dock.settings'],
];

/**
 * Round sticker buttons that pop up beside the character when the pointer rests on it
 * — the quick way into every feature without the tray menu.
 */
export class Dock {
  private readonly el: HTMLElement;
  private showTimer: ReturnType<typeof setTimeout> | null = null;
  private hideTimer: ReturnType<typeof setTimeout> | null = null;
  private overDock = false;

  constructor(
    parent: HTMLElement,
    private readonly director: Director,
    onAction: (action: UiAction) => void,
  ) {
    this.el = h('nav', { class: 'dock', 'data-hit': true, hidden: true });
    const labelled: [HTMLButtonElement, PlainKey][] = [];
    for (const [action, icon, label] of BUTTONS) {
      const button = h(
        'button',
        {
          class: 'dock-btn',
          type: 'button',
          title: t(label),
          'aria-label': t(label),
          onclick: () => {
            this.hide();
            onAction(action);
          },
        },
        icon,
      );
      labelled.push([button, label]);
      this.el.append(button);
    }
    onLangChange(() => {
      for (const [button, label] of labelled) {
        button.title = t(label);
        button.setAttribute('aria-label', t(label));
      }
    });
    this.el.addEventListener('pointerenter', () => (this.overDock = true));
    this.el.addEventListener('pointerleave', () => {
      this.overDock = false;
      this.scheduleHide();
    });
    parent.appendChild(this.el);
  }

  /** Called with the pointer position (window CSS px) whenever it moves. */
  pointer(x: number, y: number): void {
    const over = this.director.hitTest(x, y) && this.director.state !== 'dragging';
    if (over) {
      if (this.hideTimer) clearTimeout(this.hideTimer);
      this.hideTimer = null;
      if (this.el.hidden && !this.showTimer) {
        this.showTimer = setTimeout(() => {
          this.showTimer = null;
          this.show();
        }, SHOW_DELAY_MS);
      }
    } else {
      if (this.showTimer) clearTimeout(this.showTimer);
      this.showTimer = null;
      if (!this.el.hidden && !this.overDock) this.scheduleHide();
    }
  }

  private show(): void {
    const r = this.director.hitRect;
    if (!r) return;
    this.el.hidden = false;
    const w = this.el.offsetWidth;
    const hgt = this.el.offsetHeight;
    const right = r.x + r.w + 8;
    const x = right + w < window.innerWidth - 8 ? right : Math.max(8, r.x - w - 8);
    const y = Math.min(Math.max(r.y + r.h / 2 - hgt / 2, 8), window.innerHeight - hgt - 8);
    this.el.style.transform = `translate(${x}px, ${y}px)`;
    this.el.classList.remove('pop');
    void this.el.offsetWidth;
    this.el.classList.add('pop');
  }

  private scheduleHide(): void {
    if (this.hideTimer) return;
    this.hideTimer = setTimeout(() => {
      this.hideTimer = null;
      if (!this.overDock) this.hide();
    }, HIDE_DELAY_MS);
  }

  private hide(): void {
    this.el.hidden = true;
  }
}
