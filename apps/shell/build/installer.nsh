; Early builds installed to %LOCALAPPDATA%\Programs\@studymateshell (the npm package name).
; Forgetting that location makes this version install to Programs\Your StudyMate; the old copy
; is still found through its uninstall entry and removed as an update (models and data stay).
!macro preInit
  Push $0
  Push $1
  ReadRegStr $0 HKCU "${INSTALL_REGISTRY_KEY}" InstallLocation
  StrCpy $1 $0 "" -15
  ${if} $1 == "@studymateshell"
    DeleteRegValue HKCU "${INSTALL_REGISTRY_KEY}" InstallLocation
  ${endif}
  Pop $1
  Pop $0
!macroend

; Uninstaller: offers to remove the downloaded AI models and the study data as well.
; They live in %APPDATA%\StudyMate (models\ alone is tens of GB), outside the install folder,
; so an update never deletes them. A real uninstall asks once; No keeps them for a reinstall.
!macro customUnInstall
  ${ifNot} ${isUpdated}
    Push $R8
    Push $R9
    ; Language of the Windows UI (the uninstaller itself has no language page)
    System::Call 'kernel32::GetUserDefaultUILanguage() i .R9'
    IntOp $R9 $R9 & 0x3FF
    StrCpy $R8 "Also delete the downloaded AI models and your study records and settings?$\r$\n$\r$\nChoose No to remove only the app. If you install it again, you can pick up where you left off."
    ${if} $R9 == 18
      StrCpy $R8 "다운로드한 AI 모델과 학습 기록·설정도 함께 삭제할까요?$\r$\n$\r$\n'아니요'를 누르면 앱만 삭제돼요. 다시 설치하면 그대로 이어서 쓸 수 있어요."
    ${elseif} $R9 == 17
      StrCpy $R8 "ダウンロードした AI モデルと学習記録・設定も一緒に削除しますか？$\r$\n$\r$\n「いいえ」を選ぶとアプリだけを削除します。もう一度インストールすれば、そのまま続きから使えます。"
    ${endif}
    MessageBox MB_YESNO|MB_ICONQUESTION "$R8" /SD IDNO IDNO studymate_keep_data
      ; Electron keeps app data per user even for an all-users install
      SetShellVarContext current
      RMDir /r "$APPDATA\StudyMate"
      ${if} $installMode == "all"
        SetShellVarContext all
      ${endif}
    studymate_keep_data:
    Pop $R9
    Pop $R8
  ${endif}
!macroend
