#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travel_markers.yml 便捷维护脚本（无需关心 YAML 格式）

三种用法：
  1) 收件箱模式（推荐，最省心）：
     在 _data/travel_markers_inbox.txt 里直接写内容——每条之间用空行分隔，
     每条用 :: 前缀标注字段（经纬度必填）：
        ::title 上海
        ::lat 31.40527
        ::lng 121.48941
        ::url https://j.map.baidu.com/06/-yd

        （空行分隔下一条）
        ::title 草原天路
        ::lat 41.390615
        ::lng 115.787123

     命令：python3 scripts/add_marker.py

  2) 命令行直接加一条：
      python3 scripts/add_marker.py --title 上海 --lat 31.40527 --lng 121.48941 --url https://...

  3) 交互式：
      python3 scripts/add_marker.py -i

其它：
  --dry-run      只打印将要添加的内容，不写文件（安全预览）
  --inbox PATH   指定其它收件箱文件（默认 _data/travel_markers_inbox.txt）
  --list         仅打印 travel_markers.yml 当前条数
  --tail         添加到文件末尾（默认添加到最前面，最新的在最上方）

说明：默认添加到最前面（最新在最上方）；prepend 会整体重写文件，但会完整保留原有注释与历史条目。
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKERS_YML = os.path.join(ROOT, "_data", "travel_markers.yml")
INBOX_DEFAULT = os.path.join(ROOT, "_data", "travel_markers_inbox.txt")

# 收件箱里 :: 前缀 -> 数据字段 的映射
META_KEYS = {
    "title": "title",
    "lat": "latitude",
    "latitude": "latitude",
    "lng": "longitude",
    "longitude": "longitude",
    "url": "url",
    "country": "country",
}

HEADER = (
    "# a_travel-map 数据文件（页面数据 / 代码分离）\n"
    "# 维护：运行 python3 scripts/add_marker.py\n"
    "#   收件箱模式：在 _data/travel_markers_inbox.txt 写内容，每条之间空一行；\n"
    "#     用 ::title / ::lat / ::lng / ::url / ::country 前缀标注字段，例如：\n"
    "#       ::title 上海\n#       ::lat 31.40527\n#       ::lng 121.48941\n#       ::country 中国\n#       ::url https://...\n"
    "#   命令行：python3 scripts/add_marker.py --title 上海 --lat 31.4 --lng 121.4 [--country 中国] [--url ...]\n"
    "#   交互式：python3 scripts/add_marker.py -i\n"
    "# 字段：title 名称；latitude/longitude 经纬度(数字)；country 所属国家(用于按国家着色，可选)；url 可选点击跳转\n"
)


def yaml_str(value):
    """单行字段用双引号包裹并转义，确保任何内容都能安全写入。"""
    s = str(value)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + s + '"'


def to_float(value, field):
    try:
        return float(value)
    except (ValueError, TypeError):
        sys.exit(f"[error] {field} 必须是数字，收到：{value!r}")


