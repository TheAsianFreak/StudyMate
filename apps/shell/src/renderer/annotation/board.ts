import 'katex/dist/katex.min.css';
import rough from 'roughjs';
import type { Mark, StepRole } from '@studymate/protocol';
import { t, type PlainKey } from '../../shared/i18n';
import type { Rect } from '../../shared/ipc';
import { renderMath } from '../ui/dom';

/** Board width follows the screen: 36% of the window, 480..720 px. */
const BOARD_MIN_WIDTH = 480;
const BOARD_MAX_WIDTH = 720;
/** A line that still does not fit after wrapping (one wide fraction) shrinks to this at most. */
const MIN_LINE_SCALE = 0.6;
const GAP = 24;
const MARK_MS = 450;
/** Seconds a single glyph takes to appear once the chalk reaches it. */
const GLYPH_MS = 140;

export type Confidence = 'high' | 'medium' | 'low';

const CONFIDENCE_LABEL: Record<Confidence, PlainKey> = {
  high: 'confidence.high',
  medium: 'confidence.medium',
  low: 'confidence.low',
};

const CONFIDENCE_TIP: Record<Confidence, PlainKey> = {
  high: 'confidence.highTip',
  medium: 'confidence.mediumTip',
  low: 'confidence.lowTip',
};

const ROLE_LABEL: Partial<Record<StepRole, PlainKey>> = {
  intro: 'board.role.intro',
  concept: 'board.role.concept',
  check: 'board.role.check',
  summary: 'board.role.summary',
};

export interface BoardOptions {
  title: string;
  unit?: string | undefined;
  /** Non-math lessons judge options instead of calculating: their check line is "확인". */
  evidence?: boolean | undefined;
  confidence?: Confidence | undefined;
  /** Closing the board (× button) — the Director stops the explanation. */
  onClose?: () => void;
  /** 💬 button — ask a follow-up question about this board. */
  onAsk?: () => void;
}

interface Line {
  el: HTMLElement;
  ink: HTMLElement;
  note: HTMLElement | null;
  role: StepRole | undefined;
  glyphs: HTMLElement[];
  shown: number;
  /** Problem and working lines stand with their "=" in one column (per section). */
  aligned: boolean;
  section: number;
  eqOffset: number | null;
}

/**
 * The on-screen board where solutions are hand-written.
 *
 * - Math is typeset by KaTeX in a handwriting font with a chalk texture, then revealed
 *   glyph by glyph (pace driven by the audio clock) so it reads as written, not wiped in.
 * - Working lines are aligned at their "=" like a teacher's board; each can carry a small
 *   margin note ("-5 이항"). Concept / check / summary lines get their own chalk styles.
 * - Draggable by its header; × stops the explanation, 💬 asks about this problem.
 */
export class Board {
  readonly el: HTMLElement;
  private readonly body: HTMLElement;
  private readonly svg: SVGSVGElement;
  private readonly lines: Line[] = [];
  private closed = false;
  private section = 0;

  constructor(
    parent: HTMLElement,
    anchor: Rect | null,
    private readonly opts: BoardOptions,
  ) {
    ensureChalkFilter();
    this.el = document.createElement('section');
    this.el.className = 'board';
    this.el.dataset['hit'] = '';

    const header = document.createElement('header');
    const title = document.createElement('h2');
    title.textContent = opts.title;
    header.appendChild(title);
    if (opts.unit) header.appendChild(chip('unit', opts.unit));
    if (opts.confidence) {
      const badge = chip(
        `confidence confidence-${opts.confidence}`,
        t(CONFIDENCE_LABEL[opts.confidence]),
      );
      badge.title = t(CONFIDENCE_TIP[opts.confidence]);
      header.appendChild(badge);
    }
    if (opts.onAsk) {
      const ask = button('board-ask', '💬', t('board.ask'));
      ask.addEventListener('click', () => opts.onAsk?.());
      header.appendChild(ask);
    }
    const close = button('board-close', '×', t('board.close'));
    close.addEventListener('click', () => this.close());
    header.appendChild(close);

    this.body = document.createElement('div');
    this.body.className = 'board-body';
    this.svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    this.svg.classList.add('board-marks');
    this.body.appendChild(this.svg);
    this.el.append(header, this.body);
    parent.appendChild(this.el);
    this.place(anchor);
    makeDraggable(this.el, header);
  }

