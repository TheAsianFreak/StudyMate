import type { WrongNote } from '@studymate/protocol';
import { onLangChange, t } from '../../../shared/i18n';
import type { AppContext } from '../../app-context';
import { errorText } from '../../backend/client';
import { clear, formatDate, h, tex } from '../dom';
import { Panel } from '../panel';

/** Wrong-answer notebook (Phase 4): every wrong quiz answer with its solution. */
export class NotesPanel {
  private readonly panel: Panel;

  constructor(private readonly app: AppContext) {
    this.panel = new Panel(app.overlay, { title: 'notes.title', icon: '📒', width: 440 });
    onLangChange(() => {
      if (this.panel.isOpen) void this.load();
    });
  }

  open(): void {
    this.panel.open();
    void this.load();
  }

  private async load(): Promise<void> {
    const body = this.panel.body;
    clear(body);
    body.append(h('p', { class: 'status' }, t('common.loading')));
    try {
      const reply = await this.app.backend.request(
        { type: 'wrong_notes_get', id: this.app.backend.newId('notes') },
        'wrong_notes',
      );
      this.render(reply.notes);
    } catch (err) {
      clear(body);
      body.append(h('p', { class: 'status error' }, errorText(err)));
    }
  }

  private render(notes: WrongNote[]): void {
    const body = this.panel.body;
    clear(body);
    if (notes.length === 0) {
      body.append(h('p', { class: 'empty' }, t('notes.empty')));
      return;
    }
    for (const note of notes) {
      const explain = h('button', { class: 'btn small', type: 'button' }, t('common.showSolution'));
      explain.addEventListener('click', () => {
        const voice = this.app.voice();
        void this.app.timeline.play(note.item.solution.steps, {
          title: t('notes.replayTitle'),
          confidence: note.item.confidence,
          ...(voice ? { voice } : {}),
        });
      });
      const remove = h('button', { class: 'btn small ghost', type: 'button' }, t('common.delete'));
      remove.addEventListener('click', async () => {
        try {
          const reply = await this.app.backend.request(
            { type: 'wrong_note_delete', id: this.app.backend.newId('del'), note_id: note.note_id },
            'wrong_notes',
          );
          this.render(reply.notes);
        } catch (err) {
          this.app.toasts.show(t('notes.deleteFailed'), [errorText(err)], 'error');
        }
      });
      body.append(
        h(
          'article',
          { class: 'note' },
          h(
            'div',
            { class: 'note-meta' },
            `${note.item.subject}${note.item.unit ? ` · ${note.item.unit}` : ''} · ${formatDate(note.created_at)}`,
          ),
          h('div', { class: 'quiz-question' }, tex(note.item.question_latex)),
          h(
            'p',
            { class: 'note-answers' },
            t('notes.myAnswer'),
            h('span', { class: 'ng' }, note.user_answer),
            t('notes.correctAnswer'),
            tex(note.item.answer),
          ),
          h('div', { class: 'row' }, explain, remove),
        ),
      );
    }
  }
}
