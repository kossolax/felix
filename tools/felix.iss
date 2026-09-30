; Installeur Windows (Inno Setup 6), à partir du build PyInstaller (pyinstaller felix.spec → dist\felix\) :
;
;   iscc /DVersion=1.1.2 tools\felix.iss   →   dist\virtual-felix-1.1.2-windows-x64-setup.exe
;
; Installation pour l'utilisateur seul (%LOCALAPPDATA%\Programs, sans droits d'administrateur), raccourci
; dans le menu Démarrer, désinstallation propre. Compression LZMA2 : ~30 % de moins que le zip.
#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppId={{D9EC515C-BEE1-4462-ACB0-6D099BE00E67}
AppName=Virtual Felix
AppVersion={#Version}
AppPublisher=kossolax
AppPublisherURL=https://github.com/kossolax/felix
DefaultDirName={autopf}\Virtual Felix
DefaultGroupName=Virtual Felix
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=virtual-felix-{#Version}-windows-x64-setup
SetupIconFile=..\assets\icon\felix.ico
UninstallDisplayIcon={app}\felix.exe
UninstallDisplayName=Virtual Felix
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
CloseApplications=force
RestartApplications=no

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\felix\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; une mise à jour ne garde pas les fichiers d'une version précédente devenus inutiles
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\Virtual Felix"; Filename: "{app}\felix.exe"
Name: "{autodesktop}\Virtual Felix"; Filename: "{app}\felix.exe"; Tasks: desktopicon

[Registry]
; « Lancer au démarrage » (menu du chat) : l'entrée est retirée à la désinstallation
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "VirtualFelix"; Flags: uninsdeletevalue dontcreatekey

[Run]
Filename: "{app}\felix.exe"; Description: "{cm:LaunchProgram,Virtual Felix}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; le chat ne se laisse pas désinstaller en marche
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im felix.exe"; Flags: runhidden; RunOnceId: "StopFelix"