  get isOpen(): boolean {
    return !this.closed;
  }

  /** Board position in window CSS px (for moving the character next to it). */
  rect(): Rect {
    const r = this.el.getBoundingClientRect();
    return { x: r.left, y: r.top, w: r.width, h: r.height };
  }

  /** Adds a hidden line; returns its index. */
  addLine(latex: string, role?: StepRole, note?: string): number {
    const el = document.createElement('div');
    el.className = `board-line role-${role ?? 'solve'}`;
    const labelKey =
      role === 'check' && this.opts.evidence
        ? 'board.role.confirm'
        : role
          ? ROLE_LABEL[role]
          : undefined;
    const label = labelKey ? t(labelKey) : undefined;
    // Unlabelled working lines get an empty chip so every formula starts in the same
    // column and the "=" alignment below holds across the problem line and the working.
    el.appendChild(chip(label ? 'line-label' : 'line-label blank', label ?? ''));
    const ink = document.createElement('div');
    ink.className = 'board-ink';
    // Display style: fractions at full size, as they are written on a board.
    renderMath(ink, `\\displaystyle ${breakableText(latex)}`, { output: 'html' });
    handwriteMinus(ink);
    el.appendChild(ink);
    let noteEl: HTMLElement | null = null;
    if (note) {
      noteEl = document.createElement('span');
      noteEl.className = 'board-note';
      noteEl.textContent = note;
      el.appendChild(noteEl);
    }
    this.body.appendChild(el);

    const glyphs = collectGlyphs(ink);
    for (const g of glyphs) g.classList.add('glyph-pending');
    const aligned = !role || role === 'intro' || role === 'solve';
    this.lines.push({
      el,
      ink,
      note: noteEl,
      role,
      glyphs,
      shown: 0,
      aligned,
      section: this.section,
      eqOffset: null,
    });
    this.layout();
    // Laying out the line may have started loading the handwriting font; the widths
    // measured with the fallback font are wrong, so measure again once it is in.
    void document.fonts.ready.then(() => this.layout());
    this.body.scrollTop = this.body.scrollHeight;
    return this.lines.length - 1;
  }

  /** Starts a follow-up section ("Q. 왜 부호가 바뀌어요?") under what is already written. */
  addDivider(text: string): void {
    const el = document.createElement('div');
    el.className = 'board-divider';
    el.textContent = text;
    this.section++; // the answer aligns on its own, without moving the solution above
    this.body.appendChild(el);
    this.body.scrollTop = this.body.scrollHeight;
  }

  /**
   * Writes line `index` up to `progress` (0..1), glyph by glyph; returns the chalk tip
   * (right edge of the newest glyph) in window px for the character's writing hand.
   */
  reveal(index: number, progress: number): { x: number; y: number } | null {
    const line = this.lines[index];
    if (!line) return null;
    const p = Math.min(1, Math.max(0, progress));
    const target = Math.round(p * line.glyphs.length);
    while (line.shown < target) {
      const g = line.glyphs[line.shown++]!;
      g.classList.remove('glyph-pending');
      g.classList.add('glyph-written');
    }
    const last = line.shown > 0 ? line.glyphs[line.shown - 1] : undefined;
    const inkBox = line.ink.getBoundingClientRect();
    if (!last) return { x: inkBox.left, y: inkBox.top + inkBox.height / 2 };
    // a wrapped line: the chalk follows the row being written
    const r = last.getBoundingClientRect();
    return { x: r.right, y: r.top + r.height / 2 };
  }

