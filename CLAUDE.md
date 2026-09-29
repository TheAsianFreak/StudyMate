# StudyMate

모니터 위를 돌아다니는 3D 캐릭터가 문제를 풀어 화면에 판서하고, 음성으로 설명하고, 문제를 출제하고, 졸면 분필을 던져 깨우는 **로컬 AI 데스크탑 학습 컴패니언**.

상세 기획: `docs/SPEC.md` · 메시지 규격: `docs/PROTOCOL.md` · 작업 목록: `docs/TASKS.md`

## 현재 단계

**Phase 0~4 일괄 구현 완료 (2026-09-25), 실사용 검증 단계.** 기본안(Godot 웹 + Electron 투명 창) 채택. 풀이·판서·음성 대화·출제·RAG·졸음 감지·복습·모델 다운로더·설치 파일까지 구현. 남은 것은 실제 환경 확인(드래그, 마이크, 웹캠 오탐, VRM 1.0, 클린 PC 설치)과 한국어 다화자 TTS 조사 — `docs/TASKS.md`의 ⚠ 항목과 `docs/status-2026-09-25.md`. 단계가 끝나면 이 섹션을 갱신할 것.

**제품 방향 (2026-09-25):** 제품명 **Your StudyMate** (데이터 폴더는 `%APPDATA%/StudyMate` 유지), Steam 출시 목표 (`docs/steam/`). 전체 톤은 서브컬처(애니·게임) 감성 (SPEC 7.7). 기본 캐릭터는 츠쿠요미짱 타입A (크레딧 필수, 정치·종교 발화 금지 → `solve/safety.py`). 사용자가 BOOTH 등에서 받은 VRM 아바타를 직접 가져와 쓸 수 있으나 성인용 아바타는 등록 거부 (SPEC 7.5). 한국어·일본어·영어 지원 — UI, 캐릭터 말, TTS, 음성 인식, 나라별 교육과정 (SPEC 7.8, 백엔드는 요청마다 `studymate.i18n` 언어). 목소리는 언어별 **여성만** + 사용자 후보정 (SPEC 7.6). 음성 인식으로 대화·질문 (대화 기록은 셸이 보관해 `ask_request.history`로 전달). 이용약관(EULA)은 학습 목적 외·성적 목적 사용을 금지하고, 성적 요청은 모델 실행 전에 거절한다 (SPEC 7.9).

## 아키텍처 요약

단일 Electron 투명 창 안에 Godot 웹 빌드(캐릭터)와 HTML 레이어(주석·UI)를 겹치고, AI는 Python 사이드카가 담당한다.

```
Electron 투명 창
 ├─ HTML 레이어 (주석, KaTeX, UI)        ← z-index 위
 ├─ Godot 웹 빌드 <canvas> (캐릭터, 분필) ← z-index 아래
 └─ Director (타임라인 지휘, TS)
        │ JavaScriptBridge ↔ Godot
        │ WebSocket ↔ Python 백엔드 (FastAPI: LLM, OCR, SymPy, STT, TTS, 졸음 감지, RAG)
```

대안(Phase 0 실패 시): A) 네이티브 Godot 창 + Electron 창 2개, B) Electron + three.js + @pixiv/three-vrm 단독.

## 저장소 구조

```
studymate/
├─ CLAUDE.md
├─ docs/                    SPEC.md, PROTOCOL.md, TASKS.md, BUILD.md, guides/, research/
├─ apps/
│  ├─ shell/                Electron + TypeScript + Vite
│  │  ├─ src/main/          메인 프로세스 (창, 캡처, 트레이, 사이드카 관리)
│  │  ├─ src/preload/
│  │  └─ src/renderer/      director/(timeline, conversation, solve, wake), annotation/, ui/(panels), backend/, bridge/
│  └─ character/            Godot 4 프로젝트 (GDScript)
│     └─ export/web/        웹 빌드 출력 → shell이 로드
├─ services/
│  └─ backend/              Python 3.11+, FastAPI (uv로 관리)
│     └─ studymate/         handlers/, llm/, vision/, verify/, solve/, quiz/, speech/, drowsy/, rag/, db/, learning/, system/, protocol/(생성물)
├─ packages/
│  └─ protocol/             메시지 JSON Schema (TS·Python 타입 생성 원본)
└─ models/                  로컬 모델 파일 (git 제외)
```

