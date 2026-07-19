#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
moments.yml 便捷维护脚本（无需关心 YAML 格式）

三种用法：
  1) 收件箱模式（推荐，最省心）：
     在 _data/moments_inbox.txt 里直接写内容——每条之间用空行分隔，
     需要元数据就加一行 `::` 前缀。写完跑本脚本即可自动添加到最前面并清空收件箱。
        ::title 一点感悟
        ::date 2026-07-19
        ::image /images/x.jpg
        ::video https://player.bilibili.com/...
        ::link  https://...
        正文第一行
        正文第二行

        （空行分隔下一条）
        又一段纯文字，啥前缀都不用加

     命令：python3 scripts/add_moment.py

  2) 命令行直接加一条：
      python3 scripts/add_moment.py --text "今天心情不错" --title "随手记" --date 2026-07-19

  3) 交互式：
      python3 scripts/add_moment.py -i

其它：
  --dry-run      只打印将要添加的内容，不写文件（安全预览）
  --inbox PATH   指定其它收件箱文件（默认 _data/moments_inbox.txt）
  --list         仅打印 moments.yml 当前条数
  --tail         添加到文件末尾（默认添加到最前面，最新的在最上方）

说明：默认添加到最前面（最新在最上方）；prepend 会整体重写文件，但会完整保留原有注释与历史条目。
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOMENTS_YML = os.path.join(ROOT, "_data", "moments.yml")
INBOX_DEFAULT = os.path.join(ROOT, "_data", "moments_inbox.txt")

# 收件箱里 :: 前缀 -> 数据字段 的映射
META_KEYS = {
    "title": "title",
    "date": "date",
    "image": "image",
    "video": "video",
    "link": "link",
}

HEADER = "# b_moments 数据文件（页面数据 / 代码分离）\n" \
         "# 维护：在 _data/moments_inbox.txt 里直接写内容，每条之间空一行；\n" \
         "#   需要标题/日期/图/视频/链接时，在对应条目前加一行 :: 前缀，例如：\n" \
         "#     ::title 标题\n#     ::date 2026-07-19\n#     ::image /images/x.jpg\n" \
         "#     ::video https://...   ::link https://...\n" \
         "#   然后运行 python3 scripts/add_moment.py 即可自动追加并清空本文件。\n"


def yaml_str(value):
    """单行字段用双引号包裹并转义，确保任何内容都能安全写入。"""
    s = str(value)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + s + '"'


def normalize_text(block):
    """去掉首尾空行，去掉每行行尾空白，保留内部换行。"""
    lines = [ln.rstrip() for ln in block.split("\n")]
    while lines and lines[0].strip() == "":
        lines.pop(0)
    while lines and lines[-1].strip() == "":
        lines.pop()
    return "\n".join(lines)


