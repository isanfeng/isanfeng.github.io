#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b_moments 统一管理脚本（添加 / 删除 / 更新 三合一，无需手写 YAML）

页面上每条 moment 右下角显示的数字（#N，倒序：#1 最旧在底部、#总数 最新在顶部）
就是本脚本操作的目标编号：看到想删/改的那条是 #42，直接选「删除/更新」并输入 42 即可。

运行方式：
  1) 交互主菜单（推荐，最省心）：
        python3 scripts/moments.py
     启动后按提示选择：1)列出 2)添加 3)删除 4)更新 q)退出。

  2) 命令行直接操作（适合脚本/自动化）：
        python3 scripts/moments.py add --text "今天心情不错" --title "随手记" --date 2026-07-19
        python3 scripts/moments.py add --inbox _data/moments_inbox.txt
        python3 scripts/moments.py delete --index 42
        python3 scripts/moments.py delete --title "一点感悟"
        python3 scripts/moments.py update --index 42 --set-title "新标题" --set-text "新正文"
        python3 scripts/moments.py update --index 42        # 不带 --set-* 则进入该条目的交互编辑
        python3 scripts/moments.py list

  3) 收件箱模式（添加/删除均支持）：
        添加：在 _data/moments_inbox.txt 里写内容（每条空行分隔，::title/::date/::image/::video/::link 前缀），
              跑 python3 scripts/moments.py add --inbox _data/moments_inbox.txt 即追加并清空收件箱。
        删除：在 _data/moments_delete_inbox.txt 每行写一个目标（数字序号或 ::title/::date/::text），
              跑 python3 scripts/moments.py delete --inbox _data/moments_delete_inbox.txt 即删除并清空。

  4) 本地写作后台（页面内直接增删改，最直观，零依赖）：
        # 第一步：必须先生成 _site（后台就是托管这个目录）
        bundle exec jekyll build
        # 第二步：启动本地后台（托管 _site/ + /api/moments 写接口，保存后自动 build）
        python3 scripts/moments.py serve
     启动后终端会打印地址（默认 http://127.0.0.1:8000/admin，已自动带 token，直接点即可）。
     打开后：页面顶部出现编辑工具条，每张卡片 #N 旁有「编辑 / 删除」按钮；新增/修改/删除后
     后台自动 bundle exec jekyll build（约十余秒）并刷新页面。
       - 仅监听 127.0.0.1 + 随机 token，线上 GitHub Pages 没有这个后端、也拿不到 token，
         管理 UI 永远不激活，对外发布的静态站完全不受影响（安全）。
       - 若已用 jekyll serve --watch 常驻，可加 --no-build 让保存只写 YAML、由 watch 自动重建。
       - 端口可改：--port 8080；token 可固定：--token xxxxx（固定后注意别泄露）。

其它通用参数：
  --dry-run    只打印将要写入的内容，不写文件（安全预览）
  --no-backup  删除时跳过自动备份 moments.yml.bak（默认删除前会备份）

说明：b_moments 是静态站，没有后端。所有增删改 = 修改 _data/moments.yml 数据文件，
然后 bundle exec jekyll build 重新生成页面并部署。索引编号与页面显示完全一致（倒序）。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOMENTS_YML = os.path.join(ROOT, "_data", "moments.yml")
ADD_INBOX_DEFAULT = os.path.join(ROOT, "_data", "moments_inbox.txt")
DELETE_INBOX_DEFAULT = os.path.join(ROOT, "_data", "moments_delete_inbox.txt")

# 收件箱里 :: 前缀 -> 数据字段 的映射
META_KEYS = {
    "title": "title",
    "date": "date",
    "image": "image",
    "video": "video",
    "link": "link",
}

ADD_INBOX_TEMPLATE = (
    "# 在此写入要添加的 moment，每条之间空一行；\n"
    "#   需要标题/日期/图/视频/链接时，在对应条目前加一行 :: 前缀，例如：\n"
    "#     ::title 标题\n#     ::date 2026-07-19\n#     ::image /images/x.jpg\n"
    "#     ::video https://...   ::link https://...\n"
    "#   跑 python3 scripts/moments.py add 后本文件会被清空。\n"
)

