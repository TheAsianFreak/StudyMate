import type { Director } from '../director/director';

/** Left-drag on the character moves it; right-click opens the app menu. The window is interactive here because the pointer is over it. */
export function installCharacterDrag(director: Director, onEnd: () => void): void {
  window.addEventListener('pointerdown', (e) => {
    if (e.button !== 0 || !director.hitTest(e.clientX, e.clientY)) return;
    if (e.target instanceof Element && e.target.closest('[data-hit]')) return;
    e.preventDefault();
    director.beginDrag(e.clientX, e.clientY);
  });
  window.addEventListener('pointermove', (e) => director.drag(e.clientX, e.clientY));
  // Right-click on the character opens the app menu (quit, avatar, settings).
  window.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    if (director.hitTest(e.clientX, e.clientY)) window.shell.showMenu();
  });
  const end = (): void => {
    director.endDrag();
    onEnd();
  };
  window.addEventListener('pointerup', end);
  window.addEventListener('pointercancel', end);
}
