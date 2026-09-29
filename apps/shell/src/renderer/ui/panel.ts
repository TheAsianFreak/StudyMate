import { onLangChange, t, type PlainKey } from '../../shared/i18n';
import { h } from './dom';

export interface PanelOptions {
  /** Title message; the header follows language switches. */
  title: PlainKey;
  icon: string;
  width?: number;
}

/**
 * Game-style floating window (sticker outline, pastel header). Draggable by its header.
 * Marked data-hit so the overlay captures input while the pointer is over it.
 */
export class Panel {
  readonly el: HTMLElement;
  readonly body: HTMLElement;
  private readonly onCloseListeners = new Set<() => void>();

  constructor(
    private readonly parent: HTMLElement,
    opts: PanelOptions,
  ) {
    const close = h(
      'button',
      { class: 'panel-close', type: 'button', 'aria-label': t('common.close') },
      '×',
    );
    const title = h('h2', {}, t(opts.title));
    const header = h(
      'header',
      { class: 'panel-header' },
      h('span', { class: 'panel-icon' }, opts.icon),
      title,
      close,
    );
    onLangChange(() => {
      title.textContent = t(opts.title);
      close.setAttribute('aria-label', t('common.close'));
    });
    this.body = h('div', { class: 'panel-body' });
    this.el = h('section', { class: 'panel', 'data-hit': true, role: 'dialog' }, header, this.body);
    this.el.style.width = `${opts.width ?? 380}px`;
    close.addEventListener('click', () => this.close());
    this.makeDraggable(header);
  }

  get isOpen(): boolean {
    return this.el.isConnected;
  }

  open(): void {
    if (!this.isOpen) {
      this.parent.appendChild(this.el);
      const w = this.el.offsetWidth;
      const x = Math.max(16, window.innerWidth - w - 48 - Math.random() * 40);
      const y = Math.max(16, window.innerHeight * 0.12 + Math.random() * 30);
      this.el.style.left = `${x}px`;
      this.el.style.top = `${y}px`;
    }
    this.el.classList.remove('pop');
    void this.el.offsetWidth;
    this.el.classList.add('pop');
  }

  close(): void {
    if (!this.isOpen) return;
    this.el.remove();
    for (const l of this.onCloseListeners) l();
  }

  onClose(listener: () => void): void {
    this.onCloseListeners.add(listener);
  }

  private makeDraggable(handle: HTMLElement): void {
    let start: { x: number; y: number; left: number; top: number } | null = null;
    handle.addEventListener('pointerdown', (e) => {
      if ((e.target as HTMLElement).closest('button')) return;
      start = { x: e.clientX, y: e.clientY, left: this.el.offsetLeft, top: this.el.offsetTop };
      handle.setPointerCapture(e.pointerId);
    });
    handle.addEventListener('pointermove', (e) => {
      if (!start) return;
      const left = Math.min(Math.max(start.left + e.clientX - start.x, 0), window.innerWidth - 80);
      const top = Math.min(Math.max(start.top + e.clientY - start.y, 0), window.innerHeight - 40);
      this.el.style.left = `${left}px`;
      this.el.style.top = `${top}px`;
    });
    handle.addEventListener('pointerup', () => (start = null));
  }
}
