; NCM 转 MP3 / FLAC - Inno Setup 打包脚本
; 编译命令:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "D:\我的文件\idoknow\Haohaoxuedili\installer.iss"
; 产物:
;   installer\Output\NCM转MP3_Setup.exe   (单文件安装包)

[Setup]
; --- 应用基本信息 ---
AppName=NCM 转 MP3 / FLAC
AppVersion=1.0.0
AppPublisher=idoknow
AppPublisherURL=https://github.com/idoknow
AppSupportURL=https://github.com/idoknow
AppUpdatesURL=https://github.com/idoknow
AppComments=网易云音乐加密格式一键转换为 MP3 或 FLAC

; 默认安装到 当前用户 Program Files
DefaultDirName={autopf}\NCM转MP3
; 开始菜单程序组名
DefaultGroupName=NCM转MP3
; 离开开始菜单文件夹为空时自动删除
UninstallDisplayName=NCM 转 MP3 / FLAC

; --- 输出文件 ---
OutputDir=installer\Output
OutputBaseFilename=NCM转MP3_Setup
; 应用图标
SetupIconFile=app.ico
; 安装时显示自定义图标到 Add/Remove 程序列表
UninstallDisplayIcon={app}\NCM2MP3.exe

; --- 压缩 ---
; 使用 LZMA2 极限压缩（牺牲编译时间换取更小分发体积）
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; --- 权限与系统要求 ---
; 32位/64位均可，安装到 {autopf} 会自动选 Program Files 或 Program Files (x86)
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x86compatible x64compatible
; 最低系统要求 Windows 7
MinVersion=6.1.7600
; 不需要管理员权限也能安装到用户目录(默认 {autopf} 会指向用户级 Program Files)
PrivilegesRequiredOverridesAllowed=dialog
PrivilegesRequired=lowest

; --- 界面 ---
DisableProgramGroupPage=yes
DisableDirPage=no
DisableReadyPage=no
DisableFinishedPage=no
WizardStyle=modern
ShowLanguageDialog=no
LanguageDetectionMethod=none

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "在桌面创建快捷方式"; GroupDescription: "附加选项:"
Name: "associate"; Description: "将 .ncm 文件关联到此程序"; GroupDescription: "附加选项:"

[Files]
; 把整个打包目录全部拷到 {app}
Source: "dist\NCM2MP3\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; 单独标记主程序
Source: "dist\NCM2MP3\NCM2MP3.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; 开始菜单
Name: "{group}\NCM 转 MP3"; Filename: "{app}\NCM2MP3.exe"; IconFilename: "{app}\NCM2MP3.exe"; Comment: "打开 NCM 转 MP3 / FLAC"
Name: "{group}\卸载 NCM 转 MP3"; Filename: "{uninstallexe}"
; 桌面（按用户选项）
Name: "{autodesktop}\NCM 转 MP3"; Filename: "{app}\NCM2MP3.exe"; IconFilename: "{app}\NCM2MP3.exe"; Tasks: desktopicon

[Registry]
; 文件关联（按用户选项，关联到当前用户）
Root: HKCU; Subkey: "Software\Classes\.ncm"; ValueType: string; ValueName: ""; ValueData: "NCM2MP3.File"; Flags: uninsdeletevalue; Tasks: associate
Root: HKCU; Subkey: "Software\Classes\NCM2MP3.File"; ValueType: string; ValueName: ""; ValueData: "网易云音乐 NCM 文件"; Flags: uninsdeletekey; Tasks: associate
Root: HKCU; Subkey: "Software\Classes\NCM2MP3.File\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\NCM2MP3.exe,0"; Flags: uninsdeletekey; Tasks: associate
Root: HKCU; Subkey: "Software\Classes\NCM2MP3.File\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\NCM2MP3.exe"" ""%1"""; Flags: uninsdeletekey; Tasks: associate

[Run]
; 安装完成后可选择立即启动
Filename: "{app}\NCM2MP3.exe"; Description: "立即启动 NCM 转 MP3"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
