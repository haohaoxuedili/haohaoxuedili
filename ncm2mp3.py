# -*- coding: utf-8 -*-
"""NCM 文件解密与转换核心模块。

NCM 文件真实结构 (参考 xiSage/ncmdump-net 权威实现):

  [0:8]     magic header  b"CTENFDAM"
  [8:10]    2 字节 version (跳过)
  [10:14]   key_len (uint32 LE)
  [14:+key_len]  encrypted_key (每字节 XOR 0x64, AES-128-ECB/Core_KEY 解密后 unpad,
                前 17 字节 "neteasecloudmusic" 是固定前缀, 剥掉后得到 RC4 key)
  [+4]      meta_len (uint32 LE)
  [+meta_len] encrypted_meta (每字节 XOR 0x63 -> ascii "163 key(Don't modify):" + Base64,
                base64 解码后 AES-128-ECB/META_KEY 解密 unpad, 剥 "music:" 前缀得 JSON)
  [+5]      gap 5 字节 (跳过)
  [+4]      cover_frame_len (uint32 LE)
  [+4]      cover_data_len (uint32 LE)
  [+cover_data_len] cover_image (JPEG/PNG)
  [+cfl-cdl] frame 尾部填充 (跳过)
  [剩余]    加密音频 (用 RC4 key 生成 key_box 后逐字节异或)
"""

import base64
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

from Crypto.Cipher import AES
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TYER, APIC

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


# NCM 内置的核心 AES 密钥（网易云固定值）
CORE_KEY = bytes.fromhex("687A4852416D736F356B496E62617857")
META_KEY = bytes.fromhex("2331346C6A6B5F215C5D2630553C2728")

MAGIC_HEADER = b"CTENFDAM"
KEY_PREFIX = b"neteasecloudmusic"   # 17 字节
META_HDR = "163 key(Don't modify):"  # 22 字节


def _android_app_dir() -> Path | None:
    """返回 Android 应用的私有资源目录 (通常是 files/app)。"""
    app_dir_str = getattr(sys, "_APP_DIR", None) or os.environ.get("ANDROID_APP_PATH", None)
    if app_dir_str:
        return Path(app_dir_str)
    return None


def _android_native_lib_dir() -> Path | None:
    """通过 pyjnius 获取 Android APK 的 nativeLibraryDir (lib/<abi>)。"""
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        if activity is None:
            return None
        ctx = activity.getApplicationContext()
        if ctx is None:
            return None
        info = ctx.getApplicationInfo()
        nld = info.nativeLibraryDir
        if nld:
            return Path(nld)
    except Exception:
        pass
    return None