DELETE_INBOX_TEMPLATE = (
    "# 在此写入要删除的 moment 目标，每行一个：\n"
    "#   42                删页面显示为 #42 的那条\n"
    "#   ::title 一点感悟  删标题为「一点感悟」的第一条\n"
    "#   ::date 2026-07-19 删该日期第一条\n"
    "#   ::text 关键字    删正文含「关键字」的第一条\n"
    "#   跑 python3 scripts/moments.py delete 后本文件会被清空。\n"
)


# ----------------------------------------------------------------------------
# YAML 辅助：与既有格式严格一致（- text: |- 块标量 + 2 空格单行字段，双引号转义）
# ----------------------------------------------------------------------------
def yaml_str(value):
    """单行字段用双引号包裹并转义，确保任何内容都能安全写入。"""
    s = str(value)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + s + '"'


def unyaml_str(s):
    """反向解析双引号内的值：把转义还原（\" -> "，\\ -> \\）。"""
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            out.append(s[i + 1])
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def normalize_text(block):
    """去掉首尾空行，去掉每行行尾空白，保留内部换行。"""
    lines = [ln.rstrip() for ln in block.split("\n")]
    while lines and lines[0].strip() == "":
        lines.pop(0)
    while lines and lines[-1].strip() == "":
        lines.pop()
    return "\n".join(lines)


def format_entry(m):
    """把一条 moment 字典格式化为正确的 YAML 片段。"""
    lines = ["- text: |-"]
    for ln in (m.get("text") or "").split("\n"):
        lines.append("    " + ln)  # 块标量内容缩进 4 空格
    for key in ("title", "date", "image", "video", "link"):
        v = m.get(key)
        if v:
            lines.append(f"  {key}: {yaml_str(v)}")  # 同层字段缩进 2 空格
    return "\n".join(lines)


def build_block(dicts):
    """把若干 moment 拼成 YAML 片段（条目间空一行）。"""
    return "\n\n".join(format_entry(d) for d in dicts)


# ----------------------------------------------------------------------------
# 读取 / 解析
# ----------------------------------------------------------------------------
def load():
    """读取文件，返回 (头部注释行列表, 全部 moment 字典列表)。文件不存在返回 ([], [])。"""
    if not os.path.exists(MOMENTS_YML):
        return [], []
    with open(MOMENTS_YML, encoding="utf-8") as f:
        lines = f.read().split("\n")
    i = 0
    while i < len(lines) and (lines[i].startswith("#") or lines[i].strip() == ""):
        i += 1
    header = lines[:i]
    while header and header[-1].strip() == "":
        header.pop()
    body = lines[i:]
    starts = [j for j in range(len(body)) if body[j].startswith("- ")]
    blocks = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else len(body)
        blocks.append(body[s:e])
    dicts = [parse_entry_block(b) for b in blocks]
    return header, dicts


def parse_entry_block(block):
    """把一条 moment 的原始行块解析为字典（text/title/date/video/image/link）。"""
    d = {k: None for k in ("text", "title", "date", "video", "image", "link")}
    # 定位 text 块标量（兼容两种写法：`- text: |-` 同行，或 `- ` 换行后 `  text: |-`）
    text_start = None
    for i, ln in enumerate(block):
        if re.match(r"^\s*(?:-\s*)?text:\s*\|-", ln):
            text_start = i
            break
    if text_start is not None:
        tl = []
        for ln in block[text_start + 1:]:
            # 兄弟字段是 2 空格缩进（如 "  title:"），文本内容是 4 空格，遇到 2 空格字段即结束
            if re.match(r"^  [a-z]+:", ln) and not ln.startswith("    "):
                break
            tl.append(ln[4:] if ln.startswith("    ") else ln)
        d["text"] = normalize_text("\n".join(tl))
    # 解析单行字段（title/date/video/image/link）
    for key in ("title", "date", "video", "image", "link"):
        for ln in block:
            m = re.match(r'^\s*' + key + r':\s*"(.*)"\s*$', ln)
            if m:
                d[key] = unyaml_str(m.group(1))
                break
    return d


