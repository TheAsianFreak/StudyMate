/**
 * Screen-level effects for the chalk hit. The overlay can't move other windows, so
 * "window shake" shakes our own layer (character + UI) and draws a chalk splat
 * where the chalk hit the "glass".
 */
export class ScreenEffects {
  constructor(
    private readonly stage: HTMLElement,
    private readonly overlay: HTMLElement,
  ) {}

  shake(amplitude: number): void {
    const frames: Keyframe[] = [];
    for (let i = 0; i <= 10; i++) {
      const a = amplitude * (1 - i / 10);
      frames.push({ transform: `translate(${rand(a)}px, ${rand(a)}px)` });
    }
    this.stage.animate(frames, { duration: 420, easing: 'linear' });
  }

  chalkMark(x: number, y: number): void {
    const el = document.createElement('div');
    el.className = 'chalk-splat';
    el.style.left = `${x}px`;
    el.style.top = `${y}px`;
    const svgNs = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNs, 'svg');
    svg.setAttribute('viewBox', '-60 -60 120 120');
    for (let i = 0; i < 14; i++) {
      const angle = (i / 14) * Math.PI * 2 + Math.random() * 0.4;
      const len = 18 + Math.random() * 38;
      const line = document.createElementNS(svgNs, 'line');
      line.setAttribute('x1', String(Math.cos(angle) * 6));
      line.setAttribute('y1', String(Math.sin(angle) * 6));
      line.setAttribute('x2', String(Math.cos(angle) * len));
      line.setAttribute('y2', String(Math.sin(angle) * len));
      svg.appendChild(line);
    }
    const dot = document.createElementNS(svgNs, 'circle');
    dot.setAttribute('r', '9');
    svg.appendChild(dot);
    el.appendChild(svg);
    this.overlay.appendChild(el);
    el.animate([{ opacity: 1 }, { opacity: 1, offset: 0.7 }, { opacity: 0 }], {
      duration: 3500,
      fill: 'forwards',
    }).onfinish = () => el.remove();
  }
}

function rand(a: number): number {
  return (Math.random() * 2 - 1) * a;
}
