# NCM 转 MP3 / FLAC - Android 版打包指南

当前 Windows 原生**无法**用 Buildozer 直接编译 Android apk，必须在 Linux 环境（推荐 WSL2 + Ubuntu 22.04）执行。

## 目录结构

```
android/
├── main.py            # Kivy 主程序 (Android UI)
├── ncm2mp3.py         # 核心解密模块 (与项目根目录同步)
└── buildozer.spec     # Buildozer 配置文件
```

## 在 Windows 上一次性配置 WSL2 + Ubuntu + Buildozer

### 1. 启用 WSL2 并安装 Ubuntu 22.04 (管理员 PowerShell)

```powershell
wsl --install -d Ubuntu-22.04 --web-download
# 装好后会提示设置 Ubuntu 用户名密码
```

如果之前装过 WSL 但没装发行版，直接执行上面的 `-d Ubuntu-22.04`。

### 2. 进入 Ubuntu，安装 Buildozer 依赖

```bash
# 在 Ubuntu shell 里:
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool \
    pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 \
    cmake libffi-dev libssl-dev build-essential ccache

pip3 install --user --upgrade buildozer Cython==0.29.36 virtualenv
echo 'export PATH=$HOME/.local/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

### 3. 把项目从 Windows 挂载点复制到 Ubuntu 内部

千万**不要在 `/mnt/d/...` 上直接 buildozer**，符号链接 / 权限 / 性能都会出问题。

```bash
# 假设项目在 D:\我的文件\idoknow\Haohaoxuedili
mkdir -p ~/ncm2mp3
cp -r "/mnt/d/我的文件/idoknow/Haohaoxuedili/android/." ~/ncm2mp3/
cd ~/ncm2mp3
```

### 4. 第一次编译 (会下载 Android SDK/NDK, 约 2GB, 30-60 分钟)

```bash
buildozer -v android debug
```

成功后会在 `~/ncm2mp3/bin/` 生成 `ncm2mp3-1.0.0-debug.apk`。

### 5. 拷贝 apk 回 Windows

```bash
cp ~/ncm2mp3/bin/*.apk /mnt/d/我的文件/idoknow/Haohaoxuedili/android/bin/
```

## 在手机上安装

- 把 apk 传到手机 (微信/QQ发送 / USB / 网盘均可)
- Android 设置 → 安全 → 允许"未知来源应用安装"
- 点击 apk 文件安装
- 打开 App，授予存储权限
- 点"+ 添加 NCM 文件" → 选择 `.ncm` 文件 → 输出格式选 FLAC → 开始转换
- 转换后的文件保存在 `/sdcard/NCM2MP3_Output/` (在 SD 卡根目录同名文件夹)

## 关于 FFmpeg / MP3 转码

**当前 APK 默认不内置 FFmpeg，仅输出 FLAC**。原因:
- Android 上集成 FFmpeg 需要带 GPL 的 libmp3lame 编码器，LGPL 版无法编码 MP3
- 集成静态二进制后 APK 会增大 30-60MB，且需同时支持 arm64 + armv7 两个 ABI

如需 MP3 输出，两种推荐路径:
1. **手机端推荐**: 解出 FLAC 后用手机里现成的音乐格式转换 App (如"音频转换器")转 MP3，秒级完成
2. **添加内置 FFmpeg**: 把静态 ffmpeg 二进制放入 `android/bundled/`，并修改 `buildozer.spec` 的 `source.include_patterns` 包含它。`ncm2mp3.py` 已自动处理 Android 私有目录的查找和 `chmod +x`，无需改代码。

## 调试

查看应用日志:

```bash
# 手机连接 USB 后
adb logcat -s python:V SDL:V
```

## 常见问题

### Q: 编译时下载 Android SDK 超时怎么办?
A: 用代理或换镜像。`buildozer.spec` 加:
```
android.sdk_dir = /path/to/pre-downloaded-sdk
```

### Q: 报错 `No recipe for ffmpegkit`?
A: 我们已经从 requirements 移除 ffmpegkit，不应再出现。如出现说明 buildozer.spec 被改回旧版。

### Q: 应用启动闪退?
A: `adb logcat` 看堆栈。多半是权限被拒，或解密过程中遇到格式异常的 ncm。