def _candidate_ffmpeg_paths() -> list:
    """返回内置 FFmpeg 候选路径, 适用于开发模式 / PyInstaller 打包 / Android。

    Android Kivy/Buildozer: 资源随 apk 打包后会在旧 Android 的 app 私有目录
        /data/data/<package>/files/ 或 /data/user/0/<package>/files/
    PyInstaller onefile: 资源在 sys._MEIPASS (临时目录)
    PyInstaller onedir: datas 默认放到 <exe_dir>/_internal/<目标目录>
    开发模式: 取当前文件所在目录的 bundled/ 子目录
    """
    cands = []
    # -1) Android 首选: nativeLibraryDir 中的 libffmpeg.so (避免 SELinux 禁止执行 app_data_file)
    nld = _android_native_lib_dir()
    if nld:
        cands.append(Path(nld) / "libffmpeg.so")
    # 0) Android: 通过 os.environ['ANDROID_APP_PATH'] 或 sys._APP_DIR 推断 app 私有目录
    #   真机/模拟器上 sys.platform 可能是 'linux', 且不一定有 ANDROID_ROOT,
    #   因此用 _android_app_dir() 是否存在来判断更可靠。
    app_dir = _android_app_dir()
    if app_dir and app_dir.exists():
        # 根据 CPU 架构选择对应 FFmpeg 二进制
        machine = os.uname().machine.lower()
        if "aarch64" in machine:
            arch = "arm64"
        elif "arm" in machine:
            arch = "armv7"
        else:
            arch = "arm64"
        cands.append(app_dir / "bundled" / f"ffmpeg-{arch}.bin")
        cands.append(app_dir / "_python_bundle" / "_python_bundle" / "bundled" / f"ffmpeg-{arch}.bin")
        cands.append(app_dir / "ffmpeg")
        # 备用: 用当前模块位置推断
        cands.append(Path(__file__).resolve().parent / "bundled" / f"ffmpeg-{arch}.bin")
    # 1) PyInstaller onefile: sys._MEIPASS 临时解压目录
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        cands.append(Path(meipass) / "bundled" / "ffmpeg.exe")
        cands.append(Path(meipass) / "bundled" / "ffmpeg")
        cands.append(Path(meipass) / "ffmpeg.exe")
        cands.append(Path(meipass) / "ffmpeg")
    # 2) 可执行文件或主脚本所在目录 (PyInstaller onedir: <exe_dir>/_internal/bundled)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
    else:
        exe_dir = Path(__file__).resolve().parent
    cands.append(exe_dir / "_internal" / "bundled" / "ffmpeg.exe")
    cands.append(exe_dir / "_internal" / "bundled" / "ffmpeg")
    cands.append(exe_dir / "bundled" / "ffmpeg.exe")
    cands.append(exe_dir / "bundled" / "ffmpeg")
    cands.append(exe_dir / "ffmpeg.exe")
    cands.append(exe_dir / "ffmpeg")
    # 3) 当前模块所在目录的 bundled/ (开发模式: ncm2mp3.py 旁)
    cands.append(Path(__file__).resolve().parent / "bundled" / "ffmpeg.exe")
    cands.append(Path(__file__).resolve().parent / "bundled" / "ffmpeg")
    # 4) Android 标准 PATH 中
    for name in ("ffmpeg", "ffmpeg.exe"):
        which = shutil.which(name)
        if which:
            cands.append(which)
    return cands


def _android_ffmpeg_executable(src: Path) -> Path:
    """Android 上 APK 资源文件没有 x 权限, 复制到可写 files/ 目录后 chmod +x。"""
    app_dir = _android_app_dir()
    if app_dir:
        # app_dir 通常是 files/app, 其上级 files/ 是可写的
        writable_dir = app_dir.parent
    else:
        writable_dir = Path(__file__).resolve().parent
    writable_dir.mkdir(parents=True, exist_ok=True)
    dst = writable_dir / src.name
    # 仅当目标不存在或大小不一致时才复制
    if not dst.exists() or dst.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dst)
    os.chmod(dst, 0o755)
    return dst


def _find_ffmpeg() -> str | None:
    """先查找内置 FFmpeg; 找不到再查 PATH。返回 ffmpeg 可执行文件路径或 None。"""
    # 1. 内置
    for p in _candidate_ffmpeg_paths():
        if p.is_file():
            # nativeLibraryDir 中的 so 可直接执行, 不要复制到 app_data_file 目录
            nld = _android_native_lib_dir()
            if nld and p.parent.resolve() == nld.resolve():
                return str(p)
            # Android: 资源文件无执行权限, 复制到可写目录再使用
            if _android_app_dir() is not None:
                try:
                    return str(_android_ffmpeg_executable(p))
                except OSError:
                    continue
            # Linux/macOS 等其他 posix: 确保有可执行权限
            if os.name == "posix":
                try:
                    os.chmod(p, 0o755)
                except OSError:
                    pass
            return str(p)
    # 2. PATH 中的 ffmpeg/ffmpeg.exe
    return shutil.which("ffmpeg")


def has_ffmpeg() -> bool:
    """检测是否可用 FFmpeg (内置 或 PATH)。"""
    return _find_ffmpeg() is not None


