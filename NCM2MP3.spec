# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 - NCM 转 MP3 / FLAC 桌面应用

生成:
  pyinstaller NCM2MP3.spec

产出目录:
  dist/NCM2MP3/NCM2MP3.exe         (主程序)
  dist/NCM2MP3/bundled/ffmpeg.exe  (内置 FFmpeg)
"""

import sys
from pathlib import Path

block_cipher = None

project_dir = Path(SPECPATH).resolve()
ffmpeg_exe = project_dir / "bundled" / "ffmpeg.exe"

if not ffmpeg_exe.exists():
    sys.stderr.write(f"[警告] 未找到内置 ffmpeg.exe: {ffmpeg_exe}\n"
                     f"       打包出的程序将只能用系统 PATH 中的 FFmpeg 或输出原 FLAC.\n")

a = Analysis(
    ['gui.py'],
    pathex=[str(project_dir)],
    binaries=[],
    datas=[
        # (源, 目标目录): 把 bundled/ffmpeg.exe 放到打包后 bundled/ 下
        (str(ffmpeg_exe), 'bundled'),
    ],
    hiddenimports=[
        'numpy',
        'Crypto.Cipher.AES',
        'Crypto.Util.Padding',
        'mutagen.mp3',
        'mutagen.id3',
        'mutagen.flac',
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.sip',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'pydoc',
        'doctest',
        'test',
    ],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NCM2MP3',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # 不用 UPX 压缩 ffmpeg.exe (会引发杀软误报)
    console=False,       # 无控制台 (GUI 应用)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='NCM2MP3',
)
