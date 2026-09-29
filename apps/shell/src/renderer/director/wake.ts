import type { DrowsyStateMessage } from '@studymate/protocol';
import { t } from '../../shared/i18n';
import type { WakeIntensity } from '../../shared/ipc';
import type { Director } from './director';
import type { Sfx } from '../ui/sfx';
import type { ScreenEffects } from '../ui/effects';

/** Seconds without a response before escalating (SPEC 7.3). */
const ESCALATE_MS = 10_000;
const COOLDOWN_MS = 5 * 60_000;
/** Input within this window counts as the user responding. */
const RESPONSE_INPUT_MS = 1500;
const TAP_PERIOD_MS = 320;
const TAP_COUNT = 5;
const THROW_MS = 900;

export type WakeStage = 'normal' | 'talk' | 'tap_desk' | 'chalk' | 'cooldown';

const TALK_LINES = ['wake.talk1', 'wake.talk2', 'wake.talk3'] as const;

/**
 * Three-stage wake-up (SPEC 7.3): talk → tap the desk → throw chalk, each after 10 s
 * without a response, then a 5-minute cooldown. Owned by the Director side; Godot only
 * performs the gestures and reports chalk_impact.
 */
export class WakeUp {
  stage: WakeStage = 'normal';
  intensity: WakeIntensity = 'normal';
  focusMode = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private lastInputAt = 0;
  private drowsy = false;
  private readonly listeners = new Set<(stage: WakeStage) => void>();

  constructor(
    private readonly director: Director,
    private readonly sfx: Sfx,
    private readonly effects: ScreenEffects,
    private readonly canInterrupt: () => boolean,
  ) {
    director.onGodotEvent((e) => {
      if (e.type === 'chalk_impact') this.onImpact(e.x, e.y);
    });
  }

  onStage(listener: (stage: WakeStage) => void): void {
    this.listeners.add(listener);
  }

  /** Feed from the backend's drowsy_state events. */
  onDrowsyState(msg: DrowsyStateMessage): void {
    const wasDrowsy = this.drowsy;
    this.drowsy = msg.state === 'drowsy';
    if (this.drowsy && !wasDrowsy && this.stage === 'normal') this.start();
    if (!this.drowsy && wasDrowsy && this.isEscalating()) this.responded();
  }

  /** System input idle time from the main process. */
  onIdle(idleMs: number): void {
    if (idleMs < RESPONSE_INPUT_MS) {
      this.lastInputAt = performance.now();
      if (this.isEscalating()) this.responded();
    }
  }

  /** Manual trigger for testing from the HUD. */
  test(): void {
    if (this.stage === 'normal' || this.stage === 'cooldown') {
      this.clear();
      this.stage = 'normal';
      this.start();
    }
  }

  private isEscalating(): boolean {
    return this.stage === 'talk' || this.stage === 'tap_desk' || this.stage === 'chalk';
  }

  private start(): void {
    if (this.focusMode || !this.canInterrupt()) return;
    this.director.acquire();
    this.setStage('talk');
    this.director.lookAt('user');
    this.director.emotion('surprised', 0.6);
    this.director.gesture('point', 1500);
    this.director.ui.say(t(TALK_LINES[Math.floor(Math.random() * TALK_LINES.length)]!), 4000);
    this.sfx.chime();
    this.schedule(() => this.tapDesk());
  }

  private tapDesk(): void {
    this.setStage('tap_desk');
    this.director.emotion('angry', 0.4);
    // Godot taps once per ~0.32 s; knock on each strike.
    this.director.gesture('tap_desk', TAP_COUNT * TAP_PERIOD_MS);
    this.director.ui.say(t('wake.tap'), 3000);
    for (let i = 0; i < TAP_COUNT; i++) setTimeout(() => this.sfx.knock(), 90 + i * TAP_PERIOD_MS);
    this.schedule(() => this.throwChalk());
  }

  private throwChalk(): void {
    if (this.intensity === 'soft') {
      this.director.ui.say(t('wake.softWarn'), 3000);
      this.finish();
      return;
    }
    this.setStage('chalk');
    this.director.emotion('angry', 0.8);
    // Godot releases the chalk at 46% of the throw gesture; send throw_chalk right away.
    this.director.gesture('throw', THROW_MS);
    this.director.send({
      type: 'throw_chalk',
      strength: this.intensity === 'hard' ? 'hard' : 'soft',
    });
    this.director.ui.say(t(this.intensity === 'hard' ? 'wake.throwHard' : 'wake.throw'), 1800);
    setTimeout(() => this.sfx.whoosh(), THROW_MS * 0.46);
    this.schedule(() => this.finish(), 4000);
  }

  private onImpact(x: number, y: number): void {
    this.sfx.chalkHit(this.intensity === 'hard');
    this.effects.shake(this.intensity === 'hard' ? 14 : 7);
    this.effects.chalkMark(x, y);
  }

  private responded(): void {
    this.clear();
    this.director.emotion('happy', 0.7);
    this.director.gesture('nod', 900);
    this.director.ui.say(t(this.stage === 'chalk' ? 'wake.awakeAfterChalk' : 'wake.awake'), 2500);
    this.finish();
  }

  private finish(): void {
    this.clear();
    this.director.release();
    this.setStage('cooldown');
    this.timer = setTimeout(() => this.setStage('normal'), COOLDOWN_MS);
    setTimeout(() => this.director.emotion('neutral', 0), 3000);
  }

  private schedule(fn: () => void, ms = ESCALATE_MS): void {
    this.clear();
    this.timer = setTimeout(fn, ms);
  }

  private clear(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }

  private setStage(stage: WakeStage): void {
    this.stage = stage;
    for (const l of this.listeners) l(stage);
  }
}
