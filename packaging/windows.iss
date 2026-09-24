; Compilar con Inno Setup en Windows, tras generar dist/choroy_reader.
[Setup]
AppId=Choroy Reader
AppName=Choroy Reader
AppVersion=0.1.0
DefaultDirName={localappdata}\Programs\Choroy Reader
DefaultGroupName=Choroy Reader
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Choroy Reader-Setup-0.1.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\dist\choroy_reader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Choroy Reader"; Filename: "{app}\choroy_reader.exe"
Name: "{autodesktop}\Choroy Reader"; Filename: "{app}\choroy_reader.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; Flags: unchecked

[Run]
Filename: "{app}\choroy_reader.exe"; Description: "Abrir Choroy Reader"; Flags: nowait postinstall skipifsilent