class FFmpegNotFoundError(RuntimeError):
    """FFmpeg 未安装/不可用。"""


def _convert_to_mp3(src: Path, dst: Path, bitrate: str = "320k") -> None:
    """调用 FFmpeg 将 FLAC/其他音频转码到 MP3。

    参数:
        src: 源音频文件路径 (FLAC 等)
        dst: 目标 MP3 文件路径
        bitrate: MP3 比特率, 默认 320k (无损接近的高质量)
    """
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        raise FFmpegNotFoundError(
            "未找到 FFmpeg。本程序已内置 FFmpeg, 但运行环境缺失。\n"
            "请尝试重新安装本程序, 或自行安装 FFmpeg 并加入 PATH:\n"
            "  Windows:  https://www.gyan.dev/ffmpeg/builds/  下载后解压, 把 bin 加入 PATH\n"
            "  macOS:    brew install ffmpeg\n"
            "  Linux:    sudo apt install ffmpeg"
        )
    cmd = [
        ffmpeg, "-y", "-i", str(src),
        "-codec:a", "libmp3lame", "-b:a", bitrate,
        "-map_metadata", "0",
        str(dst),
    ]
    # -y 覆盖输出, 静默 stdout/stderr (保留到 pipe 供调试)
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(
            f"FFmpeg 转码失败 (code={proc.returncode}): "
            f"{proc.stderr.decode('utf-8', errors='replace')[:500]}"
        )


def _unpad(data: bytes) -> bytes:
    """去除 PKCS#7 填充。"""
    if not data:
        return data
    pad_len = data[-1]
    if isinstance(pad_len, int) and 1 <= pad_len <= 16:
        return data[:-pad_len]
    return data


def _aes_ecb_decrypt(key: bytes, data: bytes) -> bytes:
    return AES.new(key, AES.MODE_ECB).decrypt(data)


def _build_keybox(key: bytes) -> list:
    """根据 RC4 key 构建 256 字节 S 盒 (KSA)。"""
    kl = len(key)
    box = list(range(256))
    last_byte = 0
    key_offset = 0
    for i in range(256):
        swap = box[i]
        c = (swap + last_byte + key[key_offset]) & 0xFF
        key_offset = (key_offset + 1) % kl
        box[i] = box[c]
        box[c] = swap
        last_byte = c
    return box


def _keystream_256(keybox: list) -> bytes:
    """生成 256 字节 keystream。

    stream[j] = keybox[(keybox[j] + keybox[(keybox[j]+j) & 0xff]) & 0xff]
    """
    s = bytearray(256)
    for j in range(256):
        s[j] = keybox[(keybox[j] + keybox[(keybox[j] + j) & 0xFF]) & 0xFF]
    return bytes(s)


def _decrypt_audio(audio: bytes, keybox: list) -> bytes:
    """用 keybox 与 audio 逐字节异或解密 (NCM RC4 变种)。

    keystream 周期为 256: keystream[i] = stream[(i+1) & 0xff]
    为加速 50MB 处理: 预生成 256 字节 keystream, 然后用 numpy 批量异或 (O(N) 在 C 层)。
    """
    stream = _keystream_256(keybox)
    # keystream 应用: 第 i (0-based) 字节用 stream[(i+1) & 0xff]
    # 等价于 stream 左移 1 位循环
    ks_period = stream[1:] + stream[:1]  # 长度 256, ks_period[i] = stream[(i+1)&0xff]
    n = len(audio)
    if _HAS_NUMPY:
        # 用 numpy tile 扩展 keystream 到 n 字节, 然后 xor
        repeats = (n + 255) // 256
        ks_full = np.frombuffer((ks_period * repeats)[:n], dtype=np.uint8)
        a = np.frombuffer(audio, dtype=np.uint8)
        return bytes((a ^ ks_full).tobytes())
    else:
        # 回退纯 Python(慢, 但兼容)
        out = bytearray(n)
        for i in range(n):
            out[i] = audio[i] ^ ks_period[i & 0xFF]
        return bytes(out)


