; Maestro Setup NSIS Script
!define APPNAME "GestureController"
!define COMPANYNAME "Maestro"
!define DESCRIPTION "Cross-platform hand-gesture desktop controller"
!define VERSIONMAJOR 0
!define VERSIONMINOR 1
!define VERSIONBUILD 0

# Set compression type
SetCompressor lzma

# Output File
OutFile "GestureController-Setup-v${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}.exe"

# Default install directory
InstallDir "$PROGRAMFILES64\${COMPANYNAME}\${APPNAME}"

# Registry key to check for directory (to default to last install directory)
InstallDirRegKey HKLM "Software\${COMPANYNAME}\${APPNAME}" "Install_Dir"

RequestExecutionLevel admin

Page directory
Page instfiles

UninstPage uninstConfirm
UninstPage instfiles

Section "Install"
  SetOutPath "$INSTDIR"
  
  # Copy all PyInstaller compiled files
  File /r "..\dist\GestureController\*.*"
  
  # Write install path to registry
  WriteRegStr HKLM "Software\${COMPANYNAME}\${APPNAME}" "Install_Dir" "$INSTDIR"
  
  # Write uninstaller to registry for Windows Add/Remove Programs
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayName" "${APPNAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayIcon" '"$INSTDIR\GestureController.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "Publisher" "${COMPANYNAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayVersion" "${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}"
  
  WriteUninstaller "$INSTDIR\uninstall.exe"
  
  # Create Start Menu Shortcuts
  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\GestureController.exe"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Uninstall ${APPNAME}.lnk" "$INSTDIR\uninstall.exe"
  
  # Create Desktop Shortcut
  CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\GestureController.exe"
SectionEnd

Section "Uninstall"
  # Delete shortcuts
  Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
  Delete "$SMPROGRAMS\${APPNAME}\Uninstall ${APPNAME}.lnk"
  RMDir "$SMPROGRAMS\${APPNAME}"
  Delete "$DESKTOP\${APPNAME}.lnk"
  
  # Delete Registry keys
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"
  DeleteRegKey HKLM "Software\${COMPANYNAME}\${APPNAME}"
  
  # Delete files
  RMDir /r "$INSTDIR"
SectionEnd
