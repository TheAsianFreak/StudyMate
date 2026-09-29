// Japanese UI strings. Tone: a cute, friendly teacher (casual-polite です/ます).
import type { Messages } from './ko';

export const ja = {
  // --- common -----------------------------------------------------------------------------
  'common.close': '閉じる',
  'common.cancel': 'キャンセル',
  'common.delete': '削除',
  'common.loading': '読み込み中…',
  'common.back': '戻る',
  'common.showSolution': '解説を見る',

  // --- language -----------------------------------------------------------------------------
  'lang.label': '言語 (Language)',
  'lang.hint': '画面の文字、キャラクターのセリフ、音声認識がこの言語になります。',
  'lang.switched': 'はーい！これからは日本語でお話ししますね ✨',

  // --- how the character addresses the user ---------------------------------------------------
  'address.label': 'わたしの呼び方',
  'address.hint':
    'キャラクターがあなたをこう呼びます。名前を入れてもOKです。空欄ならデフォルトの呼び方になります。',
  'address.placeholder': '例) ゆうき、生徒さん、先輩',
  'address.chips': '生徒さん|先輩|マスター',
  'address.default': 'デフォルト',
  'address.save': '保存',
  'address.savedSay': '{address}これからはこう呼びますね！',
  'address.clearedSay': '呼び方をデフォルトに戻しました！',
  'address.failedTitle': '呼び方を保存できませんでした',

  // --- first-run onboarding: EULA consent before any install ----------------------------
  'onboarding.intro':
    'はじめる前に、利用規約を読んで同意してください。同意すると AI モデルのインストールを始めます。',
  'onboarding.changed': '利用規約が変わりました。新しい規約を読んで、もう一度同意してください。',
  'onboarding.eula': '利用規約 (EULA)',
  'onboarding.eulaLoading': '利用規約を読み込み中…',
  'onboarding.eulaMissing':
    '利用規約のファイルが見つかりません。アプリをインストールしなおしてください。',
  'onboarding.eulaFallback': 'この言語の規約がないため、英語の原文を表示しています。',
  'onboarding.optional': '(任意)',
  'onboarding.install': 'インストールについて',
  'onboarding.installSummary':
    'おすすめ構成 ({tier}) に合わせて、AI モデルを{n}個 (合計 {size}) ダウンロードします。',
  'onboarding.installNone': '必要な AI モデルはすべてインストール済みです。',
  'onboarding.installWaiting': 'PCのスペックを確認しています… 少し待っててくださいね！',
  'onboarding.installLocal':
    'AI はすべてこのPCの中だけで動きます。インターネットはこのモデルのダウンロードにだけ使います。',
  'onboarding.agree': '利用規約に同意します',
  'onboarding.start': '同意してインストール',
  'onboarding.startNoInstall': '同意してはじめる',
  'onboarding.quit': '終了',
  'onboarding.locked': 'まずは利用規約に同意してくださいね！',
  'models.needsEula': '利用規約に同意すると、モデルをダウンロードできます。',
  'models.openOnboarding': '利用規約を見る',

  // --- app menu (tray / right click) -------------------------------------------------------
  'menu.capture': '問題を解く (範囲キャプチャ)',
  'menu.talk': '話しかける (音声)',
  'menu.ask': '質問する (入力)',
  'menu.quiz': 'クイズ',
  'menu.notes': 'まちがいノート',
  'menu.review': '復習',
  'menu.docs': '学習資料 (PDF)',
  'menu.settings': '設定',
  'menu.importAvatar': 'アバターを読み込む (VRM)…',
  'menu.resetAvatar': 'デフォルトのキャラクターに戻す',
  'menu.language': '言語 (Language)',
  'menu.debugHud': 'デバッグ HUD',
  'menu.credits': '情報・オープンソースライセンス',
  'menu.quit': '終了',
  'tray.tooltip': 'Your StudyMate — クリック: メニュー / Ctrl+Alt+Q: 終了',
  'tray.tooltipCamera': 'Your StudyMate — Webカメラ使用中 (居眠り検知)',

  // --- main-process dialogs -----------------------------------------------------------------
  'dialog.pickPdf': '学習資料を読み込む',
  'dialog.importAvatar': 'アバターを読み込む',
  'dialog.vrmFilter': 'VRM アバター',
  'dialog.avatarFailed': 'アバターを読み込めませんでした',
  'avatar.tooLarge': 'ファイルが大きすぎます (最大 256MB)。',
  'avatar.notVrm': 'VRM ファイルではないみたいです。',
  'avatar.adult': '成人向けの要素があるアバターは登録できません。（検出: {detail}）',
  'avatar.adultEula': '利用規約により、性的な目的での使用は禁止されています。',
  'avatar.blockedTitle': 'アバターをデフォルトのキャラクターに戻しました',

  // --- backend connection -------------------------------------------------------------------
  'backend.disconnectedTitle': 'バックエンドとの接続が切れました',
  'backend.reconnecting': '再接続しています…',
  'backend.failedTitle': 'バックエンドを起動できませんでした',
  'backend.failedHint': 'AI 機能なしでキャラクターだけ動かします。ログ: %APPDATA%/StudyMate/logs',

  // --- drowsiness ---------------------------------------------------------------------------
  'drowsy.calibrating': '居眠り検知の準備中！5秒だけ画面を見ててくださいね。',
  'drowsy.ready': '準備OK！居眠りしたら起こしますね。',
  'drowsy.errorTitle': '居眠り検知が使えません',

  // --- review reminder ----------------------------------------------------------------------
  'reminder.say': '{address}復習する問題が{n}問ありますよ！一緒にやりましょうか？',
  'reminder.title': '復習のお知らせ',
  'reminder.cards': '復習カード {n}枚',
  'reminder.how': 'メニュー > 復習、またはキャラクターのボタン 🔁',

  // --- character & avatar -------------------------------------------------------------------
  'character.hello': '{address}こんにちは！今日も一緒にがんばりましょう ✨',
  'character.drag': 'わわっ、{address}どこに連れていくんですか〜？！',
  'avatar.backToDefault': 'いつもの姿に戻りました！',
  'avatar.newLook': 'じゃーん！新しい姿、どうですか？',
  'avatar.cantWear': 'うぅ、この服は着られないみたいです…',
  'avatar.loadFailed': 'アバターを読み込めませんでした',
  'avatar.title': 'アバター: {name}',
  'avatar.noName': '名前なし',
  'avatar.authors': '作者: {authors}',
  'avatar.license': 'ライセンス: {license}',
  'avatar.usage': '商用利用: {commercial}・再配布: {redistribution}',
  'avatar.terms': '利用条件は作者のライセンスに従います。ファイルはこのPCにだけ保存されます。',
  'avatar.unspecified': '記載なし',
  'avatar.use.PersonalNonProfit': '個人の非営利のみ',
  'avatar.use.PersonalProfit': '個人の営利まで',
  'avatar.use.AllowCorporation': '法人も可',
  'avatar.use.Allow': '可',
  'avatar.use.Disallow': '不可',
  'godot.missingFeatures': 'Godot に必要なブラウザ機能がありません: {features}',
  'godot.loadFailed':
    'キャラクタービルド ({src}) を読み込めませんでした。先に Godot の Web エクスポートを実行してください。',

  // --- solving ------------------------------------------------------------------------------
  'solve.stage.ocr': '問題を読んでいます…',
  'solve.stage.solving': 'どれどれ… 解いてみますね！',
  'solve.stage.verifying': '答えが合っているか検算中です。',
  'solve.stage.retry': 'あっ、もう一回解いてみますね！',
  'solve.stage.voicing': '説明の準備中…',
  'solve.stage.other': '考え中…',
  'solve.unavailableTitle': '問題を解けません',
  'solve.unavailableHint':
    '設定 > モデル から言語モデルと llama.cpp ランタイムをダウンロードしてください。',
  'solve.lowConfidence':
    '今回の答えは検証を通りませんでした。念のため、もう一度確かめてくださいね！',
  'solve.boardTitle': '解説・答え {answer}',
  'solve.failedSay': 'うぅ、この問題は解けませんでした…',
  'solve.failedTitle': '解けませんでした',
  'solve.context.intro':
    'さっき板書で解いた問題です。生徒はこの解き方について追加で質問するかもしれません。',
  'solve.context.unit': '単元: {unit}',
  'solve.context.problem': '問題: {problem}',
  'solve.context.answer': '答え: {answer}',
  'solve.context.steps': '解き方:\n{steps}',

  // --- board --------------------------------------------------------------------------------
  'board.defaultTitle': '解説',
  'board.answerTitle': '質問への答え',
  'board.ask': 'この問題について質問する',
  'board.close': '板書を閉じる (説明を止める)',
  'board.role.intro': '問題',
  'board.role.concept': 'ポイント',
  'board.role.check': '検算',
  'board.role.confirm': '確かめ',
  'board.role.summary': 'まとめ',
  'confidence.high': '✔ 検証ずみ',
  'confidence.medium': '解き直し一致',
  'confidence.low': '⚠ 要確認',
  'confidence.highTip': 'SymPy で答えを検証しました。',
  'confidence.mediumTip': '記号での検証はできませんでしたが、解き直しても同じ答えになりました。',
  'confidence.lowTip': '検証できませんでした。答えをもう一度確かめてくださいね。',

  // --- conversation -------------------------------------------------------------------------
  'stt.unavailableTitle': '音声認識が使えません',
  'stt.unavailableHint': '設定 > モデル から音声認識 (Whisper) モデルをダウンロードしてください。',
  'stt.errorTitle': '音声認識エラー',
  'talk.didntHear': 'よく聞こえませんでした。もう一回言ってくれますか？',
  'talk.cantAnswer': 'うーん、今はうまく答えられないみたいです…',
  'talk.failedTitle': '答えられませんでした',
  'bubble.listening': '聞いてますよ…',
  'bubble.thinking': 'えっと… 考え中です',

  // --- wake-up ------------------------------------------------------------------------------
  'wake.talk1': '{address}もしかして眠いですか？あとちょっとだけがんばりましょう！',
  'wake.talk2': '{address}目が閉じてるの、見えてますよ〜！',
  'wake.talk3': 'いったんストレッチしてからにしませんか？',
  'wake.tap': 'トントン！{address}起きてくださーい！',
  'wake.softWarn': '…次はチョーク投げちゃいますからね！',
  'wake.throwHard': '教壇モード！くらえーっ！',
  'wake.throw': 'えいっ！',
  'wake.awakeAfterChalk': '目、覚めましたか？{address}またがんばりましょう！',
  'wake.awake': 'よしっ！{address}集中しなおしましょう！',

  // --- dock ---------------------------------------------------------------------------------
  'dock.capture': '問題を解く (Ctrl+Shift+S)',
  'dock.talk': '話しかける (Ctrl+Shift+Space)',
  'dock.ask': '質問する',
  'dock.quiz': 'クイズ',
  'dock.review': '復習',
  'dock.notes': 'まちがいノート',
  'dock.docs': '学習資料',
  'dock.settings': '設定',

  // --- region select ------------------------------------------------------------------------
  'region.hint': '問題の範囲をドラッグしてください',
  'region.hintCancel': '右クリック: キャンセル',

  // --- first-run model setup ----------------------------------------------------------------
  'setup.title': 'AI モデルを準備中',
  'setup.titleProgress': 'AI モデルを準備中 ({i}/{n})',
  'setup.later': 'あとでダウンロード',
  'setup.stopping':
    '今ダウンロード中のファイルが終わったら止めますね。次回の起動時に続きからダウンロードします。',
  'setup.sayFirst':
    'はじめてなので準備がありますよ！AI モデルをダウンロードする間、少しだけ待っててくださいね 🌸',
  'setup.sayLanguage':
    'この言語に必要な AI モデルをダウンロードしますね！少しだけ待っててください 🌸',
  'setup.downloading': '{model} をダウンロード中…',
  'setup.failedTitle': 'モデルを全部ダウンロードできませんでした',
  'setup.failedDetail':
    '{error} 次回の起動時に続きからダウンロードします。(設定 > モデル から今すぐやり直すこともできます)',
  'setup.doneTitle': '準備完了！',
  'setup.doneDetail': 'これで解説・おしゃべり・クイズが全部使えます。',
  'setup.doneSay':
    '準備完了！{address}なんでも聞いてくださいね ✨ (Ctrl+Shift+Space で話しかけられます)',

  // --- debug HUD ----------------------------------------------------------------------------
  'hud.title': 'Your StudyMate・デバッグ',
  'hud.wander': 'うろうろ',
  'hud.move': '移動',
  'hud.boardTest': '板書テスト',
  'hud.wakeTest': '起こすテスト',
  'hud.chalk': 'チョーク',
  'hud.hitBox': 'ヒットボックス',
  'hud.error': 'エラー: {message}',
  'hud.test1': 'まず、3を右辺に移しますね。',
  'hud.test2': '整理するとこうなります。',
  'hud.test3': '両辺に2をかければ完成です！',

  // --- ask panel ----------------------------------------------------------------------------
  'ask.title': '質問する',
  'ask.placeholder':
    '気になることを聞いてくださいね。例) 二次方程式の解の公式はどうして成り立つの？',
  'ask.placeholderTopic':
    'この問題について聞いてくださいね。例) 移項するとなぜ符号が変わるの？ほかの解き方もある？',
  'ask.send': '質問する',
  'ask.solve': '問題を解いて',
  'ask.mic': '声で話す (Ctrl+Shift+Space)',
  'ask.keys': 'Enter: 送信・Shift+Enter: 改行・Ctrl+Shift+Space: 音声で会話',
  'ask.otherQuestion': 'ほかの質問',

  // --- credits panel ------------------------------------------------------------------------
  'credits.title': '情報・オープンソースライセンス',
  'credits.tagline': 'ローカル AI 学習コンパニオン。AI の処理はすべてこのPCの中で行います。',
  'credits.gpl':
    'このプログラムはフリーソフトウェアです。GNU 一般公衆利用許諾書（GPL）第3版に従って再配布・改変できます。いかなる保証もありません。ライセンス全文: https://www.gnu.org/licenses/gpl-3.0.html',
  'credits.character': 'キャラクター',
  'credits.usesCharacter':
    '本ソフトウェアでは、フリー素材キャラクター「つくよみちゃん」（© Rei Yumesaki）を使用しています。',
  'credits.modelTerms':
    '本ソフトウェアに収録されているつくよみちゃん3Dモデルの利用規約は、「つくよみちゃん公式3Dモデル タイプA」の利用規約に準じます。',
  'credits.publishDuty':
    'このキャラクターが登場するコンテンツ（スクリーンショット、動画、配信など）を公開するときは、下記のつくよみちゃん利用規約を守り、ソフトウェア名「Your StudyMate」を表記してください。',
  'credits.termsUrl': '利用規約: {url}',
  'credits.unofficial':
    'つくよみちゃんの言動は公式のものではなく、特定の政治的・宗教的立場を代弁するものではありません。',
  'credits.voices': '声',
  'credits.voicesText':
    '韓国語: MeloTTS (MIT)。日本語・英語: Kokoro-82M (Apache-2.0, © hexgrad)。日本語の声の一部は、テレビ西日本のアナウンサーによる朗読音声 (CC BY 3.0) で学習されています。',
  'credits.eula': '📜 使用許諾契約書 (EULA) を開く',
  'credits.eulaMissing': 'EULA ファイルが見つかりませんでした',
  'credits.licenses': 'オープンソースライセンス',
  'credits.licensesNote': '以下の一覧は韓国語の原文のまま表示しています。',

  // --- docs panel ---------------------------------------------------------------------------
  'docs.title': '学習資料',
  'docs.hint':
    'PDF の文字を取り出して、このPCの中だけで索引を作ります。スキャンした PDF (画像) にはまだ対応していません。',
  'docs.add': '+ PDF を読み込む',
  'docs.empty': '読み込んだ資料はまだありません。',
  'docs.meta': '{pages}ページ・{chunks}チャンク・{date}',
  'docs.skipped': '・スキャン {n}ページはスキップ',
  'docs.stage.extract': '文字を抽出',
  'docs.stage.embed': '索引を作成',
  'docs.progress': '{stage}中… {done}/{total}',
  'docs.imported': '「{title}」を読み込みました！',
  'docs.importedSay': '資料を読みました！これで問題も作れますよ。',

  // --- notes panel --------------------------------------------------------------------------
  'notes.title': 'まちがいノート',
  'notes.empty': 'まだまちがえた問題はありません。すごいです！✨',
  'notes.replayTitle': 'まちがいを見直す',
  'notes.deleteFailed': '削除できませんでした',
  'notes.myAnswer': 'あなたの答え: ',
  'notes.correctAnswer': '・正解: ',

  // --- review panel -------------------------------------------------------------------------
  'review.title': '復習',
  'review.rating.1': 'もう一度',
  'review.rating.2': '難しい',
  'review.rating.3': 'ちょうどいい',
  'review.rating.4': '簡単',
  'review.none': '今は復習するカードがありません。',
  'review.next': '次の復習: {when}',
  'review.doneSay': '今日の復習はおしまい！{address}おつかれさまでした〜',
  'review.done': '復習完了！🎉',
  'review.answer': '正解: ',
  'review.reveal': '正解を見る',
  'review.nextTitle': '次の復習',
  'review.gradeFailed': '記録できませんでした',

  // --- quiz panel ---------------------------------------------------------------------------
  'quiz.title': 'クイズ',
  'quiz.subject.math': '数学',
  'quiz.subject.science': '理科',
  'quiz.subject.english': '英語',
  'quiz.subject.language': '国語',
  'quiz.subject.social': '社会',
  'quiz.subject.history': '歴史',
  'quiz.subject': '教科',
  'quiz.unit': '単元',
  'quiz.unitPlaceholder': '単元 (例: 一次方程式) — 任意',
  'quiz.difficulty': '難易度',
  'quiz.difficulty.easy': 'やさしい',
  'quiz.difficulty.normal': 'ふつう',
  'quiz.difficulty.hard': 'むずかしい',
  'quiz.count': '問題数',
  'quiz.source': '出題元の資料',
  'quiz.noSource': '資料なし (一般の問題)',
  'quiz.verifyHint':
    '解き直して答えが一致した問題と、数学は SymPy の検証を通った問題だけを出しますね。',
  'quiz.start': '問題を出して！',
  'quiz.generating': '問題を作って検証しています…',
  'quiz.makingSay': '{subject}の問題を{n}問、作ってきますね！',
  'quiz.progress': '問題を作成中… {done}/{total}',
  'quiz.noneVerified':
    '検証を通った問題がありませんでした。条件を変えてもう一回やってみましょうか？',
  'quiz.resetup': '設定しなおす',
  'quiz.readySay': 'できました！解いてみましょうか？',
  'quiz.sourcePage': '出典: 資料 {page}ページ',
  'quiz.answerPlaceholder': '答えを入力してください',
  'quiz.submit': '答える',
  'quiz.praise1': '正解です！{address}さすがです！',
  'quiz.praise2': 'ピンポーン！正解ですよ！',
  'quiz.praise3': 'かんぺきです！',
  'quiz.correct': '⭕ 正解！',
  'quiz.wrongSay': 'おしいです！一緒に解いてみましょうか？',
  'quiz.wrong': '❌ 不正解・正解: ',
  'quiz.savedNote': ' (まちがいノートに保存しました)',
  'quiz.next': '次の問題',
  'quiz.results': '結果を見る',
  'quiz.solutionTitle': 'クイズの解説',
  'quiz.perfectSay': '全問正解です！{address}すごいです！',
  'quiz.scoreSay': '{total}問中{score}問正解でした。まちがえた問題は復習しましょうね！',
  'quiz.again': 'もう一回',

  // --- settings panel -----------------------------------------------------------------------
  'settings.title': '設定',
  'settings.tab.general': '一般',
  'settings.tab.voice': '声',
  'settings.tab.drowsy': '居眠り検知',
  'settings.tab.character': 'キャラクター',
  'settings.tab.models': 'モデル',
  'settings.wander': '休憩中は画面を歩き回る',
  'settings.autoListen': '会話モード',
  'settings.autoListenHint': '返事が終わったら、自動でまた聞き取ります',
  'settings.reviewReminders': '復習のお知らせ',
  'settings.reviewRemindersHint': '復習するカードがあると、キャラクターから話しかけます',
  'settings.focusMode': '集中モード',
  'settings.focusModeHint': '起こす機能と、キャラクターからの声かけを止めます',
  'settings.autoDownload': 'AI モデルを自動でダウンロード',
  'settings.autoDownloadHint':
    '起動時に、PCに合ったモデルのうち足りないものを自動でダウンロードします',
  'settings.shortcuts': 'ショートカット',
  'settings.shortcut.capture': ' 問題の範囲をキャプチャ → 解説',
  'settings.shortcut.talk': ' 話しかける (音声で会話)',
  'settings.shortcut.quit': ' 終了',
  'settings.shortcut.mouse': 'キャラクターを右クリック: メニュー・ドラッグ: 移動',

  'voice.type': '声のタイプ',
  'voice.hint':
    'ベースの声に後処理をかけて、いろいろなタイプを作っています。スライダーで自分だけの声も作れますよ。',
  'voice.none': 'この言語の声はまだありません。',
  'voice.mine': ' (マイボイス)',
  'voice.slider.pitch': '高さ',
  'voice.slider.formant': '声質 (フォルマント)',
  'voice.slider.speed': '速さ',
  'voice.slider.brightness': '明るさ (高音)',
  'voice.slider.warmth': 'あたたかさ (低音)',
  'voice.slider.reverb': '響き',
  'voice.slider.volume': '音量',
  'voice.unit.semitone': '半音',
  'voice.preview': '▶ 試聴する',
  'voice.previewText': 'こんにちは！今日も一緒にがんばりましょう。',
  'voice.previewFailed': '試聴できませんでした',
  'voice.namePlaceholder': '新しい声の名前',
  'voice.save': 'マイボイスとして保存',
  'voice.defaultName': 'マイボイス {date}',
  'voice.saved': '保存しました',
  'voice.savedDetail': '「{name}」の声をデフォルトにしました。',
  'voice.saveFailed': '保存できませんでした',

  'drowsy.privacyTitle': '🔒 Webカメラの扱いについて',
  'drowsy.privacy':
    'Webカメラの映像は、このPCのメモリの中で目の閉じ具合 (EAR) と頭の角度の数値に変換されて、すぐに捨てられます。映像や写真を保存したり送信したりはしません。使用中はトレイアイコンに赤い点が表示されます。',
  'drowsy.enable': '居眠り検知を使う (Webカメラ)',
  'drowsy.sensitivity': '感度',
  'drowsy.sens.low': '低め',
  'drowsy.sens.normal': 'ふつう',
  'drowsy.sens.high': '高め',
  'drowsy.intensity': '起こし方の強さ',
  'drowsy.intensity.soft': 'やさしく (声かけ・机トントン)',
  'drowsy.intensity.normal': 'ふつう (+ チョークを軽く)',
  'drowsy.intensity.hard': '教壇モード (チョーク全力！)',
  'drowsy.howItWorks':
    '声かけ → 10秒後に机をトントン → さらに10秒後にチョーク、の順で起こします。キーボードやマウスを使っている間は判定を止めます。',
  'drowsy.preview': '起こし方をプレビュー',

  'character.default': 'デフォルトキャラクター: フリー素材キャラクター「つくよみちゃん」',
  'character.import': 'VRM アバターを読み込む',
  'character.reset': 'デフォルトに戻す',
  'character.hint':
    'BOOTH などで手に入れた VRM (0.x/1.0) が使えます。.unitypackage のアバターは Unity + UniVRM で VRM に変換してください。読み込んだアバターはこのPCにだけ保存され、利用条件は作者のライセンスに従います。',

  'models.waiting': 'バックエンドへの接続を待っています…',
  'models.cpu': 'CPU: {cpu}・{cores}スレッド・RAM {ram}GB',
  'models.gpu': 'GPU: {gpus}',
  'models.noGpu': 'なし',
  'models.tier': 'スペックティア',
  'models.recommended': ' (おすすめ)',
  'models.gpuUse': 'GPU の使用量',
  'models.gpuUse.high': '高 — すべて GPU（いちばん速い）',
  'models.gpuUse.balanced': '中 — 言語モデルの一部を CPU で',
  'models.gpuUse.low': '低 — 言語モデルを CPU で（遅い）',
  'models.gpuUseHint':
    '下げるほど GPU に余裕ができ、ゲームや動画と一緒に使いやすくなりますが、答えは遅くなります。低では難しい問題の推論段階を省きます。検索用の埋め込みはいつも CPU、画像認識はいつも GPU です。',
  'models.allInstalled': '今のティアに必要なモデルはすべてインストール済みです。',
  'models.downloadAll': 'おすすめ構成をまとめてダウンロード ({size})',
  'models.downloadFailed': 'ダウンロードに失敗しました',
  'models.installed': 'インストール済み',
  'models.get': 'ダウンロード',
  'models.required': '・必須',
  'models.currentTier': '・今のティア',
  'models.otherLangs': 'ほかの言語用のモデル ({n}件)',

  // --- welcome panel ------------------------------------------------------------------------
  'welcome.title': 'Your StudyMate へようこそ！',
  'welcome.intro':
    '画面の上を歩き回る先生キャラクターが、問題を板書で解いてくれたり、声でおしゃべりしたり、居眠りしたら起こしてくれたりします。',
  'welcome.capture': ' 問題の範囲をドラッグすると解説を書きます',
  'welcome.talk': ' 話しかける — 声で質問・おしゃべり',
  'welcome.mouse':
    'キャラクターにマウスを乗せるとメニューボタン、右クリックで全部のメニューが出ます',
  'welcome.quit': ' 終了',
  'welcome.needModels': 'モデルが必要です',
  'welcome.needModelsHint':
    '解説やおしゃべりには AI モデルのダウンロードが必要です。PCのスペックに合ったティアをおすすめしますね。',
  'welcome.openModels': 'モデル設定を開く',
  'welcome.drowsyTitle': '🔒 居眠り検知 (任意)',
  'welcome.drowsyHint':
    'Webカメラで目の閉じ具合とうつむきを数値だけで計算して、映像はすぐに捨てます。保存も送信もしません。あとから設定でオンにできます。',
  'welcome.enableDrowsy': '居眠り検知をオンにする',
  'welcome.later': 'あとでにします',
  'welcome.byeDrowsy': '居眠りしたら、わたしが起こしますね！🔔',
  'welcome.bye': 'いつでも呼んでくださいね！',

  // --- relative time ------------------------------------------------------------------------
  'time.soon': 'もうすぐ',
  'time.justNow': 'たった今',

  // --- errors: shell-side -------------------------------------------------------------------
  'error.offline': 'バックエンドに接続されていません。',
  'error.disconnected': 'バックエンドとの接続が切れました。',
  'error.timeout': '応答がタイムアウトしました。',
  // --- errors: backend `error.code` ---------------------------------------------------------
  'error.unknown_item': '問題が見つかりません。もう一度問題を出してもらってください。',
  'error.unknown_model': '不明なモデルです。',
  'error.already_downloading': 'もうダウンロード中ですよ。',
  'error.checksum':
    'ダウンロードしたファイルを検証できませんでした。もう一度ダウンロードしてください。',
  'error.download_failed': 'ダウンロードに失敗しました。ネットワークを確認してください。',
  'error.model_missing':
    '必要な AI モデルがまだありません。設定 > モデル からダウンロードしてください。',
  'error.stt_busy': 'もう聞いていますよ。',
  'error.no_microphone':
    'マイクが見つかりません。マイクの接続と、Windows の設定のマイクへのアクセス許可を確認してください。',
  'error.face_model_failed':
    '顔認識モデルを読み込めませんでした。設定 > モデル からもう一度ダウンロードしてください。',
  'error.camera_unavailable':
    'カメラを開けません。カメラの接続、ほかのアプリが使っていないか、Windows のカメラへのアクセス許可を確認してください。',
  'error.camera_lost': 'カメラの接続が切れたので、居眠り検知を止めました。',
  'error.bad_path': 'PDF ファイルのフルパスが必要です。',
  'error.not_pdf': 'PDF ファイルではないか、ファイルが壊れています。',
  'error.file_not_found': 'ファイルが見つかりません。',
  'error.file_unreadable': 'ファイルを読み込めません。',
  'error.pdf_too_large': 'PDF が大きすぎます。小さいファイルに分けて読み込んでください。',
  'error.pdf_encrypted': 'パスワード付きの PDF は読み込めません。',
  'error.pdf_invalid': 'PDF を開けません。ファイルが壊れているかもしれません。',
  'error.pdf_no_text':
    'PDF から文字が見つかりませんでした。スキャンした PDF (画像) にはまだ対応していません。',
  'error.already_importing': 'その資料はもう読み込み中です。',
  'error.embed_failed': '資料の索引を作れませんでした。もう一度試してください。',
  'error.image_too_large': '画像が大きすぎます。問題の部分だけ切り取ってください。',
  'error.bad_image': '画像を読み込めないか、小さすぎます。',
  'error.ocr_empty': '画像から問題が見つかりませんでした。問題の部分をもう一度切り取ってください。',
  'error.no_problem':
    '解く問題が見つかりませんでした。問いや指示の文まで一緒に切り取ってください。',
  'error.llm_start_failed': '言語モデルを起動できませんでした。ログを確認してください。',
  'error.llm_start_timeout': '言語モデルの起動に時間がかかりすぎました。',
  'error.llm_bad_output': 'モデルの出力がおかしかったみたいです。もう一度試してください。',
  'error.llm_request_failed': '言語モデルへのリクエストに失敗しました。',
  'error.invalid_request': '問題の画像か、問題の内容を送ってください。',
  'error.unsafe_request': '学習以外の目的のお願いには、お手伝いできません。',
  'error.invalid_address': '呼び方は20文字以内で、文字・数字・スペースだけ使えます。',
  'error.unsafe_address': 'その呼び方は使えません。別の呼び方を選んでください。',
  'error.invalid_rating': '評価は 1〜4 のどれかにしてください。',
  'error.unknown_card': '復習カードが見つかりません。',
  'error.invalid_preset': '声の名前を入力してください。',
  'error.too_many_presets': '保存できる声の数を超えました。',
  'error.builtin_preset': '標準の声は変更・削除できません。新しい名前で複製して保存してください。',
  'error.unknown_preset': '声のプリセットが見つかりません。',
  'error.text_too_long': '読み上げる文章が長すぎます。分けてリクエストしてください。',
  'error.bad_json': 'リクエストを読み取れませんでした。',
  'error.unknown_type':
    'バックエンドが知らないリクエストです。アプリを最新版にアップデートしてください。',
  'error.invalid_message': 'リクエストの形式が正しくありません。',
  'error.internal': '処理中にエラーが起きました。少ししてからもう一度試してください。',
  // Uninstall cleanup (Steam runs the app with --uninstall-cleanup)
  'uninstall.question': 'ダウンロードした AI モデルと学習記録・設定も一緒に削除しますか？',
  'uninstall.detail':
    '「残す」を選ぶとアプリだけを削除します。もう一度インストールすれば、そのまま続きから使えます。',
  'uninstall.deleteAll': 'すべて削除',
  'uninstall.keep': '残す',
} as const satisfies Messages;
