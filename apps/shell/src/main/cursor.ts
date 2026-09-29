import { screen, type BrowserWindow } from 'electron';

const INTERVAL_MS = 16;

/**
 * Streams the cursor position to the renderer for click-through hit testing.
 * `setIgnoreMouseEvents(..., { forward: true })` does not deliver mouse moves to an
 * overlay that never had focus on Windows, so we poll instead of relying on it.
 */
export function startCursorTracking(
  win: BrowserWindow,
  send: (x: number, y: number) => void,
): void {
  let lastX = NaN;
  let lastY = NaN;
  const timer = setInterval(() => {
    if (win.isDestroyed()) {
      clearInterval(timer);
      return;
    }
    const cursor = screen.getCursorScreenPoint();
    const bounds = win.getBounds();
    const x = cursor.x - bounds.x;
    const y = cursor.y - bounds.y;
    if (x === lastX && y === lastY) return;
    lastX = x;
    lastY = y;
    send(x, y);
  }, INTERVAL_MS);
}
