# Third-Party Notices

Your StudyMate 자체는 GNU GPL v3 (제7조 추가 조건 포함, `LICENSE`·`NOTICE`)으로 배포한다. 아래는 StudyMate에 포함되거나 실행 중 사용하는 서드파티 소프트웨어·모델·에셋 목록이며, 각자의 라이선스를 따른다.
새 의존성을 추가할 때마다 이 파일에 기록하고 라이선스 검사를 통과시킨다.

- npm: `node scripts/check-licenses.mjs <package-dir>` (배포되는 의존성은 허용 목록 엄격 적용, 빌드 도구는 카피레프트만 차단)
- Python: `cd services/backend && uv run python ../../scripts/check_py_licenses.py` (런타임 의존성 전체)
- 검토한 예외: `scripts/license-exceptions.json`, `scripts/license-exceptions-py.json`

허용 라이선스: MIT, Apache-2.0, BSD, ISC, Zlib, SIL OFL(폰트), CC0(에셋). 코드 라이선스와 모델 가중치·에셋 라이선스를 각각 확인한다.

## 캐릭터 (기본 번들)

본 소프트웨어에서는 프리 소재 캐릭터 「츠쿠요미짱」(© Rei Yumesaki)을 사용하고 있습니다.
本ソフトウェアでは、フリー素材キャラクター「つくよみちゃん」（© Rei Yumesaki）を使用しています。

- つくよみちゃん公式サイト: https://tyc.rei-yumesaki.net/
- 모델: 「つくよみちゃん公式3Dモデル タイプA」 v1.0.0 (通常版・輪郭線あり), 3D Character by Rei Yumesaki (夢前黎)
- 이용 약관: https://tyc.rei-yumesaki.net/material/avatar/3d-a/ — 소프트웨어 수록·판매 허용, 크레딧 필수, 츠쿠요미짱 이외 캐릭터로 개조 금지, 비판·공격·특정 정치/종교 입장 표명 용도 금지, 사용자에게 약관 준수 의무 고지
- 본 소프트웨어의 스크린샷·캡처 영상을 공개할 때는 소프트웨어 이름 「StudyMate」를 표기해 주세요.

## 셸 (Electron)

| 이름 | 용도 | 라이선스 |
|---|---|---|
| Electron (Chromium, Node.js 포함) | 데스크탑 셸 | MIT (Chromium 구성 요소별 라이선스: LICENSES.chromium.html) |
| KaTeX | 수식 렌더링 | MIT |
| Rough.js | 손그림 마킹 | MIT |
| Pretendard 1.3.9 | UI 본문 폰트 | SIL OFL 1.1 |
| Jua | UI 제목 폰트 | SIL OFL 1.1 |
| Nanum Pen Script | 판서 손글씨 폰트 | SIL OFL 1.1 |
| Zen Maru Gothic (Regular, Bold) — Copyright 2021 The Zen Maru Gothic Project Authors, https://github.com/googlefonts/zen-marugothic | 일본어 UI 제목·본문 폰트 | SIL OFL 1.1 |
| Klee One (SemiBold) — Copyright 2020 The Klee Project Authors (Fontworks), https://github.com/fontworks-fonts/Klee | 일본어 판서 손글씨 폰트 | SIL OFL 1.1 |