## 핵심 설계 규칙 (반드시 지킬 것)

1. **지휘자는 하나.** 타임라인은 renderer의 Director만 소유한다. Godot은 명령을 받고 상태(`arrived`, `hand_pos` 등)만 보고한다. Godot 쪽에 타이머 기반 시나리오 로직을 넣지 않는다.
2. **오디오가 기준 시계.** TTS 음성은 Electron에서 재생하고, 모든 필기·입모양·제스처는 오디오 재생 시각(ms)에 맞춘다.
3. **좌표계는 창 기준 CSS 픽셀.** 화면 캡처 좌표만 `devicePixelRatio`로 변환한다.
4. **프로토콜 우선.** 메시지를 추가·변경할 때는 `packages/protocol`의 스키마와 `docs/PROTOCOL.md`를 먼저 고치고 타입을 재생성한다. 전송 계층(JavaScriptBridge/WebSocket)과 메시지 형식을 섞지 않는다.
5. **정답은 검증 후 표시.** 수학 풀이·출제 문제는 SymPy 검증을 통과하면 `high`, 기호 검증 불가지만 독립 재풀이가 일치하면 `medium`, 아니면 `low`로 표시한다.
6. **LLM 출력은 JSON 스키마 제약.** llama.cpp의 json_schema/grammar 기능으로 형식을 강제한다. 자유 텍스트 파싱 금지.
7. **프라이버시.** 웹캠은 옵트인. 프레임은 메모리에서 수치만 추출하고 즉시 폐기한다. 이미지·영상을 디스크나 로그에 남기지 않는다. 외부 네트워크 호출 금지(모델 다운로드 제외).
8. **클릭 통과 기본.** 창은 기본 `setIgnoreMouseEvents(true, { forward: true })`, 포인터가 캐릭터 hit_rect나 `data-hit` UI 위일 때만 해제. 포인터 위치는 메인 프로세스 커서 폴링으로 받는다 (`forward`의 mousemove는 포커스 없는 창에 오지 않음).
9. **사용자 아바타는 재배포하지 않는다.** 가져온 VRM은 `%APPDATA%/StudyMate/avatars/`에만 두고 업로드·동봉하지 않는다. 로드 시 VRM 메타 라이선스를 사용자에게 보여준다.

## 라이선스 규칙 (의존성 추가 전 필수 확인)

**프로젝트 자체는 GPL-3.0** (`LICENSE`) + 제7조 추가 조건 (`NOTICE`: 크레딧 "Your StudyMate by TheAsianFreak (NBBANGSOFT)" 유지, 수정본 표시, 이름·로고 사용 불가). 크레딧 화면의 저작권·무보증·라이선스 고지는 지우지 않는다. Steam 배포본은 저작권자가 EULA로 별도 배포(이중 라이선스)할 수 있게, 의존성은 아래 허용 목록만 쓴다 (GPL 의존성 금지 유지).

허용: MIT, Apache-2.0, BSD, ISC, Zlib, SIL OFL(폰트), CC0(에셋), CC BY(에셋·학습 데이터 — 크레디트를 `THIRD_PARTY_NOTICES.md`와 앱 크레딧 화면에 표기할 때만, 2026-09-26 승인). 코드와 **모델 가중치 라이선스를 각각** 확인한다.

**사용 금지:**

| 금지 | 이유 | 대체 |
|---|---|---|
| Coqui XTTS | 모델 비상업(CPML) | MeloTTS |
| PyMuPDF (fitz) | AGPL | pypdfium2, pdf.js |
| dlib 68점 랜드마크 모델 | 학습 데이터 비상업 | MediaPipe |
| Qwen2.5 3B/72B, Qwen2.5-VL 3B | 비 Apache 라이선스 | Qwen3, Qwen2.5-VL 7B |
| EXAONE | 비상업 | Qwen3 |
| Piper 신규(piper1-gpl) | GPL-3.0 | MeloTTS, sherpa-onnx |
| Mixamo, 타인 VRM 모델 **번들** | 재배포·상업 제한 | 자체 제작·번들 가능 라이선스 모델. 타인 VRM은 사용자 가져오기로만 (SPEC 7.5) |
| GPL/AGPL/LGPL 전반 | 배포 의무 | 허용 목록 내 대체재 |

