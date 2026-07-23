#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
a_travel-map 统一管理脚本（添加 / 删除 / 更新 三合一，无需手写 YAML）

页面（a_travel-map，地图）按 _data/travel_markers.yml 的文件顺序渲染标注点，
这里每条 marker 的索引 #N = 文件第 N 条（从上到下，#1 在第一条 = 最新置顶）。
看到想改/删的那条是 #42，直接选「更新/删除」并输入 42 即可（与文件顺序一致）。

运行方式：
  1) 交互主菜单（推荐，最省心）：
        python3 scripts/travel_map.py
     启动后按提示选择：1)列出 2)添加 3)删除 4)更新 q)退出。

  2) 命令行直接操作（适合脚本/自动化）：
        python3 scripts/travel_map.py add --title 上海 --lat 31.40527 --lng 121.48941 --country 中国 --url https://...
        python3 scripts/travel_map.py add --inbox _data/travel_markers_inbox.txt
        python3 scripts/travel_map.py delete --index 42
        python3 scripts/travel_map.py delete --title 上海
        python3 scripts/travel_map.py update --index 42 --set-title 新名 --set-lat 31.4 --set-lng 121.4
        python3 scripts/travel_map.py update --index 42        # 不带 --set-* 则进入该条目的交互编辑
        python3 scripts/travel_map.py list

  3) 收件箱模式（添加/删除均支持）：
        添加：在 _data/travel_markers_inbox.txt 里写内容（每条空行分隔，::title/::lat/::lng/::url/::country 前缀），
              跑 python3 scripts/travel_map.py add --inbox _data/travel_markers_inbox.txt 即追加并清空收件箱。
        删除：在 _data/travel_markers_delete_inbox.txt 每行写一个目标（数字序号或 ::title/::country/::url），
              跑 python3 scripts/travel_map.py delete --inbox _data/travel_markers_delete_inbox.txt 即删除并清空。

  4) 本地写作后台（页面内直接增删改，最直观，零依赖）：
        # 第一步：必须先生成 _site（后台就是托管这个目录）
        bundle exec jekyll build
        # 第二步：启动本地后台（托管 _site/ + /api/markers 写接口，保存后自动 build）
        python3 scripts/travel_map.py serve
     启动后终端会打印地址（默认 http://127.0.0.1:8000/admin，已自动带 token，直接点即可）。
     打开后：页面顶部出现添加表单，右侧出现 marker 列表（每条带「编辑 / 删除」按钮）；
     新增/修改/删除后后台自动 bundle exec jekyll build（约十余秒）并刷新页面。
       - 仅监听 127.0.0.1 + 随机 token，线上 GitHub Pages 没有这个后端、也拿不到 token，
         管理 UI 永远不激活，对外发布的静态站完全不受影响（安全）。
       - 若已用 jekyll serve --watch 常驻，可加 --no-build 让保存只写 YAML、由 watch 自动重建。
       - 端口可改：--port 8080；token 可固定：--token xxxxx（固定后注意别泄露）。

其它通用参数：
  --dry-run    只打印将要写入的内容，不写文件（安全预览）
  --no-backup  删除时跳过自动备份 travel_markers.yml.bak（默认删除前会备份）

说明：a_travel-map 是静态站，没有后端。所有增删改 = 修改 _data/travel_markers.yml 数据文件，
然后 bundle exec jekyll build 重新生成页面并部署。索引编号与文件顺序完全一致（从上到下）。
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
MARKERS_YML = os.path.join(ROOT, "_data", "travel_markers.yml")
ADD_INBOX_DEFAULT = os.path.join(ROOT, "_data", "travel_markers_inbox.txt")
DELETE_INBOX_DEFAULT = os.path.join(ROOT, "_data", "travel_markers_delete_inbox.txt")

# 收件箱里 :: 前缀 -> 数据字段 的映射（添加）
META_KEYS = {
    "title": "title",
    "lat": "latitude",
    "latitude": "latitude",
    "lng": "longitude",
    "longitude": "longitude",
    "url": "url",
    "country": "country",
}