def parse_inbox(path):
    """解析收件箱文本 -> 若干 marker 字典列表。"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 用空行分隔每条 marker（连续空行视为一个分隔符）
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

    markers = []
    for blk in blocks:
        meta = {}
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
        # 必填字段校验
        if not meta.get("title"):
            sys.stderr.write("[skip] 跳过一条缺少 ::title 的内容\n")
            continue
        if not meta.get("latitude") or not meta.get("longitude"):
            sys.stderr.write(f"[skip] 跳过「{meta.get('title')}」：缺少 ::lat / ::lng\n")
            continue
        markers.append({
            "title": meta["title"],
            "latitude": to_float(meta["latitude"], "latitude"),
            "longitude": to_float(meta["longitude"], "longitude"),
            "url": meta.get("url") or None,
            "country": meta.get("country") or None,
        })
    return markers


def format_entry(m):
    """把一条 marker 格式化为正确的 YAML 片段。"""
    lines = [f"- title: {yaml_str(m['title'])}"]
    if m.get("country"):
        lines.append(f"  country: {yaml_str(m['country'])}")
    lines.append(f"  latitude: {m['latitude']}")
    lines.append(f"  longitude: {m['longitude']}")
    if m.get("url"):
        lines.append(f"  url: {yaml_str(m['url'])}")
    return "\n".join(lines)


def build_block(entries):
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
    """写入 marker。prepend=True 加在文件最前面（默认），否则加在最后面。
    注意：prepend 会整体重写文件，但会完整保留原有注释与历史条目。"""
    block = build_block(entries)

    if dry_run:
        where = "最前面" if prepend else "最后面"
        print(f"==== 将要添加（{where}）到 travel_markers.yml 的内容 ====")
        print(block)
        print("==== 结束 ====")
        return

    existed = os.path.exists(MARKERS_YML)
    if not existed:
        with open(MARKERS_YML, "w", encoding="utf-8") as f:
            f.write(HEADER)
            if not HEADER.endswith("\n"):
                f.write("\n")
            f.write(block + "\n")
        return

    header, rest = read_split(MARKERS_YML)
    while header and header[-1].strip() == "":
        header.pop()
    while rest and rest[0].strip() == "":
        rest.pop(0)

    parts = []
    if header:
        parts.append("\n".join(header))
    if prepend:
        if parts:
            parts.append("")
        parts.append(block)
        if rest:
            parts.append("")
            parts.append("\n".join(rest))
    else:
        if rest:
            parts.append("\n".join(rest))
            parts.append("")
        parts.append(block)

    new_content = "\n".join(parts)
    if not new_content.endswith("\n"):
        new_content += "\n"
    with open(MARKERS_YML, "w", encoding="utf-8") as f:
        f.write(new_content)


def clear_inbox(path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(HEADER)


def count_markers():
    if not os.path.exists(MARKERS_YML):
        return 0
    n = 0
    with open(MARKERS_YML, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("- title:"):
                n += 1
    return n


def main():
    p = argparse.ArgumentParser(description="便捷维护 travel_markers.yml（无需手写 YAML 格式）")
    p.add_argument("--title", help="地点名称")
    p.add_argument("--lat", "--latitude", dest="lat", help="纬度（数字）")
    p.add_argument("--lng", "--longitude", dest="lng", help="经度（数字）")
    p.add_argument("--url", help="点击跳转链接（可选）")
    p.add_argument("--country", help="所属国家/地区（可选，用于按国家着色）")
    p.add_argument("-i", "--interactive", action="store_true", help="交互式逐字段输入")
    p.add_argument("--tail", action="store_true", help="添加到文件末尾（默认添加到最前面）")
    p.add_argument("--dry-run", action="store_true", help="只预览，不写入")
    p.add_argument("--inbox", default=INBOX_DEFAULT, help="收件箱文件路径")
    p.add_argument("--list", action="store_true", help="仅打印当前条数")
    args = p.parse_args()

    if args.list:
        print(f"travel_markers.yml 当前共有 {count_markers()} 个标记点")
        return

    entries = []

    if args.interactive:
        title = input("地点名称 title: ").strip()
        if not title:
            print("title 为空，已取消。")
            return
        lat = input("纬度 latitude: ").strip()
        lng = input("经度 longitude: ").strip()
        url = input("跳转链接 url（可选，回车跳过）: ").strip()
        country = input("国家 country（可选，回车跳过）: ").strip()
        entries.append({
            "title": title,
            "latitude": to_float(lat, "latitude"),
            "longitude": to_float(lng, "longitude"),
            "url": url or None,
            "country": country or None,
        })
    elif args.title is not None or args.lat is not None or args.lng is not None:
        if not (args.title and args.lat and args.lng):
            sys.exit("[error] 命令行模式需同时提供 --title --lat --lng")
        entries.append({
            "title": args.title.strip(),
            "latitude": to_float(args.lat, "latitude"),
            "longitude": to_float(args.lng, "longitude"),
            "url": (args.url.strip() if args.url else None),
            "country": (args.country.strip() if args.country else None),
        })
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
    if not (args.interactive or args.title is not None):
        clear_inbox(args.inbox)
        print(f"已在{where}添加 {len(entries)} 个标记点，并清空收件箱。")
    else:
        print(f"已在{where}添加 {len(entries)} 个标记点。")


if __name__ == "__main__":
    main()