def decrypt_ncm(ncm_path: str, output_dir: str = None,
                output_format: str = "auto", keep_intermediate: bool = False) -> str:
    """解密单个 NCM 文件并输出 MP3/FLAC。

    参数:
        ncm_path: 输入 ncm 文件路径
        output_dir: 输出目录，默认与输入同目录
        output_format: 输出格式
            - "auto": 内层什么格式就输出什么 (FLAC 或 MP3)
            - "flac": 强制输出 FLAC (内层已是 FLAC 直接写; 内层 MP3 时不转码仍输出 MP3)
            - "mp3":  强制输出 MP3 (内层 MP3 直接写; 内层 FLAC 时用 FFmpeg 转 320k MP3)
        keep_intermediate: 当转码 MP3 时, 是否保留中间的 FLAC 文件 (默认删除)

    返回:
        最终输出文件路径
    """
    ncm_path = Path(ncm_path)
    if not ncm_path.exists():
        raise FileNotFoundError(f"文件不存在: {ncm_path}")

    if output_format not in ("auto", "flac", "mp3"):
        raise ValueError(f"output_format 必须是 auto/flac/mp3, 实际: {output_format}")

    with open(ncm_path, "rb") as f:
        data = f.read()

    if data[:8] != MAGIC_HEADER:
        raise ValueError(f"不是有效的 NCM 文件 (magic={data[:8]!r})")

    pos = 10  # 跳过 magic(8) + version(2)

    # 1. RC4 key
    key_len = struct.unpack("<I", data[pos:pos + 4])[0]
    pos += 4
    key_raw = bytearray(data[pos:pos + key_len])
    pos += key_len
    for i in range(len(key_raw)):
        key_raw[i] ^= 0x64
    dec_key = _unpad(_aes_ecb_decrypt(CORE_KEY, bytes(key_raw)))
    if not dec_key.startswith(KEY_PREFIX):
        raise ValueError("RC4 key 前缀不匹配, 可能文件已损坏或非标准 NCM")
    rc4_key = dec_key[len(KEY_PREFIX):]
    keybox = _build_keybox(rc4_key)

    # 2. metadata
    metadata = None
    meta_len = struct.unpack("<I", data[pos:pos + 4])[0]
    pos += 4
    if meta_len > 0:
        meta_raw = bytearray(data[pos:pos + meta_len])
        pos += meta_len
        for i in range(len(meta_raw)):
            meta_raw[i] ^= 0x63
        desc = meta_raw.decode("utf-8", errors="replace")
        if desc.startswith(META_HDR):
            b64_str = desc[len(META_HDR):]
            try:
                b64_bytes = base64.b64decode(b64_str)
                md_dec = _unpad(_aes_ecb_decrypt(META_KEY, b64_bytes))
                if md_dec.startswith(b"music:"):
                    md_dec = md_dec[6:]
                metadata = json.loads(md_dec.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                metadata = None

    # 3. 跳过 5 字节 gap
    pos += 5

    # 4. cover 段
    cover_data = b""
    cfl = struct.unpack("<I", data[pos:pos + 4])[0]
    pos += 4
    cdl = struct.unpack("<I", data[pos:pos + 4])[0]
    pos += 4
    if cdl > 0:
        cover_data = data[pos:pos + cdl]
        pos += cdl
    pos += (cfl - cdl)  # 跳过 frame 尾部填充

    # 5. 加密音频段
    audio = data[pos:]

    # 6. 解密音频
    decrypted = _decrypt_audio(audio, keybox)

    # 7. 识别格式
    fmt = _detect_format(decrypted)

    # 8. 输出文件名
    if metadata and metadata.get("musicName"):
        base_name = Path(metadata["musicName"]).stem
    else:
        base_name = ncm_path.stem

    if output_dir is None:
        output_dir = ncm_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _sanitize_name(base_name)

    # 决定最终扩展名:
    #   auto       -> 跟随内层 fmt (flac / mp3 / ogg)
    #   flac       -> 内层 flac 输出 flac; 内层非 flac 仍输出原格式 (不强转)
    #   mp3        -> 内层 mp3 输出 mp3; 内层非 mp3 用 FFmpeg 转换到 mp3
    need_transcode_to_mp3 = (output_format == "mp3" and fmt != "mp3")

    if output_format == "auto":
        final_ext = fmt
    elif output_format == "flac":
        final_ext = fmt if fmt == "flac" else fmt  # 不强转, 输出原格式
    else:  # mp3
        final_ext = "mp3"

    # 先写出原始解密数据 (内层格式)
    raw_path = output_dir / f"{safe_name}.{fmt}"
    with open(raw_path, "wb") as f:
        f.write(decrypted)

    final_path = raw_path

    # 若需要 FLAC -> MP3, 调 FFmpeg 转码到 320k MP3
    if need_transcode_to_mp3:
        mp3_path = output_dir / f"{safe_name}.mp3"
        try:
            _convert_to_mp3(raw_path, mp3_path, bitrate="320k")
        except FFmpegNotFoundError:
            # 转码条件不满足: 保留 FLAC, 抛出到调用方让其知晓
            raise
        # 把 ID3 标签写入 MP3
        try:
            _write_mp3_tags(mp3_path, metadata, cover_data)
        except Exception:
            pass
        # 是否保留中间 FLAC
        if not keep_intermediate:
            raw_path.unlink()
        final_path = mp3_path
    else:
        # 不需转码: 内层是 mp3 直接写 ID3; 内层 flac 暂不写元数据 (原 FLAC 已含 metadata)
        if final_ext == "mp3":
            try:
                _write_mp3_tags(raw_path, metadata, cover_data)
            except Exception:
                pass

    return str(final_path)


def _detect_format(data: bytes) -> str:
    """通过文件头识别音频格式。"""
    if data[:4] == b"fLaC":
        return "flac"
    if data[:3] == b"ID3":
        return "mp3"
    if data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xfa", b"\xff\xf2"):
        return "mp3"
    if data[:4] == b"OggS":
        return "ogg"
    return "mp3"  # 默认按 mp3 处理


def _sanitize_name(name: str) -> str:
    """清理文件名中的非法字符（Windows）。"""
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, "_")
    return name.strip().rstrip(".")


