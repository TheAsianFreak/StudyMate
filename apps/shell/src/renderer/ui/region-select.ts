import { t } from '../../shared/i18n';
import type { Rect } from '../../shared/ipc';

const MIN_SIZE = 12;

/**
 * Full-window drag-to-select layer for capturing a problem. Resolves with the selected
 * rect in window CSS px, or null when cancelled (right-click or the cancel button).
 */
export function selectRegion(parent: HTMLElement): Promise<Rect | null> {
  return new Promise((resolve) => {
    const layer = document.createElement('div');
    layer.className = 'region-select';
    layer.dataset['hit'] = '';
    const box = document.createElement('div');
    box.className = 'region-box';
    box.hidden = true;
    const hint = document.createElement('div');
    hint.className = 'region-hint';
    const small = document.createElement('small');
    small.textContent = t('region.hintCancel');
    hint.append(t('region.hint'), small);
    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.className = 'region-cancel';
    cancel.textContent = t('common.cancel');
    layer.append(box, hint, cancel);
    parent.appendChild(layer);

    let start: { x: number; y: number } | null = null;
    let rect: Rect = { x: 0, y: 0, w: 0, h: 0 };
    const finish = (result: Rect | null): void => {
      layer.remove();
      resolve(result);
    };

    cancel.addEventListener('click', () => finish(null));
    layer.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      finish(null);
    });
    layer.addEventListener('pointerdown', (e) => {
      if (e.button !== 0 || e.target === cancel) return;
      start = { x: e.clientX, y: e.clientY };
      layer.setPointerCapture(e.pointerId);
      box.hidden = false;
      hint.hidden = true;
    });
    layer.addEventListener('pointermove', (e) => {
      if (!start) return;
      rect = {
        x: Math.min(start.x, e.clientX),
        y: Math.min(start.y, e.clientY),
        w: Math.abs(e.clientX - start.x),
        h: Math.abs(e.clientY - start.y),
      };
      Object.assign(box.style, {
        left: `${rect.x}px`,
        top: `${rect.y}px`,
        width: `${rect.w}px`,
        height: `${rect.h}px`,
      });
    });
    layer.addEventListener('pointerup', () => {
      if (!start) return;
      start = null;
      if (rect.w < MIN_SIZE || rect.h < MIN_SIZE) {
        box.hidden = true;
        hint.hidden = false;
        return;
      }
      finish(rect);
    });
  });
}
