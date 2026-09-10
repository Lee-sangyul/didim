; Didim (디딤) installer
; Builds a lightweight, per-user Windows installer around the PyInstaller-packaged
; backend (Didim.exe) and the pre-built frontend (frontend/dist).
; Build backend first:
;   backend> ..\.venv\Scripts\python.exe -m PyInstaller --onefile --name Didim --clean --noconfirm ^
;            --distpath ..\pyinstaller_dist --workpath ..\pyinstaller_build --specpath ..\pyinstaller_build launcher.py
; Then stage into .\release (Didim.exe, frontend\dist, .env.example) and run:
;   ISCC installer.iss

#define MyAppName "디딤"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Didim"
#define MyAppExeName "Didim.exe"

[Setup]
AppId={{8F5E7B7E-6C1E-4E62-9C3B-1D2A9F0F6B41}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Didim
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=installer_output
OutputBaseFilename=Didim-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
DisableWelcomePage=no
SetupLogging=yes

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "release\Didim.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "release\.env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "release\frontend\dist\*"; DestDir: "{app}\frontend\dist"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
