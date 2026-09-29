import type {
  AvatarMeta,
  EmotionName,
  GestureName,
  GodotCommand,
  GodotEvent,
  HitRect,
} from '@studymate/protocol';
import { t, tryT } from '../../shared/i18n';
import type { AvatarSelection, Rect } from '../../shared/ipc';
import type { GodotBridge } from '../bridge/godot-bridge';

export type { Rect };
export type CharacterState = 'booting' | 'idle' | 'walking' | 'dragging';

/** Godot pads hit_rect by this many CSS px; the feet sit at the bottom edge minus it. */
const HIT_RECT_PADDING = 4;
const WANDER_DELAY_MS: [number, number] = [4000, 9000];
const EDGE_MARGIN = 80;
const ARRIVE_TIMEOUT_MS = 15_000;
/** Fixed virtual-FS path: each load overwrites it, so memory does not grow. */
const AVATAR_FS_PATH = '/tmp/studymate/avatar.vrm';

/** What the Director needs from the UI layer. */
export interface DirectorUi {
  say(text: string, durationMs: number): void;
  notify(title: string, lines: string[], tone?: 'info' | 'error'): void;
}

/** Loads an imported avatar's bytes (preload IPC). */
export type AvatarReader = (id: string) => Promise<Uint8Array>;

type EventListener = (event: GodotEvent) => void;

/**
 * The single conductor (CLAUDE.md rule 1). Owns character state, wandering, dragging,
 * avatar swaps and the command stream to Godot; script playback (timeline.ts), the wake-up
 * sequence (wake.ts) and conversations (conversation.ts) drive the character through it.
 */
export class Director {
  state: CharacterState = 'booting';
  hitRect: Rect | null = null;
  wanderEnabled = true;
  /** Set while a script, capture or wake-up sequence owns the character. */
  busy = false;

  private wanderTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly stateListeners = new Set<() => void>();
  private readonly eventListeners = new Set<EventListener>();
  private avatar: AvatarSelection | null = null;
  private arriveWaiters: (() => void)[] = [];
  private defaultRequested = false;

  constructor(
    private readonly bridge: GodotBridge,
    readonly ui: DirectorUi,
    private readonly readAvatar: AvatarReader,
  ) {
    bridge.on((event) => this.onEvent(event));
  }

  get ready(): boolean {
    return this.state !== 'booting';
  }

  onChange(listener: () => void): void {
    this.stateListeners.add(listener);
  }

  /** Raw Godot events (gesture_done, hand_pos, chalk_impact, …). */
  onGodotEvent(listener: EventListener): () => void {
    this.eventListeners.add(listener);
    return () => this.eventListeners.delete(listener);
  }

  send(cmd: GodotCommand): void {
    this.bridge.send(cmd);
  }

  gesture(name: GestureName, durationMs: number): void {
    this.send({ type: 'gesture', name, duration_ms: Math.round(durationMs) });
  }

  emotion(name: EmotionName, weight = 0.8): void {
    this.send({ type: 'emotion', name, weight });
  }

  lookAt(target: { x: number; y: number } | 'user'): void {
    this.send(
      target === 'user' ? { type: 'look_at', target: 'user' } : { type: 'look_at', ...target },
    );
  }

  /** Marks the character as owned by a sequence (no wandering) until `release`. */
  acquire(): void {
    this.busy = true;
    this.clearWander();
  }

  release(): void {
    this.busy = false;
    if (this.state === 'idle') this.scheduleWander();
  }

  /** Selects the avatar to wear; applied now if Godot is up, otherwise on `ready`. */
  setAvatar(selection: AvatarSelection | null): void {
    if (selection?.id === this.avatar?.id) return;
    this.avatar = selection;
    if (this.ready) void this.applyAvatar();
  }

  hitTest(x: number, y: number): boolean {
    const r = this.hitRect;
    return r !== null && x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h;
  }

  /** Feet position estimated from the hit rect (window CSS px). */
  feet(): { x: number; y: number } | null {
    return this.hitRect ? feetOf(this.hitRect) : null;
  }

  moveTo(x: number, y: number, speed?: number): void {
    this.clearWander();
    const p = clampToWindow(x, y);
    this.send({ type: 'move_to', x: p.x, y: p.y, ...(speed ? { speed } : {}) });
    this.setState('walking');
  }

  /** Walks to (x, y) and resolves on `arrived` (or after a safety timeout). */
  moveToAsync(x: number, y: number, speed?: number): Promise<void> {
    return new Promise((resolve) => {
      const timer = setTimeout(done, ARRIVE_TIMEOUT_MS);
      const waiter = (): void => done();
      function done(): void {
        clearTimeout(timer);
        resolve();
      }
      this.arriveWaiters.push(waiter);
      this.moveTo(x, y, speed);
    });
  }

  setWander(enabled: boolean): void {
    this.wanderEnabled = enabled;
    if (enabled && this.state === 'idle') this.scheduleWander();
    else if (!enabled) this.clearWander();
  }

