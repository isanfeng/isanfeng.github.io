#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
部署脚本：构建 Jekyll 站点并将产物移动到发布仓库。

合并了原 deploy.bat（构建 + 调用移动）与 mv_site.py（仅移动）的功能，
统一为单个跨平台（macOS / Linux / Windows + Git Bash）脚本。

用法：
    python scripts/deploy.py            # 默认：jekyll build -> 移动到 ../isanfeng.github.io
    python scripts/deploy.py --no-build # 跳过构建，仅移动已有的 ./_site
    python scripts/deploy.py --src ./_site --dst ../isanfeng.github.io

环境变量（可选覆盖）：
    JEKYLL_BUILD_CMD   构建命令，默认 "bundle exec jekyll build"（回退 "jekyll build"）
"""

import argparse
import os
import shutil
import subprocess
import sys


def run_build(build_cmd):
    """执行 jekyll build。优先使用 bundle exec，失败则回退到 jekyll build。"""
    candidates = [build_cmd] if build_cmd else ["bundle exec jekyll build", "jekyll build"]
    for cmd in candidates:
        print(f"> 执行构建: {cmd}")
        # shell=True 便于直接写带空格的命令；脚本仅接受受控命令，无注入风险
        rc = subprocess.call(cmd, shell=True)
        if rc == 0:
            return True
        print(f"  构建命令失败 (exit={rc})，尝试下一个候选命令")
    return False


def move_all_and_overwrite(src_dir, dst_dir):
    """将 src_dir 下的所有文件和子目录移动到 dst_dir，覆盖同名项。"""
    if not os.path.exists(src_dir):
        print(f"源目录 {src_dir} 不存在，请先构建站点")
        return False

    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)

    moved = 0
    for item_name in os.listdir(src_dir):
        src_item = os.path.join(src_dir, item_name)
        dst_item = os.path.join(dst_dir, item_name)
        try:
            if os.path.isfile(src_item):
                if os.path.exists(dst_item):
                    os.remove(dst_item)
                shutil.move(src_item, dst_dir)
            elif os.path.isdir(src_item):
                if os.path.exists(dst_item):
                    shutil.rmtree(dst_item)
                shutil.move(src_item, dst_dir)
            moved += 1
        except Exception as e:
            print(f"移动 {src_item} -> {dst_dir} 时出错: {e}")
    print(f"已移动 {moved} 项: {src_dir} -> {dst_dir}")
    return True


def main():
    parser = argparse.ArgumentParser(description="构建并部署 Jekyll 站点到发布仓库")
    parser.add_argument("--no-build", action="store_true", help="跳过 jekyll build，仅移动已有 ./_site")
    parser.add_argument("--src", default="./_site", help="构建产物目录 (默认 ./_site)")
    parser.add_argument("--dst", default="../isanfeng.github.io", help="发布仓库目录 (默认 ../isanfeng.github.io)")
    parser.add_argument("--build-cmd", default=os.environ.get("JEKYLL_BUILD_CMD", ""), help="自定义构建命令")
    args = parser.parse_args()

    if not args.no_build:
        if not run_build(args.build_cmd):
            print("构建失败，已中止部署", file=sys.stderr)
            sys.exit(1)

    if not move_all_and_overwrite(args.src, args.dst):
        sys.exit(1)

    print("部署完成。")


if __name__ == "__main__":
    main()
