#define MyAppName "Controle de Estoque"
#define MyAppVersion "1.0"
#define MyAppPublisher "APAE Rio Brilhante"
#define MyAppExeName "Controle_Estoque.exe"

[Setup]
AppId={{8D01E2AA-7B73-4A63-9C39-APAEESTOQUE}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Controle de Estoque
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=instalador
OutputBaseFilename=Instalador_Controle_Estoque
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=app_icon.ico

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "dist\Controle_Estoque\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\app_icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
