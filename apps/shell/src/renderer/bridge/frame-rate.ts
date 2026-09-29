/**
 * Frame-rate cap for the whole page, including Godot's Emscripten main loop.
 *
 * Godot's own Engine.max_fps busy-waits in a single-threaded web build, and without it
 * the main loop follows requestAnimationFrame — 240 Hz on a 240 Hz monitor. Wrapping
 * rAF lets vsyncs pass without calling back until the target interval has elapsed,
 * so frames are skipped for free. Godot sets `window.studymateFrameRate` (60 while
 * something moves or talks, 30 when idle) through the bridge.
 */
declare global {
  interface Window {
    studymateFrameRate?: number;
  }
}

const DEFAULT_FPS = 60;
/** Tolerance so a 60 Hz target is not missed by vsync jitter on a 120/240 Hz display. */
const SLACK_MS = 2;

export function installFrameRateCap(): void {
  const nativeRaf = window.requestAnimationFrame.bind(window);
  let pending = new Map<number, FrameRequestCallback>();
  let nextId = 1;
  let scheduled = false;
  let last = -Infinity;

  const pump = (t: number): void => {
    scheduled = false;
    const fps = window.studymateFrameRate ?? DEFAULT_FPS;
    if (t - last < 1000 / fps - SLACK_MS) {
      scheduled = true;
      nativeRaf(pump);
      return;
    }
    last = t;
    const callbacks = pending;
    pending = new Map();
    for (const cb of callbacks.values()) cb(t);
  };

  window.requestAnimationFrame = (cb: FrameRequestCallback): number => {
    const id = nextId++;
    pending.set(id, cb);
    if (!scheduled) {
      scheduled = true;
      nativeRaf(pump);
    }
    return id;
  };
  window.cancelAnimationFrame = (id: number): void => {
    pending.delete(id);
  };
}
