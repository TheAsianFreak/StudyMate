import type { ModelInfo, Status } from '@studymate/protocol';
import { getLang, onLangChange, t } from '../../shared/i18n';
import type { BackendClient } from '../backend/client';
import { errorText } from '../backend/client';
import { missingForStatus } from '../backend/models';
import type { Director } from '../director/director';
import { formatBytes, h } from './dom';

/** Why the setup runs: the first launch (or a resume), or a switch to another language. */
export type SetupReason = 'first' | 'language';

/**
 * First-run (and resume) model setup: downloads every model the recommended tier needs
 * for the current language, one after another, with a progress card. Models for other
 * languages (`ModelInfo.langs`) are skipped. Interrupted downloads resume on the next
 * launch (the downloader keeps `.part` files), so installing the app is the only step.
 */
export class ModelSetup {
  private running = false;
  private stopRequested = false;
  private readonly card: HTMLElement;
  private readonly title: HTMLElement;
  private readonly detail: HTMLElement;
  private readonly bar: HTMLElement;
  private readonly stopBtn: HTMLButtonElement;
  private doneBytes = 0;
  private totalBytes = 0;
  private fileDone = 0;
  /** The detail text before the " · done / total" byte counter. */
  private detailLine = '';

  constructor(
    parent: HTMLElement,
    private readonly backend: BackendClient,
    private readonly director: Director,
  ) {
    this.title = h('strong', {}, t('setup.title'));
    this.detail = h('p', { class: 'setup-detail' });
    this.bar = h('span');
    this.stopBtn = h('button', { class: 'btn small ghost', type: 'button' }, t('setup.later'));
    this.stopBtn.addEventListener('click', () => {
      this.stopRequested = true;
      this.stopBtn.disabled = true;
      this.setDetail(t('setup.stopping'));
    });
    this.card = h(
      'section',
      { class: 'setup-card', 'data-hit': true, hidden: true },
      h('div', { class: 'setup-head' }, h('span', {}, '🌸'), this.title),
      h('div', { class: 'progress' }, this.bar),
      this.detail,
      h('div', { class: 'row' }, this.stopBtn),
    );
    parent.appendChild(this.card);
    onLangChange(() => (this.stopBtn.textContent = t('setup.later')));
    backend.on('download_progress', (m) => {
      if (!this.running) return;
      if (m.done) {
        this.fileDone += m.total ?? m.downloaded;
        this.render(0);
      } else {
        this.render(m.downloaded);
      }
    });
  }

  /** Models the current tier and language still need, in download order. */
  static missing(status: Status): ModelInfo[] {
    return missingForStatus(status, getLang());
  }

  get isRunning(): boolean {
    return this.running;
  }

  async run(status: Status, reason: SetupReason = 'first'): Promise<void> {
    const missing = ModelSetup.missing(status);
    if (this.running || missing.length === 0) return;
    this.running = true;
    this.stopRequested = false;
    this.stopBtn.disabled = false;
    this.stopBtn.hidden = false;
    this.doneBytes = 0;
    this.totalBytes = missing.reduce((a, m) => a + m.size, 0);
    this.card.hidden = false;
    this.director.ui.say(t(reason === 'first' ? 'setup.sayFirst' : 'setup.sayLanguage'), 6000);

    let failed: string | null = null;
    for (const [i, model] of missing.entries()) {
      if (this.stopRequested) break;
      this.fileDone = 0;
      this.title.textContent = t('setup.titleProgress', { i: i + 1, n: missing.length });
      this.setDetail(t('setup.downloading', { model: model.title }));
      try {
        await this.backend.request(
          { type: 'download_model', id: this.backend.newId('setup'), model_id: model.model_id },
          'status',
          undefined,
          12 * 3600_000,
        );
      } catch (err) {
        failed = errorText(err);
        break;
      }
      this.doneBytes += model.size;
      this.render(0);
    }
    this.running = false;

    if (failed) {
      this.title.textContent = t('setup.failedTitle');
      this.detail.textContent = t('setup.failedDetail', { error: failed });
      this.stopBtn.hidden = true;
      return;
    }
    if (this.stopRequested) {
      this.card.hidden = true;
      return;
    }
    this.title.textContent = t('setup.doneTitle');
    this.detail.textContent = t('setup.doneDetail');
    this.stopBtn.hidden = true;
    this.director.emotion('happy', 0.9);
    this.director.gesture('nod', 900);
    this.director.ui.say(t('setup.doneSay'), 6000);
    setTimeout(() => (this.card.hidden = true), 8000);
  }

  private setDetail(line: string): void {
    this.detailLine = line;
    this.render(0);
  }

  private render(currentFileBytes: number): void {
    const done = Math.min(this.totalBytes, this.doneBytes + this.fileDone + currentFileBytes);
    const pct = this.totalBytes ? (100 * done) / this.totalBytes : 100;
    this.bar.style.width = `${pct.toFixed(1)}%`;
    this.detail.textContent = `${this.detailLine} · ${formatBytes(done)} / ${formatBytes(this.totalBytes)}`;
  }
}
