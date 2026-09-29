# Phase 0 기술 검증 보고서

작성: 2026-09-25 · 환경: Windows 11 Home, 1920×1080 @100%, RTX 5080 + AMD 내장 그래픽, 32 논리 코어, Electron 44.4.5, Godot 4.7.2 (웹 익스포트, Compatibility, 싱글스레드)

## 결론

**기본안(Godot 웹 익스포트 + Electron 단일 투명 창) 채택.** 투명 합성, 클릭 통과, HTML 레이어 합성, VRM 런타임 로드가 모두 동작한다. 대안 A/B로 전환할 이유는 발견되지 않았다.

## 판정 항목

| 항목 | 결과 | 근거 |
|---|---|---|
| 바탕화면 위에 캐릭터만 보이고 배경 완전 투명 | ✅ | 데스크탑 캡처에서 뒤 창(Claude, Chrome)이 그대로 보임. `per_pixel_transparency/allowed=true`면 WebGL 컨텍스트가 alpha로 생성됨 |
| 캐릭터 외 영역 클릭이 뒤 창으로 전달 | ✅ | `WindowFromPoint`가 빈 영역에서 뒤 창을, UI 위에서 Electron 창을 반환 |
| 캐릭터 클릭·드래그 | ⚠️ 부분 확인 | 포인터가 캐릭터/UI 위일 때 입력 캡처 전환은 확인. 실제 드래그는 사용자 수동 확인 필요 (자동 테스트가 사용자 마우스와 충돌해 중단) |
| 60fps 유지 | ✅ | HUD rAF 기준 60.0fps, 최악 프레임 16.8ms (플레이스홀더). VRM(Godette) 로드 후에도 유지 |
| 유휴 시 GPU/CPU | 기록 | 아래 표 |
| HTML 레이어가 캔버스 위에 합성 | ✅ | 판서 테스트 카드·HUD·말풍선이 캐릭터 위에 정상 합성 |

### 리소스 사용량 (캐릭터 배회 중, 플레이스홀더 바디)

| 지표 | 값 | 측정 방법 |
|---|---|---|
| GPU 3D 엔진 사용률 | 3.7% | `\GPU Engine(*engtype_3D)\Utilization Percentage`, StudyMate PID 합, 5초 |
| CPU | 코어 1개의 약 49% (전체 32코어 대비 약 1.5%) | 프로세스 CPU 시간 5초 차분 |
| 메모리 | 약 800MB (전체 프로세스 합) | `app.getAppMetrics()` |

CPU가 예상보다 높았다. → 이후 해결: 웹 빌드의 `Engine.max_fps`는 busy-wait이므로 쓰지 않고 페이지의 requestAnimationFrame에 상한(활동 60 / 유휴 30fps)을 둔다. 츠쿠요미짱 기준 유휴 CPU 코어 1개의 약 50% (`docs/status-2026-09-25.md`).

## 발견한 문제와 해결

1. **`setIgnoreMouseEvents(true, { forward: true })`의 mousemove 전달이 동작하지 않음.** 포커스를 받은 적 없는 오버레이(`showInactive`)에서는 렌더러에 mousemove가 한 번도 오지 않았다. → 메인 프로세스가 `screen.getCursorScreenPoint()`를 16ms 간격으로 폴링해 렌더러로 보낸다 (`src/main/cursor.ts`). 포커스 상태와 무관하게 동작한다.
2. **Godot 런타임 PWA 콜백이 `app://`에서 예외.** 엔진이 부팅 시 `navigator.serviceWorker.getRegistration()`을 호출한다. → 커스텀 스킴에 `allowServiceWorkers` 권한 부여.
3. **Mono(.NET) Godot은 웹 익스포트 불가.** 표준 Godot 4.7.2 + 웹 템플릿을 사용한다. 팀 전원 표준 빌드 사용.
4. **godot-vrm 런타임 로드가 Godot 4.7에서 깨짐.** 런타임에서는 내장 `ConvertImporterMesh` 확장이 `_import_post`에서 ImporterMeshInstance3D를 먼저 해제한다. → godot-vrm 확장을 `first_priority`로 등록하고, 파일의 VRM 버전(0.x/1.0)에 맞는 확장만 로드 전후로 등록·해제한다 (`scripts/avatar_loader.gd`).

## 구현된 것

- Electron 셸: 투명·프레임 없음·항상 위·작업표시줄 숨김·주 모니터 작업 영역 크기 창, 커서 폴링 기반 클릭 통과 토글, 트레이(디버그 HUD, 아바타 불러오기, 기본 캐릭터로 되돌리기, 종료), `app://` 커스텀 프로토콜(COOP/COEP 헤더), 디버그 HUD(FPS, 프로세스별 CPU/메모리)
- Godot: 투명 배경, JavaScriptBridge(`bridge.gd`), 이동(`move_to`/`set_pos`), `hit_rect`/`arrived` 보고, 치비 플레이스홀더 + AnimationTree 대기/걷기, VRM 런타임 로드 + 휴머노이드 본 절차적 대기/걷기
- 프로토콜: `set_pos`, `load_avatar`, `avatar_loaded`, `avatar_error` 추가 (스키마 → PROTOCOL.md → TS 타입)
- 라이선스 검사 스크립트 `scripts/check-licenses.mjs` (npm)

## 남은 확인

- 캐릭터 드래그 수동 확인
- 트레이 "아바타 불러오기" 파일 대화상자 흐름 수동 확인 (시드 파일로 로드 경로는 확인)
- 고DPI(125%/150%) 모니터에서 좌표 변환 확인
- VRM 1.0 모델 로드 확인 (현재 VRM 0.x Godette만 확인)
