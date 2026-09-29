# 개발 환경과 빌드

## 필요한 도구

| 도구 | 버전 | 용도 |
|---|---|---|
| Node.js | 24 LTS | Electron 셸, 프로토콜 타입 생성 |
| uv | 0.12+ | Python 백엔드 환경 (Python 3.12 자동 설치) |
| Godot | 4.7.2 **표준(비 .NET)** + 웹 익스포트 템플릿 | 캐릭터 웹 빌드. Mono 빌드는 웹 익스포트 불가 |
| Visual Studio 2022 Build Tools (C++) | | Nuitka 백엔드 번들 |

## 처음 설정

```bash
# 1. 백엔드 의존성
cd services/backend && uv sync

# 2. 모델 받기 (repo 루트 models/, git 제외). --list로 목록 확인
uv run python -m studymate.system.downloader --models-dir ../../models --all

# 3. 프로토콜 타입 생성 (스키마 수정 시)
cd ../../packages/protocol && npm install && npm run gen

# 4. 캐릭터: 기본 아바타 복사 → 임포트 → 웹 익스포트
python apps/character/tools/prepare_assets.py
godot --headless --path apps/character --import
godot --headless --path apps/character --export-release "Web" export/web/index.html

# 5. 셸
cd apps/shell && npm install && npm run dev      # 개발 (Vite HMR)
cd apps/shell && npm run build && npx electron .  # 빌드본 실행
```

셸은 개발 모드에서 `services/backend/.venv`의 Python으로 백엔드를 사이드카로 띄워요(포트 8765부터 빈 포트). 로그: `%APPDATA%\StudyMate\logs\`.

## 테스트

```bash
cd services/backend && uv run pytest              # 백엔드 단위·통합 테스트
cd services/backend && uv run python -m eval.run_eval --tier pro   # 수학 50문항 평가
godot --headless --path apps/character --script res://tests/smoke_test.gd -- models/avatars/tsukuyomi/tsukuyomi-a.vrm
cd apps/shell && npm run typecheck && npm run lint && npm run check-licenses
# 앱 전체 자동 점검 (마우스·키보드를 건드리지 않음). 스크린샷은 STUDYMATE_SELFTEST_DIR에 저장
STUDYMATE_SELFTEST=all npx electron .   # 또는 panels,board,ask,solve,quiz,wake 중 선택
```

## 설치 파일 (Phase 4)

```bash
# 1. 백엔드 번들 (임베디드 CPython + 패키지 → services/backend/dist/embedded, 약 20초)
cd services/backend && uv run python build_backend_embedded.py
#    (Nuitka: build_backend.py → dist/run_backend.dist. torch 2.14가 standalone에서 abort해 현재 미사용)
# 2. 캐릭터 웹 익스포트 (위 4번)
# 3. 설치 파일 (apps/shell/release/StudyMate Setup x.y.z.exe, 코드 서명 없음)
cd apps/shell && npm run dist
```

설치 파일은 **원클릭**이에요: 실행하면 묻지 않고 사용자 폴더에 설치(관리자 권한 불필요)한 뒤 앱을 바로 켜요.
모델은 설치 파일에 넣지 않고, **첫 실행 때 자동으로** 사양에 맞는 티어의 모델만 `%APPDATA%\StudyMate\models\`에 받아요 (진행 카드 표시, 이어받기·sha256 검증, 끊기면 다음 실행 때 이어서). 설정 → 일반 → "AI 모델 자동 받기"로 끌 수 있어요.
개발 PC에서는 `%APPDATA%\StudyMate\models`를 저장소 `models/`로 연결(junction)하면 다시 받지 않아요.