def parse_inbox(path):
    """解析添加收件箱文本 -> 若干 moment 字典列表。"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    blocks = []
    current = []
    for line in content.split("\n"):
        if line.strip() == "":
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)
    moments = []
    for blk in blocks:
        meta = {}
        text_lines = []
        for line in blk:
            stripped = line.strip()
            if stripped.startswith("::"):
                rest = stripped[2:].strip()
                if " " in rest:
                    key, val = rest.split(" ", 1)
                else:
                    key, val = rest, ""
                key = key.lower()
                if key in META_KEYS:
                    meta[META_KEYS[key]] = val.strip()
                else:
                    sys.stderr.write(f"[warn] 忽略未知 ::{key}，仅支持 {list(META_KEYS)}\n")
                continue
            text_lines.append(line)
        text = normalize_text("\n".join(text_lines))
        if not text.strip():
            sys.stderr.write("[skip] 跳过一条空内容\n")
            continue
        m = {"text": text}
        m.update(meta)
        moments.append(m)
    return moments


def parse_delete_inbox(path, dicts):
    """解析删除收件箱 -> 文件位置集合（0 基）。倒序：数字 N 即页面显示 #N。"""
    with open(path, encoding="utf-8") as f:
        lines = [ln.strip() for ln in f.read().split("\n")]
    total = len(dicts)
    hits = set()
    for raw in lines:
        if raw == "":
            continue
        if raw.startswith("::"):
            rest = raw[2:].strip()
            if " " in rest:
                key, val = rest.split(" ", 1)
            else:
                key, val = rest, ""
            key = key.lower()
            val = val.strip()
            if key in ("title", "date", "text"):
                if key == "text":
                    hs = [i for i, d in enumerate(dicts) if val in (d.get("text") or "")]
                else:
                    hs = [i for i, d in enumerate(dicts) if d.get(key) == val]
                if hs:
                    hits.add(hs[0])
                else:
                    sys.stderr.write(f"[warn] 收件箱目标 ::{key} {val} 未匹配到，跳过\n")
            else:
                sys.stderr.write(f"[warn] 忽略未知 ::{key}（支持 title/date/text 或纯数字序号）\n")
        elif raw.isdigit():
            n = int(raw)
            if 1 <= n <= total:
                hits.add(total - n)  # 倒序映射
            else:
                sys.stderr.write(f"[warn] 序号 {n} 超出范围（共 {total} 条，页面 #1..#{total}），跳过\n")
        else:
            sys.stderr.write(f"[warn] 无法识别的行：「{raw}」，跳过（用数字序号或 :: 前缀）\n")
    return hits


# ----------------------------------------------------------------------------
# 写入
# ----------------------------------------------------------------------------
def write_full(header, dicts, dry_run, backup=False):
    """把 头部 + 全部条目 写回 moments.yml。dry_run 只预览。"""
    if dry_run:
        print("==== 预览将写入 moments.yml 的内容 ====")
        if header:
            print("\n".join(header))
            print("")
        print(build_block(dicts))
        print("==== 结束 ====")
        return
    if backup:
        bak = MOMENTS_YML + ".bak"
        shutil.copy(MOMENTS_YML, bak)
        print(f"已备份原文件到：{bak}")
    head = "\n".join(header).rstrip("\n")
    if head:
        content = head + "\n\n" + build_block(dicts) + "\n"
    else:
        content = build_block(dicts) + "\n"
    with open(MOMENTS_YML, "w", encoding="utf-8") as f:
        f.write(content)