  wanderNow(): void {
    const w = window.innerWidth;
    const h = window.innerHeight;
    const r = this.hitRect;
    const bodyHeight = r ? r.h : 250;
    this.moveTo(
      EDGE_MARGIN + Math.random() * (w - 2 * EDGE_MARGIN),
      bodyHeight + Math.random() * (h - bodyHeight - EDGE_MARGIN / 2),
    );
  }

  /** Picks the character up by the collar at the pointer; Godot hangs her below it (`grab`). */
  beginDrag(pointerX: number, pointerY: number): void {
    if (!this.hitRect) return;
    this.clearWander();
    this.setState('dragging');
    this.send({ type: 'grab', ...clampToWindow(pointerX, pointerY) });
    this.emotion('surprised', 0.7);
    this.ui.say(t('character.drag'), 1500);
  }

  drag(pointerX: number, pointerY: number): void {
    if (this.state !== 'dragging') return;
    this.send({ type: 'grab', ...clampToWindow(pointerX, pointerY) });
  }

  /** Lets go: she drops onto her feet and Godot reports `arrived` (feet) after landing. */
  endDrag(): void {
    // Always let go (Godot ignores it when nothing is held), so a state change
    // mid-drag (e.g. a script's moveTo) cannot leave her hanging in the air.
    this.send({ type: 'release' });
    if (this.state !== 'dragging') return;
    this.emotion('neutral', 0);
    this.setState('idle');
    this.scheduleWander();
  }

  private async applyAvatar(): Promise<void> {
    const selection = this.avatar;
    if (!selection) {
      this.defaultRequested = true;
      this.send({ type: 'load_avatar', id: 'default' });
      return;
    }
    try {
      const bytes = await this.readAvatar(selection.id);
      await this.bridge.writeFile(AVATAR_FS_PATH, bytes);
      this.send({ type: 'load_avatar', id: selection.id, path: AVATAR_FS_PATH });
    } catch (err) {
      this.ui.notify(t('avatar.loadFailed'), [String(err)], 'error');
    }
  }

  private onEvent(event: GodotEvent): void {
    switch (event.type) {
      case 'ready':
        this.setState('idle');
        this.scheduleWander();
        this.ui.say(t('character.hello'), 4000);
        if (this.avatar) void this.applyAvatar();
        break;
      case 'avatar_loaded':
        if (event.id === 'default') {
          // Godot also announces the bundled avatar right after `ready`; only react when asked.
          if (this.defaultRequested) this.ui.say(t('avatar.backToDefault'), 2500);
          this.defaultRequested = false;
        } else {
          this.ui.say(t('avatar.newLook'), 3000);
          this.ui.notify(
            t('avatar.title', {
              name: event.meta.title || this.avatar?.name || t('avatar.noName'),
            }),
            describeLicense(event.meta),
          );
        }
        break;
      case 'avatar_error':
        this.ui.say(t('avatar.cantWear'), 3000);
        this.ui.notify(t('avatar.loadFailed'), [event.message], 'error');
        break;
      case 'arrived':
        if (this.state === 'walking') this.setState('idle');
        for (const w of this.arriveWaiters.splice(0)) w();
        if (!this.busy) this.scheduleWander();
        break;
      case 'hit_rect':
        this.hitRect = toRect(event);
        this.emit();
        break;
      default:
        break;
    }
    for (const l of this.eventListeners) l(event);
  }

  private scheduleWander(): void {
    this.clearWander();
    if (!this.wanderEnabled || this.busy) return;
    const [min, max] = WANDER_DELAY_MS;
    this.wanderTimer = setTimeout(
      () => {
        if (!this.busy && this.state === 'idle') this.wanderNow();
      },
      min + Math.random() * (max - min),
    );
  }

  private clearWander(): void {
    if (this.wanderTimer !== null) clearTimeout(this.wanderTimer);
    this.wanderTimer = null;
  }

  private setState(state: CharacterState): void {
    this.state = state;
    this.emit();
  }

  private emit(): void {
    for (const listener of this.stateListeners) listener();
  }
}

/** Summarises VRM meta so the user sees the terms of an avatar they imported. */
function describeLicense(meta: AvatarMeta): string[] {
  const none = t('avatar.unspecified');
  // VRM usage values (PersonalNonProfit, Allow, …) have labels; unknown ones show as-is.
  const label = (v: string): string => tryT(`avatar.use.${v}`) ?? (v || none);
  return [
    t('avatar.authors', { authors: meta.authors.join(', ') || none }),
    t('avatar.license', { license: meta.license_name || none }),
    t('avatar.usage', {
      commercial: label(meta.commercial_usage),
      redistribution: label(meta.allow_redistribution),
    }),
    t('avatar.terms'),
  ];
}

function toRect({ x, y, w, h }: HitRect): Rect {
  return { x, y, w, h };
}

function feetOf(r: Rect): { x: number; y: number } {
  return { x: r.x + r.w / 2, y: r.y + r.h - HIT_RECT_PADDING };
}

export function clampToWindow(x: number, y: number): { x: number; y: number } {
  return {
    x: Math.min(Math.max(x, 0), window.innerWidth),
    y: Math.min(Math.max(y, 0), window.innerHeight),
  };
}
