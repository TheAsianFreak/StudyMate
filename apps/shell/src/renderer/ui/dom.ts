import katex, { type KatexOptions } from 'katex';
import { localeTag, t } from '../../shared/i18n';

type Child = Node | string | null | undefined | false;
type Attrs = Record<string, string | number | boolean | EventListener | undefined>;

/** Tiny element factory: h('button', { class: 'x', onclick: fn }, 'label'). */
export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs: Attrs = {},
  ...children: Child[]
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === false) continue;
    if (key.startsWith('on') && typeof value === 'function') {
      el.addEventListener(key.slice(2), value);
    } else if (key === 'class') {
      el.className = String(value);
    } else if (value === true) {
      el.setAttribute(key, '');
    } else {
      el.setAttribute(key, String(value));
    }
  }
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child);
  }
  return el;
}

/**
 * Natural-language prose (Korean, Japanese or English words) that must not be typeset as
 * one math expression, which would drop its spaces: "2x - 5 = 11 일 때", "x = 3 のとき",
 * "Solve 2x = 6 for x".
 */
const PROSE =
  /[가-힣]{4,}|[\u3040-\u30ff\u4e00-\u9fff]{3,}|(?<![\\a-zA-Z])[a-zA-Z]{2,}\s+[a-zA-Z]{3,}\b/;

/**
 * Renders LaTeX written by the model without KaTeX's red error text. Model LaTeX is
 * sometimes invalid (a stray `$` or trailing `\`, a bare `%` `#` `&`, `^` inside \text{},
 * a command KaTeX lacks, a missing brace): those are repaired and rendered; what still
 * fails is shown as readable plain text.
 */
export function renderMath(el: HTMLElement, latex: string, options: KatexOptions = {}): void {
  // "%" is always a percent sign in model output; as a LaTeX comment it would silently drop
  // the rest of the line (no parse error to repair)
  let source = latex.replace(/(?<!\\)%/g, '\\%');
  for (let tries = 0; tries < 6; tries++) {
    try {
      katex.render(source, el, { ...options, throwOnError: true, strict: 'ignore' });
      return;
    } catch (err) {
      const next = repairLatex(source, err instanceof Error ? err.message : '');
      if (next === source) break;
      source = next;
    }
  }
  console.warn('[math] shown as text:', latex);
  el.textContent = plainMath(latex);
}

