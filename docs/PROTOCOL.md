# StudyMate 메시지 프로토콜

단일 원본은 `packages/protocol/schema/*.json`(JSON Schema)이며, 이 문서는 사람이 읽는 요약이다. 변경 시 스키마 → 이 문서 → 타입 재생성 순서로 반영한다.

## 공통 규칙

- 모든 메시지: `{ "type": string, "id"?: string, "t"?: number, ... }`
- `t` = 오디오 기준 시각(ms). 오디오가 없는 명령은 생략 가능
- 좌표 = Electron 창 기준 CSS 픽셀, 원점 좌상단
- 요청-응답 쌍은 같은 `id`로 매칭
- 전송 계층: Director ↔ Godot = `JavaScriptBridge`, Director ↔ Backend = WebSocket `ws://127.0.0.1:8765/ws`

## Director → Godot (명령)

| type | 필드 | 설명 |
|---|---|---|
| `move_to` | `x, y, speed?` | 지정 위치로 걷기 (`x, y` = 발 위치, `speed` = CSS px/s, 생략 시 85 = 초당 약 2.4걸음. 걸음걸이가 자연스러운 범위는 ~120 이하, 150이면 약 3.4걸음/초) |
| `set_pos` | `x, y` | 즉시 위치 지정 (텔레포트). 진행 중인 `move_to`·잡기·낙하는 취소되고 `arrived`를 보내지 않음 |
| `grab` | `x, y` | 마우스로 집어 드는 중: 포인터 위치. 드래그 시작과 포인터가 움직일 때마다 보낸다. 첫 `grab`에서 뒷덜미를 잡혀 포인터 쪽으로 들려 올라가고, 몸은 그 아래에 매달려 진자처럼 흔들리며 버둥거린다 |
| `release` | — | 드래그 끝: 짧게(약 30 CSS px, 창 아래 가장자리 밑으로는 안 감) 떨어져 발로 착지한 뒤 `arrived`를 보낸다 |
| `gesture` | `name, duration_ms` | `write` \| `point` \| `nod` \| `tap_desk` \| `throw` \| `idle` |
| `emotion` | `name, weight` | VRM 표정 `happy` \| `surprised` \| `sleepy` \| `angry` \| `neutral`, weight 0~1 |
| `look_at` | `x, y` 또는 `target: "user"` | 시선 목표. `user`는 부드럽게: 주로 눈으로 보고 머리는 일부만 돌리며, 가끔 시선을 피했다 돌아온다 |
| `ik_target` | `x, y` | 판서 중 손 목표점 (필기 선두) |
| `viseme` | `aa, ih, ou, ee, oh` | 입모양 가중치 0~1 |
| `throw_chalk` | `strength` | `soft` \| `normal` \| `hard` |
| `load_avatar` | `id, path` | VRM 아바타 교체. `path` = Godot 가상 FS 경로(렌더러가 `Engine.copyToFS`로 미리 기록) 또는 `res://`. `id: "default"` + `path` 생략 시 기본 캐릭터로 복귀 |

## Godot → Director (상태)

| type | 필드 | 설명 |
|---|---|---|
| `ready` | — | Godot 초기화 완료 |
| `arrived` | `x, y` | move_to 완료, 또는 `release` 뒤 착지 완료 (`x, y` = 발 위치) |
| `gesture_done` | `name` | 제스처 종료 |
| `hand_pos` | `x, y` | 손 좌표, 30Hz |
| `hit_rect` | `x, y, w, h` | 캐릭터 바운딩 박스 (클릭 통과 판정) |
| `chalk_impact` | `x, y` | 분필 화면 충돌 지점 |
| `avatar_loaded` | `id, meta: AvatarMeta` | 아바타 교체 완료 |
| `avatar_error` | `id, message` | 아바타 로드 실패 (기존 아바타 유지) |

`AvatarMeta` = VRM 메타 요약 `{ title, authors[], version, license_name, license_url, commercial_usage, allow_redistribution, modification, credit_notation, spec_version }`. 값이 없으면 빈 문자열. 사용자가 가져온 아바타의 이용 조건을 UI에 표시하는 데 쓴다.

### Godot 동작 규칙

