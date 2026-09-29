import { t } from '../../shared/i18n';
import type { SubtitleSink } from '../director/timeline';
import type { Director } from '../director/director';

const GAP = 10;
const TYPE_INTERVAL_MS = 35;

/**
 * Game-style speech bubble above the character. Three modes:
 * - `say`: short line typed out on a timer (chatter, status),
 * - `speak`: subtitle typed out in step with the voice (audio-clock progress),
 * - `listening`: mic level bars + partial transcript during push-to-talk.
 */
export class SpeechBubble implements SubtitleSink {
  private readonly el: HTMLElement;
  private readonly text: HTMLElement;
  private readonly meter: HTMLElement;
  private hideTimer: ReturnType<typeof setTimeout> | null = null;
  private typeTimer: ReturnType<typeof setInterval> | null = null;
  private speaking = false;

  constructor(
    parent: HTMLElement,
    private readonly director: Director,
  ) {
    this.el = document.createElement('div');
    this.el.className = 'speech-bubble';
    this.el.hidden = true;
    this.meter = document.createElement('div');
    this.meter.className = 'mic-meter';
    for (let i = 0; i < 5; i++) this.meter.appendChild(document.createElement('i'));
    this.meter.hidden = true;
    this.text = document.createElement('span');
    this.el.append(this.meter, this.text);
    parent.appendChild(this.el);
    director.onChange(() => this.place());
  }

  say(message: string, durationMs: number): void {
    if (this.speaking) return; // subtitles of the voice take priority
    this.reset('say');
    const chars = [...message];
    let i = 0;
    this.typeTimer = setInterval(() => {
      this.text.textContent += chars[i++] ?? '';
      this.place();
      if (i >= chars.length && this.typeTimer) clearInterval(this.typeTimer);
    }, TYPE_INTERVAL_MS);
    this.hideTimer = setTimeout(() => this.hide(), durationMs + chars.length * TYPE_INTERVAL_MS);
  }

  speak(line: string, progress: () => number): void {
    this.reset('speak');
    this.speaking = true;
    const chars = [...line];
    const tick = (): void => {
      if (!this.speaking) return;
      // Text runs slightly ahead of the voice so reading never lags behind hearing.
      const n = Math.min(
        chars.length,
        Math.ceil(chars.length * Math.min(1, progress() * 1.15 + 0.05)),
      );
      if (n !== this.text.textContent?.length) {
        this.text.textContent = chars.slice(0, n).join('');
        this.place();
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  clear(): void {
    this.speaking = false;
    this.hide();
  }

  /** level < 0 keeps the previous meter; partial replaces the text when non-empty. */
  listening(level: number, partial: string): void {
    if (this.el.hidden || this.meter.hidden) {
      this.reset('listen');
      this.meter.hidden = false;
      this.text.textContent = t('bubble.listening');
    }
    if (level >= 0) {
      const bars = [...this.meter.children] as HTMLElement[];
      bars.forEach((bar, i) => {
        const h = Math.max(0.15, Math.min(1, level * 3 - i * 0.12 + Math.random() * 0.15));
        bar.style.transform = `scaleY(${h.toFixed(2)})`;
      });
    }
    if (partial) this.text.textContent = partial;
    this.place();
  }

  thinking(): void {
    this.reset('think');
    this.text.textContent = t('bubble.thinking');
    this.el.classList.add('thinking');
    this.place();
  }

  hide(): void {
    this.clearTimers();
    this.el.hidden = true;
    this.meter.hidden = true;
    this.el.classList.remove('thinking');
  }

  private reset(mode: string): void {
    this.clearTimers();
    this.speaking = false;
    this.el.hidden = false;
    this.meter.hidden = true;
    this.el.classList.remove('thinking');
    this.el.dataset['mode'] = mode;
    this.el.classList.remove('pop');
    void this.el.offsetWidth; // restart the pop-in animation
    this.el.classList.add('pop');
    this.text.textContent = '';
  }

  private place(): void {
    const r = this.director.hitRect;
    if (!r || this.el.hidden) return;
    const w = this.el.offsetWidth;
    const h = this.el.offsetHeight;
    const x = Math.min(Math.max(r.x + r.w / 2 - w / 2, 8), window.innerWidth - w - 8);
    let y = Math.max(r.y - h - GAP, 8);
    // Never cover the writing: drop below any board the bubble would overlap.
    for (const board of document.querySelectorAll<HTMLElement>('.board')) {
      const b = board.getBoundingClientRect();
      const overlaps = x < b.right && x + w > b.left && y < b.bottom && y + h > b.top;
      if (overlaps) y = Math.min(b.bottom + GAP, window.innerHeight - h - 8);
    }
    this.el.classList.toggle('below', y > r.y);
    this.el.style.transform = `translate(${x}px, ${y}px)`;
  }

  private clearTimers(): void {
    if (this.hideTimer) clearTimeout(this.hideTimer);
    if (this.typeTimer) clearInterval(this.typeTimer);
    this.hideTimer = null;
    this.typeTimer = null;
  }
}
