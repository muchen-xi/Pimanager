; PiManager Windows 安装脚本 (Inno Setup 6)
; 用法: 安装 Inno Setup 6 → 用 ISCC.exe 编译此文件
; 输出: dist/installer/PiManager-2.2.2-setup.exe

#define MyAppName "PiManager"
#define MyAppVersion "2.2.2"
#define MyAppPublisher "Chenxi"
#define MyAppURL "https://github.com/muchen-xi/Pimanager"
#define MyAppExeName "PiManager.exe"

[Setup]
AppId={{B8F4A3D2-7C19-4E5A-9F32-E6D1A8B4C507}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\dist\installer
OutputBaseFilename=PiManager-{#MyAppVersion}-setup
SetupIconFile=..\pimanager\assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\DISCLAIMER.txt
PrivilegesRequired=admin
Uninstallable=yes
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\PiManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\DISCLAIMER.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
