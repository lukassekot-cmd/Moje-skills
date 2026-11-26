; Inno Setup – inštalátor Kalkulátora spotreby materiálu
#define AppVer GetEnv("APP_VERSION")
#if AppVer == ""
  #define AppVer "1.0"
#endif

[Setup]
AppId={{7B2C3E61-4F7A-4B7E-9C1D-6A1E2F0B5D11}
AppName=Kalkulátor spotreby materiálu
AppVersion={#AppVer}
AppPublisher=Moje-skills
DefaultDirName={autopf}\Kalkulator nabytku
DefaultGroupName=Kalkulátor nábytku
OutputDir=..\dist
OutputBaseFilename=Kalkulator_instalator
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
ChangesAssociations=yes

[Languages]
Name: "slovak"; MessagesFile: "compiler:Languages\Slovak.isl"

[Tasks]
Name: "desktopicon"; Description: "Vytvoriť ikonu na ploche"; GroupDescription: "Ikony:"

[Files]
Source: "..\dist\Kalkulator.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\priklady\liptovska.nkp"; DestDir: "{app}\priklady"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; DestName: "Navod.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\Kalkulátor spotreby materiálu"; Filename: "{app}\Kalkulator.exe"
Name: "{group}\Návod"; Filename: "{app}\Navod.txt"
Name: "{group}\Odinštalovať"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Kalkulátor nábytku"; Filename: "{app}\Kalkulator.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.nkp"; ValueType: string; ValueName: ""; ValueData: "KalkulatorNabytku.Projekt"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\KalkulatorNabytku.Projekt\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Kalkulator.exe"" ""%1"""; Flags: uninsdeletekey

[Run]
Filename: "{app}\Kalkulator.exe"; Description: "Spustiť kalkulátor"; Flags: nowait postinstall skipifsilent
