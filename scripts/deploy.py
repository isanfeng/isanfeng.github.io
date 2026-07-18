#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
部署脚本：构建 Jekyll 站点、移动到发布仓库，并按选择提交/推送源码仓库与发布仓库。

合并了原 deploy.bat（构建 + 调用移动）与 mv_site.py（仅移动）的功能，
并新增 git 提交/推送能力，统一为单个跨平台脚本。

交互说明：
    默认在终端（tty）运行会询问推送目标：
        1) 只推送 isanfeng.github.io（发布仓库）
        2) 只推送 isanfeng.github.io.dev（源码仓库）
        3) 两个仓库都推送
    非交互环境（管道/CI）默认只推送发布仓库；也可用 --target 显式指定。

用法：
    python scripts/deploy.py                 # 交互选择推送目标（默认全自动发布到发布仓库）
    python scripts/deploy.py --target both   # 非交互：两个仓库都推送
    python scripts/deploy.py --target dev    # 非交互：只推送源码仓库
    python scripts/deploy.py --no-push       # 选定目标 commit 但不 push，留给你确认
    python scripts/deploy.py --no-git        # 只 build+移动，不碰任何 git
    python scripts/deploy.py --commit-msg "发布说明" --dev-commit-msg "源码说明"

环境变量（可选覆盖）：
    JEKYLL_BUILD_CMD   构建命令，默认 "bundle exec jekyll build"（回退 "jekyll build"）
"""

import argparse
import datetime
import os
import shutil
import subprocess
import sys

# .dev 源码仓库根：deploy.py 位于 <dev>/scripts/ 下，上两级即项目根
DEV_REPO_DEFAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DST = os.path.normpath(os.path.join(DEV_REPO_DEFAULT, "..", "isanfeng.github.io"))


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
    """在仓库内执行 git add / commit / push。返回 True 表示流程正常完成。"""
    rc = subprocess.call(
        ["git", "-C", repo_dir, "rev-parse", "--is-inside-work-tree"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if rc != 0:
        print(f"目标目录 {repo_dir} 不是 git 仓库，跳过 git 步骤", file=sys.stderr)
        return False

    if not repo_has_changes(repo_dir):
        print(f"仓库 {repo_dir} 无改动，跳过 commit/push。")
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
        print("已 commit，按 --no-push 跳过 push（你可在该仓库手动 git push）。")
        return True

    branch = get_current_branch(repo_dir) or "main"
    print(f"> git push origin {branch}")
    rc = subprocess.call(["git", "-C", repo_dir, "push", "origin", branch])
    if rc != 0:
        print(f"git push 失败（exit={rc}）。commit 已保留在本地，请手动检查后 push。", file=sys.stderr)
        return False

    print("已推送到 origin。")
    return True


def prompt_target():
    """终端交互询问推送目标，返回 'pub' / 'dev' / 'both'。"""
    print("请选择要推送的仓库：")
    print("  1) 只推送 isanfeng.github.io（发布仓库）")
    print("  2) 只推送 isanfeng.github.io.dev（源码仓库）")
    print("  3) 两个仓库都推送")
    mapping = {"1": "pub", "2": "dev", "3": "both"}
    while True:
        try:
            choice = input("输入选项 [1/2/3，默认 1]：").strip()
        except EOFError:
            choice = "1"
        if choice == "":
            choice = "1"
        if choice in mapping:
            return mapping[choice]
        print("无效输入，请输入 1、2 或 3。")


def resolve_targets(args):
    """确定要推送的仓库集合。"""
    if args.target:
        return {"pub": {"pub"}, "dev": {"dev"}, "both": {"pub", "dev"}}[args.target]
    if sys.stdin.isatty():
        return {"pub": {"pub"}, "dev": {"dev"}, "both": {"pub", "dev"}}[prompt_target()]
    # 非交互环境：默认只推发布仓库，保持一键/CI 兼容
    return {"pub"}


def main():
    parser = argparse.ArgumentParser(
        description="构建并部署 Jekyll 站点到发布仓库（含 git 提交/推送，支持选择推送目标）")
    parser.add_argument("--no-build", action="store_true", help="跳过 jekyll build，仅移动已有 ./_site")
    parser.add_argument("--src", default="./_site", help="构建产物目录 (默认 ./_site)")
    parser.add_argument("--dst", default=DEFAULT_DST,
                        help="发布仓库目录 (默认 ../isanfeng.github.io，相对脚本所在项目)")
    parser.add_argument("--build-cmd", default=os.environ.get("JEKYLL_BUILD_CMD", ""), help="自定义构建命令")
    parser.add_argument("--no-git", action="store_true", help="只 build+移动，不执行任何 git 操作")
    parser.add_argument("--no-push", action="store_true", help="git add/commit 但跳过 push（留给你确认）")
    parser.add_argument("--target", choices=["pub", "dev", "both"], default=None,
                        help="非交互指定推送目标：pub=发布仓库, dev=源码仓库, both=两者（默认交互询问）")
    parser.add_argument("--dev-repo", default=None, help="高级：覆盖 .dev 源码仓库路径（默认自动推导）")
    parser.add_argument("--commit-msg", default="", help="发布仓库 commit message（默认自动生成时间戳）")
    parser.add_argument("--dev-commit-msg", default="", help="源码仓库(.dev) commit message（默认自动生成时间戳）")
    args = parser.parse_args()

    dev_repo = args.dev_repo or DEV_REPO_DEFAULT

    if args.no_git:
        if not args.no_build:
            if not run_build(args.build_cmd):
                print("构建失败，已中止部署", file=sys.stderr)
                sys.exit(1)
        if not move_all_and_overwrite(args.src, args.dst):
            sys.exit(1)
        print("部署完成（--no-git：未执行任何 git 操作）。")
        return

    targets = resolve_targets(args)

    # 仅当目标含发布仓库时才需要构建并移动产物
    if "pub" in targets:
        if not args.no_build:
            if not run_build(args.build_cmd):
                print("构建失败，已中止部署", file=sys.stderr)
                sys.exit(1)
        if not move_all_and_overwrite(args.src, args.dst):
            sys.exit(1)

    ok = True
    if "pub" in targets:
        if not run_git_deploy(args.dst, args.commit_msg, do_push=not args.no_push):
            ok = False
    if "dev" in targets:
        dev_msg = args.dev_commit_msg or f"chore: 源码更新 {datetime.datetime.now():%Y-%m-%d %H:%M}"
        if not run_git_deploy(dev_repo, dev_msg, do_push=not args.no_push):
            ok = False

    if not ok:
        sys.exit(1)
    print("部署完成。")


if __name__ == "__main__":
    main()