  /** Finishes line `index`: every glyph visible, margin note written in. */
  finishLine(index: number): void {
    const line = this.lines[index];
    if (!line) return;
    this.reveal(index, 1);
    line.note?.classList.add('shown');
    line.el.classList.add('done');
  }

  lineCount(): number {
    return this.lines.length;
  }

  /** Draws a hand-drawn circle/underline/arrow on `target` inside line `index`. */
  async mark(index: number, mark: Mark): Promise<{ x: number; y: number } | null> {
    const line = this.lines[index];
    if (!line) return null;
    const box = this.relative(
      findTarget(line.ink, mark.target) ?? line.ink.getBoundingClientRect(),
    );
    const rc = rough.svg(this.svg);
    const opts = { stroke: '#ffd166', strokeWidth: 2.4, roughness: 1.6, bowing: 1.4 };
    let node: SVGGElement;
    if (mark.type === 'circle') {
      node = rc.ellipse(box.x + box.w / 2, box.y + box.h / 2, box.w + 22, box.h + 16, opts);
    } else if (mark.type === 'underline') {
      node = rc.line(box.x - 4, box.y + box.h + 4, box.x + box.w + 4, box.y + box.h + 6, opts);
    } else {
      const tipX = box.x + box.w + 8;
      const tipY = box.y + box.h / 2;
      node = rc.linearPath(
        [
          [tipX + 60, tipY + 18],
          [tipX, tipY],
          [tipX + 12, tipY - 9],
          [tipX, tipY],
          [tipX + 14, tipY + 8],
        ],
        opts,
      );
    }
    this.svg.appendChild(node);
    await animateStroke(node, MARK_MS);
    const base = this.body.getBoundingClientRect();
    return { x: base.left + box.x + box.w / 2, y: base.top + box.y + box.h / 2 };
  }

  /** User closed the board: stop everything that belongs to it. */
  close(): void {
    if (this.closed) return;
    this.remove();
    this.opts.onClose?.();
  }

  remove(): void {
    if (this.closed) return;
    this.closed = true;
    this.el.classList.add('closing');
    setTimeout(() => this.el.remove(), 250);
  }

  private layout(): void {
    if (this.closed) return;
    this.alignEquals();
    for (const line of this.lines) fitLine(line.ink);
  }

  /** Shifts working lines so their "=" signs stand in one column. */
  private alignEquals(): void {
    const lines = this.lines.filter((l) => l.aligned);
    for (const l of lines) l.eqOffset = equalsOffset(l.ink);
    for (let section = 0; section <= this.section; section++) {
      const group = lines.filter((l) => l.section === section);
      const column = Math.max(0, ...group.map((l) => l.eqOffset ?? 0));
      // an indent that would push a line into wrapping is not worth the column
      const room = this.body.clientWidth * 0.3;
      for (const l of group) {
        if (l.eqOffset !== null) {
          l.ink.style.marginLeft = `${Math.min(column - l.eqOffset, room)}px`;
        }
      }
    }
  }

  /** Rect relative to the board body (the marks SVG's coordinate space). */
  private relative(r: DOMRect): Rect {
    const base = this.body.getBoundingClientRect();
    return {
      x: r.left - base.left,
      y: r.top - base.top + this.body.scrollTop,
      w: r.width,
      h: r.height,
    };
  }

  private place(anchor: Rect | null): void {
    const vw = window.innerWidth;
    const w = Math.round(Math.min(BOARD_MAX_WIDTH, Math.max(BOARD_MIN_WIDTH, vw * 0.36), vw - 32));
    const vh = window.innerHeight;
    let x: number;
    let y: number;
    if (!anchor) {
      x = vw / 2 - w / 2;
      y = vh * 0.18;
    } else if (anchor.x + anchor.w + GAP + w < vw - 16) {
      x = anchor.x + anchor.w + GAP;
      y = anchor.y;
    } else if (anchor.x - GAP - w > 16) {
      x = anchor.x - GAP - w;
      y = anchor.y;
    } else {
      x = Math.min(Math.max(anchor.x, 16), vw - w - 16);
      y = anchor.y + anchor.h + GAP;
    }
    y = Math.min(Math.max(y, 16), vh * 0.55);
    Object.assign(this.el.style, { left: `${x}px`, top: `${y}px`, width: `${w}px` });
  }
}