def parse_inbox(path):
    """解析收件箱文本 -> 若干 moment 字典列表。"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 用空行分隔每条 moment（连续空行视为一个分隔符）
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
                    sys.stderr.write(f"[warn] 忽略未知 ::{key}，仅支持 {list(META_KEYS)} \n")
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


def format_entry(m):
    """把一条 moment 格式化为正确的 YAML 片段。"""
    lines = ["- text: |-"]
    for ln in m["text"].split("\n"):
        lines.append("    " + ln)  # 块标量内容缩进 4 空格
    for key in ("title", "date", "image", "video", "link"):
        v = m.get(key)
        if v:
            lines.append(f"  {key}: {yaml_str(v)}")  # 同层字段缩进 2 空格
    return "\n".join(lines)


def build_block(entries):
    """把若干 moment 拼成 YAML 片段（条目间空一行）。"""
    return "\n\n".join(format_entry(e) for e in entries)


def read_split(path):
    """把文件拆成 (头部注释行列表, 数据条目行列表)。"""
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    i = 0
    while i < len(lines) and (lines[i].startswith("#") or lines[i].strip() == ""):
        i += 1
    return lines[:i], lines[i:]


def write_entries(entries, dry_run, prepend):
    """写入 moment。prepend=True 加在文件最前面（默认），否则加在最后面。
    注意：prepend 会整体重写文件，但会完整保留原有注释与历史条目。"""
    block = build_block(entries)

    if dry_run:
        where = "最前面" if prepend else "最后面"
        print(f"==== 将要添加（{where}）到 moments.yml 的内容 ====")
        print(block)
        print("==== 结束 ====")
        return

    existed = os.path.exists(MOMENTS_YML)
    if not existed:
        # 新文件：写头部 + 条目
        with open(MOMENTS_YML, "w", encoding="utf-8") as f:
            f.write(HEADER)
            if not HEADER.endswith("\n"):
                f.write("\n")
            f.write(block + "\n")
        return

    header, rest = read_split(MOMENTS_YML)
    # 去掉头尾空行，干净拼接
    while header and header[-1].strip() == "":
        header.pop()
    while rest and rest[0].strip() == "":
        rest.pop(0)

    parts = []
    if header:
        parts.append("\n".join(header))
    if prepend:
        if parts:
            parts.append("")          # 头部与新条目间空一行
        parts.append(block)
        if rest:
            parts.append("")          # 新条目与旧条目间空一行
            parts.append("\n".join(rest))
    else:
        if rest:
            parts.append("\n".join(rest))
            parts.append("")          # 旧条目与新条目间空一行
        parts.append(block)

    new_content = "\n".join(parts)
    if not new_content.endswith("\n"):
        new_content += "\n"
    with open(MOMENTS_YML, "w", encoding="utf-8") as f:
        f.write(new_content)


def clear_inbox(path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(HEADER)


def count_moments():
    if not os.path.exists(MOMENTS_YML):
        return 0
    n = 0
    with open(MOMENTS_YML, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("- "):
                n += 1
    return n


def main():
    p = argparse.ArgumentParser(description="便捷维护 moments.yml（无需手写 YAML 格式）")
    p.add_argument("--text", help="直接添加一条正文（配合下方元数据使用）")
    p.add_argument("--title", help="标题")
    p.add_argument("--date", help="日期")
    p.add_argument("--image", help="图片地址")
    p.add_argument("--video", help="视频地址")
    p.add_argument("--link", help="跳转链接")
    p.add_argument("-i", "--interactive", action="store_true", help="交互式逐字段输入")
    p.add_argument("--tail", action="store_true", help="添加到文件末尾（默认添加到最前面）")
    p.add_argument("--dry-run", action="store_true", help="只预览，不写入")
    p.add_argument("--inbox", default=INBOX_DEFAULT, help="收件箱文件路径")
    p.add_argument("--list", action="store_true", help="仅打印当前条数")
    args = p.parse_args()

    if args.list:
        print(f"moments.yml 当前共有 {count_moments()} 条 moment")
        return

    entries = []

    if args.interactive:
        text = input("正文（可多行，结束输入空行）:\n").strip()
        if not text:
            print("正文为空，已取消。")
            return
        m = {"text": text}
        for key in ("title", "date", "image", "video", "link"):
            v = input(f"{key}（可选，回车跳过）: ").strip()
            if v:
                m[key] = v
        entries.append(m)
    elif args.text is not None:
        m = {"text": args.text.strip()}
        for key in ("title", "date", "image", "video", "link"):
            v = getattr(args, key)
            if v:
                m[key] = v
        entries.append(m)
    else:
        # 收件箱模式
        if not os.path.exists(args.inbox):
            print(f"收件箱不存在：{args.inbox}\n如需使用，请先创建该文件并写入内容。")
            return
        entries = parse_inbox(args.inbox)
        if not entries:
            print("收件箱为空或无有效内容，未做任何改动。")
            return

    prepend = not args.tail
    write_entries(entries, args.dry_run, prepend)

    if args.dry_run:
        return

    where = "最前面" if prepend else "最后面"
    if not (args.interactive or args.text is not None):
        # 收件箱模式：添加成功后清空
        clear_inbox(args.inbox)
        print(f"已在{where}添加 {len(entries)} 条 moment，并清空收件箱。")
    else:
        print(f"已在{where}添加 {len(entries)} 条 moment。")


if __name__ == "__main__":
    main()
