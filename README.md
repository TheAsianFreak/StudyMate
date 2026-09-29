# Your StudyMate

**한국어** | [English](README.en.md) | [日本語](README.ja.md)

모니터 위를 돌아다니는 3D 캐릭터가 문제를 풀어 칠판에 판서하고, 음성으로 설명하고, 문제를 출제하고, 졸면 분필을 던져 깨우는 **로컬 AI 데스크탑 학습 컴패니언**.

모든 AI 처리는 PC 안에서 이루어진다. 문제·질문·음성·화면 캡처를 서버로 보내지 않으며, 인터넷은 처음 실행할 때 AI 모델 파일을 받을 때만 쓴다.

**Your StudyMate by TheAsianFreak (NBBANGSOFT)**

## 기능

- 화면 캡처나 텍스트로 받은 문제를 단계별로 풀어 손글씨 칠판에 쓰고 음성으로 설명 (수학은 SymPy로 검산)
- 수능 전 과목 풀이 (국어·수학·영어·한국사·사회탐구·과학탐구)
- 음성·텍스트 대화, 풀이에 대한 후속 질문
- 복습 문제 출제와 채점, 오답 노트, 간격 반복 복습
- 웹캠 졸음 감지 (선택, 영상은 저장하지 않음)
- 한국어·일본어·영어 (UI, 음성, 교육과정)
- 사용자 VRM 아바타 가져오기 (성인용 아바타는 등록 거부)

## 구조

단일 Electron 투명 창 안에 Godot 웹 빌드(캐릭터)와 HTML 레이어(판서·UI)를 겹치고, AI는 Python 사이드카(FastAPI, llama.cpp, SymPy, faster-whisper, MeloTTS, Kokoro)가 맡는다.

```
apps/shell/        Electron + TypeScript (창, 판서, UI, 타임라인 지휘)
apps/character/    Godot 4 프로젝트 (캐릭터)
services/backend/  Python 백엔드 (LLM, OCR, 검산, 음성, 졸음 감지, RAG)
packages/protocol/ 메시지 JSON Schema
docs/              기획(SPEC), 메시지 규격(PROTOCOL), 빌드(BUILD), 작업 목록(TASKS)
```

## 시작하기

필요한 것: Windows 10/11 64비트, Node.js 22+, [uv](https://docs.astral.sh/uv/) (Python 3.12), Godot 4.7.2 (표준판, 웹 익스포트 템플릿 포함). 자세한 설정은 [docs/BUILD.md](docs/BUILD.md).

```bash
# 1. 백엔드
cd services/backend && uv sync

# 2. AI 모델 받기 (티어별, 원본 배포처에서 받아 체크섬 검증)
uv run python -m studymate.system.downloader --models-dir ../../models --list

# 3. 셸 실행 (개발 모드)
cd ../../apps/shell && npm install && npm run dev
```

### 기본 캐릭터 모델 (직접 받기)

기본 캐릭터 「つくよみちゃん公式3Dモデル タイプA」(© Rei Yumesaki)는 이 저장소에 들어 있지 않다. [공식 사이트](https://tyc.rei-yumesaki.net/material/avatar/3d-a/)에서 약관을 확인하고 받아 `models/avatars/tsukuyomi/tsukuyomi-a.vrm`에 둔 뒤 캐릭터를 빌드한다.

```bash
python apps/character/tools/prepare_assets.py --godot <godot.exe>
godot --headless --path apps/character --export-release "Web" export/web/index.html
```

### 설치 파일

```bash
cd services/backend && uv run python build_backend_embedded.py
cd ../../apps/shell && npm run dist
```

## 라이선스

**GNU General Public License v3.0** ([LICENSE](LICENSE)). 상업적 이용·수정·재배포가 가능하며, 수정본을 배포하면 그 소스도 GPL-3.0으로 공개해야 한다.

GPL-3.0 제7조에 따른 추가 조건 ([NOTICE](NOTICE)):

- **출처 표기:** 이 프로그램을 바탕으로 한 모든 저작물은 사용자에게 보이는 정보·크레딧 화면과 문서에 "Your StudyMate by TheAsianFreak (NBBANGSOFT)"를 표기해야 한다.
- **수정본 표시:** 수정본은 원본과 다르다는 것을 밝혀야 하며, 원본이나 저작자가 만든·보증한 것처럼 보이게 하면 안 된다.
- **이름·로고:** "Your StudyMate"라는 이름과 로고·아이콘을 다른 제품의 이름이나 표지로 쓸 권리는 주지 않는다. 수정본은 자기 이름을 쓰고 "Your StudyMate 기반"이라고 밝힐 수 있다.

서드파티 소프트웨어·모델·에셋은 각자의 라이선스를 따른다 ([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)). AI 모델과 기본 캐릭터 모델은 이 저장소에 포함되지 않으며 이 라이선스의 대상이 아니다. 기본 캐릭터를 쓰는 배포본은 츠쿠요미짱 이용 약관(크레딧 표기, 개조·용도 제한)을 따라야 한다.