- `gesture_done`은 받아들인 제스처마다 정확히 한 번: `duration_ms`가 끝날 때, 또는 새 `gesture`가 이전 것을 대체할 때 즉시.
- 권장 길이: `write` = 해당 스텝 음성 길이, `nod` 0.5~1.1초(0.55초당 한 번, 최대 3번), `tap_desk` 두드림당 약 0.32초, `point` 0.6초 이상, `throw` 0.8~1.0초, `idle` 0ms 가능.
- `throw_chalk`는 `gesture throw` 직후 보낸다. 분필은 throw 길이의 46% 지점에서 손을 떠나고 soft 0.70초 / normal 0.52초 / hard 0.36초 뒤 `chalk_impact`. throw 제스처 없이 보내면 즉시 날아간다.
- `hand_pos`는 제스처 중인 손의 분필 끝 위치(CSS px)이며 write/point/tap_desk/throw 동안에만 30Hz로 보낸다.
- 필기 손(오른손)은 어깨에서 약 75 CSS px까지 닿는다. Director는 필기 선두를 따라 캐릭터를 옮긴다 (`timeline.ts`).
- `write`/`point`는 다음 `look_at`까지 자기 목표를 본다. 표정은 바뀔 때까지 유지된다.
- 시선 연출은 Godot 몫(무작위 타이밍, 시나리오 없음): `look_at user`는 눈맞춤 2~5초마다 0.5~1.3초 시선을 피하고(대개 깜빡임과 함께) 얼굴은 살짝 비스듬히 둔다. `look_at` 명령이 한 번도 없으면 주변을 둘러보며 가끔 사용자를 본다. 제스처 중에는 목표에서 눈을 떼지 않는다. 커서를 가끔 보게 하려면 Director가 커서 좌표로 `look_at {x, y}`를 보내면 된다.
- 드래그: 드래그 시작과 포인터 이동마다 `grab {x, y}`, 끝에 `release`. 잡혀 있는 동안에도 `hit_rect`는 매달린 몸을 따라가고, 착지하면 `arrived {x, y}`(발 위치)가 온다. 잡혀 있거나 떨어지는 중에 온 `move_to`는 착지 뒤에 실행되며, 그때는 착지 `arrived` 대신 그 이동의 `arrived`만 온다.
- 시작 직후 `ready` 다음에 요청 없이 `avatar_loaded {id:"default"}`(기본 캐릭터 크레딧 메타)가 온다. `load_avatar {id:"placeholder"}`는 디버그용 치비 캐릭터.

## Director/UI ↔ Backend

원본: `packages/protocol/schema/backend.schema.json`. `→` = 백엔드로, `←` = 백엔드에서. 응답은 요청의 `id`를 그대로 쓴다.

### 시스템·모델

| type | 방향 | 필드 |
|---|---|---|
| `hello` | → | `client?, lang?: Lang, profile?: UserProfile` — 연결 직후. 응답으로 `status` |
| `status` | ← | `version, tier, lang, profile?, hardware: HardwareInfo, models: ModelInfo[], capabilities` (상태가 바뀌면 푸시). `capabilities.tts`는 현재 언어의 음성 모델 기준 |
| `set_tier` | → | `tier: "lite" \| "standard" \| "pro" \| "max"` |
| `set_gpu_use` | → | `gpu_use: "high" \| "balanced" \| "low"` — 언어 모델의 GPU/CPU 배치 (high 전부 GPU, balanced 카드 절반만 쓰고 나머지 층은 CPU, low CPU·추론 단계 생략). 임베딩은 항상 CPU, 비전은 항상 GPU. 저장되며 `status.gpu_use`로 알린다 |
| `set_language` | → | `lang: "ko" \| "ja" \| "en"` — 캐릭터의 말(LLM 출력·TTS), 음성 인식, 교육과정이 이 언어를 따른다. 응답·푸시 `status` |
| `set_profile` | → | `profile: {address?}` — 캐릭터가 사용자를 부르는 호칭 (20자 이내, 글자·숫자·띄어쓰기만). 백엔드가 검사하며 성적·연인 호칭·욕설은 `error {code: "unsafe_address"}`, 형식 오류는 `invalid_address`. 빈 문자열은 기본값. 응답·푸시 `status` (`profile`에 적용된 호칭) |
| `download_model` | → | `id, model_id` |
| `download_progress` | ← | `id, model_id, file, downloaded, total?, done` |
| `error` | ← | `id?, code, message` (message는 사용자용 한국어) |

### 풀이·질문

| type | 방향 | 필드 |
|---|---|---|
| `solve_request` | → | `id, image_base64? \| problem_text?, subject_hint?` |
| `solve_progress` | ← | `id, stage: "ocr" \| "solving" \| "verifying" \| "retry" \| "voicing", attempt?, detail?` |
| `solve_script` | ← | `id, script: SolveScript` |
| `ask_request` | → | `id, text, context?, problem_id?, history?: [{role: "user" \| "assistant", text}], mode?: "question" \| "chat"` — 음성/텍스트 대화. 대화 기록은 셸이 보관해 매번 보낸다 |
| `ask_answer` | ← | `id, steps: ScriptStep[]` |

### 음성