def _write_mp3_tags(mp3_path: Path, metadata: dict, cover_data: bytes) -> None:
    """将元数据写入 MP3 文件的 ID3 标签。"""
    audio = MP3(str(mp3_path))
    try:
        audio.add_tags()
    except Exception:
        pass

    tags = audio.tags if audio.tags is not None else None
    if tags is None:
        tags = ID3()
        audio.tags = tags

    if metadata:
        if metadata.get("musicName"):
            tags.add(TIT2(encoding=3, text=Path(metadata["musicName"]).stem))
        artists = metadata.get("artist") or metadata.get("artists")
        if artists:
            if isinstance(artists, list):
                names = []
                for a in artists:
                    if isinstance(a, list) and len(a) >= 2 and isinstance(a[1], dict):
                        names.append(a[1].get("name", ""))
                    else:
                        names.append(str(a))
                text = "/".join(names)
            else:
                text = str(artists)
            tags.add(TPE1(encoding=3, text=text))
        if metadata.get("album"):
            tags.add(TALB(encoding=3, text=metadata["album"]))
        year = metadata.get("year") or metadata.get("publishTime")
        if year:
            tags.add(TYER(encoding=3, text=str(year)[:4]))

    if cover_data:
        mime = "image/jpeg" if cover_data[:3] == b"\xff\xd8\xff" else "image/png"
        tags.add(APIC(encoding=3, mime=mime, type=3, data=cover_data))

    audio.save()