/** One round of fixes for a KaTeX parse error (`message`); returns `latex` when out of ideas. */
export function repairLatex(latex: string, message: string): string {
  const undefinedCommand = /Undefined control sequence: \\([A-Za-z]+)/.exec(message);
  if (undefinedCommand) {
    // \degree, \overarc, ...: keep the word, drop the command
    return latex.replace(new RegExp(`\\\\${undefinedCommand[1]}(?![A-Za-z])`, 'g'), '');
  }
  const fixed = latex
    .replace(/(?<!\\)\$/g, '') // $ inside math
    .replace(/\\+\s*$/, '') // trailing backslash
    .replace(/(?<!\\)([%#])/g, '\\$1') // % starts a comment, # is a macro parameter
    .replace(/\\(?=[^ -~])/g, '') // backslash before a non-ASCII letter ("\Ω")
    .replace(/\\text\s*\{([^{}]*)\}/g, (_m, body: string) => {
      const text = body.replace(/(?<!\\)_/g, '\\_').replace(/(?<!\\)\^/g, '\\textasciicircum{}');
      return `\\text{${text}}`;
    });
  const noEnv = latex.includes('\\begin') ? fixed : fixed.replace(/(?<!\\)&/g, '\\&');
  return balanceBraces(noEnv);
}

function balanceBraces(latex: string): string {
  let depth = 0;
  let out = '';
  for (let i = 0; i < latex.length; i++) {
    const ch = latex[i]!;
    const escaped = i > 0 && latex[i - 1] === '\\';
    if (ch === '{' && !escaped) depth++;
    if (ch === '}' && !escaped) {
      if (depth === 0) continue; // unmatched closing brace
      depth--;
    }
    out += ch;
  }
  return out + '}'.repeat(depth);
}

const PLAIN_SYMBOLS: Record<string, string> = {
  times: '×',
  cdot: '·',
  div: '÷',
  pm: '±',
  le: '≤',
  leq: '≤',
  ge: '≥',
  geq: '≥',
  ne: '≠',
  neq: '≠',
  approx: '≈',
  infty: '∞',
  pi: 'π',
  theta: 'θ',
  alpha: 'α',
  beta: 'β',
  to: '→',
  rightarrow: '→',
  Rightarrow: '⇒',
  therefore: '∴',
  circ: '°',
  angle: '∠',
  triangle: '△',
  sum: 'Σ',
  int: '∫',
};

/** Readable text for LaTeX KaTeX cannot render: \frac{a}{b} -> (a)/(b), \sqrt{x} -> √(x). */
export function plainMath(latex: string): string {
  return latex
    .replace(/\\(?:text|mathrm|mathbf|textbf|operatorname)\s*\{([^{}]*)\}/g, '$1')
    .replace(/\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, '($1)/($2)')
    .replace(/\\sqrt\s*\{([^{}]*)\}/g, '√($1)')
    .replace(/\\([A-Za-z]+)/g, (_m, name: string) => PLAIN_SYMBOLS[name] ?? '')
    .replace(/[{}$\\]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Renders text that may contain LaTeX: `$...$` segments or a whole LaTeX string. */
export function tex(source: string, className = 'tex'): HTMLElement {
  const el = h('span', { class: className });
  const parts = source.split(/(\$[^$]+\$)/g);
  const hasDelims = parts.length > 1;
  if (!hasDelims && /\\|\^|_|=/.test(source) && !PROSE.test(source)) {
    renderMath(el, source);
    return el;
  }
  for (const part of parts) {
    if (part.startsWith('$') && part.endsWith('$')) {
      const span = h('span');
      renderMath(span, part.slice(1, -1));
      el.append(span);
    } else if (part) {
      el.append(renderMixed(part));
    }
  }
  return el;
}

/** Sentences with inline math-like fragments (e.g. "2x - 5 = 11 일 때"). */
function renderMixed(text: string): Node {
  const frag = document.createDocumentFragment();
  // \text{...} wrapped Korean inside LaTeX is handled by katex; plain text stays as is.
  if (/\\[a-zA-Z]+|\\text\{/.test(text)) {
    const span = h('span');
    renderMath(span, text);
    frag.append(span);
  } else {
    frag.append(text);
  }
  return frag;
}

/** Drops absent children so optional elements can be passed to append(). */
export function nodes(...children: Child[]): (Node | string)[] {
  return children.filter((c): c is Node | string => c !== null && c !== undefined && c !== false);
}

export function clear(el: HTMLElement): void {
  while (el.firstChild) el.firstChild.remove();
}

export function formatBytes(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)} GB`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(0)} MB`;
  return `${Math.max(1, Math.round(n / 1e3))} KB`;
}

/** Relative time in the UI language: "3일 후", "2時間前", "in 5 minutes". */
export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const now = Date.now();
  const diff = d.getTime() - now;
  const abs = Math.abs(diff);
  const units: [number, Intl.RelativeTimeFormatUnit][] = [
    [86_400_000, 'day'],
    [3_600_000, 'hour'],
    [60_000, 'minute'],
  ];
  const rtf = new Intl.RelativeTimeFormat(localeTag(), { numeric: 'always' });
  for (const [ms, unit] of units) {
    if (abs >= ms) {
      const n = Math.round(abs / ms);
      return rtf.format(diff > 0 ? n : -n, unit);
    }
  }
  return t(diff > 0 ? 'time.soon' : 'time.justNow');
}
