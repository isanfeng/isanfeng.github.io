#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_post_markers.py — 把文章正文里的地理锚点同步到 travel_markers.yml

锚点写法（正文内联，读者可见 📍）：
  <span class="geo-pin" id="loc-shanghai" data-lat="31.23" data-lng="121.49">上海</span>

- 扫描 _posts/*.md（默认 --all，或 --post <slug> 只处理一篇）
- 提取每个 geo-pin 的 id / lat / lng / 名称 / 可选 data-country
- 计算文章永久链接（默认 /YYYY/MM/DD/<slug>/，front-matter `permalink: /xxx/` 可覆盖）
- 派生 marker：title=名称, latitude/longitude, url=<文章链接>#<id>,
  country=派生或 data-country 覆盖, source="post:<slug>:<id>"
- 全文为准 upsert：按 source 匹配——文中改→更新；文中删→删除；
  只动带 source 的派生点，手动加的点（无 source）永不动
- country 离线派生：内置国家包围盒表（点在内即命中，多个命中取面积最小），
  data-country 可覆盖；落在所有盒子外则 country 留空（地图走"未知"默认色）

用法：
  python3 scripts/sync_post_markers.py --all [--dry-run] [--commit] [--build]
  python3 scripts/sync_post_markers.py --post my-ride [--dry-run] [--commit] [--build]

  --dry-run   只预览将要写入的内容，不改动文件
  --commit    有改动则 `git add _data/travel_markers.yml` 并提交（不 push）
  --build     写完后 `bundle exec jekyll build`（仅 sanity check，失败不影响提交）
"""

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_DIR = os.path.join(ROOT, "_posts")
MARKERS_YML = os.path.join(ROOT, "_data", "travel_markers.yml")
GEO_PIN_RE = re.compile(r"<span\b([^>]*)>(.*?)</span>", re.S | re.I)

# 国家包围盒 [min_lat, min_lng, max_lat, max_lng]（度）。
# 命中多个时取面积最小（最具体）的那个；台湾坐标含在中国盒子内，统一标"中国"。
COUNTRY_BBOX = {
    "中国": [18.0, 73.0, 54.0, 135.0],
    "日本": [24.0, 122.0, 46.0, 146.0],
    "韩国": [33.0, 124.0, 132.0, 39.0],
    "朝鲜": [37.5, 125.5, 43.0, 130.5],
    "蒙古": [41.5, 87.5, 52.5, 120.0],
    "越南": [8.5, 102.0, 23.5, 110.0],
    "老挝": [13.5, 100.0, 22.5, 107.5],
    "缅甸": [9.5, 92.0, 28.5, 101.5],
    "泰国": [5.5, 97.0, 20.5, 106.0],
    "柬埔寨": [10.0, 102.0, 14.5, 108.0],
    "尼泊尔": [26.0, 80.0, 31.0, 89.0],
    "印度": [6.0, 68.0, 36.0, 98.0],
    "马来西亚": [0.5, 99.5, 7.5, 120.0],
    "新加坡": [1.2, 103.5, 1.5, 104.0],
    "印度尼西亚": [-11.0, 95.0, 6.0, 141.0],
    "菲律宾": [4.0, 116.0, 21.0, 127.0],
    "俄罗斯": [41.0, 27.0, 82.0, 180.0],
    "哈萨克斯坦": [40.0, 46.5, 56.0, 88.0],
    "美国": [19.0, -125.0, 49.0, -66.5],
    "加拿大": [41.0, -141.0, 84.0, -52.0],
    "墨西哥": [14.0, -118.0, 33.0, -86.0],
    "巴西": [-34.0, -74.0, 6.0, -34.0],
    "阿根廷": [-56.0, -74.0, -21.0, -53.0],
    "英国": [49.5, -8.5, 61.0, 2.0],
    "法国": [41.0, -5.0, 51.5, 10.0],
    "德国": [47.0, 5.5, 55.5, 15.5],
    "意大利": [35.5, 6.5, 47.5, 19.0],
    "西班牙": [35.5, -10.0, 44.0, 5.0],
    "葡萄牙": [36.5, -10.0, 43.0, -6.0],
    "荷兰": [50.5, 3.0, 54.0, 7.5],
    "瑞士": [45.5, 5.5, 48.0, 11.0],
    "奥地利": [46.0, 9.5, 49.5, 17.5],
    "澳大利亚": [-44.0, 112.0, -10.0, 154.0],
    "新西兰": [-47.5, 166.0, -34.0, 179.0],
    "埃及": [21.5, 24.5, 32.0, 35.0],
    "土耳其": [35.5, 25.5, 43.0, 45.0],
    "希腊": [34.5, 19.5, 41.5, 27.0],
}


# ----------------------------------------------------------------------------
# YAML 辅助（与 travel_map.py 既有格式严格一致）
# ----------------------------------------------------------------------------
def yaml_str(value):
    s = str(value)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + s + '"'


def unyaml_str(s):
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


def to_float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def derive_country(lat, lng):
    if lat is None or lng is None:
        return None
    hits = []
    for name, (mnlat, mnlng, mxlat, mxlng) in COUNTRY_BBOX.items():
        if mnlat <= lat <= mxlat and mnlng <= lng <= mxlng:
            area = (mxlat - mnlat) * (mxlng - mnlng)
            hits.append((area, name))
    if not hits:
        return None
    hits.sort()
    return hits[0][1]


# ----------------------------------------------------------------------------
# markers yml 读取 / 解析（含 source 字段）
# ----------------------------------------------------------------------------
def load_markers():
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
    dicts = [parse_block(b) for b in blocks]
    return header, dicts


def parse_block(block):
    d = {k: None for k in ("title", "country", "latitude", "longitude", "url", "source")}
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
            d["latitude"] = to_float(m.group(1))
            continue
        m = re.match(r'^\s*longitude:\s*([-\d.eE]+)', ln)
        if m:
            d["longitude"] = to_float(m.group(1))
            continue
        m = re.match(r'^\s*url:\s*"(.*)"\s*$', ln)
        if m:
            d["url"] = unyaml_str(m.group(1))
            continue
        m = re.match(r'^\s*source:\s*"(.*)"\s*$', ln)
        if m:
            d["source"] = unyaml_str(m.group(1))
            continue
    return d


def format_entry(m):
    lines = [f"- title: {yaml_str(m['title'])}"]
    if m.get("country"):
        lines.append(f"  country: {yaml_str(m['country'])}")
    lines.append(f"  latitude: {m['latitude']}")
    lines.append(f"  longitude: {m['longitude']}")
    if m.get("url"):
        lines.append(f"  url: {yaml_str(m['url'])}")
    if m.get("source"):
        lines.append(f"  source: {yaml_str(m['source'])}")
    return "\n".join(lines)


def write_markers(header, dicts, dry_run):
    if dry_run:
        print("==== 预览 travel_markers.yml（--dry-run，未写入）====")
        if header:
            print("\n".join(header))
            print("")
        print("\n\n".join(format_entry(d) for d in dicts))
        print("==== 结束 ====")
        return False
    head = "\n".join(header).rstrip("\n")
    content = (head + "\n\n" if head else "") + "\n\n".join(format_entry(d) for d in dicts) + "\n"
    with open(MARKERS_YML, "w", encoding="utf-8") as f:
        f.write(content)
    return True


# ----------------------------------------------------------------------------
# 文章扫描
# ----------------------------------------------------------------------------
def parse_front_matter(text):
    fm = {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return fm
    for line in m.group(1).split("\n"):
        km = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if km:
            key = km.group(1)
            val = km.group(2).strip().strip('"').strip("'")
            fm[key] = val
    return fm


def post_url(path, fm):
    base = os.path.basename(path)
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})-(.+)\.md$", base)
    if not m:
        return None
    y, mo, d, slug = m.group(1), m.group(2), m.group(3), m.group(4)
    perm = fm.get("permalink", "").strip()
    if perm.startswith("/"):
        base_url = perm.rstrip("/") + "/"
    else:
        base_url = f"/{y}/{mo}/{d}/{slug}/"
    return base_url, slug


def extract_anchors(text):
    anchors = []
    for tag, inner in GEO_PIN_RE.findall(text):
        if "geo-pin" not in tag:
            continue
        idm = re.search(r'\bid="([^"]*)"', tag)
        latm = re.search(r'\bdata-lat="([^"]*)"', tag)
        lngm = re.search(r'\bdata-lng="([^"]*)"', tag)
        ctrym = re.search(r'\bdata-country="([^"]*)"', tag)
        missing = []
        if not idm:
            missing.append("id")
        if not latm:
            missing.append("data-lat")
        if not lngm:
            missing.append("data-lng")
        if missing:
            sys.stderr.write(f"[skip] 锚点缺少 {', '.join(missing)}，已跳过：{tag[:60]}...\n")
            continue
        name = re.sub(r"<[^>]+>", "", inner).strip()
        lat = to_float(latm.group(1))
        lng = to_float(lngm.group(1))
        if lat is None or lng is None:
            sys.stderr.write(f"[skip] 锚点「{name}」经纬度无法解析，已跳过\n")
            continue
        anchors.append({
            "id": idm.group(1),
            "lat": lat,
            "lng": lng,
            "name": name,
            "country_override": ctrym.group(1) if ctrym else None,
        })
    return anchors


def collect_from_post(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    fm = parse_front_matter(text)
    res = post_url(path, fm)
    if not res:
        sys.stderr.write(f"[skip] 无法解析文章名（非 YYYY-MM-DD-slug.md）：{path}\n")
        return []
    base_url, slug = res
    anchors = extract_anchors(text)
    derived = []
    for a in anchors:
        country = a["country_override"] or derive_country(a["lat"], a["lng"])
        derived.append({
            "title": a["name"],
            "country": country,
            "latitude": a["lat"],
            "longitude": a["lng"],
            "url": f"{base_url}#{a['id']}",
            "source": f"post:{slug}:{a['id']}",
        })
    return derived


# ----------------------------------------------------------------------------
# 入口
# ----------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="把文章正文地理锚点同步到 travel_markers.yml")
    p.add_argument("--post", help="只同步某篇（slug，不含日期前缀）")
    p.add_argument("--all", action="store_true", help="同步全部 _posts（默认）")
    p.add_argument("--dry-run", action="store_true", help="只预览，不写文件")
    p.add_argument("--commit", action="store_true", help="有改动则 git add travel_markers.yml 并提交（不 push）")
    p.add_argument("--build", action="store_true", help="写完后 bundle exec jekyll build（仅 sanity check）")
    args = p.parse_args()

    if not args.all and not args.post:
        args.all = True

    targets = {args.post} if args.post else None

    header, dicts = load_markers()

    # 本次处理范围内、文中仍存在的派生 source 集合（用于删除过时点）
    scope_sources = set() if targets else None

    new_derived = []
    if not os.path.isdir(POSTS_DIR):
        sys.stderr.write(f"[warn] _posts 目录不存在：{POSTS_DIR}\n")
    else:
        for fn in sorted(os.listdir(POSTS_DIR)):
            if not fn.endswith(".md"):
                continue
            m = re.match(r"^\d{4}-\d{2}-\d{2}-(.+)\.md$", fn)
            if not m:
                continue
            slug = m.group(1)
            if targets and slug not in targets:
                continue
            got = collect_from_post(os.path.join(POSTS_DIR, fn))
            new_derived.extend(got)
            if scope_sources is not None:
                scope_sources.update(g["source"] for g in got)

    new_by_source = {x["source"]: x for x in new_derived}

    kept = []
    removed = []
    for entry in dicts:
        src = entry.get("source")
        in_scope = (scope_sources is None) or (src in scope_sources)
        if src and src.startswith("post:") and in_scope:
            if src in new_by_source:
                kept.append(new_by_source[src])  # 更新（替换）
            else:
                removed.append(entry)  # 文中已删 -> 移除
        else:
            kept.append(entry)  # 手动点 / 无 source -> 保留

    existing_sources = {e.get("source") for e in kept if e.get("source")}
    for x in new_derived:
        if x["source"] not in existing_sources:
            kept.append(x)

    if args.dry_run:
        write_markers(header, kept, True)
        return

    if kept == dicts:
        print("无变化，travel_markers.yml 保持不变。")
    else:
        write_markers(header, kept, False)
        print(f"已同步：处理 {len(new_derived)} 个派生点，移除 {len(removed)} 个过时派生点。")
        for r in removed:
            print(f"  - 移除（文中已删）：{r.get('title')} [{r.get('source')}]")

    if args.commit:
        rel = os.path.relpath(MARKERS_YML, ROOT)
        subprocess.run(["git", "add", rel], cwd=ROOT, check=False)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet", rel], cwd=ROOT)
        if diff.returncode != 0:
            subprocess.run(
                ["git", "commit", "-m", "chore(markers): 同步文章地理锚点到 travel_markers.yml"],
                cwd=ROOT, check=False,
            )
            print("已提交 travel_markers.yml（未 push，请在本机 push）。")
        else:
            print("无改动需要提交。")

    if args.build:
        print("运行 bundle exec jekyll build ...")
        subprocess.run(["bundle", "exec", "jekyll", "build"], cwd=ROOT, check=False)


if __name__ == "__main__":
    main()