ADD_INBOX_TEMPLATE = (
    "# a_travel-map 收件箱（维护 travel_markers.yml 用）\n"
    "#\n"
    "# 用法：每条标记点之间用空行分隔，每条用 :: 前缀标注字段：\n"
    "#   ::title 地点名称（必填）\n"
    "#   ::lat   纬度（必填，数字）\n"
    "#   ::lng   经度（必填，数字）\n"
    "#   ::url     点击跳转链接（可选）\n"
    "#   ::country 所属国家/地区（可选，用于按国家着色；如 中国 / 日本 / 泰国）\n"
    "#\n"
    "# 写完运行：python3 scripts/travel_map.py add\n"
    "# 即可自动添加到最前面（最新置顶）并清空本文件。\n"
    "# 也可：--title/--lat/--lng/--url/--country 命令行直加，或 add -i 交互式。\n"
    "# 预览不落盘：python3 scripts/travel_map.py add --dry-run\n"
    "# 查条数：python3 scripts/travel_map.py list\n"
    "#\n"
    "# 示例（删除示例后即可写入你自己的内容）：\n"
    "# ::title 草原天路\n# ::lat 41.390615\n# ::lng 115.787123\n# ::country 中国\n"
)

DELETE_INBOX_TEMPLATE = (
    "# 在此写入要删除的 marker 目标，每行一个：\n"
    "#   42                删第 42 条（文件顺序，从上到下）\n"
    "#   ::title 上海       删标题为「上海」的第一条\n"
    "#   ::country 中国     删国家为「中国」的第一条\n"
    "#   ::url https://...  删 url 为指定值的第一个\n"
    "#   跑 python3 scripts/travel_map.py delete 后本文件会被清空。\n"
)

HEADER = (
    "# a_travel-map 数据文件（页面数据 / 代码分离）\n"
    "# 维护：运行 python3 scripts/travel_map.py（add/delete/update/list/serve 合一）\n"
    "#   收件箱模式：在 _data/travel_markers_inbox.txt 写内容，每条之间空一行；\n"
    "#     用 ::title / ::lat / ::lng / ::url / ::country 前缀标注字段，例如：\n"
    "#       ::title 上海\n#       ::lat 31.40527\n#       ::lng 121.48941\n#       ::country 中国\n#       ::url https://...\n"
    "#   命令行：python3 scripts/travel_map.py add --title 上海 --lat 31.4 --lng 121.4 [--country 中国] [--url ...]\n"
    "#   交互式：python3 scripts/travel_map.py add -i\n"
    "# 字段：title 名称（必填）；latitude/longitude 经纬度(数字，必填)；country 所属国家(用于按国家着色，可选)；url 可选点击跳转\n"
)


# ----------------------------------------------------------------------------
# YAML 辅助：与既有格式严格一致（- title: "..." + 2 空格单行字段，双引号转义；经纬度数字）
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


def to_float(value, field):
    try:
        return float(value)
    except (ValueError, TypeError):
        sys.exit(f"[error] {field} 必须是数字，收到：{value!r}")


def format_entry(m):
    """把一条 marker 字典格式化为正确的 YAML 片段。"""
    lines = [f"- title: {yaml_str(m['title'])}"]
    if m.get("country"):
        lines.append(f"  country: {yaml_str(m['country'])}")
    lines.append(f"  latitude: {m['latitude']}")
    lines.append(f"  longitude: {m['longitude']}")
    if m.get("url"):
        lines.append(f"  url: {yaml_str(m['url'])}")
    return "\n".join(lines)


def build_block(dicts):
    """把若干 marker 拼成 YAML 片段（条目间空一行）。"""
    return "\n\n".join(format_entry(d) for d in dicts)


# ----------------------------------------------------------------------------
# 读取 / 解析
# ----------------------------------------------------------------------------
def load():
    """读取文件，返回 (头部注释行列表, 全部 marker 字典列表)。文件不存在返回 ([], [])。"""
    if not os.path.exists(MARKERS_YML):
        return [], []
    with open(MARKERS_YML, encoding="utf-8") as f:
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
    """把一条 marker 的原始行块解析为字典（title/country/latitude/longitude/url）。"""
    d = {k: None for k in ("title", "country", "latitude", "longitude", "url")}
    for ln in block:
        m = re.match(r'^\s*-?\s*title:\s*"(.*)"\s*$', ln)
        if m:
            d["title"] = unyaml_str(m.group(1))
            continue
        m = re.match(r'^\s*country:\s*"(.*)"\s*$', ln)
        if m:
            d["country"] = unyaml_str(m.group(1))
            continue
        m = re.match(r'^\s*latitude:\s*([-\d.eE]+)', ln)
        if m:
            try:
                d["latitude"] = float(m.group(1))
            except ValueError:
                pass
            continue
        m = re.match(r'^\s*longitude:\s*([-\d.eE]+)', ln)
        if m:
            try:
                d["longitude"] = float(m.group(1))
            except ValueError:
                pass
            continue
        m = re.match(r'^\s*url:\s*"(.*)"\s*$', ln)
        if m:
            d["url"] = unyaml_str(m.group(1))
            continue
    return d


