#ifndef AppVersion
  #define AppVersion "0.1.0-alpha.2"
#endif
#ifndef AppSource
  #error AppSource is required
#endif
#ifndef BuildOutput
  #error BuildOutput is required
#endif

[Setup]
AppId={{87F975F4-9D5C-4A70-9710-3921BE03DCAA}
AppName=Aram Cartinha Overlay
AppVersion={#AppVersion}
AppVerName=Aram Cartinha Overlay {#AppVersion}
AppPublisher=Luis Henrique Ferreira
AppPublisherURL=https://github.com/luishferreira/aram-cartinha-overlay
AppSupportURL=https://github.com/luishferreira/aram-cartinha-overlay/issues
DefaultDirName={localappdata}\Programs\AramCartinhaOverlay
DefaultGroupName=Aram Cartinha Overlay
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.19041
OutputDir={#BuildOutput}
OutputBaseFilename=AramCartinhaOverlay-{#AppVersion}-Setup-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\AramCartinhaOverlay.exe
AppMutex=Local\MayhemDebugOverlay,Local\MayhemDebugOverlayPreview
CloseApplications=no
RestartApplications=no
SetupLogging=yes
ChangesAssociations=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Aram Cartinha Overlay"; Filename: "{app}\AramCartinhaOverlay.exe"
Name: "{group}\Prévia do overlay"; Filename: "{app}\AramCartinhaOverlay.exe"; Parameters: "--demo"
Name: "{group}\Fechar overlay"; Filename: "{app}\AramCartinhaOverlay.exe"; Parameters: "--stop"
Name: "{group}\Desinstalar"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Aram Cartinha Overlay"; Filename: "{app}\AramCartinhaOverlay.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AramCartinhaOverlay.exe"; Description: "Abrir Aram Cartinha Overlay"; Flags: nowait postinstall skipifsilent unchecked

; User state lives in a different directory. Never remove it on uninstall.
