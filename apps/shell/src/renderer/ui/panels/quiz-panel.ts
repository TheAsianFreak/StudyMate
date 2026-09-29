import type { Difficulty, DocInfo, QuizItem } from '@studymate/protocol';
import { onLangChange, t, type PlainKey } from '../../../shared/i18n';
import type { AppContext } from '../../app-context';
import { errorText } from '../../backend/client';
import { clear, h, tex } from '../dom';
import { Panel } from '../panel';

/** Subjects offered per language; the localized name is what the backend receives. */
const SUBJECTS: PlainKey[] = [
  'quiz.subject.math',
  'quiz.subject.science',
  'quiz.subject.english',
  'quiz.subject.language',
  'quiz.subject.social',
  'quiz.subject.history',
];
const DIFFICULTY_LABEL: Record<Difficulty, PlainKey> = {
  easy: 'quiz.difficulty.easy',
  normal: 'quiz.difficulty.normal',
  hard: 'quiz.difficulty.hard',
};
const PRAISE: PlainKey[] = ['quiz.praise1', 'quiz.praise2', 'quiz.praise3'];
const CIRCLED = ['①', '②', '③', '④', '⑤'];

/** Scene B (SPEC 2): generate verified questions, answer them, grade, explain. */
export class QuizPanel {
  private readonly panel: Panel;
  private items: QuizItem[] = [];
  private index = 0;
  private score = 0;
  /** The shown item was submitted: Enter must not grade it again (score, wrong notes). */
  private answered = false;
  /** Setup form on screen (re-rendered on a language switch; a running quiz is left alone). */
  private inSetup = false;

  constructor(private readonly app: AppContext) {
    this.panel = new Panel(app.overlay, { title: 'quiz.title', icon: '✏️', width: 420 });
    onLangChange(() => {
      if (this.panel.isOpen && this.inSetup) void this.renderSetup();
    });
  }

  open(): void {
    this.panel.open();
    void this.renderSetup();
  }

  private async renderSetup(): Promise<void> {
    const body = this.panel.body;
    clear(body);
    this.inSetup = true;
    let docs: DocInfo[] = [];
    try {
      docs = (
        await this.app.backend.request(
          { type: 'docs_get', id: this.app.backend.newId('docs') },
          'docs',
        )
      ).docs;
    } catch {
      // no docs or offline
    }
    if (!this.inSetup) return;
    clear(body);
    const subject = h(
      'select',
      { class: 'field' },
      ...SUBJECTS.map((key) => h('option', { value: t(key) }, t(key))),
    );
    const unit = h('input', { class: 'field', placeholder: t('quiz.unitPlaceholder') });
    const difficulty = h(
      'select',
      { class: 'field' },
      ...(['easy', 'normal', 'hard'] as const).map((d) =>
        h('option', { value: d, selected: d === 'normal' }, t(DIFFICULTY_LABEL[d])),
      ),
    );
    const count = h('input', { class: 'field', type: 'number', min: 1, max: 10, value: 5 });
    const source = h(
      'select',
      { class: 'field' },
      h('option', { value: '' }, t('quiz.noSource')),
      ...docs.map((d) => h('option', { value: d.doc_id }, `📄 ${d.title}`)),
    );
    const start = h('button', { class: 'btn primary', type: 'button' }, t('quiz.start'));
    start.addEventListener(
      'click',
      () =>
        void this.generate({
          subject: subject.value,
          unit: unit.value.trim(),
          difficulty: difficulty.value as Difficulty,
          count: Math.min(10, Math.max(1, Number(count.value) || 5)),
          source: source.value,
        }),
    );
    body.append(
      h('label', {}, t('quiz.subject'), subject),
      h('label', {}, t('quiz.unit'), unit),
      h(
        'div',
        { class: 'row' },
        h('label', {}, t('quiz.difficulty'), difficulty),
        h('label', {}, t('quiz.count'), count),
      ),
      h('label', {}, t('quiz.source'), source),
      h('p', { class: 'hint' }, t('quiz.verifyHint')),
      start,
    );
  }

  private async generate(opts: {
    subject: string;
    unit: string;
    difficulty: Difficulty;
    count: number;
    source: string;
  }): Promise<void> {
    const body = this.panel.body;
    clear(body);
    this.inSetup = false;
    const status = h('p', { class: 'status' }, t('quiz.generating'));
    const bar = h('div', { class: 'progress' }, h('span'));
    body.append(status, bar);
    this.app.director.ui.say(t('quiz.makingSay', { subject: opts.subject, n: opts.count }), 3000);
    try {
      const reply = await this.app.backend.request(
        {
          type: 'generate_quiz',
          id: this.app.backend.newId('quiz'),
          subject: opts.subject,
          difficulty: opts.difficulty,
          count: opts.count,
          ...(opts.unit ? { unit: opts.unit } : {}),
          ...(opts.source ? { source_doc_id: opts.source } : {}),
        },
        'quiz_items',
        (m) => {
          if (m.type === 'quiz_progress') {
            status.textContent = t('quiz.progress', { done: m.done, total: m.total });
            (bar.firstElementChild as HTMLElement).style.width =
              `${(100 * m.done) / Math.max(1, m.total)}%`;
          }
        },
      );
      this.items = reply.items;
      this.index = 0;
      this.score = 0;
      if (this.items.length === 0) {
        status.textContent = t('quiz.noneVerified');
        body.append(
          h(
            'button',
            { class: 'btn', type: 'button', onclick: () => void this.renderSetup() },
            t('quiz.resetup'),
          ),
        );
        return;
      }
      this.app.director.ui.say(t('quiz.readySay'), 2500);
      this.renderItem();
    } catch (err) {
      status.textContent = errorText(err);
      body.append(
        h(
          'button',
          { class: 'btn', type: 'button', onclick: () => void this.renderSetup() },
          t('common.back'),
        ),
      );
    }
  }

