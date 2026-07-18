#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
部署脚本：构建 Jekyll 站点、移动到发布仓库，并提交/推送到 GitHub Pages。

合并了原 deploy.bat（构建 + 调用移动）与 mv_site.py（仅移动）的功能，
并新增 git 提交/推送能力，统一为单个跨平台脚本。

用法：
    python scripts/deploy.py                 # 默认：build -> 移动 -> git add/commit/push（全自动一键发布）
    python scripts/deploy.py --no-build      # 跳过构建，仅移动已有 ./_site 并发布
    python scripts/deploy.py --no-push       # build -> 移动 -> commit，但 push 前停下（留给你确认）
    python scripts/deploy.py --no-git        # 只 build + 移动，不碰 git（旧行为）
    python scripts/deploy.py --commit-msg "发布说明"
    python scripts/deploy.py --src ./_site --dst ../isanfeng.github.io

环境变量（可选覆盖）：
    JEKYLL_BUILD_CMD   构建命令，默认 "bundle exec jekyll build"（回退 "jekyll build"）
"""

import argparse
import datetime
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


def get_current_branch(repo_dir):
    """获取当前分支名；detached HEAD 或异常时返回 None。"""
    try:
        out = subprocess.run(
            ["git", "-C", repo_dir, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        branch = out.stdout.strip()
        return branch if branch and branch != "HEAD" else None
    except Exception:
        return None


def repo_has_changes(repo_dir):
    """工作树或暂存区是否有改动（含未跟踪文件）。"""
    out = subprocess.run(
        ["git", "-C", repo_dir, "status", "--porcelain"],
        capture_output=True, text=True,
    )
    return bool(out.stdout.strip())


def run_git_deploy(repo_dir, commit_msg, do_push):
    """在发布仓库内执行 git add / commit / push。返回 True 表示流程正常完成。"""
    rc = subprocess.call(
        ["git", "-C", repo_dir, "rev-parse", "--is-inside-work-tree"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if rc != 0:
        print(f"目标目录 {repo_dir} 不是 git 仓库，跳过 git 步骤", file=sys.stderr)
        return False

    if not repo_has_changes(repo_dir):
        print("发布仓库无改动，跳过 commit/push。")
        return True

    print(f"> git add -A  ({repo_dir})")
    if subprocess.call(["git", "-C", repo_dir, "add", "-A"]) != 0:
        print("git add 失败，已中止", file=sys.stderr)
        return False

    # add 后仍可能无 staged 改动（如全部被 .gitignore 忽略）
    if subprocess.call(["git", "-C", repo_dir, "diff", "--cached", "--quiet"]) == 0:
        print("没有可提交的内容（可能被 .gitignore 忽略），跳过 commit。")
        return True

    msg = commit_msg or f"deploy: 站点自动发布 {datetime.datetime.now():%Y-%m-%d %H:%M}"
    print(f'> git commit -m "{msg}"')
    if subprocess.call(["git", "-C", repo_dir, "commit", "-m", msg]) != 0:
        print("git commit 失败，已中止", file=sys.stderr)
        return False

    if not do_push:
        print("已 commit，按 --no-push 跳过 push（你可在发布仓库手动 git push）。")
        return True

    branch = get_current_branch(repo_dir) or "main"
    print(f"> git push origin {branch}")
    rc = subprocess.call(["git", "-C", repo_dir, "push", "origin", branch])
    if rc != 0:
        print(f"git push 失败（exit={rc}）。commit 已保留在本地，请手动检查后 push。", file=sys.stderr)
        return False

    print("已推送到 origin。")
    return True


def main():
    parser = argparse.ArgumentParser(description="构建并部署 Jekyll 站点到发布仓库（含 git 提交/推送）")
    parser.add_argument("--no-build", action="store_true", help="跳过 jekyll build，仅移动已有 ./_site")
    parser.add_argument("--src", default="./_site", help="构建产物目录 (默认 ./_site)")
    parser.add_argument("--dst", default="../isanfeng.github.io", help="发布仓库目录 (默认 ../isanfeng.github.io)")
    parser.add_argument("--build-cmd", default=os.environ.get("JEKYLL_BUILD_CMD", ""), help="自定义构建命令")
    parser.add_argument("--no-git", action="store_true", help="只 build+移动，不执行任何 git 操作")
    parser.add_argument("--no-push", action="store_true", help="git add/commit 但跳过 push（留给你确认）")
    parser.add_argument("--commit-msg", default="", help="自定义 commit message（默认自动生成时间戳）")
    args = parser.parse_args()

    if not args.no_build:
        if not run_build(args.build_cmd):
            print("构建失败，已中止部署", file=sys.stderr)
            sys.exit(1)

    if not move_all_and_overwrite(args.src, args.dst):
        sys.exit(1)

    if not args.no_git:
        if not run_git_deploy(args.dst, args.commit_msg, do_push=not args.no_push):
            # git 失败不回滚已移动产物；按具体错误提示处理
            sys.exit(1)

    print("部署完成。")


if __name__ == "__main__":
    main()
