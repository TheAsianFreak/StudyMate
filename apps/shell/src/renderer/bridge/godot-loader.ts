/** Loads the Godot web export into our own canvas (instead of Godot's HTML shell). */
import { t } from '../../shared/i18n';
import { installFrameRateCap } from './frame-rate';
import { installWebGlScissorShim } from './webgl-shim';

export interface GodotEngine {
  startGame(override?: Record<string, unknown>): Promise<void>;
  /** Writes a file into the engine's virtual filesystem (engine must be initialised). */
  copyToFS(path: string, buffer: ArrayBuffer): void;
}

interface GodotEngineConstructor {
  new (config: Record<string, unknown>): GodotEngine;
  getMissingFeatures(features?: { threads?: boolean }): string[];
}

// index.js declares `const Engine` at global scope, so it is a global binding, not a window property.
declare const Engine: GodotEngineConstructor;

const BASE = 'character/';

export async function startGodot(canvas: HTMLCanvasElement): Promise<GodotEngine> {
  installWebGlScissorShim();
  installFrameRateCap();
  await loadScript(`${BASE}index.js`);

  const missing = Engine.getMissingFeatures({ threads: false });
  if (missing.length > 0) {
    throw new Error(t('godot.missingFeatures', { features: missing.join(', ') }));
  }

  const engine = new Engine({
    executable: `${BASE}index`,
    mainPack: `${BASE}index.pck`,
    canvas,
    // 2 = adaptive: the canvas follows the window size at devicePixelRatio.
    canvasResizePolicy: 2,
    focusCanvas: false,
    ensureCrossOriginIsolationHeaders: false,
    experimentalVK: false,
    args: [],
    gdextensionLibs: [],
  });
  await engine.startGame();
  return engine;
}

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(t('godot.loadFailed', { src })));
    document.head.appendChild(script);
  });
}
