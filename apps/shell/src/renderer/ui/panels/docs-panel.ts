import type { DocInfo } from '@studymate/protocol';
import { onLangChange, t } from '../../../shared/i18n';
import type { AppContext } from '../../app-context';
import { errorText } from '../../backend/client';
import { clear, formatDate, h } from '../dom';
import { Panel } from '../panel';

/** Study material (PDF) library used for grounded quizzes and answers (RAG). */
export class DocsPanel {
  private readonly panel: Panel;
  private readonly intro: HTMLElement;
  private readonly list: HTMLElement;
  private readonly status: HTMLElement;

  constructor(private readonly app: AppContext) {
    this.panel = new Panel(app.overlay, { title: 'docs.title', icon: '📚', width: 400 });
    this.intro = h('div');
    this.list = h('div', { class: 'doc-list' });
    this.status = h('p', { class: 'status' });
    this.renderIntro();
    this.panel.body.append(this.intro, this.status, this.list);
    onLangChange(() => {
      this.renderIntro();
      this.status.textContent = '';
      if (this.panel.isOpen) void this.refresh();
    });
  }

  open(): void {
    this.panel.open();
    void this.refresh();
  }

  private renderIntro(): void {
    const add = h('button', { class: 'btn primary', type: 'button' }, t('docs.add'));
    add.addEventListener('click', () => void this.importPdf());
    this.intro.replaceChildren(h('p', { class: 'hint' }, t('docs.hint')), add);
  }

  private async refresh(): Promise<void> {
    try {
      const reply = await this.app.backend.request(
        { type: 'docs_get', id: this.app.backend.newId('docs') },
        'docs',
      );
      this.render(reply.docs);
    } catch (err) {
      this.status.textContent = errorText(err);
    }
  }

  private render(docs: DocInfo[]): void {
    clear(this.list);
    if (docs.length === 0) {
      this.list.append(h('p', { class: 'empty' }, t('docs.empty')));
      return;
    }
    for (const doc of docs) {
      const del = h('button', { class: 'btn small ghost', type: 'button' }, t('common.delete'));
      del.addEventListener('click', async () => {
        const reply = await this.app.backend.request(
          { type: 'doc_delete', id: this.app.backend.newId('dd'), doc_id: doc.doc_id },
          'docs',
        );
        this.render(reply.docs);
      });
      this.list.append(
        h(
          'div',
          { class: 'doc' },
          h('strong', {}, `📄 ${doc.title}`),
          h(
            'small',
            {},
            t('docs.meta', {
              pages: doc.pages,
              chunks: doc.chunks,
              date: formatDate(doc.imported_at),
            }) + (doc.empty_pages?.length ? t('docs.skipped', { n: doc.empty_pages.length }) : ''),
          ),
          del,
        ),
      );
    }
  }

  private async importPdf(): Promise<void> {
    const path = await window.shell.pickPdf();
    if (!path) return;
    this.status.textContent = t('common.loading');
    try {
      const reply = await this.app.backend.request(
        { type: 'doc_import', id: this.app.backend.newId('imp'), path },
        'doc_imported',
        (m) => {
          if (m.type === 'doc_progress') {
            const stage = t(m.stage === 'extract' ? 'docs.stage.extract' : 'docs.stage.embed');
            this.status.textContent = t('docs.progress', { stage, done: m.done, total: m.total });
          }
        },
      );
      this.status.textContent = t('docs.imported', { title: reply.doc.title });
      this.app.director.ui.say(t('docs.importedSay'), 3000);
      await this.refresh();
    } catch (err) {
      this.status.textContent = errorText(err);
    }
  }
}
