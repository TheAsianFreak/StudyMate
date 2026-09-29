# Your StudyMate

[한국어](README.md) | [English](README.en.md) | **日本語**

画面の上を歩き回る 3D キャラクターが、問題を解いて手書きの黒板に板書し、声で説明し、問題を出し、居眠りするとチョークを投げて起こしてくれる **ローカル AI デスクトップ学習コンパニオン**です。

AI の処理はすべて PC の中で行います。問題・質問・音声・画面キャプチャをサーバーに送ることはなく、インターネットは初回起動時に AI モデルのファイルをダウンロードするときだけ使います。

**Your StudyMate by TheAsianFreak (NBBANGSOFT)**

## 機能

- 画面キャプチャやテキストで受け取った問題を段階ごとに解き、手書きの黒板に書いて声で説明（数学は SymPy で検算）
- 韓国の大学修学能力試験（修能）の全教科に対応（国語・数学・英語・韓国史・社会探究・科学探究）
- 音声とテキストでの会話、解説へのフォローアップ質問
- 復習問題の出題と採点、まちがいノート、間隔反復の復習
- Web カメラによる居眠り検知（任意、映像は保存しません）
- 韓国語・日本語・英語（UI、音声、教育課程）
- 自分の VRM アバターの読み込み（成人向けアバターは登録できません）

## 構成

1 つの透明な Electron ウィンドウの中に Godot の Web ビルド（キャラクター）と HTML レイヤー（板書・UI）を重ね、AI は Python のサイドカー（FastAPI、llama.cpp、SymPy、faster-whisper、MeloTTS、Kokoro）が担当します。

```
apps/shell/        Electron + TypeScript（ウィンドウ、板書、UI、タイムラインの指揮）
apps/character/    Godot 4 プロジェクト（キャラクター）
services/backend/  Python バックエンド（LLM、OCR、検算、音声、居眠り検知、RAG）
packages/protocol/ メッセージの JSON Schema
docs/              企画（SPEC）、メッセージ仕様（PROTOCOL）、ビルド（BUILD）、作業リスト（TASKS）— 韓国語
```

## はじめに

必要なもの: Windows 10/11 64 ビット、Node.js 22 以上、[uv](https://docs.astral.sh/uv/)（Python 3.12）、Godot 4.7.2（標準版、Web エクスポートテンプレート付き）。詳しい設定は [docs/BUILD.md](docs/BUILD.md) を参照してください。

```bash
# 1. バックエンド
cd services/backend && uv sync

# 2. AI モデルのダウンロード（ティア別、元の配布元から取得しチェックサムを検証）
uv run python -m studymate.system.downloader --models-dir ../../models --list

# 3. シェルの起動（開発モード）
cd ../../apps/shell && npm install && npm run dev
```

### 標準キャラクターのモデル（各自でダウンロード）

標準キャラクター「つくよみちゃん公式3Dモデル タイプA」（© Rei Yumesaki）はこのリポジトリに含まれていません。[公式サイト](https://tyc.rei-yumesaki.net/material/avatar/3d-a/)で利用規約を確認してダウンロードし、`models/avatars/tsukuyomi/tsukuyomi-a.vrm` に置いてからキャラクターをビルドしてください。

```bash
python apps/character/tools/prepare_assets.py --godot <godot.exe>
godot --headless --path apps/character --export-release "Web" export/web/index.html
```

### インストーラー

```bash
cd services/backend && uv run python build_backend_embedded.py
cd ../../apps/shell && npm run dist
```

## ライセンス

**GNU General Public License v3.0**（[LICENSE](LICENSE)）。商用利用・改変・再配布ができます。改変版を配布する場合は、そのソースも GPL-3.0 で公開する必要があります。

GPL-3.0 第 7 条にもとづく追加条項（[NOTICE](NOTICE)）:

- **クレジット表記:** このプログラムをもとにしたすべての著作物は、ユーザーに表示される情報・クレジット画面とドキュメントに「Your StudyMate by TheAsianFreak (NBBANGSOFT)」を表記しなければなりません。
- **改変版の表示:** 改変版はオリジナルと異なることを明示し、オリジナルや作者が作成・保証したものであるかのように見せてはいけません。
- **名前・ロゴ:** 「Your StudyMate」という名前とロゴ・アイコンを、別の製品の名前や標章として使う権利は与えません。改変版は独自の名前を使い、「Your StudyMate ベース」であると明記できます。

サードパーティのソフトウェア・モデル・アセットはそれぞれのライセンスに従います（[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)）。AI モデルと標準キャラクターのモデルはこのリポジトリに含まれず、このライセンスの対象外です。標準キャラクターを使う配布物は、つくよみちゃんの利用規約（クレジット表記、改変・用途の制限）に従う必要があります。