def parse_inbox(path):
    """解析添加收件箱文本 -> 若干 marker 字典列表。"""
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
        if not meta.get("title"):
            sys.stderr.write("[skip] 跳过一条缺少 ::title 的内容\n")
            continue
        if not meta.get("latitude") or not meta.get("longitude"):
            sys.stderr.write(f"[skip] 跳过「{meta.get('title')}」：缺少 ::lat / ::lng\n")
            continue
        markers.append({
            "title": meta["title"],
            "country": meta.get("country") or None,
            "latitude": to_float(meta["latitude"], "latitude"),
            "longitude": to_float(meta["longitude"], "longitude"),
            "url": meta.get("url") or None,
        })
    return markers


def parse_delete_inbox(path, dicts):
    """解析删除收件箱 -> 文件位置集合（0 基）。数字 N = 文件第 N 条（从上到下）。"""
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
            if key in ("title", "country", "url"):
                hs = [i for i, d in enumerate(dicts) if d.get(key) == val]
                if hs:
                    hits.add(hs[0])
                else:
                    sys.stderr.write(f"[warn] 收件箱目标 ::{key} {val} 未匹配到，跳过\n")
            else:
                sys.stderr.write(f"[warn] 忽略未知 ::{key}（支持 title/country/url 或纯数字序号）\n")
        elif raw.isdigit():
            n = int(raw)
            if 1 <= n <= total:
                hits.add(n - 1)  # 文件位置（0 基）
            else:
                sys.stderr.write(f"[warn] 序号 {n} 超出范围（共 {total} 条，#1..#{total}），跳过\n")
        else:
            sys.stderr.write(f"[warn] 无法识别的行：「{raw}」，跳过（用数字序号或 :: 前缀）\n")
    return hits


# ----------------------------------------------------------------------------
# 写入
# ----------------------------------------------------------------------------
def write_full(header, dicts, dry_run, backup=False):
    """把 头部 + 全部条目 写回 travel_markers.yml。dry_run 只预览。"""
    if dry_run:
        print("==== 预览将写入 travel_markers.yml 的内容 ====")
        if header:
            print("\n".join(header))
            print("")
        print(build_block(dicts))
        print("==== 结束 ====")
        return
    if backup:
        bak = MARKERS_YML + ".bak"
        shutil.copy(MARKERS_YML, bak)
        print(f"已备份原文件到：{bak}")
    head = "\n".join(header).rstrip("\n")
    if head:
        content = head + "\n\n" + build_block(dicts) + "\n"
    else:
        content = build_block(dicts) + "\n"
    with open(MARKERS_YML, "w", encoding="utf-8") as f:
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
    head = d.get("title") or "(无标题)"
    extra = []
    if d.get("country"):
        extra.append(d["country"])
    if d.get("latitude") is not None:
        extra.append(f"{d['latitude']:.4f},{d['longitude']:.4f}")
    return (head + "  [" + ", ".join(extra) + "]") if extra else head


def list_markers():
    if not os.path.exists(MARKERS_YML):
        print("travel_markers.yml 不存在。")
        return
    header, dicts = load()
    total = len(dicts)
    print(f"travel_markers.yml 当前共有 {total} 个标记点（索引 #1 在第一条 = 文件最上方）：")
    for pos, d in enumerate(dicts):
        disp = pos + 1  # 文件顺序：第 pos 条（0 基）对应 #(pos+1)
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
    print(f"已在{where}添加 {len(entries_new)} 个标记点。")
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
        print(f"[warn] {label}「{val}」命中 {len(hits)} 条，仅删第 1 条（文件 # {hits[0] + 1}）")


