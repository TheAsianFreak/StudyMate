/**
 * Keeps the window click-through except where the pointer is over something we own.
 * The pointer position comes from the main process (cursor polling) and from DOM
 * mousemove while the window is interactive.
 * Elements that should receive input are marked with `data-hit`.
 */
export class ClickThrough {
  interactive = false;
  last: { x: number; y: number } | null = null;
  moves = 0;
  private readonly pointerListeners = new Set<(x: number, y: number) => void>();

  constructor(private readonly isOverCharacter: (x: number, y: number) => boolean) {
    window.addEventListener('mousemove', (e) => this.pointerAt(e.clientX, e.clientY));
    window.shell.onCursor((x, y) => this.pointerAt(x, y));
  }

  onPointer(listener: (x: number, y: number) => void): void {
    this.pointerListeners.add(listener);
  }

  private pointerAt(x: number, y: number): void {
    this.last = { x, y };
    this.moves++;
    this.refresh();
    for (const l of this.pointerListeners) l(x, y);
  }

  /** Re-evaluates at the last pointer position, e.g. when the character moved under it. */
  refresh(): void {
    if (!this.last) return;
    const { x, y } = this.last;
    this.set(this.isOverCharacter(x, y) || isOverUi(x, y));
  }

  private set(interactive: boolean): void {
    if (interactive === this.interactive) return;
    this.interactive = interactive;
    window.shell.setInteractive(interactive);
  }
}

function isOverUi(x: number, y: number): boolean {
  return document.elementFromPoint(x, y)?.closest('[data-hit]') != null;
}
