import type { ScriptStep } from '@studymate/protocol';
import { getLang, LANGS, setAddress, t, type Lang } from '../shared/i18n';
import type { AppContext } from './app-context';
import { tex } from './ui/dom';

/** Test content in each UI language, so screenshots show that language on the board too. */
interface SelfTestContent {
  board: ScriptStep[];
  unit: string;
  followUpStep: ScriptStep;
  followUpQuestion: string;
  closeTest: ScriptStep[];
  chat: string;
  question: string;
  solve: string;
  followUp: string;
  quizSubject: string;
  quizUnit: string;
}

const CONTENT: Record<Lang, SelfTestContent> = {
  ko: {
    board: [
      { say: '일차방정식이네요.', write: String.raw`\frac{x}{2} + 3 = 7`, role: 'intro', note: '' },
      {
        say: '이항하면 부호가 바뀌어요.',
        write: String.raw`\text{이항: 부호를 바꿔 다른 변으로}`,
        role: 'concept',
        note: '등식의 성질',
      },
      {
        say: '3을 오른쪽으로 이항해요.',
        write: String.raw`\frac{x}{2} = 7 - 3`,
        role: 'solve',
        note: '3 이항',
      },
      {
        say: '정리하면 이렇게 돼요.',
        write: String.raw`\frac{x}{2} = 4`,
        role: 'solve',
        note: '정리',
        mark: { type: 'circle', target: '4' },
      },
      {
        say: '양변에 2를 곱하면 끝이에요!',
        write: 'x = 8',
        role: 'solve',
        note: '양변 × 2',
        emotion: 'happy',
      },
      {
        say: '넣어 보면 딱 맞아요.',
        write: String.raw`\frac{8}{2} + 3 = 7`,
        role: 'check',
        note: '검산',
      },
      {
        say: '이항, 정리, 계수 없애기!',
        write: String.raw`\text{이항 → 정리 → 계수 없애기}`,
        role: 'summary',
        note: '',
      },
    ],
    unit: '중1 · 일차방정식',
    followUpStep: {
      say: '양변에 같은 수를 빼도 등식은 그대로예요.',
      write: String.raw`\frac{x}{2} + 3 - 3 = 7 - 3`,
    },
    followUpQuestion: '왜 3을 넘기면 빼기가 돼요?',
    closeTest: [
      {
        say: '첫 줄을 써 볼게요. 천천히 설명할게요.',
        write: '2x - 5 = 11',
        role: 'intro',
        note: '',
      },
      { say: '이 줄은 닫으면 나오면 안 돼요.', write: '2x = 16', role: 'solve', note: '5 이항' },
      { say: '이 줄도 나오면 안 돼요.', write: 'x = 8', role: 'solve', note: '양변 ÷ 2' },
    ],
    chat: '오늘 공부하기 너무 싫어요. 한마디 해줘요.',
    question: '피타고라스 정리가 뭐예요?',
    solve: '2x - 5 = 11 일 때 x의 값을 구하시오.',
    followUp: '왜 이항하면 부호가 바뀌어요?',
    quizSubject: '수학',
    quizUnit: '일차방정식',
  },
  ja: {
    board: [
      {
        say: '一次方程式ですね。',
        write: String.raw`\frac{x}{2} + 3 = 7`,
        role: 'intro',
        note: '',
      },
      {
        say: '移項すると符号が変わりますよ。',
        write: String.raw`\text{移項：符号を変えて反対の辺へ}`,
        role: 'concept',
        note: '等式の性質',
      },
      {
        say: '3を右辺に移項しますね。',
        write: String.raw`\frac{x}{2} = 7 - 3`,
        role: 'solve',
        note: '3を移項',
      },
      {
        say: '整理するとこうなります。',
        write: String.raw`\frac{x}{2} = 4`,
        role: 'solve',
        note: '整理',
        mark: { type: 'circle', target: '4' },
      },
      {
        say: '両辺に2をかければ完成です！',
        write: 'x = 8',
        role: 'solve',
        note: '両辺 × 2',
        emotion: 'happy',
      },
      {
        say: '代入するとぴったりですね。',
        write: String.raw`\frac{8}{2} + 3 = 7`,
        role: 'check',
        note: '検算',
      },
      {
        say: '移項、整理、係数を消す！',
        write: String.raw`\text{移項 → 整理 → 係数を消す}`,
        role: 'summary',
        note: '',
      },
    ],
    unit: '中1・一次方程式',
    followUpStep: {
      say: '両辺から同じ数をひいても、等式はそのままです。',
      write: String.raw`\frac{x}{2} + 3 - 3 = 7 - 3`,
    },
    followUpQuestion: 'どうして3を移すとひき算になるの？',
    closeTest: [
      {
        say: '1行目を書きますね。ゆっくり説明します。',
        write: '2x - 5 = 11',
        role: 'intro',
        note: '',
      },
      { say: 'この行は閉じたら出ちゃだめです。', write: '2x = 16', role: 'solve', note: '5を移項' },
      { say: 'この行も出ちゃだめです。', write: 'x = 8', role: 'solve', note: '両辺 ÷ 2' },
    ],
    chat: '今日は勉強したくないです。ひとこと言ってください。',
    question: '三平方の定理って何ですか？',
    solve: '2x - 5 = 11 のとき、x の値を求めなさい。',
    followUp: 'どうして移項すると符号が変わるの？',
    quizSubject: '数学',
    quizUnit: '一次方程式',
  },
  en: {
    board: [
      {
        say: "It's a linear equation.",
        write: String.raw`\frac{x}{2} + 3 = 7`,
        role: 'intro',
        note: '',
      },
      {
        say: 'Moving a term across flips its sign.',
        write: String.raw`\text{Move a term: flip its sign}`,
        role: 'concept',
        note: 'balance rule',
      },
      {
        say: "Let's move the 3 to the right.",
        write: String.raw`\frac{x}{2} = 7 - 3`,
        role: 'solve',
        note: 'move 3',
      },
      {
        say: 'Tidying up, we get this.',
        write: String.raw`\frac{x}{2} = 4`,
        role: 'solve',
        note: 'simplify',
        mark: { type: 'circle', target: '4' },
      },
      {
        say: "Multiply both sides by 2 and we're done!",
        write: 'x = 8',
        role: 'solve',
        note: 'both sides × 2',
        emotion: 'happy',
      },
      {
        say: 'Plug it back in and it fits perfectly.',
        write: String.raw`\frac{8}{2} + 3 = 7`,
        role: 'check',
        note: 'check',
      },
      {
        say: 'Move, simplify, clear the coefficient!',
        write: String.raw`\text{move → simplify → divide}`,
        role: 'summary',
        note: '',
      },
    ],
    unit: 'Grade 7 · Linear equations',
    followUpStep: {
      say: 'Subtracting the same number from both sides keeps them equal.',
      write: String.raw`\frac{x}{2} + 3 - 3 = 7 - 3`,
    },
    followUpQuestion: 'Why does moving the 3 turn it into a minus?',
    closeTest: [
      {
        say: "I'll write the first line. Nice and slow.",
        write: '2x - 5 = 11',
        role: 'intro',
        note: '',
      },
      {
        say: 'This line must not appear after closing.',
        write: '2x = 16',
        role: 'solve',
        note: 'move 5',
      },
      { say: 'Neither should this one.', write: 'x = 8', role: 'solve', note: 'both sides ÷ 2' },
    ],
    chat: "I really don't feel like studying today. Say something!",
    question: 'What is the Pythagorean theorem?',
    solve: 'Find x if 2x - 5 = 11.',
    followUp: 'Why does the sign flip when you move a term?',
    quizSubject: 'Math',
    quizUnit: 'linear equations',
  },
};