def resolve_delete(args, dicts):
    """根据 --index/--title/--country/--url 解析要删除的文件位置集合（0 基）。"""
    targets = set()
    total = len(dicts)
    if args.index is not None:
        if 1 <= args.index <= total:
            targets.add(args.index - 1)  # 文件位置（0 基）= 索引-1
        else:
            print(f"[error] --index {args.index} 超出范围（共 {total} 条，#1..#{total}）")
            sys.exit(1)
    if args.title is not None:
        _add_first(targets, [i for i, d in enumerate(dicts) if d.get("title") == args.title], "title", args.title, total)
    if args.country is not None:
        _add_first(targets, [i for i, d in enumerate(dicts) if d.get("country") == args.country], "country", args.country, total)
    if args.url is not None:
        _add_first(targets, [i for i, d in enumerate(dicts) if d.get("url") == args.url], "url", args.url, total)
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
            print(f"--- 文件 #{i + 1} 条 ---")
            print(format_entry(dicts[i]))
            print()
        print("==== 以上为 --dry-run 预览，未写入文件 ====")
        return
    if not no_backup:
        bak = MARKERS_YML + ".bak"
        shutil.copy(MARKERS_YML, bak)
        print(f"已备份原文件到：{bak}")
    new_dicts = [d for i, d in enumerate(dicts) if i not in targets]
    write_full(header, new_dicts, dry_run=False)
    print(f"已删除 {len(targets)} 条：")
    for p in removed:
        print(f"  - {p}")
    print(f"删除后 travel_markers.yml 剩余 {len(new_dicts)} 条。")


# ----------------------------------------------------------------------------
# 更新 / 编辑
# ----------------------------------------------------------------------------
def do_update_interactive(pos, dicts, header, dry_run):
    total = len(dicts)
    d = dicts[pos]
    print(f"\n--- 当前文件 #{pos + 1} 条 ---")
    print(format_entry(d))
    print()
    title = input(f"title（当前：{d.get('title') or '无'}；回车=不变，输入 - 表示清空该字段）: ").strip()
    if title == "":
        pass
    elif title == "-":
        d["title"] = None
    else:
        d["title"] = title
    country = input(f"country（当前：{d.get('country') or '无'}；回车=不变，- =清空）: ").strip()
    if country == "":
        pass
    elif country == "-":
        d["country"] = None
    else:
        d["country"] = country
    lat = input(f"latitude（当前：{d.get('latitude')}；回车=不变）: ").strip()
    if lat != "":
        d["latitude"] = to_float(lat, "latitude")
    lng = input(f"longitude（当前：{d.get('longitude')}；回车=不变）: ").strip()
    if lng != "":
        d["longitude"] = to_float(lng, "longitude")
    url = input(f"url（当前：{d.get('url') or '无'}；回车=不变，- =清空）: ").strip()
    if url == "":
        pass
    elif url == "-":
        d["url"] = None
    else:
        d["url"] = url
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
    for key in ("title", "country", "latitude", "longitude", "url"):
        if key in sets:
            v = sets[key]
            if key in ("latitude", "longitude"):
                if v == "":
                    d[key] = None
                else:
                    d[key] = to_float(v, key)
            else:
                d[key] = v if v != "" else None  # 空字符串表示清空
    print(f"--- 更新后文件 #{pos + 1} 条 ---")
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
    title = input("title（地点名称，必填）: ").strip()
    if not title:
        print("title 为空，已取消。")
        return
    country = input("country（可选，回车跳过）: ").strip()
    lat = input("latitude（纬度，必填）: ").strip()
    lng = input("longitude（经度，必填）: ").strip()
    url = input("url（点击跳转链接，可选，回车跳过）: ").strip()
    if not lat or not lng:
        print("经纬度为必填，已取消。")
        return
    m = {
        "title": title,
        "country": country or None,
        "latitude": to_float(lat, "latitude"),
        "longitude": to_float(lng, "longitude"),
        "url": url or None,
    }
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
    list_markers()
    ans = input("\n要删除哪条？输入文件 #N（q 取消）: ").strip()
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
    pos = d - 1
    print(f"\n将删除文件 #{d} 条：")
    print(format_entry(dicts[pos]))
    confirm = input("确认删除？(Y/n): ").strip().lower()
    if confirm not in ("", "y", "yes"):
        print("已取消。")
        return
    do_delete({pos}, dicts, header, False, False)


