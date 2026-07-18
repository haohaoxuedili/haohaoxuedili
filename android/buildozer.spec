[app]
# 应用名称 (显示在 Android 桌面图标下)
title = NCM 转 MP3 / FLAC

# 包名 (反域名格式)
package.name = ncm2mp3
package.domain = io.github.idoknow

# 源码目录 (Buildozer 默认在 spec 同目录的 main.py)
source.dir = .
source.include_exts = py,png,jpg

# 版本号
version = 1.0.0

# 应用需求配置
# - python3, kivy: 框架
# - pycryptodome: AES 解密 NCM 元数据和 key 段
# - mutagen: 写入音频元数据 (标题/歌手/专辑/封面)
# - numpy: 大音频流异或解密的 C 层加速
requirements = python3,kivy,pycryptodome,mutagen,numpy

# Android 配置
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE
android.api = 33              # 目标 Android 13 (API 33)
android.minapi = 24           # 最低 Android 7.0 (API 24)
android.sdk = 33
android.ndk = 25b
android.arch = arm64-v8a,armeabi-v7a

# 横竖屏
orientation = portrait

# 是否全屏
fullscreen = 0

# 应用图标 (PNG 格式, 推荐 512x512)
# android.icon = icon.png

# 应用名
android.app_name = NCM 转 MP3

# 允许备份
android.allow_backup = 1

# 主程序入口
android.entrypoint = main.py

# 包含额外 Python 文件 (核心解密模块)
source.include_patterns = ncm2mp3.py,main.py,*.py

# 编译时清空之前构建
# (命令行加 --clean 即可, 不必固定写)

[buildozer]
# Buildozer 输出目录
build_dir = ./build
bin_dir = ./bin

# 日志等级
log_level = 2

# 接受 p4a / SDK 许可证
android.accept_sdk_license = true

warn_on_skip = true
