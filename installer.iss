[Setup]
AppName=CREC-ERP
AppVersion=1.0
AppPublisher=CREC
DefaultDirName={autopf}\CREC_ERP_POS
DefaultGroupName=CREC-ERP
UninstallDisplayIcon={app}\CREC_ERP_POS.exe
Compression=lzma2
SolidCompression=yes
OutputDir=dist_installer
OutputBaseFilename=CREC_ERP_POS_Instalador

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\CREC_ERP_POS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\CREC-ERP"; Filename: "{app}\CREC_ERP_POS.exe"
Name: "{autodesktop}\CREC-ERP"; Filename: "{app}\CREC_ERP_POS.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CREC_ERP_POS.exe"; Description: "{cm:LaunchProgram,CREC-ERP}"; Flags: nowait postinstall skipifsilent