def interactive_update():
    list_markers()
    ans = input("\n要更新哪条？输入文件 #N（q 取消）: ").strip()
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
    pos = d - 1
    do_update_interactive(pos, dicts, header, False)


def interactive_menu():
    while True:
        header, dicts = load()
        total = len(dicts)
        print("\n" + "=" * 42)
        print(f"  TRAVEL-MAP 管理控制台   当前共 {total} 个标记点")
        print("=" * 42)
        print("  1) 列出全部（带 #N 编号）")
        print("  2) 添加标记点")
        print("  3) 删除标记点")
        print("  4) 更新 / 编辑标记点")
        print("  q) 退出")
        choice = input("请选择: ").strip().lower()
        if choice in ("q", "quit", "exit", ""):
            print("再见。")
            break
        elif choice == "1":
            list_markers()
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
        description="a_travel-map 统一管理：添加 / 删除 / 更新 marker（数据文件 _data/travel_markers.yml，改完需 bundle exec jekyll build）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="无参数运行进入交互主菜单。",
    )
    sub = p.add_subparsers(dest="command")

    pa = sub.add_parser("add", help="添加 marker")
    pa.add_argument("--title", help="地点名称（必填）")
    pa.add_argument("--lat", "--latitude", dest="lat", help="纬度（数字，必填）")
    pa.add_argument("--lng", "--longitude", dest="lng", help="经度（数字，必填）")
    pa.add_argument("--url", help="点击跳转链接（可选）")
    pa.add_argument("--country", help="所属国家/地区（可选，用于按国家着色）")
    pa.add_argument("--inbox", default=ADD_INBOX_DEFAULT, help="收件箱文件路径（默认 _data/travel_markers_inbox.txt）")
    pa.add_argument("-i", "--interactive", action="store_true", help="交互式逐字段输入")
    pa.add_argument("--tail", action="store_true", help="添加到文件末尾（默认最前面）")
    pa.add_argument("--dry-run", action="store_true", help="只预览，不写入")

    pd = sub.add_parser("delete", help="删除 marker")
    pd.add_argument("--index", type=int, help="删除文件显示为 #N 的那条（从上到下）")
    pd.add_argument("--title")
    pd.add_argument("--country")
    pd.add_argument("--url")
    pd.add_argument("--inbox", default=DELETE_INBOX_DEFAULT, help="删除收件箱路径（默认 _data/travel_markers_delete_inbox.txt）")
    pd.add_argument("-i", "--interactive", action="store_true", help="列出后输入 #N 删除")
    pd.add_argument("--dry-run", action="store_true", help="只预览，不写入")
    pd.add_argument("--no-backup", action="store_true", help="跳过自动备份 travel_markers.yml.bak")

    pu = sub.add_parser("update", help="更新 / 编辑 marker")
    pu.add_argument("--index", type=int, required=True, help="要更新的条目（文件 #N，从上到下）")
    pu.add_argument("--set-title")
    pu.add_argument("--set-country")
    pu.add_argument("--set-lat", "--set-latitude", dest="set_lat", help="新纬度")
    pu.add_argument("--set-lng", "--set-longitude", dest="set_lng", help="新经度")
    pu.add_argument("--set-url")
    pu.add_argument("--dry-run", action="store_true", help="只预览，不写入")

    pl = sub.add_parser("list", help="列出全部（带 #N）")

    ps = sub.add_parser("serve", help="启动本地写作后台（托管 _site/ + /api/markers 写接口 + 自动 jekyll build）")
    ps.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    ps.add_argument("--token", default=None, help="访问令牌（不填则随机生成并打印）")
    ps.add_argument("--no-build", action="store_true", help="保存后只写 YAML，不自动 jekyll build（配合 jekyll serve --watch 使用）")

    args = p.parse_args()

    if args.command is None:
        interactive_menu()
        return

    if args.command == "list":
        list_markers()
        return

    if args.command == "add":
        entries = []
        if args.interactive:
            title = input("title（地点名称，必填）: ").strip()
            if not title:
                print("title 为空，已取消。")
                return
            country = input("country（可选，回车跳过）: ").strip()
            lat = input("latitude（纬度，必填）: ").strip()
            lng = input("longitude（经度，必填）: ").strip()
            url = input("url（可选，回车跳过）: ").strip()
            if not lat or not lng:
                print("经纬度为必填，已取消。")
                return
            entries.append({
                "title": title,
                "country": country or None,
                "latitude": to_float(lat, "latitude"),
                "longitude": to_float(lng, "longitude"),
                "url": url or None,
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
            if not os.path.exists(args.inbox):
                print(f"收件箱不存在：{args.inbox}\n如需使用，请先创建并写入内容。")
                return
            entries = parse_inbox(args.inbox)
            if not entries:
                print("收件箱为空或无有效内容，未做任何改动。")
                return
        do_add(entries, not args.tail, args.dry_run,
                inbox_path=(None if (args.interactive or args.title is not None) else args.inbox),
                clear=(not (args.interactive or args.title is not None)))
        return

    if args.command == "delete":
        header, dicts = load()
        has_selector = any([args.index is not None, args.title, args.country, args.url, args.interactive])
        inbox_active = (not has_selector)
        if args.interactive:
            list_markers()
            ans = input("要删除第几条？（输入文件 #N，回车取消）: ").strip()
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
            print(f"[error] --index {d} 超出范围（共 {total} 条，#1..#{total}）")
            sys.exit(1)
        pos = d - 1
        sets = {}
        for key in ("title", "country", "latitude", "longitude", "url"):
            if key in ("latitude", "longitude"):
                v = getattr(args, "set_" + ("lat" if key == "latitude" else "lng"))
            else:
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
# 本地 HTTP 服务（serve 子命令）：托管 _site/ + /api/markers 写接口 + 自动重建
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
        "title": d.get("title"),
        "country": d.get("country"),
        "latitude": d.get("latitude"),
        "longitude": d.get("longitude"),
        "url": d.get("url"),
    }


def _list_json():
    _, dicts = load()
    return [_entry_to_json(d, i + 1) for i, d in enumerate(dicts)]


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
        # 无扩展名的路径尝试补 .html（如 /a_travel-map）
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
            self.send_header("Location", f"/a_travel-map?admin={_serve_cfg['token']}")
            self.end_headers()
            return
        if u.path == "/api/markers":
            if not _check_token(q):
                _send_json(self, {"error": "unauthorized"}, 403)
                return
            _send_json(self, _list_json())
            return
        _serve_static(self, u.path)

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/markers":
            if not _check_token(q):
                _send_json(self, {"error": "unauthorized"}, 403)
                return
            data = self._body_json()
            title = str(data.get("title", "")).strip()
            if not title:
                _send_json(self, {"error": "title 不能为空"}, 400)
                return
            try:
                lat = float(data.get("latitude"))
                lng = float(data.get("longitude"))
            except (TypeError, ValueError):
                _send_json(self, {"error": "latitude / longitude 必须是数字"}, 400)
                return
            country = str(data.get("country") or "").strip() or None
            url = str(data.get("url") or "").strip() or None
            m = {"title": title, "country": country, "latitude": lat, "longitude": lng, "url": url}
            prepend = str(data.get("prepend", "true")).lower() not in ("0", "false", "no")
            do_add([m], prepend, False, inbox_path=None, clear=False)
            ok = run_build()
            _, dicts = load()
            _send_json(self, {"ok": True, "build": ok, "total": len(dicts),
                                "admin": f"/a_travel-map?admin={_serve_cfg['token']}"})
            return
        self.send_error(404)

    def do_PUT(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        m = re.match(r"^/api/markers/(\d+)$", u.path)
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
            pos = n - 1
            data = self._body_json()
            sets = {}
            for key in ("title", "country", "latitude", "longitude", "url"):
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
        m = re.match(r"^/api/markers/(\d+)$", u.path)
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
            pos = n - 1
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
    print("  a_travel-map 本地写作后台已启动（仅本机 127.0.0.1）")
    if not os.path.isdir(SITE_DIR):
        print("  ⚠️ 未检测到 _site/ 目录！请先在本仓库根目录运行：")
        print("       bundle exec jekyll build")
        print("     否则打开页面会 404。后台仍会启动，但静态资源需要 build 后才存在。")
    print(f"  管理页面： http://127.0.0.1:{port}/a_travel-map?admin={token}")
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
