# 내 아바타 불러오기 (VRM)

StudyMate는 **VRM 0.x / 1.0** 아바타를 불러올 수 있어요. 트레이 메뉴 또는 캐릭터 우클릭 → **아바타 불러오기 (VRM)…** 에서 파일을 고르면 바로 갈아입어요.

- 불러온 파일은 `%APPDATA%\StudyMate\avatars\`에만 복사되고, 어디에도 업로드되지 않아요.
- 로드할 때 VRM에 적힌 **제작자·라이선스·상업 이용·재배포 조건**을 알림으로 보여줘요. 이용 조건은 각 제작자의 라이선스를 따라요. (예: 방송·영상에 쓸 수 있는지, 이 앱처럼 "소프트웨어 안에서 쓰기"가 허용되는지)
- 되돌리기: 메뉴 → **기본 캐릭터로 되돌리기**

## BOOTH의 VRChat 아바타 (.unitypackage)

VRChat용 아바타는 대부분 Unity 패키지(FBX + lilToon/Poiyomi 셰이더)로 배포돼요. StudyMate는 이 형식을 직접 읽지 못하므로 VRM으로 변환해야 해요. 먼저 상품 페이지에 **VRM 파일이 함께 들어 있는지** 확인하세요. 들어 있다면 그 파일을 바로 쓰면 돼요.

### 변환 전에 라이선스 확인

많은 BOOTH 아바타는 VN3 라이선스 등 자체 약관을 따라요. 다음을 확인하세요.

- **개인 이용** 범위에서 다른 앱(VRChat 외)에 쓰는 것이 허용되는지
- **개변(改変)** 이 허용되는지 — VRM 변환은 개변에 해당할 수 있어요
- 변환한 VRM을 **남에게 배포하지 않기** (대부분 금지)

### 변환 방법 (Unity + UniVRM)

1. 아바타가 권장하는 Unity 버전(예: VRChat 권장 2022.3 LTS)으로 새 3D 프로젝트를 만들어요.
2. [UniVRM](https://github.com/vrm-c/UniVRM/releases) 최신 `.unitypackage`를 가져와요 (MIT 라이선스).
3. 아바타의 `.unitypackage`와 필요한 셰이더(lilToon 등)를 가져와요.
4. 아바타 프리팹을 씬에 놓고 Rig가 **Humanoid**인지 확인해요 (FBX Import Settings → Rig → Animation Type: Humanoid).
5. 메뉴 **VRM0 → Export UniVRM-0.x** (또는 VRM1 Export)를 열고 루트 오브젝트를 지정해요.
6. Meta 탭에 제작자·라이선스 정보를 원본 약관대로 입력해요.
7. **Force T-Pose**를 켜고 Export → `.vrm` 저장.
8. StudyMate에서 불러와요.

### 자주 생기는 문제

| 증상 | 해결 |
|---|---|
| 캐릭터가 누워 있거나 팔이 이상하게 꺾임 | Export 때 T-Pose가 아니었어요. Force T-Pose를 켜고 다시 내보내세요. |
| 너무 밝거나 어둡게 보임 | lilToon/Poiyomi 재질은 MToon으로 근사 변환돼요. UniVRM에서 재질을 MToon으로 바꾸면 더 비슷해요. |
| "VRM 정보가 없는 파일" 오류 | 일반 glTF/GLB예요. UniVRM으로 VRM으로 내보내 주세요. |
| 파일이 너무 큼 (256MB 초과) | 텍스처 해상도를 줄여서 다시 내보내세요. |

크기는 자동으로 맞춰져요 (키 1.55 단위로 정규화).