def clear_add_inbox(path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(ADD_INBOX_TEMPLATE)


def clear_delete_inbox(path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(DELETE_INBOX_TEMPLATE)


# ----------------------------------------------------------------------------
# 展示 / 预览
# ----------------------------------------------------------------------------
def preview_short(d):
    text = d.get("text") or ""
    head = d.get("title") or (text[:30] + ("..." if len(text) > 30 else ""))
    tail = f"  [{d['date']}]" if d.get("date") else ""
    return (head + tail).strip()


def list_moments():
    if not os.path.exists(MOMENTS_YML):
        print("moments.yml 不存在。")
        return
    header, dicts = load()
    total = len(dicts)
    print(f"moments.yml 当前共有 {total} 条 moment（页面倒序显示：#1 最旧在底部，#{total} 最新在顶部）：")
    for pos, d in enumerate(dicts):
        disp = total - pos  # 倒序：第 pos 条（0 基）对应页面 #(total-pos)
        print(f"  [#{disp:>3}] {preview_short(d)}")


# ----------------------------------------------------------------------------
# 添加
# ----------------------------------------------------------------------------
def do_add(entries_new, prepend, dry_run, inbox_path=None, clear=False):
    if not entries_new:
        print("没有要添加的内容。")
        return
    header, dicts = load()
    if prepend:
        new_dicts = entries_new + dicts
    else:
        new_dicts = dicts + entries_new
    write_full(header, new_dicts, dry_run)
    if dry_run:
        return
    where = "最前面" if prepend else "最后面"
    print(f"已在{where}添加 {len(entries_new)} 条 moment。")
    if clear and inbox_path:
        clear_add_inbox(inbox_path)
        print("已清空收件箱。")


# ----------------------------------------------------------------------------
# 删除
# ----------------------------------------------------------------------------
def _add_first(targets, hits, label, val, total):
    if not hits:
        print(f"[error] 未找到{label}为「{val}」的条目")
        sys.exit(1)
    targets.add(hits[0])
    if len(hits) > 1:
        print(f"[warn] {label}「{val}」命中 {len(hits)} 条，仅删第 1 条（页面 #{total - hits[0]}）")


def resolve_delete(args, dicts):
    """根据 --index/--title/--date/--text 解析要删除的文件位置集合（0 基）。"""
    targets = set()
    total = len(dicts)
    if args.index is not None:
        if 1 <= args.index <= total:
            targets.add(total - args.index)  # 倒序映射：页面 #N -> 文件第 (total-N) 条
        else:
            print(f"[error] --index {args.index} 超出范围（共 {total} 条，页面 #1..#{total}）")
            sys.exit(1)
    if args.title is not None:
        _add_first(targets, [i for i, d in enumerate(dicts) if d.get("title") == args.title], "title", args.title, total)
    if args.date is not None:
        _add_first(targets, [i for i, d in enumerate(dicts) if d.get("date") == args.date], "date", args.date, total)
    if args.text is not None:
        _add_first(targets, [i for i, d in enumerate(dicts) if args.text in (d.get("text") or "")], "text", args.text, total)
    return targets


def do_delete(targets, dicts, header, dry_run, no_backup):
    targets = sorted(targets)
    if not targets:
        print("没有指定要删除的条目。")
        return
    total = len(dicts)
    removed = [preview_short(dicts[i]) for i in targets]
    if dry_run:
        print(f"==== 将要删除 {len(targets)} 条（共 {total} 条 -> 剩 {total - len(targets)} 条）====")
        for i in targets:
            print(f"--- 页面 #{total - i} 条 ---")
            print(format_entry(dicts[i]))
            print()
        print("==== 以上为 --dry-run 预览，未写入文件 ====")
        return
    if not no_backup:
        bak = MOMENTS_YML + ".bak"
        shutil.copy(MOMENTS_YML, bak)
        print(f"已备份原文件到：{bak}")
    new_dicts = [d for i, d in enumerate(dicts) if i not in targets]
    write_full(header, new_dicts, dry_run=False)
    print(f"已删除 {len(targets)} 条：")
    for p in removed:
        print(f"  - {p}")
    print(f"删除后 moments.yml 剩余 {len(new_dicts)} 条。")


def do_reorder(order, dicts, header, dry_run=False):
    """按页面 #N 的新顺序（顶部 -> 底部）重排 moments.yml。

    约定（与全局倒序显示一致）：文件顺序 dicts 是「最新在前」，页面显示 = dicts 顺序
    （#total 最新在顶部、#1 最旧在底部），页面 #N 对应文件位置 (total - N)。
    故把「从上到下的页面 #N 序列」order 还原成文件顺序：
        new_dicts = [dicts[total - n] for n in order]
    order 必须是 1..total 的一个排列，长度等于条目数。
    返回 {"ok": True, "total": N} 或 {"error": "..."}。
    """
    total = len(dicts)
    if not isinstance(order, list):
        return {"error": f"order 必须是列表（收到 {type(order).__name__}）"}
    if len(order) != total:
        return {"error": f"order 长度须等于条目数 {total}（收到 {len(order)}）"}
    try:
        nums = [int(x) for x in order]
    except Exception:
        return {"error": "order 含非整数元素"}
    if sorted(nums) != list(range(1, total + 1)):
        return {"error": f"order 必须是 1..{total} 的排列（收到 {nums}）"}
    new_dicts = [dicts[total - n] for n in nums]
    write_full(header, new_dicts, dry_run, backup=not dry_run)
    return {"ok": True, "total": len(new_dicts)}


# ----------------------------------------------------------------------------
# 更新 / 编辑
# ----------------------------------------------------------------------------
def input_multiline(prompt):
    print(prompt)
    lines = []
    while True:
        ln = input()
        if ln == ".":
            break
        lines.append(ln)
    return "\n".join(lines)


def do_update_interactive(pos, dicts, header, dry_run):
    total = len(dicts)
    d = dicts[pos]
    print(f"\n--- 当前页面 #{total - pos} 条 ---")
    print(format_entry(d))
    print()
    # 正文（多行）
    print("正文（当前内容见上；输入新正文，多行，单独一行输入 . 结束；直接回车 . 表示保持不变）：")
    new_text = input_multiline("（输入 . 结束）")
    if new_text.strip():
        d["text"] = normalize_text(new_text)
    # 单行字段
    for key in ("title", "date", "video", "image", "link"):
        cur = d.get(key)
        prompt = f"{key}（当前：{cur if cur else '无'}；回车=不变，输入 - 表示清空该字段）: "
        v = input(prompt).strip()
        if v == "":
            pass  # 不变
        elif v == "-":
            d[key] = None
        else:
            d[key] = v
    print("\n--- 更新后预览 ---")
    print(format_entry(d))
    print()
    if dry_run:
        print("==== --dry-run 预览，未写入 ====")
        return
    confirm = input("确认写入？(Y/n): ").strip().lower()
    if confirm in ("", "y", "yes"):
        write_full(header, dicts, dry_run=False)
        print("已更新。")
    else:
        print("已取消，未改动。")


def do_update_cli(pos, dicts, header, sets, dry_run):
    total = len(dicts)
    d = dicts[pos]
    for key in ("text", "title", "date", "video", "image", "link"):
        if key in sets:
            v = sets[key]
            if key == "text":
                if v.strip():
                    d["text"] = normalize_text(v)
            else:
                d[key] = v if v != "" else None  # 空字符串表示清空
    print(f"--- 更新后页面 #{total - pos} 条 ---")
    print(format_entry(d))
    if dry_run:
        print("==== --dry-run 预览，未写入 ====")
        return
    write_full(header, dicts, dry_run=False)
    print("已更新。")


# ----------------------------------------------------------------------------
# 交互主菜单
# ----------------------------------------------------------------------------
def interactive_add():
    text = normalize_text(input_multiline("正文（多行，单独一行输入 . 结束；直接回车 . 表示取消）："))
    if not text.strip():
        print("正文为空，已取消。")
        return
    fields = {}
    for key in ("title", "date", "image", "video", "link"):
        v = input(f"{key}（可选，回车跳过）: ").strip()
        if v:
            fields[key] = v
    m = {"text": text}
    m.update(fields)
    where = input("添加到（1=最前面[默认] / 2=最后面）: ").strip()
    prepend = (where != "2")
    header, dicts = load()
    if prepend:
        new_dicts = [m] + dicts
    else:
        new_dicts = dicts + [m]
    write_full(header, new_dicts, dry_run=False)
    print(f"已添加到{'最前面' if prepend else '最后面'}。")


def interactive_delete():
    list_moments()
    ans = input("\n要删除哪条？输入页面 #N（q 取消）: ").strip()
    if ans.lower() in ("q", "quit", ""):
        print("已取消。")
        return
    if not ans.isdigit():
        print("无效输入。")
        return
    d = int(ans)
    header, dicts = load()
    total = len(dicts)
    if not (1 <= d <= total):
        print(f"超出范围（共 {total} 条）。")
        return
    pos = total - d
    print(f"\n将删除页面 #{d} 条：")
    print(format_entry(dicts[pos]))
    confirm = input("确认删除？(Y/n): ").strip().lower()
    if confirm not in ("", "y", "yes"):
        print("已取消。")
        return
    do_delete({pos}, dicts, header, False, False)


def interactive_update():
    list_moments()
    ans = input("\n要更新哪条？输入页面 #N（q 取消）: ").strip()
    if ans.lower() in ("q", "quit", ""):
        print("已取消。")
        return
    if not ans.isdigit():
        print("无效输入。")
        return
    d = int(ans)
    header, dicts = load()
    total = len(dicts)
    if not (1 <= d <= total):
        print(f"超出范围（共 {total} 条）。")
        return
    pos = total - d
    do_update_interactive(pos, dicts, header, False)


def interactive_menu():
    while True:
        header, dicts = load()
        total = len(dicts)
        print("\n" + "=" * 42)
        print(f"  MOMENTS 管理控制台   当前共 {total} 条")
        print("=" * 42)
        print("  1) 列出全部（带 #N 编号）")
        print("  2) 添加 moment")
        print("  3) 删除 moment")
        print("  4) 更新 / 编辑 moment")
        print("  q) 退出")
        choice = input("请选择: ").strip().lower()
        if choice in ("q", "quit", "exit", ""):
            print("再见。")
            break
        elif choice == "1":
            list_moments()
        elif choice == "2":
            interactive_add()
        elif choice == "3":
            interactive_delete()
        elif choice == "4":
            interactive_update()
        else:
            print("无效选择，请重输。")


# ----------------------------------------------------------------------------
# 命令行入口
# ----------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(
        description="b_moments 统一管理：添加 / 删除 / 更新 moment（数据文件 _data/moments.yml，改完需 bundle exec jekyll build）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="无参数运行进入交互主菜单。",
    )
    sub = p.add_subparsers(dest="command")

    pa = sub.add_parser("add", help="添加 moment")
    pa.add_argument("--text", help="直接添加一条正文")
    pa.add_argument("--title")
    pa.add_argument("--date")
    pa.add_argument("--image")
    pa.add_argument("--video")
    pa.add_argument("--link")
    pa.add_argument("--inbox", default=ADD_INBOX_DEFAULT, help="收件箱文件路径（默认 _data/moments_inbox.txt）")
    pa.add_argument("-i", "--interactive", action="store_true", help="交互式逐字段输入")
    pa.add_argument("--tail", action="store_true", help="添加到文件末尾（默认最前面）")
    pa.add_argument("--dry-run", action="store_true", help="只预览，不写入")

    pd = sub.add_parser("delete", help="删除 moment")
    pd.add_argument("--index", type=int, help="删除页面显示为 #N 的那条（倒序）")
    pd.add_argument("--title")
    pd.add_argument("--date")
    pd.add_argument("--text")
    pd.add_argument("--inbox", default=DELETE_INBOX_DEFAULT, help="删除收件箱路径（默认 _data/moments_delete_inbox.txt）")
    pd.add_argument("-i", "--interactive", action="store_true", help="列出后输入 #N 删除")
    pd.add_argument("--dry-run", action="store_true", help="只预览，不写入")
    pd.add_argument("--no-backup", action="store_true", help="跳过自动备份 moments.yml.bak")

    pu = sub.add_parser("update", help="更新 / 编辑 moment")
    pu.add_argument("--index", type=int, required=True, help="要更新的条目（页面 #N，倒序）")
    pu.add_argument("--set-text", help="新正文（覆盖）")
    pu.add_argument("--set-title")
    pu.add_argument("--set-date")
    pu.add_argument("--set-image")
    pu.add_argument("--set-video")
    pu.add_argument("--set-link")
    pu.add_argument("--dry-run", action="store_true", help="只预览，不写入")

    pl = sub.add_parser("list", help="列出全部（带 #N）")

    ps = sub.add_parser("serve", help="启动本地写作后台（托管 _site/ + /api/moments 写接口 + 自动 jekyll build）")
    ps.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    ps.add_argument("--token", default=None, help="访问令牌（不填则随机生成并打印）")
    ps.add_argument("--no-build", action="store_true", help="保存后只写 YAML，不自动 jekyll build（配合 jekyll serve --watch 使用）")

    args = p.parse_args()

    if args.command is None:
        interactive_menu()
        return

    if args.command == "list":
        list_moments()
        return

    if args.command == "add":
        entries = []
        if args.interactive:
            text = normalize_text(input_multiline("正文（多行，单独一行 . 结束；直接回车 . 取消）："))
            if not text.strip():
                print("正文为空，已取消。")
                return
            fields = {}
            for key in ("title", "date", "image", "video", "link"):
                v = input(f"{key}（可选，回车跳过）: ").strip()
                if v:
                    fields[key] = v
            m = {"text": text}
            m.update(fields)
            entries.append(m)
        elif args.text is not None:
            m = {"text": args.text.strip()}
            for key in ("title", "date", "image", "video", "link"):
                v = getattr(args, key)
                if v:
                    m[key] = v
            entries.append(m)
        else:
            if not os.path.exists(args.inbox):
                print(f"收件箱不存在：{args.inbox}\n如需使用，请先创建并写入内容。")
                return
            entries = parse_inbox(args.inbox)
            if not entries:
                print("收件箱为空或无有效内容，未做任何改动。")
                return
        do_add(entries, not args.tail, args.dry_run,
                inbox_path=(None if (args.interactive or args.text is not None) else args.inbox),
                clear=(not (args.interactive or args.text is not None)))
        return

    if args.command == "delete":
        header, dicts = load()
        has_selector = any([args.index is not None, args.title, args.date, args.text, args.interactive])
        inbox_active = (not has_selector)
        if args.interactive:
            list_moments()
            ans = input("要删除第几条？（输入页面 #N，回车取消）: ").strip()
            if not ans.isdigit():
                print("已取消。")
                return
            args.index = int(ans)
        if inbox_active:
            if not os.path.exists(args.inbox):
                print(f"收件箱不存在：{args.inbox}\n如需使用，请先创建并写入目标。")
                return
            targets = parse_delete_inbox(args.inbox, dicts)
            if not targets:
                print("收件箱无有效目标，未做任何改动。")
                return
        else:
            targets = resolve_delete(args, dicts)
        do_delete(targets, dicts, header, args.dry_run, args.no_backup)
        if args.dry_run:
            return
        if inbox_active and not (args.interactive or args.index is not None):
            clear_delete_inbox(args.inbox)
            print("已清空收件箱。")
        return

    if args.command == "update":
        header, dicts = load()
        total = len(dicts)
        d = args.index
        if not (1 <= d <= total):
            print(f"[error] --index {d} 超出范围（共 {total} 条，页面 #1..#{total}）")
            sys.exit(1)
        pos = total - d
        sets = {}
        for key in ("text", "title", "date", "video", "image", "link"):
            v = getattr(args, "set_" + key)
            if v is not None:
                sets[key] = v
        if sets:
            do_update_cli(pos, dicts, header, sets, args.dry_run)
        else:
            do_update_interactive(pos, dicts, header, args.dry_run)
        return

    if args.command == "serve":
        serve(args)
        return


# ----------------------------------------------------------------------------
# 本地 HTTP 服务（serve 子命令）：托管 _site/ + /api/moments 写接口 + 自动重建
# 仅本机 127.0.0.1，绝不暴露公网；线上 GitHub Pages 静态站不受影响。
# ----------------------------------------------------------------------------
SITE_DIR = os.path.join(ROOT, "_site")
BUILD_CMD = ["bundle", "exec", "jekyll", "build"]
_serve_cfg = {"token": "", "do_build": True}


def run_build():
    """写接口后触发 jekyll 重建；失败仅记录，不阻断。"""
    if not _serve_cfg["do_build"]:
        return True
    try:
        r = subprocess.run(BUILD_CMD, cwd=ROOT, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            sys.stderr.write("[serve] jekyll build 失败：\n" + (r.stderr or r.stdout or "")[-2000:] + "\n")
            return False
        return True
    except Exception as e:
        sys.stderr.write(f"[serve] jekyll build 异常：{e}\n")
        return False


def _entry_to_json(d, disp):
    return {
        "index": disp,
        "text": d.get("text") or "",
        "title": d.get("title"),
        "date": d.get("date"),
        "video": d.get("video"),
        "image": d.get("image"),
        "link": d.get("link"),
    }


def _list_json():
    _, dicts = load()
    total = len(dicts)
    return [_entry_to_json(d, total - i) for i, d in enumerate(dicts)]


def _check_token(q):
    t = q.get("token", [""])[0]
    return t == _serve_cfg["token"]


def _send_json(handler, obj, code=200):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _serve_static(handler, path):
    if path in ("", "/"):
        path = "/index.html"
    rel = path.lstrip("/")
    full = os.path.normpath(os.path.join(SITE_DIR, rel))
    base = os.path.normpath(SITE_DIR)
    if not full.startswith(base):
        handler.send_error(404, "Not Found")
        return
    if not os.path.isfile(full):
        # 无扩展名的路径尝试补 .html（如 /b_moments）
        if not os.path.splitext(full)[1] and os.path.isfile(full + ".html"):
            full = full + ".html"
        else:
            handler.send_error(404, "Not Found")
            return
    try:
        with open(full, "rb") as f:
            data = f.read()
    except Exception:
        handler.send_error(404, "Not Found")
        return
    ext = os.path.splitext(full)[1].lower()
    mime = {
        ".html": "text/html; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".ico": "image/x-icon",
        ".woff2": "font/woff2",
        ".woff": "font/woff",
        ".ttf": "font/ttf",
        ".mp4": "video/mp4",
    }.get(ext, "application/octet-stream")
    handler.send_response(200)
    handler.send_header("Content-Type", mime)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _body_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/admin", "/admin/"):
            self.send_response(302)
            self.send_header("Location", f"/b_moments?admin={_serve_cfg['token']}")
            self.end_headers()
            return
        if u.path == "/api/moments":
            if not _check_token(q):
                _send_json(self, {"error": "unauthorized"}, 403)
                return
            _send_json(self, _list_json())
            return
        _serve_static(self, u.path)

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/moments/reorder":
            if not _check_token(q):
                _send_json(self, {"error": "unauthorized"}, 403)
                return
            data = self._body_json()
            order = data.get("order")
            header, dicts = load()
            res = do_reorder(order, dicts, header, False)
            if "error" in res:
                _send_json(self, res, 400)
                return
            ok = run_build()
            _send_json(self, {"ok": True, "build": ok, "total": res["total"]})
            return
        if u.path == "/api/moments":
            if not _check_token(q):
                _send_json(self, {"error": "unauthorized"}, 403)
                return
            data = self._body_json()
            m = {"text": normalize_text(str(data.get("text", "")))}
            if not m["text"].strip():
                _send_json(self, {"error": "text 不能为空"}, 400)
                return
            for key in ("title", "date", "image", "video", "link"):
                v = data.get(key)
                if v not in (None, ""):
                    m[key] = str(v).strip()
            prepend = str(data.get("prepend", "true")).lower() not in ("0", "false", "no")
            do_add([m], prepend, False, inbox_path=None, clear=False)
            ok = run_build()
            _, dicts = load()
            _send_json(self, {"ok": True, "build": ok, "total": len(dicts),
                                "admin": f"/b_moments?admin={_serve_cfg['token']}"})
            return
        self.send_error(404)

    def do_PUT(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        m = re.match(r"^/api/moments/(\d+)$", u.path)
        if m:
            if not _check_token(q):
                _send_json(self, {"error": "unauthorized"}, 403)
                return
            n = int(m.group(1))
            header, dicts = load()
            total = len(dicts)
            if not (1 <= n <= total):
                _send_json(self, {"error": f"index {n} 超出范围（共 {total}）"}, 400)
                return
            pos = total - n
            data = self._body_json()
            sets = {}
            for key in ("text", "title", "date", "video", "image", "link"):
                if key in data and data[key] is not None:
                    sets[key] = str(data[key])
            do_update_cli(pos, dicts, header, sets, False)
            ok = run_build()
            _send_json(self, {"ok": True, "build": ok, "index": n})
            return
        self.send_error(404)

    def do_DELETE(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        m = re.match(r"^/api/moments/(\d+)$", u.path)
        if m:
            if not _check_token(q):
                _send_json(self, {"error": "unauthorized"}, 403)
                return
            n = int(m.group(1))
            header, dicts = load()
            total = len(dicts)
            if not (1 <= n <= total):
                _send_json(self, {"error": f"index {n} 超出范围（共 {total}）"}, 400)
                return
            pos = total - n
            do_delete({pos}, dicts, header, False, False)
            ok = run_build()
            _send_json(self, {"ok": True, "build": ok, "index": n})
            return
        self.send_error(404)


def serve(args):
    import secrets
    token = args.token or secrets.token_hex(8)
    _serve_cfg["token"] = token
    _serve_cfg["do_build"] = not args.no_build
    port = args.port or 8000
    print("=" * 52)
    print("  b_moments 本地写作后台已启动（仅本机 127.0.0.1）")
    if not os.path.isdir(SITE_DIR):
        print("  ⚠️ 未检测到 _site/ 目录！请先在本仓库根目录运行：")
        print("       bundle exec jekyll build")
        print("     否则打开页面会 404。后台仍会启动，但静态资源需要 build 后才存在。")
    print(f"  管理页面： http://127.0.0.1:{port}/b_moments?admin={token}")
    print(f"  或者：     http://127.0.0.1:{port}/admin")
    print(f"  Token： {token}   （写接口与 /api 均需 ?token=...）")
    if _serve_cfg["do_build"]:
        print("  保存后将自动 jekyll build 重建（约十几秒）")
    else:
        print("  --no-build：保存只写 YAML，不自动 build（请另行 jekyll serve --watch）")
    print("  按 Ctrl-C 停止。")
    print("=" * 52)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
        httpd.server_close()


if __name__ == "__main__":
    main()
