# Steam 출시 준비 (Your StudyMate)

Steam 등록에 필요한 입력값과 빌드 방법. 영어 문안은 Steamworks 양식에 그대로 붙여 넣는다.

## 1. 체크리스트

| 항목 | 상태 | 비고 |
|---|---|---|
| Steam Direct 등록비 | 사용자 결제 필요 | 앱당 US$100, 총매출 US$1,000 이상이면 환급 |
| 앱 이름 | Your StudyMate | 스토어·상표 중복은 등록 전에 사용자가 검색해 확인 |
| EULA | 완료 | `apps/shell/build/eula/EULA.{ko,ja,en}.txt`. 앱이 첫 실행 때 약관을 보여주고 동의를 받은 뒤 모델을 설치한다. Steamworks "사용자 지정 EULA"에도 언어별로 등록 (한 파일본: `EULA.txt`) |
| AI 콘텐츠 공개 | 문안 준비 (아래 2절) | 콘텐츠 조사 양식의 "AI 생성 콘텐츠" 항목 |
| 성인 콘텐츠 | 없음 | 콘텐츠 조사에서 성적 콘텐츠·누드 모두 "없음". 앱이 성적 요청을 거부하고 성인 아바타 등록을 막는다 |
| 개인정보 | 문안 준비 (아래 3절) | 스토어 설명 또는 FAQ |
| 빌드 업로드 | 스크립트 준비 (아래 4절) | AppID·DepotID는 Steamworks에서 발급 후 기입 |
| 지원 언어 | 한국어, 일본어, 영어 | 인터페이스, 음성(여성 목소리), 자막 모두 3개 언어 |
| 시스템 요구 사항 | 아래 5절 | 티어별 |
| 캐릭터 크레딧 | 완료 | 앱 크레딧 화면 + 스토어 설명에 츠쿠요미짱 크레딧 문구 넣기 |

## 2. AI 생성 콘텐츠 공개 문안 (Content Survey → AI Generated Content)

Pre-generated: 없음 (캐릭터·그림·효과음·문구는 사람이 만들었거나 오픈 라이선스 소재).

Live-generated — 양식에 붙여 넣을 영어 문안:

```text
Your StudyMate generates content with AI while it runs: math solution explanations and board
writing, answers to study questions, casual encouragement, review questions, and the character's
speech (text-to-speech). All AI models run locally on the player's PC (Qwen3 / Qwen2.5-VL via
llama.cpp, Whisper for speech recognition, open-license TTS voices); no player input is sent to
any server.

Guardrails against illegal or inappropriate content:
1. Every LLM output is constrained to a JSON schema (llama.cpp grammar), so the model can only
   produce the fields the app renders (spoken lines, LaTeX board lines, answers). No free-form
   output reaches the screen.
2. Every prompt that makes the character speak includes explicit safety rules: no sexual content,
   no political or religious advocacy, no hate speech or attacks on people or groups, no
   instructions for illegal or dangerous activities.
3. Player requests for sexual content are refused before any model runs, and every generated
   line (speech, board text, notes) passes a keyword/pattern filter in Korean, Japanese and
   English; offending lines are replaced with a neutral refusal.
4. Math answers are verified with a symbolic math engine (SymPy); unverified answers are labelled
   as such.
5. Imported custom avatars are screened for adult content (adult labels in the model metadata and
   file name, explicit anatomy parts) and rejected. The EULA prohibits any sexual use and any use
   outside the designated study purpose.
6. The app is a study tool with a fixed set of features; it does not generate images, and players
   cannot share generated content with other players through the app.
```

## 3. 개인정보 문안 (스토어 설명 / FAQ)

```text
Privacy: everything runs on your PC. Your problems, questions, voice and screen captures are never
uploaded. The webcam (optional, for drowsiness alerts) is processed in memory only and no images
are saved. The internet is used only to download the AI model files on first run.
```

한국어: 모든 AI 처리는 PC 안에서 이루어지며 문제·질문·음성·화면 캡처를 서버로 보내지 않습니다. 웹캠(졸음 알림, 선택)은 메모리에서만 처리하고 이미지를 저장하지 않습니다. 인터넷은 처음 실행할 때 AI 모델 파일을 받을 때만 사용합니다.

## 4. 빌드와 업로드 (SteamPipe)

Steam은 설치 파일(NSIS)이 아니라 앱 폴더를 그대로 배포한다.

1. 백엔드 번들과 앱 폴더 만들기:
   ```bash
   cd services/backend && uv run python build_backend_embedded.py
   cd apps/shell && npm run dist:steam
   ```
   결과: `apps/shell/release/win-unpacked/` (실행 파일 `Your StudyMate.exe`).
2. Steamworks에서 AppID와 Windows DepotID를 받아 `apps/shell/steam/app_build.vdf`, `depot_build.vdf`의
   `APPID`, `DEPOTID` 자리를 바꾼다.
3. Steamworks의 "설치 → 일반 설치"에서 실행 파일을 `Your StudyMate.exe`로 지정한다 (인수 없음, OS: Windows 64비트).
   `depot_build.vdf`가 `steam/installscript.vdf`를 함께 올리고 설치 스크립트로 지정한다: Steam에서 게임을 삭제하면
   `Your StudyMate.exe --uninstall-cleanup`이 실행돼 모델(수십 GB)과 학습 기록·설정까지 지울지 묻는다.
4. steamcmd로 업로드 (Steamworks 계정 로그인은 사용자가 직접 한다):
   ```bash
   steamcmd +login <빌드 계정> +run_app_build "<repo>/apps/shell/steam/app_build.vdf" +quit
   ```
5. AI 모델은 첫 실행 때 앱이 받는다 (`%APPDATA%/StudyMate/models`). 모델까지 Steam으로 배포하려면
   모델 파일을 별도 depot으로 올릴 수 있다 (모델 라이선스는 모두 재배포 허용 — THIRD_PARTY_NOTICES.md).

## 5. 시스템 요구 사항 (초안)

| | 최소 (Lite) | 권장 (Pro) |
|---|---|---|
| OS | Windows 10 64비트 | Windows 11 64비트 |
| CPU | 4코어 | 8코어 |
| 메모리 | 8 GB | 16 GB |
| GPU | 없어도 됨 (CPU 추론) | Vulkan 지원 GPU, VRAM 8 GB 이상 (VRAM 16 GB면 Max 티어: Qwen3 14B) |
| 저장 공간 | 8 GB | 20 GB (모델 포함, Max 티어 25 GB) |
| 네트워크 | 첫 실행 때 모델 다운로드 | 첫 실행 때 모델 다운로드 |