function chip(className: string, text: string): HTMLElement {
  const el = document.createElement('span');
  el.className = className;
  el.textContent = text;
  return el;
}

function button(className: string, text: string, label: string): HTMLButtonElement {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = className;
  b.textContent = text;
  b.title = label;
  b.setAttribute('aria-label', label);
  return b;
}

function makeDraggable(el: HTMLElement, handle: HTMLElement): void {
  let start: { x: number; y: number; left: number; top: number } | null = null;
  handle.addEventListener('pointerdown', (e) => {
    if ((e.target as HTMLElement).closest('button')) return;
    start = { x: e.clientX, y: e.clientY, left: el.offsetLeft, top: el.offsetTop };
    try {
      handle.setPointerCapture(e.pointerId);
    } catch {
      // synthetic events (self-test) have no active pointer to capture
    }
    el.classList.add('dragging');
  });
  handle.addEventListener('pointermove', (e) => {
    if (!start) return;
    const left = Math.min(Math.max(start.left + e.clientX - start.x, 0), window.innerWidth - 80);
    const top = Math.min(Math.max(start.top + e.clientY - start.y, 0), window.innerHeight - 40);
    el.style.left = `${left}px`;
    el.style.top = `${top}px`;
  });
  const end = (): void => {
    start = null;
    el.classList.remove('dragging');
  };
  handle.addEventListener('pointerup', end);
  handle.addEventListener('pointercancel', end);
}

/**
 * Pieces of ink in writing order: text leaves (letters, digits, operators) plus the
 * strokes KaTeX draws with borders or SVG (fraction bars, radicals).
 */
function collectGlyphs(root: HTMLElement): HTMLElement[] {
  const base = root.querySelector<HTMLElement>('.katex-html') ?? root;
  const out: HTMLElement[] = [];
  const walk = (node: Element): void => {
    // zero-width struts and spacers carry no ink
    if (node.matches('.vlist-s, .strut, .pstrut, .mspace')) return;
    if (node.matches('.frac-line, svg')) {
      out.push(node as HTMLElement);
      return;
    }
    const hasElementChild = [...node.children].some((c) => !c.matches('.vlist-s, .strut, .pstrut'));
    if (!hasElementChild) {
      if ((node.textContent ?? '').trim()) out.push(node as HTMLElement);
      return;
    }
    for (const child of node.children) walk(child);
  };
  walk(base);
  return out;
}

/**
 * KaTeX breaks an inline formula only between atoms, never inside \text{}, so long sentences
 * ran off the board. Each \text{} run is split into words (Japanese: characters, which may
 * break anywhere) joined by \allowbreak, so a line wraps like handwriting on a board.
 */
export function breakableText(latex: string): string {
  return latex.replace(/\\text\{([^{}]*)\}/g, (whole, body: string) => {
    const pieces = body.match(CJK_OR_WORD);
    if (!pieces || pieces.length < 2) return whole;
    return pieces.map((p) => `\\text{${p}}`).join('\\allowbreak ');
  });
}

// One Japanese character (closing punctuation stays on its line), a word with its trailing
// space, or a run of spaces.
const CJK_OR_WORD =
  /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}ー][、。，．・）」』]*|[^\s\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}ー]+\s*|\s+/gu;

/** Shrinks a line that is still wider than the board after wrapping (a wide fraction). */
function fitLine(ink: HTMLElement): void {
  ink.style.fontSize = '';
  if (ink.clientWidth === 0 || ink.scrollWidth - ink.clientWidth <= 1) return;
  const scale = Math.max(MIN_LINE_SCALE, ink.clientWidth / ink.scrollWidth);
  ink.style.fontSize = `${scale.toFixed(3)}em`;
}