  private renderItem(): void {
    const item = this.items[this.index];
    const body = this.panel.body;
    clear(body);
    this.answered = false;
    if (!item) {
      this.renderSummary();
      return;
    }
    const header = h(
      'p',
      { class: 'quiz-meta' },
      `${this.index + 1} / ${this.items.length}`,
      item.confidence !== 'high'
        ? h(
            'span',
            { class: `confidence confidence-${item.confidence}` },
            t(item.confidence === 'medium' ? 'confidence.medium' : 'confidence.low'),
          )
        : null,
    );
    const question = h('div', { class: 'quiz-question' }, tex(item.question_latex));
    body.append(header, question);
    if (item.source) {
      body.append(h('p', { class: 'hint' }, t('quiz.sourcePage', { page: item.source.page })));
    }
    const submit = (answer: string): void => void this.grade(item, answer);
    if (item.choices && item.choices.length > 0) {
      const list = h('div', { class: 'choices' });
      item.choices.forEach((c, i) => {
        list.append(
          h(
            'button',
            { class: 'btn choice', type: 'button', onclick: () => submit(c) },
            h('span', { class: 'choice-no' }, CIRCLED[i] ?? `${i + 1}.`),
            tex(c),
          ),
        );
      });
      body.append(list);
    } else {
      const input = h('input', { class: 'field', placeholder: t('quiz.answerPlaceholder') });
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') submit(input.value);
      });
      body.append(
        input,
        h(
          'button',
          { class: 'btn primary', type: 'button', onclick: () => submit(input.value) },
          t('quiz.submit'),
        ),
      );
      input.focus();
    }
  }

  private async grade(item: QuizItem, answer: string): Promise<void> {
    if (!answer.trim() || this.answered) return;
    this.answered = true;
    const body = this.panel.body;
    const controls = [
      ...body.querySelectorAll<HTMLButtonElement | HTMLInputElement>('button, input'),
    ];
    for (const c of controls) c.disabled = true;
    try {
      const graded = await this.app.backend.request(
        { type: 'quiz_answer', id: this.app.backend.newId('grade'), item_id: item.item_id, answer },
        'quiz_graded',
      );
      const result = h('div', { class: `quiz-result ${graded.correct ? 'ok' : 'ng'}` });
      if (graded.correct) {
        this.score++;
        this.app.sfx.chime();
        this.app.director.emotion('happy', 0.9);
        this.app.director.gesture('nod', 900);
        this.app.director.ui.say(t(PRAISE[this.index % PRAISE.length]!), 2000);
        result.append(t('quiz.correct'));
      } else {
        this.app.director.emotion('surprised', 0.6);
        this.app.director.ui.say(t('quiz.wrongSay'), 2500);
        result.append(t('quiz.wrong'), tex(graded.correct_answer));
        if (graded.note_id) result.append(h('small', {}, t('quiz.savedNote')));
      }
      const next = h(
        'button',
        { class: 'btn primary', type: 'button' },
        t(this.index + 1 < this.items.length ? 'quiz.next' : 'quiz.results'),
      );
      next.addEventListener('click', () => {
        this.index++;
        this.renderItem();
      });
      const explain = h('button', { class: 'btn', type: 'button' }, t('common.showSolution'));
      explain.addEventListener('click', () => {
        const voice = this.app.voice();
        void this.app.timeline.play(item.solution.steps, {
          title: t('quiz.solutionTitle'),
          confidence: item.confidence,
          ...(voice ? { voice } : {}),
        });
      });
      body.append(result, h('div', { class: 'row' }, explain, next));
      next.focus(); // Enter now goes on to the next question
    } catch (err) {
      body.append(h('p', { class: 'status error' }, errorText(err)));
      // not graded: let the student submit again
      this.answered = false;
      for (const c of controls) c.disabled = false;
    }
  }

  private renderSummary(): void {
    const body = this.panel.body;
    const total = this.items.length;
    const perfect = this.score === total;
    this.app.director.emotion(perfect ? 'happy' : 'neutral', perfect ? 1 : 0);
    this.app.director.ui.say(
      perfect ? t('quiz.perfectSay') : t('quiz.scoreSay', { total, score: this.score }),
      3500,
    );
    body.append(
      h(
        'div',
        { class: 'quiz-summary' },
        h('strong', {}, `${this.score} / ${total}`),
        perfect ? ' 🎉' : '',
      ),
      h(
        'div',
        { class: 'row' },
        h(
          'button',
          { class: 'btn primary', type: 'button', onclick: () => void this.renderSetup() },
          t('quiz.again'),
        ),
      ),
    );
  }
}