폰트 파일과 라이선스 전문은 `apps/shell/src/renderer/assets/fonts/`(`*-OFL.txt`)에 있다. 일본어 폰트는 Google Fonts 공식 저장소(https://github.com/google/fonts, `ofl/zenmarugothic`, `ofl/kleeone`)에서 받았다.

Electron에는 Chromium의 FFmpeg(`ffmpeg.dll`, LGPL-2.1, 동적 링크)가 포함되어 있다. 소스: https://github.com/electron/electron , https://ffmpeg.org

## 캐릭터 엔진 (Godot)

| 이름 | 용도 | 라이선스 | 출처 |
|---|---|---|---|
| Godot Engine 4.7.2 (웹 익스포트 템플릿) | 캐릭터 렌더링 | MIT | https://godotengine.org/license |
| godot-vrm (V-Sekai, master `e15199f`, 2026-07-08) | VRM 0.x/1.0 로드 | MIT | https://github.com/V-Sekai/godot-vrm |
| Godot-MToon-Shader (godot-vrm 포함) | VRM MToon 셰이더 | MIT | https://github.com/V-Sekai/godot-vrm |

Godot Engine에 포함된 서드파티 구성 요소: https://github.com/godotengine/godot/blob/4.7.2-stable/COPYRIGHT.txt

## 백엔드 (Python)

백엔드는 CPython 3.12 (python-build-standalone) 런타임과 함께 배포된다. CPython은 PSF License 2.0이며, 포함된 OpenSSL(Apache-2.0), libffi(MIT), SQLite(Public Domain), zlib(Zlib), bzip2(BSD), xz(0BSD/Public Domain) 구성 요소를 가진다. Tcl/Tk는 배포본에서 제거했다.

| 이름 | 용도 | 라이선스 |
|---|---|---|
| FastAPI, Starlette, Uvicorn, websockets, httpx, pydantic | 서버 | MIT / BSD-3-Clause |
| NumPy, SciPy, SymPy (+ ANTLR4 runtime) | 수치·기호 계산, 정답 검증 | BSD-3-Clause |
| Pillow | 이미지 처리 | MIT-CMU (HPND) |
| RapidOCR (+ 패키지에 포함된 PaddleOCR 검출·방향 모델) + ONNX Runtime | 텍스트 OCR | Apache-2.0 / MIT |
| pix2tex (LaTeX-OCR), timm, x-transformers, PyTorch (CPU) | 수식 OCR | MIT / Apache-2.0 / BSD-3-Clause |
| faster-whisper, CTranslate2, Silero VAD | 음성 인식, 발화 구간 검출 | MIT |
| MeloTTS (한국어 추론 코드만 발췌, commit `2091453`, © 2024 MyShell.ai) | 음성 합성 | MIT |
| g2pkk (g2pK), jamo, NLTK | 한국어 발음 변환 | Apache-2.0 |
| Kokoro (추론 코드만 발췌·수정, `kokoro` 0.9.4, © hexgrad) | 일본어·영어 음성 합성 | Apache-2.0 |
| misaki 0.9.4 (영어 발음 사전 us/gb gold·silver, `en.py` 발췌·수정, 가나→IPA 표 발췌, © hexgrad) | 일본어·영어 발음 변환 | Apache-2.0 (가나 표 원본 cutlet: MIT, © 2020 Paul O'Leary McCann) |
| pyopenjtalk-plus (Open JTalk 1.11, HTS Engine API, NAIST 일본어 사전·UniDic 기반 사전 포함) | 일본어 읽기·숫자/조수사 처리 | MIT (pyopenjtalk, © 2018 Ryuichi Yamamoto) / Modified BSD (Open JTalk, HTS Engine API, © Nagoya Institute of Technology) / BSD-3-Clause (NAIST-jdic © 2009 NAIST, UniDic © 2011-2017 The UniDic Consortium). 동봉된 HTS 음성 "Mei"(CC BY 3.0)는 쓰지 않아 배포본에서 제거 |
| SudachiPy | pyopenjtalk-plus 의존성 (사전 sudachidict_core는 배포하지 않음) | Apache-2.0 |
| spaCy, thinc, blis, cymem, preshed, murmurhash, srsly, catalogue, confection, wasabi, weasel, spacy-legacy, spacy-loggers, cloudpathlib, smart-open, wrapt, addict | 영어 품사 분석 (발음 사전 선택) | MIT / BSD-3-Clause (blis) / BSD-2-Clause (wrapt) |
| Transformers (ALBERT 구현) | Kokoro 텍스트 인코더 | Apache-2.0 |
| g2p_en 추론 방식 재구현 (Kyubyong Park & Jongseok Kim) | 사전에 없는 영어 단어 발음 추정 | Apache-2.0 |
| pyworld (WORLD vocoder) | 목소리 후보정 | MIT (WORLD: modified BSD) |
| sounddevice (PortAudio) | 마이크 입력 | MIT |
| MediaPipe | 얼굴 랜드마크 | Apache-2.0 |
| OpenCV | 웹캠 캡처 | Apache-2.0 (FFmpeg 비디오 백엔드 DLL은 배포본에서 제외) |
| pypdfium2 (PDFium) | PDF 텍스트 추출 | Apache-2.0 / BSD-3-Clause |
| sqlite-vec | 벡터 검색 | MIT / Apache-2.0 |
| py-fsrs | 간격 반복 복습 | MIT |
| psutil | 사양 감지 | BSD-3-Clause |
| certifi | CA 인증서 (모델 다운로드) | MPL-2.0 (수정 없이 포함) |
| typing-extensions, defusedxml | 보조 | PSF-2.0 |

## AI 모델 (앱에 포함하지 않음 — 첫 실행 때 사용자가 받음)

| 모델 | 용도 | 라이선스 | 출처 |
|---|---|---|---|
| llama.cpp b11177 (llama-server, Vulkan/CPU) | LLM 추론 서버 | MIT | https://github.com/ggml-org/llama.cpp |
| Qwen3 4B / 8B / 14B (GGUF Q4_K_M) | 풀이·대화·출제 | Apache-2.0 | https://huggingface.co/Qwen |
| Qwen2.5-VL 7B Instruct (GGUF + mmproj) | 문제 이미지 인식 | Apache-2.0 | https://huggingface.co/ggml-org/Qwen2.5-VL-7B-Instruct-GGUF |
| bge-m3 (GGUF Q8_0) | 자료 임베딩 | MIT | https://huggingface.co/BAAI/bge-m3 |
| Whisper small / medium / large-v3 (faster-whisper 변환) | 음성 인식 | MIT | https://huggingface.co/Systran |
| MeloTTS-Korean | 음성 합성 (한국어) | MIT | https://huggingface.co/myshell-ai/MeloTTS-Korean |
| Kokoro-82M v1.0 가중치 + 여성 목소리 jf_alpha, jf_nezumi, jf_tebukuro, jf_gongitsune, af_bella, af_heart, af_sarah, bf_emma | 음성 합성 (일본어·영어) | Apache-2.0, © hexgrad | https://huggingface.co/hexgrad/Kokoro-82M |
| spaCy en_core_web_sm 3.8.0 | 영어 품사 분석 | MIT (학습 데이터 OntoNotes 5는 Explosion이 상업 라이선스로 사용, 표제어 표 WordNet 3.0 License) | https://github.com/explosion/spacy-models |
| g2p_en 2.1.0 가중치 (`checkpoint20.npz`, CMUdict 학습) | 사전에 없는 영어 단어 발음 추정 | Apache-2.0 | https://github.com/Kyubyong/g2p |
| MediaPipe Face Landmarker | 졸음 감지 | Apache-2.0 | https://ai.google.dev/edge/mediapipe |
| PP-OCRv5 한국어 인식 모델 (RapidOCR ONNX) | 텍스트 OCR (Lite 티어) | Apache-2.0 | https://github.com/RapidAI/RapidOCR |
| CMUdict 0.7a (NLTK data) | 영어 단어 → 한글 발음 (한국어), 사전에 없는 영어 고유명사 발음 (영어) | BSD-2-Clause, © 1993-2008 Carnegie Mellon University | https://github.com/nltk/nltk_data |
| pix2tex 가중치 v0.0.1 | 수식 OCR (Lite 티어) | MIT | https://github.com/lukas-blecher/LaTeX-OCR |

MeloTTS 한국어는 원래 BERT 특징(kykim/bert-kor-base)을 쓰지만, 해당 모델은 상업 이용에 별도 MOU가 필요해 사용하지 않는다 (BERT 없이 추론).

Kokoro 일본어 목소리 중 jf_gongitsune, jf_nezumi, jf_tebukuro는 테레비니시닛폰(TNC) 아나운서의 낭독 음성(「ごんぎつね」「ねずみの嫁入り」「手袋を買いに」, CC BY 3.0, 声庭 Koniwa 코퍼스 경유)으로 학습되었다 (출처: Kokoro-82M VOICES.md). 원문은 퍼블릭 도메인(아오조라 문고). 크레디트: 音声 © テレビ西日本 (https://www.tnc.co.jp/forchildren/roudoku), CC BY 3.0.

일본어·영어 발음 변환은 GPL/LGPL 구성 요소(espeak-ng, phonemizer, num2words, pykakasi)를 쓰지 않는다: 숫자 읽기는 자체 구현, 사전에 없는 영어 단어는 CMUdict → 로마자 규칙 → g2p_en 가중치 순으로 추정한다.

## 빌드·개발 도구 (배포물에 포함되지 않음)

electron-vite, Vite, electron-builder, TypeScript, ESLint, typescript-eslint, Prettier, json-schema-to-typescript (MIT / Apache-2.0), uv, Nuitka (Apache-2.0), pytest, ruff, mypy, datamodel-code-generator (MIT).

## 에셋

| 이름 | 용도 | 라이선스 |
|---|---|---|
| 앱 아이콘, 효과음(절차적 합성), 치비 플레이스홀더 캐릭터 | UI·폴백 캐릭터 | 자체 제작 |

### 배포물에 포함하지 않는 것

| 이름 | 용도 | 라이선스 |
|---|---|---|
| Low-Poly Godette VRM (SirRichard94, VRM 변환 Lyuma) | 로컬 테스트 전용, `models/test/` | CC-BY 3.0 |
| 사용자가 가져온 VRM 아바타 | 사용자 PC의 `%APPDATA%/StudyMate/avatars/`에만 저장 | 각 제작자 라이선스 (앱이 재배포하지 않음) |