/**
 * KaTeX typesets minus as U+2212, which the handwriting font draws as a long dash; a
 * hand-written minus is the short stroke of "-".
 */
function handwriteMinus(root: HTMLElement): void {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (n.textContent?.includes('−')) n.textContent = n.textContent.replaceAll('−', '-');
  }
}

/** Horizontal offset of the first "=" (or inequality) in a rendered line, or null. */
function equalsOffset(ink: HTMLElement): number | null {
  const rel = [...ink.querySelectorAll<HTMLElement>('.mrel')].find((el) =>
    /^[=<>≤≥≠]$/.test((el.textContent ?? '').trim()),
  );
  if (!rel) return null;
  // Layout px, not screen px: the first line is measured while the board still pops in (scaled).
  const box = ink.getBoundingClientRect();
  const scale = box.width > 0 ? ink.offsetWidth / box.width : 1;
  return (rel.getBoundingClientRect().left - box.left) * scale;
}

/** One shared SVG filter that roughens edges and adds grain, like chalk on a board. */
function ensureChalkFilter(): void {
  if (document.getElementById('chalk-filter')) return;
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('width', '0');
  svg.setAttribute('height', '0');
  svg.style.position = 'absolute';
  svg.innerHTML = `
    <filter id="chalk-filter" x="-5%" y="-10%" width="110%" height="120%">
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="wobble"/>
      <feDisplacementMap in="SourceGraphic" in2="wobble" scale="1.6" result="rough"/>
      <feTurbulence type="fractalNoise" baseFrequency="2.2" numOctaves="1" seed="3" result="grain"/>
      <feColorMatrix in="grain" type="matrix"
        values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 -0.7 1.2" result="mask"/>
      <feComposite in="rough" in2="mask" operator="in"/>
    </filter>`;
  document.body.appendChild(svg);
}

/** Locates the rendered glyphs for a LaTeX fragment by matching plain text. */
function findTarget(root: HTMLElement, latex: string): DOMRect | null {
  const plain = (s: string): string =>
    s
      .replace(/\\(text|mathrm|mathbf)\{([^}]*)\}/g, '$2')
      .replace(/\\frac\{([^}]*)\}\{([^}]*)\}/g, '$1$2')
      .replace(/\\[a-zA-Z]+/g, '')
      .replace(/[{}\s^_]/g, '')
      .replace(/−/g, '-');
  const wanted = plain(latex);
  if (!wanted) return null;
  const base = root.querySelector('.katex-html') ?? root;
  const walker = document.createTreeWalker(base, NodeFilter.SHOW_TEXT);
  const nodes: { node: Text; start: number }[] = [];
  let text = '';
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const t = (n.textContent ?? '').replace(/\s/g, '').replace(/−/g, '-');
    if (!t) continue;
    nodes.push({ node: n as Text, start: text.length });
    text += t;
  }
  const at = text.indexOf(wanted);
  if (at < 0) return null;
  const end = at + wanted.length;
  const hit = nodes.filter(
    (n) => n.start < end && n.start + (n.node.textContent?.length ?? 0) > at,
  );
  if (hit.length === 0) return null;
  const range = document.createRange();
  range.setStartBefore(hit[0]!.node);
  range.setEndAfter(hit[hit.length - 1]!.node);
  return range.getBoundingClientRect();
}

function animateStroke(group: SVGGElement, ms: number): Promise<void> {
  const paths = [...group.querySelectorAll('path')];
  for (const p of paths) {
    const len = p.getTotalLength();
    p.style.strokeDasharray = `${len}`;
    p.style.strokeDashoffset = `${len}`;
    p.animate([{ strokeDashoffset: len }, { strokeDashoffset: 0 }], {
      duration: ms,
      easing: 'ease-out',
      fill: 'forwards',
    });
  }
  return new Promise((r) => setTimeout(r, ms));
}

export const GLYPH_WRITE_MS = GLYPH_MS;
