import type { ScriptStep } from '@studymate/protocol';
import { onLangChange, t } from '../../shared/i18n';
import type { ProcessMetric } from '../../shared/ipc';
import type { BackendClient } from '../backend/client';
import type { GodotBridge } from '../bridge/godot-bridge';
import type { Director } from '../director/director';
import type { Timeline } from '../director/timeline';
import type { WakeUp } from '../director/wake';
import type { ClickThrough } from './click-through';

interface HudDeps {
  director: Director;
  bridge: GodotBridge;
  clickThrough: ClickThrough;
  backend: BackendClient;
  timeline: Timeline;
  wake: WakeUp;
}

/** Board-writing test script: works offline (silent clock when TTS is unavailable). */
function testScript(): ScriptStep[] {
  return [
    { say: t('hud.test1'), write: String.raw`\frac{x}{2} = 7 - 3`, gesture: 'write' },
    {
      say: t('hud.test2'),
      write: String.raw`\frac{x}{2} = 4`,
      mark: { type: 'circle', target: '4' },
    },
    { say: t('hud.test3'), write: 'x = 8', emotion: 'happy' },
  ];
}

/** Debug HUD: FPS, process CPU/memory, bridge, backend, click-through and sync state. */
export class Hud {
  private readonly el: HTMLElement;
  private readonly stats: HTMLElement;
  private readonly hitBox: HTMLElement;
  private readonly fps = new FpsMeter();
  private metrics: ProcessMetric[] = [];
  private error: string | null = null;

  constructor(
    parent: HTMLElement,
    private readonly deps: HudDeps,
  ) {
    this.hitBox = el('div', 'hit-box');
    parent.appendChild(this.hitBox);

    this.el = el('section', 'hud');
    this.el.dataset['hit'] = '';
    this.stats = el('pre', 'hud-stats');
    const buttons = el('div', 'hud-buttons');
    const title = el('h1', 'hud-title');
    const fill = (): void => {
      title.textContent = t('hud.title');
      buttons.replaceChildren(
        toggle(t('hud.wander'), deps.director.wanderEnabled, (on) => deps.director.setWander(on)),
        button(t('hud.move'), () => deps.director.wanderNow()),
        button(
          t('hud.boardTest'),
          () =>
            void deps.timeline.play(testScript(), {
              title: t('hud.boardTest'),
              confidence: 'high',
            }),
        ),
        button(t('hud.wakeTest'), () => deps.wake.test()),
        button(t('hud.chalk'), () =>
          deps.director.send({ type: 'throw_chalk', strength: 'normal' }),
        ),
        toggle(t('hud.hitBox'), !this.hitBox.hidden, (on) => (this.hitBox.hidden = !on)),
      );
    };
    fill();
    onLangChange(fill);
    this.el.append(title, this.stats, buttons);
    parent.appendChild(this.el);

    deps.director.onChange(() => this.drawHitBox());
    setInterval(() => this.render(), 250);
  }

  setVisible(visible: boolean): void {
    this.el.hidden = !visible;
    this.hitBox.style.display = visible ? '' : 'none';
  }

  setMetrics(metrics: ProcessMetric[]): void {
    this.metrics = metrics;
  }

  showError(message: string): void {
    this.error = message;
    this.setVisible(true);
    this.render();
  }

  private drawHitBox(): void {
    const r = this.deps.director.hitRect;
    if (!r) return;
    Object.assign(this.hitBox.style, {
      transform: `translate(${r.x}px, ${r.y}px)`,
      width: `${r.w}px`,
      height: `${r.h}px`,
    });
  }

