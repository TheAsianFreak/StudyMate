import type { ChatTurn, ScriptStep } from '@studymate/protocol';
import { t } from '../../shared/i18n';
import { errorText, type BackendClient } from '../backend/client';
import type { Director } from './director';
import type { Timeline } from './timeline';

const MAX_HISTORY = 16;
const MAX_EMPTY_TURNS = 2;
/** A solved problem stays the topic of follow-up questions for this long. */
const TOPIC_TTL_MS = 30 * 60_000;

/** The problem currently being discussed (e.g. the last captured and solved one). */
export interface Topic {
  /** Short label for the UI, e.g. "2x - 5 = 11". */
  label: string;
  /** Sent as ask_request.context: problem, answer and how it was explained. */
  context: string;
  /** Sent as ask_request.problem_id: the backend answers from the full problem text and
   * re-solves when the student corrects the answer. */
  problemId?: string | undefined;
  at: number;
}

export interface ConversationUi {
  listening(level: number, partial: string): void;
  heard(text: string): void;
  thinking(): void;
  idle(): void;
  /** The character's answer as text (for the ask panel log). */
  answered(text: string): void;
}

/**
 * Voice (or typed) conversation with the character (SPEC: 음성 질문, 대화).
 * Push-to-talk starts a turn; the backend records until silence (VAD), transcribes,
 * and the answer is played by the Timeline. With auto-listen on, the next turn starts
 * once the character has finished speaking (half-duplex so it never hears itself).
 */
export class Conversation {
  private history: ChatTurn[] = [];
  private topic: Topic | null = null;
  private active = false;
  private listeningId: string | null = null;
  private emptyTurns = 0;
  /** Counts questions: an answer that arrives after a newer question was asked is dropped. */
  private asked = 0;
  autoListen = true;

  constructor(
    private readonly director: Director,
    private readonly backend: BackendClient,
    private readonly timeline: Timeline,
    private readonly ui: ConversationUi,
    private readonly voice: () => string | undefined,
  ) {
    backend.on('stt_level', (m) => {
      if (m.id === this.listeningId) this.ui.listening(m.level, '');
    });
    backend.on('stt_partial', (m) => {
      if (!m.id || m.id === this.listeningId) this.ui.listening(-1, m.text);
    });
  }

  get isListening(): boolean {
    return this.listeningId !== null;
  }

  /** Hotkey / button: start talking, or stop the current recording early. */
  toggle(): void {
    if (this.listeningId) {
      this.backend.send({ type: 'stt_stop', id: this.listeningId });
      return;
    }
    if (this.timeline.playing) this.timeline.stop();
    this.active = true;
    this.emptyTurns = 0;
    void this.listen();
  }

  end(): void {
    this.active = false;
    if (this.listeningId) this.backend.send({ type: 'stt_stop', id: this.listeningId });
    this.ui.idle();
  }

  /** Makes follow-up questions (typed or spoken) refer to this problem. */
  setTopic(label: string, context: string, problemId?: string): void {
    this.topic = { label, context: context.slice(0, 780), problemId, at: Date.now() };
  }

  /** The current topic if it is still fresh. */
  currentTopic(): Topic | null {
    if (this.topic && Date.now() - this.topic.at > TOPIC_TTL_MS) this.topic = null;
    return this.topic;
  }

  clearTopic(): void {
    this.topic = null;
  }

  /** Forgets the history and topic (after a language switch they are in the old language). */
  forget(): void {
    this.history = [];
    this.topic = null;
  }

  /** Typed question from the ask panel. */
  async ask(text: string, context?: string): Promise<void> {
    this.active = false;
    // A new question interrupts whatever the character is saying, like the talk hotkey.
    if (this.timeline.playing) this.timeline.stop();
    await this.respond(text, context);
  }

  private async listen(): Promise<void> {
    if (this.backend.status?.capabilities.stt !== true) {
      this.director.ui.notify(t('stt.unavailableTitle'), [t('stt.unavailableHint')], 'error');
      this.active = false;
      return;
    }
    const id = this.backend.newId('stt');
    this.listeningId = id;
    this.director.lookAt('user');
    this.director.emotion('happy', 0.35);
    this.ui.listening(0, '');
    let text = '';
    try {
      const final = await this.backend.request(
        { type: 'stt_start', id },
        'stt_final',
        undefined,
        90_000,
      );
      text = final.text.trim();
    } catch (err) {
      this.director.ui.notify(t('stt.errorTitle'), [errorText(err)], 'error');
      this.active = false;
    } finally {
      this.listeningId = null;
    }
    if (!text) {
      this.emptyTurns++;
      this.ui.idle();
      if (this.active && this.emptyTurns < MAX_EMPTY_TURNS) {
        this.director.ui.say(t('talk.didntHear'), 2200);
        await sleep(1800);
        if (this.active) void this.listen();
      } else {
        this.active = false;
      }
      return;
    }
    this.emptyTurns = 0;
    this.ui.heard(text);
    await this.respond(text);
    if (this.active && this.autoListen) void this.listen();
    else this.active = false;
  }

  private async respond(text: string, explicitContext?: string): Promise<void> {
    const topic = explicitContext ? null : this.currentTopic();
    const context = explicitContext ?? topic?.context;
    const turn = ++this.asked;
    this.ui.thinking();
    this.director.emotion('neutral', 0);
    let steps: ScriptStep[];
    try {
      const answer = await this.backend.request(
        {
          type: 'ask_request',
          id: this.backend.newId('ask'),
          text,
          ...(context ? { context } : {}),
          ...(topic?.problemId ? { problem_id: topic.problemId } : {}),
          history: this.history.slice(-MAX_HISTORY),
        },
        'ask_answer',
      );
      steps = answer.steps;
    } catch (err) {
      if (turn !== this.asked) return; // a newer question is being answered
      this.ui.idle();
      this.director.ui.say(t('talk.cantAnswer'), 2500);
      this.director.ui.notify(t('talk.failedTitle'), [errorText(err)], 'error');
      return;
    }
    if (turn !== this.asked) return; // a newer question is being answered
    this.ui.idle();
    const said = steps.map((s) => s.say).join(' ');
    this.remember({ role: 'user', text });
    this.remember({ role: 'assistant', text: said });
    this.ui.answered(said);
    const voice = this.voice();
    await this.timeline.play(steps, {
      title: t('board.answerTitle'),
      // A follow-up about the problem on the board is written under its solution.
      ...(context && !explicitContext ? { followUp: text } : {}),
      ...(voice ? { voice } : {}),
    });
  }

  private remember(turn: ChatTurn): void {
    this.history.push(turn);
    if (this.history.length > MAX_HISTORY)
      this.history.splice(0, this.history.length - MAX_HISTORY);
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
