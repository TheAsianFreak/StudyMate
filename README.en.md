# Your StudyMate

[한국어](README.md) | **English** | [日本語](README.ja.md)

A **local AI desktop study companion**: a 3D character walks around on top of your screen, solves problems on a handwritten board, explains them out loud, makes quizzes, and throws chalk to wake you up when you doze off.

All AI processing happens on your PC. Problems, questions, voice and screen captures are never sent to a server; the internet is only used to download the AI model files on first run.

**Your StudyMate by TheAsianFreak (NBBANGSOFT)**

## Features

- Solves problems from a screen capture or text step by step, writes them on a handwritten board and explains them by voice (math is checked with SymPy)
- Covers every subject of the Korean CSAT (Korean, math, English, Korean history, social studies, science)
- Voice and text conversation, follow-up questions about a solution
- Review quizzes with grading, a wrong-answer notebook and spaced repetition
- Webcam drowsiness detection (optional; no video is saved)
- Korean, Japanese and English (UI, voice, curriculum)
- Import your own VRM avatar (adult avatars are rejected)

## Structure

A Godot web build (the character) and an HTML layer (board, UI) share one transparent Electron window; the AI runs in a Python sidecar (FastAPI, llama.cpp, SymPy, faster-whisper, MeloTTS, Kokoro).

```
apps/shell/        Electron + TypeScript (window, board, UI, timeline director)
apps/character/    Godot 4 project (the character)
services/backend/  Python backend (LLM, OCR, answer checking, speech, drowsiness, RAG)
packages/protocol/ Message JSON Schema
docs/              Design (SPEC), message spec (PROTOCOL), build (BUILD), task list (TASKS) — in Korean
```

## Getting started

Requirements: Windows 10/11 64-bit, Node.js 22+, [uv](https://docs.astral.sh/uv/) (Python 3.12), Godot 4.7.2 (standard edition with the web export templates). See [docs/BUILD.md](docs/BUILD.md) for details.

```bash
# 1. Backend
cd services/backend && uv sync

# 2. Download the AI models (per tier, from the original publishers, checksum-verified)
uv run python -m studymate.system.downloader --models-dir ../../models --list

# 3. Run the shell (development mode)
cd ../../apps/shell && npm install && npm run dev
```

### Default character model (download it yourself)

The default character, "つくよみちゃん公式3Dモデル タイプA" (© Rei Yumesaki), is not in this repository. Read the terms on the [official site](https://tyc.rei-yumesaki.net/material/avatar/3d-a/), download it, put it at `models/avatars/tsukuyomi/tsukuyomi-a.vrm`, then build the character.

```bash
python apps/character/tools/prepare_assets.py --godot <godot.exe>
godot --headless --path apps/character --export-release "Web" export/web/index.html
```

### Installer

```bash
cd services/backend && uv run python build_backend_embedded.py
cd ../../apps/shell && npm run dist
```

## License

**GNU General Public License v3.0** ([LICENSE](LICENSE)). Commercial use, modification and redistribution are allowed; if you distribute a modified version, its source must also be released under GPL-3.0.

Additional terms under section 7 of the GPL-3.0 ([NOTICE](NOTICE)):

- **Attribution:** every work based on this program must show "Your StudyMate by TheAsianFreak (NBBANGSOFT)" on the About / credits screen shown to the user and in its documentation.
- **Modified versions:** a modified version must say that it differs from the original and must not be presented as the original or as made or endorsed by the author.
- **Name and logo:** no rights are granted to use the name "Your StudyMate" or its logo or icon as the name or mark of another product. A modified version uses its own name and may say it is "based on Your StudyMate".

Third-party software, models and assets keep their own licenses ([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)). The AI models and the default character model are not part of this repository and are not covered by this license. A distribution that uses the default character must follow the Tsukuyomi-chan terms (credit, limits on modification and use).
