import { GODOT_EVENT_TYPES, type GodotCommand, type GodotEvent } from '@studymate/protocol';
import type { GodotEngine } from './godot-loader';

/**
 * Renderer side of the JavaScriptBridge transport (counterpart of character/scripts/bridge.gd).
 * Godot looks up `window.studymateHost` at startup, hands over its receive callback,
 * and posts events as JSON strings through `receive`.
 */
interface StudymateHost {
  attachGodot(callback: (json: string) => void): void;
  receive(json: string): void;
}

declare global {
  interface Window {
    studymateHost?: StudymateHost;
  }
}

type Listener = (event: GodotEvent) => void;

export class GodotBridge {
  private toGodot: ((json: string) => void) | null = null;
  private attachEngineResolve: (engine: GodotEngine) => void = () => {};
  private readonly engine = new Promise<GodotEngine>((resolve) => {
    this.attachEngineResolve = resolve;
  });
  private readonly queue: GodotCommand[] = [];
  private readonly listeners = new Set<Listener>();
  sent = 0;
  received = 0;

  constructor() {
    window.studymateHost = {
      attachGodot: (callback) => {
        this.toGodot = callback;
        for (const cmd of this.queue.splice(0)) this.send(cmd);
      },
      // Deferred so listeners never re-enter the engine from inside its own call stack.
      receive: (json) => queueMicrotask(() => this.dispatch(json)),
    };
  }

  get attached(): boolean {
    return this.toGodot !== null;
  }

  attachEngine(engine: GodotEngine): void {
    this.attachEngineResolve(engine);
  }

  /**
   * Binary side channel: writes a file into Godot's virtual FS so a JSON command
   * (e.g. load_avatar) can reference it by path. Waits until the engine has started,
   * since Godot may report `ready` before `startGame()` resolves.
   */
  async writeFile(path: string, bytes: Uint8Array): Promise<void> {
    const engine = await this.engine;
    const copy = new Uint8Array(bytes.byteLength);
    copy.set(bytes);
    engine.copyToFS(path, copy.buffer);
  }

  send(cmd: GodotCommand): void {
    if (!this.toGodot) {
      this.queue.push(cmd);
      return;
    }
    this.sent++;
    this.toGodot(JSON.stringify(cmd));
  }

  on(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private dispatch(json: string): void {
    let event: unknown;
    try {
      event = JSON.parse(json);
    } catch {
      console.warn('[bridge] invalid JSON from Godot', json);
      return;
    }
    if (!isGodotEvent(event)) {
      console.warn('[bridge] unknown event from Godot', event);
      return;
    }
    this.received++;
    for (const listener of this.listeners) listener(event);
  }
}

function isGodotEvent(value: unknown): value is GodotEvent {
  if (typeof value !== 'object' || value === null) return false;
  const type = (value as { type?: unknown }).type;
  return typeof type === 'string' && GODOT_EVENT_TYPES.has(type as GodotEvent['type']);
}
