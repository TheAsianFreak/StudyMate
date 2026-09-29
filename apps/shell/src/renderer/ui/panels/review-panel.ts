import type { ReviewCard } from '@studymate/protocol';
import { onLangChange, t } from '../../../shared/i18n';
import type { AppContext } from '../../app-context';
import { errorText } from '../../backend/client';
import { clear, formatDate, h, nodes, tex } from '../dom';
import { Panel } from '../panel';

const RATINGS = [1, 2, 3, 4] as const;
const RATING_LABEL = {
  1: 'review.rating.1',
  2: 'review.rating.2',
  3: 'review.rating.3',
  4: 'review.rating.4',
} as const;

/** FSRS spaced-repetition review of wrong answers (Phase 4). */
export class ReviewPanel {
  private readonly panel: Panel;
  private cards: ReviewCard[] = [];
  private index = 0;

  constructor(private readonly app: AppContext) {
    this.panel = new Panel(app.overlay, { title: 'review.title', icon: '🔁', width: 420 });
    // Re-render the card on screen (the answer is hidden again) in the new language.
    onLangChange(() => {
      if (this.panel.isOpen && this.cards[this.index]) this.show(this.index);
    });
  }

  open(): void {
    this.panel.open();
    void this.load();
  }

  /** Number of cards due now (for reminders); 0 on error. */
  async dueCount(): Promise<number> {
    try {
      const reply = await this.app.backend.request(
        { type: 'review_due_get', id: this.app.backend.newId('due') },
        'review_due',
      );
      return reply.cards.length;
    } catch {
      return 0;
    }
  }

  private async load(): Promise<void> {
    const body = this.panel.body;
    clear(body);
    this.cards = [];
    try {
      const reply = await this.app.backend.request(
        { type: 'review_due_get', id: this.app.backend.newId('due') },
        'review_due',
      );
      this.cards = reply.cards;
      if (this.cards.length === 0) {
        body.append(
          ...nodes(
            h('p', { class: 'empty' }, t('review.none')),
            reply.next_due
              ? h('p', { class: 'hint' }, t('review.next', { when: formatDate(reply.next_due) }))
              : null,
          ),
        );
        return;
      }
      this.show(0);
    } catch (err) {
      body.append(h('p', { class: 'status error' }, errorText(err)));
    }
  }

  private show(i: number): void {
    this.index = i;
    const body = this.panel.body;
    clear(body);
    const card = this.cards[i];
    if (!card) {
      this.app.director.emotion('happy', 0.8);
      this.app.director.ui.say(t('review.doneSay'), 2500);
      body.append(h('p', { class: 'empty' }, t('review.done')));
      return;
    }
    const answerBox = h(
      'div',
      { class: 'review-answer', hidden: true },
      t('review.answer'),
      tex(card.item.answer),
    );
    const ratings = h('div', { class: 'row ratings', hidden: true });
    for (const rating of RATINGS) {
      ratings.append(
        h(
          'button',
          {
            class: `btn rating r${rating}`,
            type: 'button',
            onclick: () => void this.grade(card, rating, i),
          },
          t(RATING_LABEL[rating]),
        ),
      );
    }
    const reveal = h('button', { class: 'btn primary', type: 'button' }, t('review.reveal'));
    reveal.addEventListener('click', () => {
      answerBox.hidden = false;
      ratings.hidden = false;
      reveal.remove();
    });
    body.append(
      h('p', { class: 'quiz-meta' }, `${i + 1} / ${this.cards.length} · ${card.item.subject}`),
      h('div', { class: 'quiz-question' }, tex(card.item.question_latex)),
      reveal,
      answerBox,
      ratings,
    );
  }

  private async grade(card: ReviewCard, rating: 1 | 2 | 3 | 4, i: number): Promise<void> {
    try {
      const reply = await this.app.backend.request(
        { type: 'review_grade', id: this.app.backend.newId('rg'), card_id: card.card_id, rating },
        'review_graded',
      );
      this.app.toasts.show(t('review.nextTitle'), [formatDate(reply.next_due)]);
    } catch (err) {
      this.app.toasts.show(t('review.gradeFailed'), [errorText(err)], 'error');
    }
    this.show(i + 1);
  }
}
