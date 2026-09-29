import { desktopCapturer, screen, type BrowserWindow } from 'electron';
import type { Rect } from '../shared/ipc';

/**
 * Captures a region of the overlay's display as PNG base64.
 * `rect` is in window CSS pixels (the project-wide coordinate system); only here is it
 * converted to physical screen pixels with the display scale factor (CLAUDE.md rule 3).
 * The overlay is made fully transparent during the grab so it doesn't capture itself.
 */
export async function captureRegion(win: BrowserWindow, rect: Rect): Promise<string> {
  const bounds = win.getBounds();
  const display = screen.getDisplayMatching(bounds);
  const scale = display.scaleFactor;
  const physical = {
    width: Math.round(display.bounds.width * scale),
    height: Math.round(display.bounds.height * scale),
  };

  const previousOpacity = win.getOpacity();
  win.setOpacity(0);
  try {
    await new Promise((r) => setTimeout(r, 120)); // let the compositor drop our layer
    const sources = await desktopCapturer.getSources({
      types: ['screen'],
      thumbnailSize: physical,
    });
    const source = sources.find((s) => s.display_id === String(display.id)) ?? sources[0];
    if (!source) throw new Error('no screen source');

    // Window CSS px -> display-relative DIP -> physical px.
    const crop = {
      x: Math.round((rect.x + bounds.x - display.bounds.x) * scale),
      y: Math.round((rect.y + bounds.y - display.bounds.y) * scale),
      width: Math.max(1, Math.round(rect.w * scale)),
      height: Math.max(1, Math.round(rect.h * scale)),
    };
    const image = source.thumbnail.crop(crop);
    return image.toPNG().toString('base64');
  } finally {
    win.setOpacity(previousOpacity);
  }
}
