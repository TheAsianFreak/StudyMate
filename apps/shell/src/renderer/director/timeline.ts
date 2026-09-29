import type { PhonemeTiming, ScriptStep } from '@studymate/protocol';
import { t } from '../../shared/i18n';
import type { Rect } from '../../shared/ipc';
import { Board, type Confidence } from '../annotation/board';
import type { BackendClient } from '../backend/client';
import { AudioEngine, type Playback, type Voice } from './audio';
import type { Director } from './director';
import { CLOSED, syllableTimeline, visemesAt, type Visemes } from './lipsync';
import { SyncStats } from './sync-stats';

/** Portion of a step's audio during which its line is written (the rest is lead-in/out). */
const WRITE_START = 0.08;
const WRITE_END = 0.85;
const STEP_GAP_MS = 280;
const COMMAND_INTERVAL_MS = 33; // ~30 Hz for ik_target / viseme
const FALLBACK_MS_PER_CHAR = 110;
const TTS_CONCURRENCY = 2;
/**
 * The writing arm reaches ~65 CSS px from the shoulder without leaning and ~100–110 px
 * sideways with a lean (Godot IK), far less than a board line, so the character follows
 * the chalk: feet stay a little left of and below the writing head, with the shoulder at
 * the line's height. Upward reach is the shortest (~73 px), hence the shoulder ratio.
 * Follow steps stay within the lean range; walking speeds stay at or under ~120 px/s,
 * above which the small, light steps look hurried.
 */
const FOLLOW_DX = -46;
const SHOULDER_RATIO = 0.8;
const FOLLOW_STEP_PX = 45;
const FOLLOW_MIN_INTERVAL_MS = 250;
const REPOSITION_SPEED = 120;
const FOLLOW_SPEED: [number, number] = [80, 120];

export interface SubtitleSink {
  /** Shows a spoken line; `progress()` returns how much of it has been spoken (0..1). */
  speak(text: string, progress: () => number): void;
  clear(): void;
}

export interface ScriptOptions {
  /** Region of the problem on screen; the board is placed beside it. */
  anchor?: Rect | null;
  title?: string;
  /** Curriculum unit shown on the board, e.g. "중1 · 일차방정식". */
  unit?: string | undefined;
  /** Evidence-style lesson (non-math subject). */
  evidence?: boolean | undefined;
  confidence?: Confidence;
  /** 💬 on the board: ask a follow-up question about this script. */
  onAsk?: () => void;
  /** Voice preset id; backend default when omitted. */
  voice?: string;
  /**
   * Question this script answers about the board still open: its lines are written under
   * the existing solution (after a "Q." divider) instead of on a new board.
   */
  followUp?: string;
}

interface Run {
  cancelled: boolean;
  /** Resolves waits (walking to a line) as soon as the script is stopped. */
  onCancel: (() => void) | null;
}

interface PreparedStep {
  step: ScriptStep;
  voice: Voice | null;
  phonemes: PhonemeTiming[];
}

/**
 * Plays a script (solution or answer) with audio as the master clock (CLAUDE.md rule 2):
 * all TTS is synthesized first, then every visual — handwriting reveal, IK target, lip
 * sync, gestures — is computed from the audio time the listener is hearing.
 */
export class Timeline {
  readonly audio = new AudioEngine();
  readonly sync = new SyncStats();
  private current: Playback | null = null;
  /**
   * The script playing now. Each `play` has its own run: a shared "cancelled" flag was reset
   * by the next `play`, so the stopped script went on to its next line and two voices
   * talked over each other (a new question while the answer was still being spoken).
   */
  private run: Run | null = null;
  private board: Board | null = null;
  playing = false;

  constructor(
    private readonly director: Director,
    private readonly backend: BackendClient,
    private readonly overlay: HTMLElement,
    private readonly subtitles: SubtitleSink,
  ) {}

  /** Stops the running script (e.g. the user starts talking). */
  stop(): void {
    const run = this.run;
    if (run) {
      run.cancelled = true;
      run.onCancel?.();
      run.onCancel = null;
    }
    this.current?.stop();
  }

  /** `promise`, or earlier if the script is stopped meanwhile. */
  private untilCancelled(run: Run, promise: Promise<void>): Promise<void> {
    if (run.cancelled) return Promise.resolve();
    return Promise.race([promise, new Promise<void>((resolve) => (run.onCancel = resolve))]);
  }

  closeBoard(): void {
    this.board?.remove();
    this.board = null;
  }

  async play(steps: ScriptStep[], opts: ScriptOptions = {}): Promise<void> {
    if (steps.length === 0) return;
    this.stop();
    const run: Run = { cancelled: false, onCancel: null };
    this.run = run;
    this.playing = true;
    this.director.acquire();
    try {
      const prepared = await this.prepare(run, steps, opts.voice);
      if (run.cancelled) return;

      const writes = prepared.some((p) => p.step.write);
      if (writes && opts.followUp && this.board?.isOpen) {
        this.board.addDivider(`Q. ${opts.followUp}`);
        const b = this.board.rect();
        this.director.lookAt({ x: b.x + b.w / 2, y: b.y + b.h - 60 });
      } else if (writes) {
        this.closeBoard();
        this.board = new Board(this.overlay, opts.anchor ?? null, {
          title: opts.title ?? t('board.defaultTitle'),
          unit: opts.unit,
          evidence: opts.evidence,
          confidence: opts.confidence,
          // Closing the board ends the explanation it belongs to.
          onClose: () => this.stop(),
          ...(opts.onAsk ? { onAsk: opts.onAsk } : {}),
        });
        const b = this.board.rect();
        this.director.lookAt({ x: b.x + b.w / 2, y: b.y + 60 });
      } else {
        this.director.lookAt('user');
      }

      for (const [i, p] of prepared.entries()) {
        if (run.cancelled) break;
        await this.playStep(run, p, i);
        if (i < prepared.length - 1) await sleep(STEP_GAP_MS);
      }
    } finally {
      // A script stopped by a newer one leaves the character, subtitles and mouth to it.
      if (this.run === run) {
        this.send({ ...CLOSED });
        this.director.gesture('idle', 400);
        this.director.emotion('neutral', 0);
        this.subtitles.clear();
        this.current = null;
        this.playing = false;
        this.run = null;
        this.director.release();
      }
    }
  }