| type | 방향 | 필드 |
|---|---|---|
| `tts_request` | → | `id, text, voice? (preset_id), preset? (저장 전 미리듣기)` — 프리셋의 `lang`으로 합성한다. `preset`은 그대로 쓰고, `voice`가 없거나 현재 언어가 아닌 프리셋이면 현재 언어의 기본 프리셋으로 대신한다 (셸 설정에 남은 다른 언어 목소리로 읽지 않도록) |
| `tts_audio` | ← | `id, wav_base64, sample_rate, duration_ms, phonemes?: [{char, start_ms, end_ms, vowel?}]` — `vowel`(`a i u e o n`)은 언어와 무관한 입모양 입력. 한국어는 생략 시 음절에서 유도. `char`: 한국어 음절, 일본어 가나 모라(카타카나, `ー`·`ン`·`ッ` 포함), 영어 음절 단위 음소 묶음(IPA, 입술이 닫히는 m·b·p는 `vowel: "n"`인 별도 단위) |
| `voice_presets_get` / `voice_presets` | → / ← | `presets: VoicePreset[]` (모든 언어), `default_preset_id` (현재 언어의 기본값) |
| `voice_preset_save` | → | `preset, make_default?` → 응답 `voice_presets`. `make_default`는 프리셋 언어의 기본값을 바꾼다 |
| `voice_preset_delete` | → | `preset_id` → 응답 `voice_presets` (내장 프리셋은 삭제 불가) |
| `stt_start` / `stt_stop` | → | `id` — 푸시투토크. 백엔드가 마이크 녹음, VAD로 자동 종료도 함 |
| `stt_level` | ← | `id, level 0~1` (마이크 레벨 표시) |
| `stt_partial` / `stt_final` | ← | `id?, text` |

`stt_final.text`가 빈 문자열이면 아무 말도 듣지 못한 것이다. 음성 인식은 현재 언어(`set_language`)로 디코딩한다. 음성 관련 오류 코드: `stt_busy`, `no_microphone`, `builtin_preset`, `unknown_preset`, `invalid_preset`, `unknown_speaker` (프리셋 언어에 없는 `speaker`), `too_many_presets`, `text_too_long`.


### 출제·복습

| type | 방향 | 필드 |
|---|---|---|
| `generate_quiz` | → | `id, subject, unit?, difficulty: "easy" \| "normal" \| "hard", count, source_doc_id?` |
| `quiz_progress` | ← | `id, done, total` |
| `quiz_items` | ← | `id, items: QuizItem[]` (검증 통과한 문항만) |
| `quiz_answer` / `quiz_graded` | → / ← | `item_id, answer` / `item_id, correct, correct_answer, note_id?` (오답은 오답노트 + 복습 카드로 저장) |
| `wrong_notes_get` / `wrong_notes` | → / ← | `notes: WrongNote[]` |
| `wrong_note_delete` | → | `note_id` → 응답 `wrong_notes` |
| `review_due_get` / `review_due` | → / ← | `cards: ReviewCard[], next_due?` |
| `review_grade` / `review_graded` | → / ← | `card_id, rating 1~4` (FSRS) / `card_id, next_due` |

### 문서 (RAG)

| type | 방향 | 필드 |
|---|---|---|
| `doc_import` | → | `id, path` (사용자가 고른 PDF 절대 경로) |
| `doc_progress` | ← | `id, stage: "extract" \| "embed", done, total` |
| `doc_imported` | ← | `id, doc: DocInfo` |
| `docs_get` / `docs` | → / ← | `docs: DocInfo[]` |
| `doc_delete` | → | `doc_id` → 응답 `docs` |

### 졸음 감지 (웹캠 옵트인)

| type | 방향 | 필드 |
|---|---|---|
| `drowsy_start` | → | `sensitivity: "low" \| "normal" \| "high", camera_index?` |
| `drowsy_stop` | → | — |
| `drowsy_calibration` | ← | `progress 0~1, done, baseline_ear?` (시작 5초 눈 뜬 상태 측정) |
| `drowsy_state` | ← | `state: "normal" \| "candidate" \| "drowsy" \| "no_face" \| "paused", perclos, pitch, ear?` |
| `camera_state` | ← | `active` (트레이 표시용) |
| `user_activity` | → | `last_input_ms` (최근 입력이 있으면 판정 보류) |

## 데이터 타입

### SolveScript

```json
{
  "problem_latex": "\\frac{x}{2} + 3 = 7",
  "final_answer": "x = 8",
  "verified": true,
  "confidence": "high",
  "steps": [
    {
      "say": "먼저 3을 오른쪽으로 넘겨요.",
      "write": "\\frac{x}{2} = 4",
      "mark": { "type": "circle", "target": "3" },
      "gesture": "write",
      "emotion": "neutral"
    },
    {
      "say": "양변에 2를 곱하면 끝이에요!",
      "write": "x = 8",
      "gesture": "point",
      "emotion": "happy"
    }
  ]
}
```

