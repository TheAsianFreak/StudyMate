/**
 * Web Audio playback that doubles as the Director's master clock (CLAUDE.md rule 2).
 * `audibleMs()` estimates what the listener hears right now, compensating output latency,
 * so handwriting, gestures and lip sync are driven from the same time base as the voice.
 */

export interface Voice {
  buffer: AudioBuffer;
  durationMs: number;
}

export interface Playback {
  /** Milliseconds of audio the listener has heard so far (clamped to [0, duration]). */
  audibleMs(): number;
  /** RMS of the currently playing signal, 0..~1. */
  level(): number;
  readonly durationMs: number;
  readonly done: Promise<void>;
  stop(): void;
}

export class AudioEngine {
  readonly ctx = new AudioContext({ latencyHint: 'interactive' });
  private readonly analyser: AnalyserNode;
  private readonly samples: Float32Array<ArrayBuffer>;
  readonly master: GainNode;

  constructor() {
    this.master = this.ctx.createGain();
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 1024;
    this.samples = new Float32Array(this.analyser.fftSize);
    this.master.connect(this.analyser);
    this.analyser.connect(this.ctx.destination);
  }

  async decodeWav(base64: string): Promise<Voice> {
    const bin = atob(base64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const buffer = await this.ctx.decodeAudioData(bytes.buffer);
    return { buffer, durationMs: buffer.duration * 1000 };
  }

  play(voice: Voice): Playback {
    if (this.ctx.state === 'suspended') void this.ctx.resume();
    const source = this.ctx.createBufferSource();
    source.buffer = voice.buffer;
    source.connect(this.master);
    const startAt = this.ctx.currentTime + 0.05;
    source.start(startAt);
    let stopped = false;
    const done = new Promise<void>((resolve) => {
      source.onended = () => resolve();
    });
    return {
      durationMs: voice.durationMs,
      done,
      audibleMs: () => {
        const ms = (this.audibleContextTime() - startAt) * 1000;
        return Math.min(Math.max(ms, 0), voice.durationMs);
      },
      level: () => (stopped ? 0 : this.level()),
      stop: () => {
        stopped = true;
        try {
          source.stop();
        } catch {
          // already ended
        }
      },
    };
  }

  /** A silent clock for steps without audio (TTS unavailable): same interface, wall time. */
  silent(durationMs: number): Playback {
    const start = performance.now();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let resolveDone: () => void = () => {};
    const done = new Promise<void>((resolve) => {
      resolveDone = resolve;
      timer = setTimeout(resolve, durationMs);
    });
    return {
      durationMs,
      done,
      audibleMs: () => Math.min(performance.now() - start, durationMs),
      level: () => 0,
      stop: () => {
        clearTimeout(timer);
        resolveDone();
      },
    };
  }

  /** Context time the listener is hearing now: output timestamp extrapolated to this frame. */
  audibleContextTime(): number {
    const ts = this.ctx.getOutputTimestamp();
    if (
      ts.contextTime !== undefined &&
      ts.performanceTime !== undefined &&
      ts.performanceTime > 0
    ) {
      return ts.contextTime + (performance.now() - ts.performanceTime) / 1000;
    }
    return this.ctx.currentTime - (this.ctx.outputLatency || this.ctx.baseLatency || 0);
  }

  level(): number {
    this.analyser.getFloatTimeDomainData(this.samples);
    let sum = 0;
    for (const s of this.samples) sum += s * s;
    return Math.sqrt(sum / this.samples.length);
  }
}
