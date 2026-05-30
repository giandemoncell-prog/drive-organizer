[Setup]
AppName=Drive Organizer
AppVersion=1.0.0
AppPublisher=Drive Organizer
DefaultDirName={autopf}\DriveOrganizer
DefaultGroupName=Drive Organizer
OutputDir=.
OutputBaseFilename=DriveOrganizer_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea icona sul Desktop"; GroupDescription: "Icone aggiuntive:"

[Files]
Source: "dist_windows\drive-organizer.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist_windows\LEGGIMI.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\MANUALE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\taxonomy_custom.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Drive Organizer"; Filename: "{app}\drive-organizer.exe"; Parameters: "setup"
Name: "{group}\Drive Organizer (terminale)"; Filename: "{app}\drive-organizer.exe"
Name: "{userdesktop}\Drive Organizer"; Filename: "{app}\drive-organizer.exe"; Parameters: "setup"; Tasks: desktopicon

[Run]
Filename: "{app}\drive-organizer.exe"; Parameters: "setup"; Description: "Avvia il setup guidato"; Flags: nowait postinstall skipifsilent
