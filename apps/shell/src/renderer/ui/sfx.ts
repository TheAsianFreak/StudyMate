/**
 * Procedurally synthesized sound effects (no third-party audio assets, so no licence
 * questions): UI pops, a knock on the desk, a whoosh and the chalk hit.
 */
export class Sfx {
  constructor(private readonly ctx: AudioContext) {}

  pop(): void {
    this.tone(880, 0.07, 0.12, 'sine', 1320);
  }

  chime(): void {
    this.tone(1046, 0.18, 0.15, 'triangle');
    setTimeout(() => this.tone(1568, 0.25, 0.12, 'triangle'), 120);
  }

  knock(): void {
    this.noise(0.09, 0.5, 420, 3);
    this.tone(120, 0.08, 0.35, 'sine', 60);
  }

  whoosh(): void {
    this.noise(0.35, 0.18, 1800, 0.7, true);
  }

  chalkHit(hard: boolean): void {
    this.noise(0.05, hard ? 0.9 : 0.55, 3200, 1.2);
    this.noise(0.25, hard ? 0.35 : 0.2, 900, 0.5);
    this.tone(hard ? 180 : 260, 0.06, 0.4, 'square', 90);
  }

  private tone(
    freq: number,
    dur: number,
    gain: number,
    type: OscillatorType,
    endFreq?: number,
  ): void {
    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const g = this.ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, t);
    if (endFreq) osc.frequency.exponentialRampToValueAtTime(endFreq, t + dur);
    g.gain.setValueAtTime(gain, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    osc.connect(g).connect(this.ctx.destination);
    osc.start(t);
    osc.stop(t + dur + 0.02);
  }

  private noise(dur: number, gain: number, freq: number, q: number, sweep = false): void {
    const t = this.ctx.currentTime;
    const len = Math.ceil(this.ctx.sampleRate * dur);
    const buf = this.ctx.createBuffer(1, len, this.ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < len; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / len);
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    const filter = this.ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.setValueAtTime(freq, t);
    if (sweep) filter.frequency.exponentialRampToValueAtTime(freq * 3, t + dur);
    filter.Q.value = q;
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(gain, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    src.connect(filter).connect(g).connect(this.ctx.destination);
    src.start(t);
  }
}