Llama·Gemma 계열은 자체 약관이 있으므로 사용자 승인 없이 추가하지 않는다. 새 의존성을 추가하면 `THIRD_PARTY_NOTICES.md`에 기록한다.

## 기술 스택

- **Shell:** Electron 44, TypeScript, electron-vite, KaTeX, Rough.js, electron-builder
- **Character:** Godot 4.7.2 (Compatibility 렌더러, 싱글스레드 웹 익스포트, GDScript), godot-vrm
- **Backend:** Python 3.12, uv, FastAPI (배포: 임베디드 CPython), llama.cpp llama-server(Vulkan/CPU), Qwen3 4B/8B/14B(Max 티어), Qwen2.5-VL 7B, RapidOCR(PaddleOCR 모델), pix2tex, SymPy, faster-whisper, Silero VAD, MeloTTS(KR, BERT 없이 — 코드 발췌 `speech/melo`), Kokoro-82M(JA/EN, 코드 발췌 `speech/kokoro`) + pyopenjtalk-plus·misaki·spaCy(G2P), pyworld, MediaPipe Face Landmarker, OpenCV(contrib 하나만), bge-m3, sqlite-vec, pypdfium2, py-fsrs, Nuitka
- **Fonts:** Nanum Pen Script(판서), Jua(UI 제목), Pretendard(본문), 일본어 Zen Maru Gothic(UI)·Klee One(판서) — 모두 SIL OFL

## 코딩 컨벤션

- TypeScript: strict 모드, ESLint + Prettier. renderer에서 Node API 직접 사용 금지(preload 경유).
- Python: 타입 힌트 필수, ruff + mypy, pytest. 모델 로딩은 지연 로딩·언로드 가능한 구조로.
- GDScript: 정적 타입 사용, 시그널로 상태 보고. 브리지 코드는 `character/scripts/bridge.gd` 한 곳에 모은다.
- 사용자에게 보이는 문자열은 한국어·일본어·영어 세 벌 (셸은 i18n 사전, 백엔드는 `i18n.tr(ko, ja, en)`), 코드·주석·커밋 메시지는 영어.
- 모델 경로·임계값은 하드코딩하지 말고 `config` 모듈로.

## 자주 쓰는 명령

자세한 설정은 `docs/BUILD.md`.

```bash
# shell (개발: Vite HMR, 백엔드는 services/backend/.venv로 자동 실행)
cd apps/shell && npm install && npm run dev
cd apps/shell && npm run typecheck && npm run lint && npm run check-licenses
# 앱 자동 점검 (마우스·키보드를 건드리지 않음)
cd apps/shell && npm run build && STUDYMATE_SELFTEST=all npx electron .
# backend
cd services/backend && uv sync && uv run pytest
cd services/backend && uv run python -m eval.run_eval --tier pro          # 수학 50문항
cd services/backend && uv run python -m studymate.system.downloader --models-dir ../../models --list
cd services/backend && uv run python ../../scripts/check_py_licenses.py
# character: 표준(비 .NET) Godot 4.7.2 + 웹 템플릿. 새 체크아웃은 기본 아바타 준비부터
python apps/character/tools/prepare_assets.py --godot <godot.exe>
godot --headless --path apps/character --fixed-fps 60 --script res://tests/command_test.gd
godot --headless --path apps/character --export-release "Web" export/web/index.html
# protocol 타입 생성 (스키마 수정 후)
cd packages/protocol && npm run gen
# 설치 파일 (백엔드는 임베디드 CPython 번들)
cd services/backend && uv run python build_backend_embedded.py && cd ../../apps/shell && npm run dist
```
