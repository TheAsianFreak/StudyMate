/**
 * Voice/handwriting sync measurement (Phase 2 target: under 100 ms).
 *
 * For every rendered frame we know the audio time the listener hears (`t`, from the
 * output timestamp) and the handwriting progress we drew. The drawn progress is a pure
 * function of `t`, so the visible error is how stale `t` is when the frame reaches the
 * screen: the time from computing it to the next frame. We therefore record, per frame,
 * the frame interval and the drift between the audio clock and wall-clock since the step
 * began (clock skew / audio underruns), and report the worst case as max(interval) + |drift|.
 */
export class SyncStats {
  readonly steps: StepSync[] = [];

  begin(index: number): StepSync {
    const s = new StepSync(index);
    this.steps.push(s);
    if (this.steps.length > 200) this.steps.shift();
    return s;
  }

  report(): { steps: number; worstErrorMs: number; p95ErrorMs: number; meanFrameMs: number } {
    const errors = this.steps.flatMap((s) => s.errors);
    const frames = this.steps.flatMap((s) => s.frameIntervals);
    const sorted = [...errors].sort((a, b) => a - b);
    return {
      steps: this.steps.length,
      worstErrorMs: sorted.at(-1) ?? 0,
      p95ErrorMs: sorted[Math.floor(sorted.length * 0.95)] ?? 0,
      meanFrameMs: frames.length ? frames.reduce((a, b) => a + b, 0) / frames.length : 0,
    };
  }
}

export class StepSync {
  readonly errors: number[] = [];
  readonly frameIntervals: number[] = [];
  private firstAudio = -1;
  private firstWall = -1;
  private lastWall = -1;

  constructor(readonly index: number) {}

  sample(audioMs: number, _progress: number, wallMs: number): void {
    if (audioMs <= 0) return;
    if (this.firstAudio < 0) {
      this.firstAudio = audioMs;
      this.firstWall = wallMs;
    }
    const interval = this.lastWall < 0 ? 0 : wallMs - this.lastWall;
    this.lastWall = wallMs;
    if (interval > 0) this.frameIntervals.push(interval);
    const drift = audioMs - this.firstAudio - (wallMs - this.firstWall);
    this.errors.push(interval + Math.abs(drift));
  }

  end(): void {}
}