  private async prepare(run: Run, steps: ScriptStep[], voice?: string): Promise<PreparedStep[]> {
    const canSpeak = this.backend.status?.capabilities.tts === true && this.backend.connected;
    const out: PreparedStep[] = steps.map((step) => ({ step, voice: null, phonemes: [] }));
    if (!canSpeak) return out;
    let next = 0;
    const worker = async (): Promise<void> => {
      while (next < out.length && !run.cancelled) {
        const item = out[next++]!;
        try {
          const reply = await this.backend.request(
            {
              type: 'tts_request',
              id: this.backend.newId('tts'),
              text: item.step.say,
              ...(voice ? { voice } : {}),
            },
            'tts_audio',
          );
          item.voice = await this.audio.decodeWav(reply.wav_base64);
          item.phonemes = reply.phonemes ?? [];
        } catch (err) {
          console.warn('[timeline] tts failed, using silent timing', err);
        }
      }
    };
    await Promise.all(Array.from({ length: TTS_CONCURRENCY }, worker));
    return out;
  }

  private async playStep(run: Run, p: PreparedStep, index: number): Promise<void> {
    const { step } = p;
    const board = this.board;
    const line =
      step.write && board && board.isOpen ? board.addLine(step.write, step.role, step.note) : -1;
    let anchor: { x: number; y: number } | null = null;
    if (line >= 0 && board) {
      const start = board.reveal(line, 0);
      if (start) {
        anchor = this.standFor(start);
        await this.untilCancelled(
          run,
          this.director.moveToAsync(anchor.x, anchor.y, REPOSITION_SPEED),
        );
      }
    }
    // Closed or interrupted while walking to the line: don't start talking.
    if (run.cancelled) return;
    const fallbackMs = Math.max(1400, [...step.say].length * FALLBACK_MS_PER_CHAR);
    const playback = p.voice ? this.audio.play(p.voice) : this.audio.silent(fallbackMs);
    this.current = playback;
    const duration = playback.durationMs;
    const lipTimeline = syllableTimeline(step.say, duration, p.phonemes);

    if (step.emotion) this.director.emotion(step.emotion, step.emotion === 'neutral' ? 0 : 0.8);
    if (line >= 0) this.director.gesture('write', duration * WRITE_END);
    else this.director.gesture(step.gesture ?? 'idle', Math.min(duration, 2500));
    this.subtitles.speak(step.say, () => playback.audibleMs() / duration);

    const stepSync = this.sync.begin(index);
    let lastCommand = 0;
    let lastMove = 0;
    let running = true;
    const frame = (): void => {
      if (!running) return;
      const t = playback.audibleMs();
      const now = performance.now();
      if (line >= 0 && board) {
        const progress = (t / duration - WRITE_START) / (WRITE_END - WRITE_START);
        const head = board.reveal(line, progress);
        // Only while audio is audible: after the end the clamped clock would read as drift.
        if (t > 0 && t < duration) stepSync.sample(t, progress, now);
        if (head && now - lastCommand >= COMMAND_INTERVAL_MS && progress > 0 && progress < 1) {
          this.director.send({ type: 'ik_target', x: head.x, y: head.y, t });
          const want = this.standFor(head);
          if (
            !anchor ||
            (Math.hypot(want.x - anchor.x, want.y - anchor.y) > FOLLOW_STEP_PX &&
              now - lastMove > FOLLOW_MIN_INTERVAL_MS)
          ) {
            // Speed covers the gap before the next follow step so the walk looks continuous.
            const gap = anchor ? Math.hypot(want.x - anchor.x, want.y - anchor.y) : 0;
            const [slow, fast] = FOLLOW_SPEED;
            this.director.moveTo(want.x, want.y, Math.min(fast, Math.max(slow, gap / 0.4)));
            anchor = want;
            lastMove = now;
          }
        }
      }
      if (now - lastCommand >= COMMAND_INTERVAL_MS) {
        lastCommand = now;
        const v = visemesAt(lipTimeline, t, p.voice ? playback.level() : 0.2);
        this.send(v, t);
      }
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
    await playback.done;
    running = false;
    stepSync.end();
    if (line >= 0 && board) board.finishLine(line);
    if (run.cancelled) return; // play()'s cleanup (or the newer script) owns the mouth now
    this.send({ ...CLOSED });

    if (step.mark && board && line >= 0) {
      this.director.gesture('point', 900);
      const at = await board.mark(line, step.mark);
      if (at) this.director.lookAt(at);
    }
  }

  /** Feet position that puts the writing shoulder next to `head` (window CSS px). */
  private standFor(head: { x: number; y: number }): { x: number; y: number } {
    const bodyPx = this.director.hitRect?.h ?? 250;
    return {
      x: Math.min(Math.max(head.x + FOLLOW_DX, 40), innerWidth - 40),
      y: Math.min(head.y + bodyPx * SHOULDER_RATIO, innerHeight - 4),
    };
  }

  private send(v: Visemes, t?: number): void {
    this.director.send({ type: 'viseme', ...v, ...(t !== undefined ? { t } : {}) });
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
