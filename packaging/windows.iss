; Compilar con Inno Setup en Windows, tras generar dist/choroy_reader.
#ifndef AppVersion
  #define AppVersion "0.1.1"
#endif
#ifndef BundleDir
  #define BundleDir "..\dist\choroy_reader"
#endif
[Setup]
AppId=Choroy Reader
AppName=Choroy Reader
AppVersion={#AppVersion}
AppPublisher=Bastian Enrique
AppPublisherURL=https://github.com/bastideveloper1
AppSupportURL=https://github.com/bastideveloper1/minimalfeed/issues
AppUpdatesURL=https://github.com/bastideveloper1/minimalfeed/releases
DefaultDirName={localappdata}\Programs\Choroy Reader
DefaultGroupName=Choroy Reader
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Choroy-Reader-Setup-{#AppVersion}-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
SetupIconFile=..\assets\choroyreader.ico
UninstallDisplayIcon={app}\choroy_reader.exe
WizardImageFile=..\assets\choroybosque.png
WizardSmallImageFile=..\assets\bosqueicon.png
WizardImageStretch=yes
WizardImageBackColor=$00151612
DisableWelcomePage=no
CloseApplications=yes
InfoBeforeFile=windows-welcome.txt

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Choroy Reader"; Filename: "{app}\choroy_reader.exe"
Name: "{autodesktop}\Choroy Reader"; Filename: "{app}\choroy_reader.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; Flags: unchecked

[Run]
Filename: "{app}\choroy_reader.exe"; Description: "Abrir Choroy Reader"; Flags: nowait postinstall skipifsilent