/** Hooks the self test needs from main.ts beyond the app context. */
export interface SelfTestHooks {
  openPanel(name: string): void;
  /** Switches the UI and backend language like the settings would (not persisted). */
  switchLanguage(lang: Lang): void;
  /** Hides the onboarding card again (self-test runs count as accepted). */
  closeOnboarding(): void;
}

/**
 * Development self-test (`STUDYMATE_SELFTEST=1`): drives the real app end to end without
 * touching the user's mouse or keyboard. Progress is logged to the console (forwarded to
 * the main process stdout); `SNAP <name>` asks the main process to screenshot our window.
 */
export async function runSelfTest(app: AppContext, hooks: SelfTestHooks): Promise<void> {
  const { openPanel } = hooks;
  const content = CONTENT[getLang()];
  const log = (msg: string): void => console.log(`[selftest] ${msg}`);
  const wait = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms));
  // The capture happens asynchronously in the main process: hold the scene still for it.
  const snap = async (name: string): Promise<void> => {
    console.log(`SNAP ${name}`);
    await wait(700);
  };
  const until = async (cond: () => boolean, ms: number, what: string): Promise<boolean> => {
    const end = Date.now() + ms;
    while (!cond()) {
      if (Date.now() > end) {
        log(`timeout waiting for ${what}`);
        return false;
      }
      await wait(200);
    }
    return true;
  };
  const step = async (name: string, fn: () => Promise<void>): Promise<void> => {
    const t = performance.now();
    try {
      await fn();
      log(`OK ${name} (${((performance.now() - t) / 1000).toFixed(1)}s)`);
    } catch (err) {
      log(`FAIL ${name}: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const only = new URLSearchParams(location.search).get('selftest') ?? 'all';
  const want = (name: string): boolean => only === 'all' || only.split(',').includes(name);

  await until(() => app.director.ready, 60_000, 'godot ready');
  await until(() => app.backend.connected && app.backend.status !== null, 180_000, 'backend');
  log(
    `status ${JSON.stringify(app.backend.status?.capabilities)} tier=${app.backend.status?.tier}`,
  );
  await wait(2500);
  await snap('idle');

  // Closes the newest open panel so the next screenshot shows one panel at a time.
  const closeTopPanel = (): void =>
    [...document.querySelectorAll<HTMLElement>('.panel')]
      .pop()
      ?.querySelector<HTMLButtonElement>('.panel-close')
      ?.click();
  const clickTab = (tab: string): void =>
    document.querySelector<HTMLButtonElement>(`.panel .tab[data-tab="${tab}"]`)?.click();

  if (want('panels')) {
    await step('panels', async () => {
      openPanel('settings');
      for (const tab of ['general', 'voice', 'drowsy', 'character', 'models']) {
        clickTab(tab);
        await wait(tab === 'voice' ? 2500 : 900);
        await snap(`panel-settings-${tab}`);
      }
      closeTopPanel();
      for (const name of ['quiz', 'docs', 'credits', 'ask', 'notes', 'review']) {
        openPanel(name);
        await wait(1500);
        await snap(`panel-${name}`);
        closeTopPanel();
      }
      // Toast and the capture overlay (cancelled by its own button, not OS input).
      app.toasts.show(t('reminder.title'), [t('reminder.cards', { n: 3 }), t('reminder.how')]);
      openPanel('capture');
      await wait(900);
      await snap('region-select');
      document.querySelector<HTMLButtonElement>('.region-cancel')?.click();
    });
  }
  if (want('onboarding')) {
    await step('onboarding card (not accepted)', async () => {
      app.openOnboarding();
      await until(() => document.querySelector('.eula-text') !== null, 10_000, 'EULA text');
      await wait(900);
      await snap('onboarding-top');
      const body = document.querySelector<HTMLElement>('.onboarding-body');
      if (body) body.scrollTop = body.scrollHeight;
      await wait(500);
      await snap('onboarding-bottom');
      const start = document.querySelector<HTMLButtonElement>('.onboarding-footer .btn.primary');
      log(`agree button disabled before checking: ${start?.disabled ?? '-'}`);
      hooks.closeOnboarding();
    });
  }
  if (want('address')) {
    await step('address in canned lines', async () => {
      // Local only: the user's saved address is restored and nothing reaches the backend.
      const sample = { ko: '선배', ja: '先輩', en: 'Alex' }[getLang()];
      const keys = ['character.hello', 'wake.tap', 'wake.awake', 'quiz.praise1'] as const;
      for (const address of ['', sample]) {
        setAddress(address);
        log(`address "${address}": ${keys.map((k) => t(k)).join(' | ')}`);
      }
      app.director.ui.say(t('character.hello'), 3000);
      await wait(2200);
      await snap('address-hello');
      setAddress(app.settings().address);
    });
  }
  if (want('langswitch')) {
    await step('language switch (live)', async () => {
      const from = getLang();
      const to = LANGS[(LANGS.indexOf(from) + 1) % LANGS.length]!;
      openPanel('settings');
      clickTab('general');
      hooks.switchLanguage(to);
      await wait(2500);
      log(`switched ${from} -> ${to}: html lang=${document.documentElement.lang}`);
      await snap(`langswitch-${to}`);
      hooks.switchLanguage(from);
      await wait(1500);
      await snap(`langswitch-back-${from}`);
      closeTopPanel();
    });
  }
  if (want('board')) {
    await step('board (offline script)', async () => {
      await app.timeline.play(content.board, {
        title: t('hud.boardTest'),
        unit: content.unit,
        confidence: 'high',
        onAsk: () => openPanel('ask'),
      });
      await snap('board');
      const eqs = [...document.querySelectorAll<HTMLElement>('.board-line')].map((l) => {
        const ink = l.querySelector<HTMLElement>('.board-ink')!;
        const eq = [...ink.querySelectorAll('.mrel')].find((e) => e.textContent?.trim() === '=');
        return `${l.className.split(' ')[1]} ink@${Math.round(ink.getBoundingClientRect().left)} ml=${ink.style.marginLeft} eq@${eq ? Math.round(eq.getBoundingClientRect().left) : '-'}`;
      });
      log(`board eq ${JSON.stringify(eqs)}`);
      const board = document.querySelector<HTMLElement>('.board');
      const header = board?.querySelector<HTMLElement>('header');
      if (board && header) {
        const before = board.getBoundingClientRect();
        const r = header.getBoundingClientRect();
        const at = { x: r.left + 40, y: r.top + 10 };
        const ev = (type: string, dx: number): PointerEvent =>
          new PointerEvent(type, {
            bubbles: true,
            pointerId: 7,
            clientX: at.x + dx,
            clientY: at.y + dx / 2,
          });
        header.dispatchEvent(ev('pointerdown', 0));
        header.dispatchEvent(ev('pointermove', -120));
        header.dispatchEvent(ev('pointerup', -120));
        const after = board.getBoundingClientRect();
        log(
          `drag moved board by ${Math.round(after.left - before.left)},${Math.round(after.top - before.top)}`,
        );
        await snap('board-dragged');
      }
      await app.timeline.play([content.followUpStep], { followUp: content.followUpQuestion });
      const sections = document.querySelectorAll('.board:not(.closing)').length;
      const dividers = document.querySelectorAll('.board:not(.closing) .board-divider').length;
      log(`follow-up on same board: boards=${sections} dividers=${dividers}`);
      await snap('board-followup');
      app.timeline.closeBoard();
    });
    await step('board close stops explanation', async () => {
      const t0 = performance.now();
      const done = app.timeline.play(content.closeTest, { title: t('hud.boardTest') });
      // the previous test's board may still be fading out (.closing)
      const live = '.board:not(.closing)';
      await until(
        () => document.querySelector(`${live} .board-line`) !== null,
        30_000,
        'first line',
      );
      await wait(1500);
      document.querySelector<HTMLButtonElement>(`${live} .board-close`)?.click();
      const closedAt = performance.now();
      await done;
      log(
        `close -> play resolved in ${Math.round(performance.now() - closedAt)}ms (total ${Math.round(performance.now() - t0)}ms), playing=${app.timeline.playing}`,
      );
      await wait(400);
      log(`boards left after close: ${document.querySelectorAll(live).length}`);
    });
  }
  if (want('math')) {
    await step('broken model LaTeX never shows red error text', async () => {
      // shapes the model really writes (trailing \, $ inside, %, ^ in \text, missing brace, ...)
      const broken = [
        'R_{\\text{병렬}} = 2 \\Omega\\',
        String.raw`P = $I^2 R$ = 16\text{ W}`,
        String.raw`\text{x^2의 계수}`,
        String.raw`50% \text{ 증가}`,
        String.raw`a & b = 3`,
        String.raw`\angle A = 30\degree`,
        String.raw`\frac{1}{2`,
        String.raw`x = 3 # 답`,
        String.raw`\Ω = 5`,
        String.raw`\foo{x} + \bar{y}`,
      ];
      const host = document.createElement('div');
      document.body.append(host);
      for (const latex of broken) host.append(tex(latex));
      const errors = host.querySelectorAll('.katex-error').length;
      const plain = [...host.children].filter((c) => !c.querySelector('.katex')).length;
      log(
        `math: ${broken.length} broken inputs -> katex-error ${errors} (expected 0), as plain text ${plain}`,
      );
      host.remove();
      await app.timeline.play(
        broken.slice(0, 4).map((write) => ({ say: '확인', write })),
        { title: t('hud.boardTest') },
      );
      const boardErrors = document.querySelectorAll('.board .katex-error').length;
      log(`math on board: katex-error ${boardErrors} (expected 0)`);
      await snap('math');
      app.timeline.closeBoard();
    });
  }
  if (want('overlap')) {
    await step('a new script interrupts the one speaking (no two voices)', async () => {
      const audio = app.timeline.audio;
      const play = audio.play.bind(audio);
      let active = 0;
      let most = 0;
      audio.play = (voice) => {
        const pb = play(voice);
        active++;
        most = Math.max(most, active);
        void pb.done.then(() => active--);
        return pb;
      };
      try {
        const lines = (n: number, what: string): ScriptStep[] =>
          Array.from({ length: n }, (_, i) => ({
            say: `${what} ${i + 1}번째 문장이에요. 조금 길게 말해 볼게요.`,
          }));
        const first = app.timeline.play(lines(4, '첫 번째 대답의'));
        await until(() => active > 0, 30_000, 'first answer speaking');
        await wait(1200);
        const second = app.timeline.play(lines(2, '두 번째 대답의'));
        await Promise.all([first, second]);
        log(`voices at once: max ${most} (expected 1), playing=${app.timeline.playing}`);
      } finally {
        audio.play = play;
      }
    });
  }
  if (want('boardlong')) {
    await step('board long lines wrap inside the board', async () => {
      const long: ScriptStep[] = [
        {
          say: '긴 문장이에요.',
          write: String.raw`\text{다음 글을 읽고 글쓴이의 주장으로 가장 적절한 것을 고르시오. 단, 지문에 제시된 근거만 사용하시오.}`,
          role: 'intro',
        },
        {
          say: 'English.',
          write: String.raw`\text{Read the passage and choose the statement that best matches the author's main claim about technology.}`,
          role: 'concept',
        },
        {
          say: '日本語です。',
          write: String.raw`\text{移項すると符号が変わるので、両辺から同じ数を引いて整理します。}`,
          role: 'solve',
          note: '移項',
        },
        {
          say: '긴 식이에요.',
          write: String.raw`3x^2 + 12x - 7 + 5x^3 - 8x + 2x^2 - 14 + 9x - 21 = 4x^3 + 7x^2 - 3x + 18 - 2x + 11`,
          role: 'solve',
          note: '동류항 정리',
        },
        {
          say: '큰 분수예요.',
          write: String.raw`\frac{1+2+3+4+5+6+7+8+9+10+11+12+13+14+15+16+17+18+19+20}{21+22+23+24+25+26+27+28+29+30+31+32+33+34+35}`,
          role: 'solve',
        },
      ];
      await app.timeline.play(long, { title: t('hud.boardTest') });
      const board = document.querySelector<HTMLElement>('.board:not(.closing)');
      const edge = board?.getBoundingClientRect();
      const lines = [...document.querySelectorAll<HTMLElement>('.board:not(.closing) .board-line')];
      const report = lines.map((l) => {
        const ink = l.querySelector<HTMLElement>('.board-ink')!;
        const glyphs = [...ink.querySelectorAll<HTMLElement>('.glyph-written')];
        const right = Math.max(...glyphs.map((g) => g.getBoundingClientRect().right));
        const rows = new Set(glyphs.map((g) => Math.round(g.getBoundingClientRect().top / 8))).size;
        return `${l.className.split(' ')[1]} past-edge=${edge ? Math.max(0, Math.round(right - edge.right + 20)) : '?'}px rows~${rows} font=${ink.style.fontSize || '1'}`;
      });
      log(`board width ${Math.round(edge?.width ?? 0)}px; ${JSON.stringify(report)}`);
      await snap('board-long');
      app.timeline.closeBoard();
    });
  }
  if (want('ask')) {
    await step('ask (chat)', async () => {
      await app.conversation.ask(content.chat);
      await snap('ask-chat');
    });
    await step('ask (question)', async () => {
      await app.conversation.ask(content.question);
      await snap('ask-question');
      app.timeline.closeBoard();
    });
  }
  if (want('solve')) {
    await step('solve text', async () => {
      const done = app.solve.solveText(content.solve);
      await wait(20_000);
      await snap('solve-midway');
      await done;
      await snap('solve-done');
      const lines = [...document.querySelectorAll('.board-line')].map(
        (l) =>
          `${l.className.replace('board-line ', '')}: ${l.querySelector('.board-note')?.textContent ?? ''}`,
      );
      log(`board lines ${JSON.stringify(lines)}`);
    });
    await step('follow-up about solved problem', async () => {
      const topic = app.conversation.currentTopic();
      log(`topic ${topic ? topic.label : 'none'}`);
      openPanel('ask');
      await wait(600);
      await snap('ask-topic');
      await app.conversation.ask(content.followUp);
      await snap('ask-followup');
      const answer = [...document.querySelectorAll('.turn.assistant')].pop()?.textContent;
      const dividers = document.querySelectorAll('.board:not(.closing) .board-divider').length;
      log(`follow-up answer (dividers on board: ${dividers}): ${answer ?? '-'}`);
      app.timeline.closeBoard();
    });
  }
  if (want('csat')) {
    // A non-math CSAT item: evidence-style lesson (English text on the board, "확인" label).
    await step('solve CSAT English (evidence lesson)', async () => {
      const done = app.solve.solveText(
        '다음 빈칸에 들어갈 말로 가장 적절한 것은?\n' +
          'Many people believe that success comes from talent alone. However, studies of top performers show ' +
          'that what separates them from others is not innate ability but the amount of deliberate practice ' +
          'they have done. In other words, excellence is less a gift than ________.\n' +
          '① a matter of luck ② the result of sustained effort ③ something we are born with ' +
          '④ a product of competition ⑤ an illusion created by media',
      );
      await wait(35_000);
      await snap('csat-midway');
      await done;
      await snap('csat-done');
      const labels = [...document.querySelectorAll('.board .line-label')].map((l) => l.textContent);
      const title = document.querySelector('.board h2')?.textContent;
      log(`csat board: ${title} | labels ${JSON.stringify(labels)}`);
      app.timeline.closeBoard();
    });
  }
  if (want('quiz')) {
    await step('quiz generate + grade', async () => {
      const reply = await app.backend.request(
        {
          type: 'generate_quiz',
          id: app.backend.newId('q'),
          subject: content.quizSubject,
          unit: content.quizUnit,
          difficulty: 'easy',
          count: 2,
        },
        'quiz_items',
      );
      log(
        `quiz items: ${reply.items.length} ${JSON.stringify(reply.items.map((i) => [i.question_latex, i.answer, i.confidence]))}`,
      );
      const item = reply.items[0];
      if (item) {
        const wrong = await app.backend.request(
          {
            type: 'quiz_answer',
            id: app.backend.newId('a'),
            item_id: item.item_id,
            answer: '__wrong__',
          },
          'quiz_graded',
        );
        const right = await app.backend.request(
          {
            type: 'quiz_answer',
            id: app.backend.newId('a'),
            item_id: item.item_id,
            answer: item.answer,
          },
          'quiz_graded',
        );
        log(`graded wrong=${wrong.correct} right=${right.correct} note=${wrong.note_id ?? '-'}`);
        const due = await app.backend.request(
          { type: 'review_due_get', id: app.backend.newId('d') },
          'review_due',
        );
        log(`review due cards: ${due.cards.length}`);
      }
    });
  }
  if (want('quizui')) {
    await step('quiz panel: count kept, no repeats, one grade per question', async () => {
      openPanel('quiz');
      const panel = (): HTMLElement | null =>
        [...document.querySelectorAll<HTMLElement>('.panel')].find((p) =>
          p.querySelector('.quiz-question, .field[type="number"]'),
        ) ?? null;
      await until(() => panel()?.querySelector('input[type="number"]') != null, 20_000, 'setup');
      const setup = panel()!;
      const count = setup.querySelector<HTMLInputElement>('input[type="number"]')!;
      count.value = '3';
      const unit = setup.querySelector<HTMLInputElement>('input:not([type])');
      if (unit) unit.value = content.quizUnit;
      setup.querySelector<HTMLButtonElement>('button.btn.primary')!.click();
      await until(() => panel()?.querySelector('.quiz-question') != null, 600_000, 'quiz items');
      const questions: string[] = [];
      const results: number[] = [];
      let total = '';
      for (let i = 0; i < 10; i++) {
        const body = panel();
        const q = body?.querySelector('.quiz-question');
        if (!body || !q) break;
        total = body.querySelector('.quiz-meta')?.textContent ?? '';
        questions.push(q.textContent ?? '');
        const choice = body.querySelector<HTMLButtonElement>('button.choice');
        const input = body.querySelector<HTMLInputElement>('input.field');
        const enter = (): boolean =>
          input!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
        if (choice) {
          choice.click();
          choice.click();
        } else if (input) {
          input.value = '1';
          enter();
          enter();
          await wait(300);
          enter();
        }
        await until(() => body.querySelector('.quiz-result') !== null, 60_000, 'graded');
        if (input) enter(); // after grading: must not grade again
        await wait(1500);
        results.push(body.querySelectorAll('.quiz-result').length);
        const next = [...body.querySelectorAll<HTMLButtonElement>('.row .btn.primary')].pop();
        log(`item ${i + 1}: focus on next=${document.activeElement === next}`);
        next?.click();
      }
      const summary = panel()?.querySelector('.quiz-summary')?.textContent ?? '';
      log(
        `quiz ${total}: results per item ${JSON.stringify(results)} (expected all 1), ` +
          `unique questions ${new Set(questions).size}/${questions.length}, summary ${summary}`,
      );
      closeTopPanel();
    });
  }
  if (want('wake')) {
    await step('wake-up sequence', async () => {
      app.wake.intensity = 'normal';
      app.wake.test();
      await wait(1500);
      await snap('wake-talk');
      await wait(10_500);
      await snap('wake-tap');
      await wait(11_000);
      await snap('wake-chalk');
      await wait(4000);
    });
  }
  log(`sync ${JSON.stringify(app.timeline.sync.report())}`);
  log('SELFTEST DONE');
}
