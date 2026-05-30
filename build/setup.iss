[Setup]
AppName=Drive Organizer
AppVersion=1.0.0
AppPublisher=Gianluca Demontis
AppPublisherURL=https://github.com/giandemoncell-prog/drive-organizer
AppSupportURL=https://github.com/giandemoncell-prog/drive-organizer/issues
AppUpdatesURL=https://github.com/giandemoncell-prog/drive-organizer/releases
DefaultDirName={autopf}\DriveOrganizer
DefaultGroupName=Drive Organizer
OutputDir=..\
OutputBaseFilename=DriveOrganizer_Setup_v1.0.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\drive-organizer.exe

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea collegamento sul Desktop"; GroupDescription: "Icone aggiuntive:"; Flags: checkedonce

[Files]
; Eseguibile principale
Source: "..\dist_windows\drive-organizer.exe"; DestDir: "{app}"; Flags: ignoreversion
; Documentazione
Source: "..\dist_windows\LEGGIMI.txt";         DestDir: "{app}"; Flags: ignoreversion
Source: "..\MANUALE.md";                       DestDir: "{app}"; Flags: ignoreversion
; Configurazione
Source: "..\dist_windows\taxonomy_custom.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist_windows\.env.example";         DestDir: "{app}"; DestName: ".env.example"; Flags: ignoreversion
; Icona per collegamento desktop/Start
Source: "..\assets\icon.ico";                  DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Drive Organizer";          Filename: "{app}\drive-organizer.exe"; IconFilename: "{app}\icon.ico"; Parameters: "setup"
Name: "{group}\Drive Organizer (avanzato)"; Filename: "{app}\drive-organizer.exe"; IconFilename: "{app}\icon.ico"
Name: "{group}\Disinstalla Drive Organizer"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Drive Organizer";    Filename: "{app}\drive-organizer.exe"; IconFilename: "{app}\icon.ico"; Parameters: "setup"; Tasks: desktopicon

[Run]
Filename: "{app}\drive-organizer.exe"; Parameters: "setup"; Description: "Avvia il setup guidato (consigliato)"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\tokens"
Type: files;          Name: "{app}\.env"
