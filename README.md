# NCM 转 MP3 / FLAC

一个开源的网易云音乐 `.ncm` 文件解密与转换工具，支持 **Windows 桌面** 与 **Android** 双端，可批量将 NCM 文件还原为 MP3 或 FLAC，并保留歌曲元数据（标题、艺术家、专辑、封面等）。

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Android-blue)
![License](https://img.shields.io/github/license/haohaoxuedili/haohaoxuedili)
![Release](https://img.shields.io/github/v-tag/haohaoxuedili/haohaoxuedili)

## 功能特性

- 解密网易云 `.ncm` 文件，还原内层音频（FLAC / MP3）
- 支持 MP3 320k 转码（内置 FFmpeg，Android 端打包为 native library 绕过 SELinux 限制）
- 保留并写入 ID3 元数据：标题、艺术家、专辑、年份、封面
- Android 端 UI 适配中文显示（内置 DroidSansFallback.ttf）
- Android 端自动扫描下载目录中的 `.ncm` 文件
- Windows 端提供 GUI + 一键安装器
- 通过 GitHub Actions 自动构建并发布 Release APK

## 项目结构

```
.
├── ncm2mp3.py            # 核心解密与转换模块（跨平台）
├── main.py               # Windows 桌面 GUI 入口
├── gui.py                # Windows GUI 附加逻辑
├── requirements.txt      # 桌面端 Python 依赖
├── NCM2MP3.spec          # PyInstaller 打包配置
├── installer.iss         # Inno Setup 安装器脚本
├── gemini-svg.svg        # 应用图标源文件
├── android/
│   ├── main.py           # Android Kivy UI 入口
│   ├── ncm2mp3.py        # 核心模块副本（构建时同步）
│   ├── buildozer.spec    # Buildozer 打包配置
│   ├── DroidSansFallback.ttf  # 内置中文字体
│   └── bundled/          # 内置 FFmpeg 二进制
└── .github/workflows/
    ├── build-apk.yml     # Debug APK 构建
    └── release-apk.yml   # Release APK 签名发布
```

## 桌面端使用

### 环境要求

- Python 3.10+
- 依赖：`pycryptodome`, `mutagen`, `numpy`（可选，加速大文件解密）
- FFmpeg（用于 MP3 转码；桌面端可用系统 PATH 中的 ffmpeg）

### 安装与运行

```bash
pip install -r requirements.txt
python main.py
```

或直接用打包好的 exe：从 [Releases](https://github.com/haohaoxuedili/haohaoxuedili/releases) 下载 Windows 安装包。

## Android 端使用

从 [Releases](https://github.com/haohaoxuedili/haohaoxuedili/releases) 下载签名 APK 安装即可。首次安装需要授予存储访问权限。

支持架构：`arm64-v8a`、`armeabi-v7a`

## NCM 文件格式

NCM 是网易云音乐的加密封装格式，结构如下：

```
[0:8]   magic header "CTENFDAM"
[8:10]  version (2 字节)
[10:14] key_len (uint32 LE)
,key_len]  encrypted_key  (XOR 0x64 → AES-128-ECB/Core_KEY → 去 PKCS#7 → 剥 "neteasecloudmusic" → RC4 key)
[+4]    meta_len
[+meta_len]  encrypted_meta (XOR 0x63 → "163 key(Don't modify):" + base64 → AES-128-ECB/META_KEY → JSON)
[+5]    gap 5 字节
[+4]    cover_frame_len
[+4]    cover_data_len
[+cover_data_len]  cover image
[剩余]  加密音频 (RC4 key 生成 key_box 逐字节异或)
```

核心密钥为固定值：

- `CORE_KEY = 687A4852416D736F356B496E62617857`
- `META_KEY = 2331346C6A6B5F215C5D2630553C2728`

## 开发与构建

### Android Debug APK

```bash
cd android
buildozer android debug
```

或通过 GitHub Actions 自动构建（推送 `android/**` 或 `.github/workflows/**` 变更即触发）。

### Android Release APK

1. 在仓库 Settings → Secrets 中配置：
   - `KEYSTORE_BASE64`：keystore 文件的 base64
   - `KEYSTORE_PASSWORD`
   - `KEY_ALIAS`
   - `KEY_PASSWORD`
2. 推送 `v*` 标签，例如：
   ```bash
   git tag v1.0.3
   git push origin v1.0.3
   ```
3. 工作流自动签名并发布到 GitHub Releases。

### Windows 桌面打包

```bash
pip install pyinstaller
pyinstaller NCM2MP3.spec
```

## 致谢

- NCM 格式参考：[xiSage/ncmdump-net](https://github.com/xiSage/ncmdump-net)
- Android FFmpeg 二进制：[Khang-NT/ffmpeg-binary-android](https://github.com/Khang-NT/ffmpeg-binary-android)
- UI 框架：[Kivy](https://kivy.org/) / [Buildozer](https://buildozer.readthedocs.io/)
- 元数据处理：[mutagen](https://mutagen.readthedocs.io/)
- 加密：[pycryptodome](https://pycryptodome.com/)

## License

[MIT License](LICENSE)
