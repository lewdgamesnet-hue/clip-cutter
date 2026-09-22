#define MyAppName "Premium Clip Cutter"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Premium Clip Cutter"
#define MyAppExeName "PremiumClipCutter.exe"

[Setup]
AppId={{D4A7F4B7-2A9A-4D3C-9D9E-CLIPCUTTER001}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Premium Clip Cutter
DefaultGroupName={#MyAppName}
OutputDir=Output
OutputBaseFilename=PremiumClipCutter_Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=app.ico
PrivilegesRequired=admin

[Files]
Source: "dist\PremiumClipCutter.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\Premium Clip Cutter"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Premium Clip Cutter"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Premium Clip Cutter"; Flags: nowait postinstall skipifsilent
