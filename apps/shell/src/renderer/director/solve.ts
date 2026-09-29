import type { ScriptStep, SolveProgress, SolveScript } from '@studymate/protocol';
import { t } from '../../shared/i18n';
import type { Rect } from '../../shared/ipc';
import { errorText, type BackendClient } from '../backend/client';
import { selectRegion } from '../ui/region-select';
import type { Director } from './director';
import type { Timeline } from './timeline';

/** What the character says while the backend works on each solve stage. */
function stageLine(stage: SolveProgress['stage'] | 'ocr'): string {
  switch (stage) {
    case 'ocr':
      return t('solve.stage.ocr');
    case 'solving':
      return t('solve.stage.solving');
    case 'verifying':
      return t('solve.stage.verifying');
    case 'retry':
      return t('solve.stage.retry');
    case 'voicing':
      return t('solve.stage.voicing');
    default:
      return t('solve.stage.other');
  }
}

/**
 * Scene A (SPEC 2): capture a region → OCR/vision → verified solve script → the
 * character walks to the board and hand-writes while explaining.
 */
export interface SolveHooks {
  /** A problem was solved: make it the topic of follow-up questions. */
  onSolved(label: string, context: string, problemId?: string): void;
  /** 💬 on the solution board. */
  onAsk(): void;
}

export class SolveFlow {
  private running = false;

  constructor(
    private readonly director: Director,
    private readonly backend: BackendClient,
    private readonly timeline: Timeline,
    private readonly overlay: HTMLElement,
    private readonly voice: () => string | undefined,
    private readonly hooks: SolveHooks,
  ) {}

  async captureAndSolve(): Promise<void> {
    if (this.running) return;
    if (this.backend.status?.capabilities.solve !== true) {
      this.director.ui.notify(t('solve.unavailableTitle'), [t('solve.unavailableHint')], 'error');
      return;
    }
    this.running = true;
    this.timeline.stop();
    try {
      const rect = await selectRegion(this.overlay);
      if (!rect) return;
      const image = await window.shell.captureRegion(rect);
      await this.solve({ image_base64: image }, rect);
    } finally {
      this.running = false;
    }
  }

  /** Typed problem (ask panel "풀어줘" or evaluation). */
  async solveText(problem: string): Promise<void> {
    await this.solve({ problem_text: problem }, null);
  }

  private async solve(
    input: { image_base64?: string; problem_text?: string },
    anchor: Rect | null,
  ): Promise<void> {
    this.director.acquire();
    const feet = this.director.feet();
    if (anchor && feet)
      this.director.lookAt({ x: anchor.x + anchor.w / 2, y: anchor.y + anchor.h / 2 });
    this.director.emotion('neutral', 0);
    this.director.gesture('nod', 800);
    this.director.ui.say(stageLine('ocr'), 20_000);
    try {
      const reply = await this.backend.request(
        { type: 'solve_request', id: this.backend.newId('solve'), ...input },
        'solve_script',
        (progress) => {
          if (progress.type === 'solve_progress') {
            this.director.ui.say(stageLine(progress.stage), 20_000);
          }
        },
      );
      const script = reply.script;
      const steps: ScriptStep[] = [...script.steps];
      if (script.confidence === 'low') {
        steps.push({ say: t('solve.lowConfidence'), emotion: 'sleepy' });
      }
      const voice = this.voice();
      this.hooks.onSolved(
        script.problem_latex || script.final_answer,
        describeSolution(script),
        script.problem_id,
      );
      await this.timeline.play(steps, {
        anchor,
        title: t('solve.boardTitle', { answer: script.final_answer }),
        unit: script.unit,
        evidence: script.subject !== undefined && script.subject !== 'math',
        confidence: script.confidence,
        onAsk: () => this.hooks.onAsk(),
        ...(voice ? { voice } : {}),
      });
      if (script.confidence !== 'low') this.director.emotion('happy', 0.8);
    } catch (err) {
      this.director.emotion('surprised', 0.6);
      this.director.ui.say(t('solve.failedSay'), 3000);
      this.director.ui.notify(t('solve.failedTitle'), [errorText(err)], 'error');
    } finally {
      this.director.release();
    }
  }
}

/**
 * Compact description of a solved problem for follow-up questions (ask_request.context),
 * in the current language like the rest of the LLM's input.
 */
function describeSolution(script: SolveScript): string {
  const lines = script.steps
    .map((s) => [s.write, s.note ? `(${s.note})` : '', s.say].filter(Boolean).join(' '))
    .join('\n');
  return [
    t('solve.context.intro'),
    script.unit ? t('solve.context.unit', { unit: script.unit }) : '',
    t('solve.context.problem', { problem: script.problem_latex }),
    t('solve.context.answer', { answer: script.final_answer }),
    t('solve.context.steps', { steps: lines }),
  ]
    .filter(Boolean)
    .join('\n');
}