- `confidence`: `"high"` (SymPy 검증 통과) | `"medium"` (재풀이 일치만) | `"low"`
- `unit`(선택): 정규 교육과정 단원, 예 `"중1 · 일차방정식"`. 판서 머리에 표시
- `subject`(선택): 단원의 과목 (`math` · `korean` · `english` · `korean_history` · `social` · `science` · `other`). 수학이 아니면 근거·선택지 판단형 수업이며, 셸은 check 줄 이름을 "검산" 대신 "확인"으로 표시한다
- 스텝 `role`(선택): 수업 흐름. `intro` 문제 파악 → `concept` 단원 핵심 개념 → `solve` 교과서식 풀이 줄 → `check` 대입 검산 → `summary` 한 줄 정리. SymPy는 `solve` 줄만 검증한다
- 스텝 `note`(선택, 24자 이내): 선생님이 줄 옆에 적는 짧은 메모, 예 `"-5 이항"`, `"양변 ÷ 2"`
- `problem_id`(선택): 백엔드가 문제 원문을 메모리에만(최근 20개, 디스크 저장 없음) 보관하는 키. 이 문제에 대한 후속 질문은 `ask_request.problem_id`로 돌려준다. 학생이 "정답은 ③이야"처럼 답을 바로잡으면 원문으로 다시 풀어 인정·설명하고, 정답지가 틀렸다고 우기지 않는다
- `mark.type`: `"circle"` | `"underline"` | `"arrow"`
- `write`는 LaTeX. 일반 문장은 `\text{...}`로 감싼다

### QuizItem

```json
{
  "item_id": "q_3f2a",
  "subject": "수학",
  "difficulty": "normal",
  "question_latex": "2x - 5 = 11 일 때 x의 값은?",
  "choices": ["6", "7", "8", "9"],
  "answer": "8",
  "solution": { "steps": [] },
  "confidence": "high",
  "source": { "doc_id": "abc", "page": 12 }
}
```

### VoicePreset

TTS 합성 후 적용하는 후보정 체인. 내장 프리셋(`builtin: true`)은 모두 여성 목소리이며 언어마다 여러 타입이고(한국어 3종: MeloTTS 한 화자의 후보정, 일본어·영어 각 4종: 서로 다른 Kokoro 원어민 화자 + 가벼운 후보정), 이름은 그 언어로 쓴다. 사용자가 복제해 수정한다. `lang`은 이 목소리가 말하는 언어(생략 시 `ko`), `speaker`는 후보정을 적용할 기본 TTS 화자(생략 시 그 언어의 기본 화자). 화자 id(첫 번째가 기본): `ko` `melo_kr` / `ja` `jf_alpha jf_nezumi jf_tebukuro jf_gongitsune` / `en` `af_bella af_heart af_sarah bf_emma` (`bf_*`는 영국 영어 발음). 일본어·영어는 `speed`를 모델 안에서 적용한다(시간 늘이기보다 깨끗함). 셸은 현재 언어의 프리셋만 보여준다. 기본값은 언어마다 따로 저장하며, 저장된 기본값이 사라진 프리셋(예: 예전 남성 내장 프리셋)이면 그 언어의 기본 프리셋으로 돌아간다.

```json
{
  "preset_id": "female_bright", "name": "밝은 여성", "gender": "female", "builtin": true,
  "lang": "ko", "speaker": "melo_kr",
  "pitch_semitones": 1.0, "formant_ratio": 1.05, "speed": 1.05,
  "brightness_db": 2.0, "warmth_db": 0.0, "reverb": 0.05, "volume_db": 0.0
}
```

### ModelInfo.langs / required

`langs`는 그 모델을 쓰는 언어 목록이다(생략 = 모든 언어). 셸은 현재 언어가 목록에 있는 모델만 보여주고 받는다. `required`는 앱 동작에 필요한 모델이며, `langs`가 있으면 "그 언어 사용자에게 필요"라는 뜻이다. 예: `melo-korean`(`ko`), `kokoro-82m`(`ja`, `en`), `kokoro-voices-ja`(`ja`), `kokoro-voices-en`·`spacy-en-core-web-sm`·`g2p-en-oov`(`en`), `g2p-cmudict`(`ko`, `en`, 선택).

### 기타

`ModelInfo`, `HardwareInfo`, `DocInfo`, `WrongNote`, `ReviewCard`, `PhonemeTiming`은 스키마 정의를 따른다.

- 쪽 번호는 모두 1부터 시작한다. `DocInfo.empty_pages`는 글자 층이 없어(스캔본) 건너뛴 쪽이다.
- `quiz_graded.correct_answer`는 객관식이면 선택지 문자열 그대로다 (UI에서 강조용).
- 오답으로 만든 복습 카드는 즉시 복습 대상(due = now)이다. 같은 문항을 또 틀리면 기존 노트를 재사용하고 FSRS "다시"로 기록한다.
