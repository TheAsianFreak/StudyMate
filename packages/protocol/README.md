# @studymate/protocol

메시지 규격의 단일 원본. 사람이 읽는 요약은 `docs/PROTOCOL.md`.

- `schema/*.schema.json` — JSON Schema (원본)
- `ts/generated/` — TypeScript 타입 (생성물)
- `services/backend/studymate/protocol/` — Python pydantic v2 모델 (생성물)

생성: `cd packages/protocol && npm install && npm run gen` (Python 쪽은 backend의 uv 환경에서 datamodel-code-generator 실행)

변경 순서: 스키마 → `docs/PROTOCOL.md` → 타입.