  private render(): void {
    if (this.el.hidden) return;
    const { director, bridge, clickThrough, backend, timeline, wake } = this.deps;
    const f = this.fps.snapshot();
    const r = director.hitRect;
    const sync = timeline.sync.report();
    const caps = backend.status?.capabilities;
    const lines = [
      `FPS        ${f.fps.toFixed(1)}  (worst frame ${f.worstMs.toFixed(1)} ms)`,
      `viewport   ${innerWidth}x${innerHeight} css @ ${devicePixelRatio}x`,
      `godot      ${bridge.attached ? 'attached' : 'loading'}  sent ${bridge.sent} / recv ${bridge.received}`,
      `character  ${director.state}`,
      `hit_rect   ${r ? `${r.x.toFixed(0)},${r.y.toFixed(0)} ${r.w.toFixed(0)}x${r.h.toFixed(0)}` : '-'}`,
      `input      ${clickThrough.interactive ? 'ON (captured)' : 'off (click-through)'}`,
      `pointer    ${clickThrough.last ? `${clickThrough.last.x},${clickThrough.last.y}` : '-'}  moves ${clickThrough.moves}`,
      `backend    ${backend.connected ? `connected · tier ${backend.status?.tier ?? '?'}` : 'offline'}`,
      `caps       ${
        caps
          ? Object.entries(caps)
              .map(([k, v]) => `${k}${v ? '✓' : '✗'}`)
              .join(' ')
          : '-'
      }`,
      `sync       steps ${sync.steps}  worst ${sync.worstErrorMs.toFixed(1)} ms  p95 ${sync.p95ErrorMs.toFixed(1)} ms`,
      `wake       ${wake.stage}  busy ${director.busy}`,
      '',
      ...formatMetrics(this.metrics),
    ];
    if (this.error) lines.unshift(t('hud.error', { message: this.error }), '');
    this.stats.textContent = lines.join('\n');
  }
}

/** Frame rate from requestAnimationFrame over a sliding one-second window. */
class FpsMeter {
  private frames: number[] = [];

  constructor() {
    const tick = (t: number): void => {
      this.frames.push(t);
      while (this.frames.length > 0 && t - this.frames[0]! > 1000) this.frames.shift();
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  snapshot(): { fps: number; worstMs: number } {
    const f = this.frames;
    if (f.length < 2) return { fps: 0, worstMs: 0 };
    let worst = 0;
    for (let i = 1; i < f.length; i++) worst = Math.max(worst, f[i]! - f[i - 1]!);
    return { fps: ((f.length - 1) * 1000) / (f[f.length - 1]! - f[0]!), worstMs: worst };
  }
}

function formatMetrics(metrics: ProcessMetric[]): string[] {
  if (metrics.length === 0) return ['process    (waiting for metrics)'];
  const byType = new Map<string, { cpu: number; mem: number }>();
  for (const m of metrics) {
    const agg = byType.get(m.type) ?? { cpu: 0, mem: 0 };
    agg.cpu += m.cpu;
    agg.mem += m.memoryMb;
    byType.set(m.type, agg);
  }
  let cpu = 0;
  let mem = 0;
  const lines = [...byType].map(([type, a]) => {
    cpu += a.cpu;
    mem += a.mem;
    return `${type.padEnd(10)} cpu ${a.cpu.toFixed(1).padStart(5)}%  mem ${a.mem.toFixed(0).padStart(4)} MB`;
  });
  lines.push(
    `${'total'.padEnd(10)} cpu ${cpu.toFixed(1).padStart(5)}%  mem ${mem.toFixed(0).padStart(4)} MB`,
  );
  return lines;
}

function el(tag: string, className: string, text?: string): HTMLElement {
  const node = document.createElement(tag);
  node.className = className;
  if (text) node.textContent = text;
  return node;
}

function button(label: string, onClick: () => void): HTMLButtonElement {
  const b = document.createElement('button');
  b.type = 'button';
  b.textContent = label;
  b.addEventListener('click', onClick);
  return b;
}

function toggle(
  label: string,
  initial: boolean,
  onChange: (on: boolean) => void,
): HTMLButtonElement {
  let on = initial;
  const b = button(label, () => {
    on = !on;
    b.setAttribute('aria-pressed', String(on));
    onChange(on);
  });
  b.setAttribute('aria-pressed', String(on));
  return b;
}
