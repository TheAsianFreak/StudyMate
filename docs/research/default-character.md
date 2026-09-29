# 기본 캐릭터 후보 조사 (2026-09-25)

기준: **유료 앱 설치 파일에 모델 파일을 번들**해도 되는가. 설치 파일을 풀면 원본 VRM이 나오므로 "원본 재배포" 허용 여부를 가장 중요하게 본다. 모델 파일은 받지 않고 약관 페이지만 확인했다. 출시 전 원문을 다시 확인할 것.

## 번들 가능 / 조건부

| # | 모델 · 작성자 | 형식 · 외형 | 핵심 조항 | 판정 |
|---|---|---|---|---|
| 1 | VRoid CC0 샘플: 센다가야 시노, β AvatarSample_1~4, 사쿠라다 후미리야 · pixiv | VRM 0.0, VRoid 애니풍 (시노: 긴 생머리 고3 학생회장, β1: 단발 여고생, 후미리야: 남성) | CC0. VRoid Hub 설정도 법인 사용·재배포·개변 Allow, 크레딧 불필요 | **번들 가능.** 개명·의상 교체·표정 추가 자유. 구 베타 데이터라 품질 보정 필요할 수 있음 |
| 2 | 츠쿠요미짱 3D 모델 타입A · 夢前黎 | VRM (+ .vroid), 소녀 148cm, 2만 폴리곤 미만 | 개인·법인, 영리·비영리 가능. 유료 소프트 수록 명시 허용. 크레딧 필수 | **조건부.** 다른 캐릭터로 개조 배포 금지, 사용자에게 약관 준수 의무 전달, 무개변 모델 유료 판매 금지, 정치·종교 지지/반대·공격 용도 금지(LLM 발화 필터 필요), VRoid Hub 공개 금지 |
| 3 | Seed-san · VirtualCast | VRM 1.0 / 0.x, 흑발 SF풍 슈트 | VRM Public License 1.0, meta: 재배포·개변 허용, 법인 상업 이용, 크레딧 필요. 위키판 FAQ상 게임 편입은 "개변" | **번들 가능.** 크레딧 필요, 공식 제품처럼 보이면 안 됨, 권리자 라이선스 중지 가능 조항 |
| 4 | VRM1_Constraint_Twist_Sample · pixiv | VRM 1.0, 갈색 긴 머리 소녀 | README는 VRM PL 1.0. 파일 meta 미확인 | **조건부.** 번들 전 파일 meta 직접 확인 |
| 5 | AvatarSample_A/B/C (VRoidPreset) · pixiv | VRM 0.0, 최신 VRoid 품질 | 영리 포함 사용 가능, 크레딧 불필요. 단 "VRM 파일을 대가를 받고 재배포" 금지 | **조건부.** 유료 앱 번들은 유상 재배포 소지 → pixiv 문의 |
| 6 | 쿼리짱 · Pocket Queries | FBX (VRM판 미확인) | CC-BY 4.0 근거가 2차 출처뿐 | **보류** |
| 7 | 유니티짱 · Unity Technologies Japan | FBX | UCL 3.0: 타 엔진 가능, 표기·로고 필요, 머신러닝 사용 금지 조항 | **비추천** (AI 앱과 충돌 소지) |
| 8 | Quaternius Universal Base Characters | FBX/glTF | CC0 | **번들 가능**, 애니풍 아님 |

## 번들 불가 (사용자 가져오기로만)

| 모델 | 이유 |
|---|---|
| 니코니 입체짱 (Alicia Solid) | 법인 사용 불가, 원본 모델 배포 불가 |
| 미라이 코마치 | 상업 이용·재배포 금지 |
| 즌다몬 / 토호쿠 즌코 | 무료 상업 이용은 토호쿠 지역 기업 한정 |
| 프로생짱 | 허가 없는 법인·상업 이용 금지 (원문 미열람) |
| 키즈나 아이 | 상업 이용 개별 문의 |
| Ready Player Me | 2026-01-31 서비스 종료 |
| Sketchfab Standard 라이선스 | 단독 파일 배포 금지, 추출 방지 의무 |
| BOOTH VN3 무료 아바타 대부분 | 제품 편입(R) 항목이 대개 불허, 모델별 확인 필요 |
| Mixamo, 타인 VRM | 프로젝트 규칙상 번들 금지 |

## 권장

- 우리만의 선생님 캐릭터가 목표면 **VRoid CC0 샘플(예: 센다가야 시노)을 개조**하는 것이 가장 자유롭다.
- 기성 캐릭터를 그대로 써도 되면 **츠쿠요미짱**이 유료 앱 수록을 가장 명확히 허용한다 (조건 준수 필요).
- 번들 시 VRM meta를 수정하지 말고 `THIRD_PARTY_NOTICES.md`에 크레딧·라이선스 URL을 기록한다.

## 출처

- VRoid 샘플 이용 조건 FAQ: https://vroid.pixiv.help/hc/en-us/articles/4402614652569
- β AvatarSample_1~4: https://vroid.pixiv.help/hc/en-us/articles/360012381793 · https://vroid.pixiv.help/hc/en-us/articles/360014900273 · https://vroid.pixiv.help/hc/en-us/articles/360014900113 · https://vroid.pixiv.help/hc/en-us/articles/360014900233
- 센다가야 시노: https://vroid.pixiv.help/hc/en-us/articles/360013482714 · https://hub.vroid.com/en/characters/5860098757548846785/models/6567311261748429976
- 사쿠라다 후미리야: https://vroid.pixiv.help/hc/en-us/articles/360014788554
- VRoidPreset A-Z 조건: https://vroid.pixiv.help/hc/en-us/articles/4402394424089
- 츠쿠요미짱 3D 타입A: https://tyc.rei-yumesaki.net/material/avatar/3d-a/ · 캐릭터 라이선스: https://tyc.rei-yumesaki.net/about/terms/
- Seed-san: https://github.com/vrm-c/vrm-specification/tree/master/samples/Seed-san · https://wiki.virtualcast.jp/wiki/vrm/seedsanvrm · VRM PL 1.0: https://vrm.dev/en/licenses/1.0/
- 유니티짱 앱 가이드라인: https://support.unity.com/hc/en-us/articles/29102655807252-Guidelines-regarding-the-use-of-Unity-chan-in-your-app
- Quaternius UBC: https://quaternius.com/packs/universalbasecharacters.html
- Sketchfab 라이선스: https://sketchfab.com/licenses
- 니코니 입체짱: https://3d.nicovideo.jp/alicia/rule.html · 미라이 코마치: https://github.com/Miraikomachi/MiraikomachiUnity · 즌즌PJ: https://zunko.jp/guideline.html · 키즈나 아이: https://kizunaai.com/terms/ · VN3: https://www.vn3.org/terms
