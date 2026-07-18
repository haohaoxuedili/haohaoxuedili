# -*- coding: utf-8 -*-
"""NCM 转换命令行工具入口。

用法:
    python main.py <ncm 文件或目录> [-o 输出目录] [-f auto|flac|mp3] [-k]
    python main.py demo.ncm
    python main.py "D:\\音乐\\ncm" -o "D:\\音乐\\mp3" -f mp3
"""

import argparse
import sys
import traceback
from pathlib import Path

from ncm2mp3 import decrypt_ncm, FFmpegNotFoundError, has_ffmpeg


def convert_one(ncm_path: str, output_dir: str = None, output_format: str = "auto",
                keep_intermediate: bool = False) -> bool:
    """转换单个文件, 返回是否成功。"""
    try:
        out = decrypt_ncm(ncm_path, output_dir, output_format=output_format,
                          keep_intermediate=keep_intermediate)
        print(f"[OK] {Path(ncm_path).name} -> {Path(out).name}")
        return True
    except FileNotFoundError as e:
        print(f"[跳过] {e}")
    except FFmpegNotFoundError as e:
        print(f"[失败] {Path(ncm_path).name}: 需要 FFmpeg 才能转 MP3\n{e}")
    except ValueError as e:
        print(f"[忽略] {Path(ncm_path).name}: {e}")
    except Exception as e:
        print(f"[失败] {Path(ncm_path).name}: {e}")
        traceback.print_exc(limit=2)
    return False


def main():
    parser = argparse.ArgumentParser(
        description="将网易云音乐的 NCM 文件转换为 MP3/FLAC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  python main.py demo.ncm\n"
               "  python main.py \"D:\\ncm 文件夹\" -o \"D:\\mp3 输出\"\n"
               "  python main.py a.ncm b.ncm -o output -f mp3\n"
               "  python main.py \"D:\\ncm 文件夹\" -f mp3 -k   (保留中间 FLAC)",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="一个或多个 .ncm 文件, 或包含 ncm 文件的文件夹",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="输出目录 (默认与源文件同目录)",
    )
    parser.add_argument(
        "-f", "--format",
        choices=["auto", "flac", "mp3"],
        default="auto",
        help="输出格式: auto=按内层格式(默认), flac=FLAC, mp3=MP3(需 FFmpeg)",
    )
    parser.add_argument(
        "-k", "--keep-intermediate",
        action="store_true",
        help="转 MP3 时保留中间的 FLAC 文件 (默认删除)",
    )
    args = parser.parse_args()

    # 若选了 mp3 但没装 ffmpeg, 提前提示
    if args.format == "mp3" and not has_ffmpeg():
        print("[警告] 未检测到 FFmpeg, 选 -f mp3 时若内层是 FLAC 将会失败。")
        print("       请安装 FFmpeg (Windows: https://www.gyan.dev/ffmpeg/builds/)")
        print("       或改用 -f auto / -f flac 输出。\n")

    # 收集所有目标 ncm 文件
    targets: list[str] = []
    for inp in args.inputs:
        p = Path(inp)
        if p.is_dir():
            targets.extend(str(x) for x in p.rglob("*.ncm"))
        elif p.is_file():
            if p.suffix.lower() == ".ncm":
                targets.append(str(p))
            else:
                print(f"[忽略] 非 .ncm 文件: {p}")
        else:
            print(f"[忽略] 路径不存在: {p}")

    if not targets:
        print("未找到任何 .ncm 文件。")
        sys.exit(1)

    print(f"共发现 {len(targets)} 个 NCM 文件, 输出格式={args.format}, 开始转换...\n")
    success = 0
    for ncm in targets:
        if convert_one(ncm, args.output, args.format, args.keep_intermediate):
            success += 1

    print(f"\n转换完成: {success}/{len(targets)} 成功。")
    sys.exit(0 if success == len(targets) else 2)


if __name__ == "__main__":
    main()
