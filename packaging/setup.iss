[Setup]
AppId={{0BB69D16-F40C-46A3-A716-33440B109E56}
AppName=Peripheral Battery Tray
AppVersion={#AppVersion}
AppPublisher=Peripheral Battery Tray contributors
AppPublisherURL=https://github.com/Bratuha1/peripheral-battery-tray
DefaultDirName={localappdata}\Programs\Peripheral Battery Tray
DefaultGroupName=Peripheral Battery Tray
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
AppMutex=Local\PeripheralBatteryTray.Desktop
OutputDir={#ReleaseDir}
OutputBaseFilename=PeripheralBatteryTray-{#AppVersion}-windows-x64-setup
SetupIconFile=..\assets\battery.ico
UninstallDisplayIcon={app}\PeripheralBatteryTray.exe
LicenseFile=..\LICENSE
WizardStyle=modern
Compression=lzma2
SolidCompression=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
Source: "..\dist\PeripheralBatteryTray.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\build\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Peripheral Battery Tray"; Filename: "{app}\PeripheralBatteryTray.exe"; Parameters: "--show"

[Run]
Filename: "{app}\PeripheralBatteryTray.exe"; Parameters: "--show"; Description: "{cm:LaunchProgram,Peripheral Battery Tray}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(Step: TUninstallStep);
var
  Startup: String;
  Executable: String;
  RunKey: String;
begin
  if Step <> usUninstall then
    exit;
  RunKey := 'Software\Microsoft\Windows\CurrentVersion\Run';
  Executable := ExpandConstant('{app}\PeripheralBatteryTray.exe');
  if RegQueryStringValue(HKCU, RunKey, 'PeripheralBatteryTray', Startup) then
    if (CompareText(Startup, '"' + Executable + '" --autostart') = 0) or
       (CompareText(Startup, Executable + ' --autostart') = 0) then
      RegDeleteValue(HKCU, RunKey, 'PeripheralBatteryTray');
end;
