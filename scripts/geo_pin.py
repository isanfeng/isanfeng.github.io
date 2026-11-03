#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
geo_pin.py — 生成文章地理锚点 <span> 片段，复制粘贴进 .md 正文即可。

用法：
  python3 scripts/geo_pin.py --name 上海 --lat 31.23 --lng 121.49 [--id loc-shanghai] [--country 中国]

输出示例：
  <span class="geo-pin" id="loc-shanghai" data-lat="31.23" data-lng="121.49">上海</span>

说明：
  --id 省略时自动取 loc-<name>；中文 id 合法，浏览器可直接用作 url 片段（#loc-上海）。
  建议显式给一个稳定 id（如 loc-shanghai），它同时是地图上的回跳锚点与 upsert 主键，
  文中插入新锚点时不会让后面所有点的序号错位。
"""

import argparse


def main():
    p = argparse.ArgumentParser(description="生成 geo-pin 锚点 <span> 片段")
    p.add_argument("--name", required=True, help="地点名称（span 内文）")
    p.add_argument("--lat", required=True, help="纬度（数字）")
    p.add_argument("--lng", required=True, help="经度（数字）")
    p.add_argument("--id", default=None, help="锚点 id（默认 loc-<name>），亦是地图回跳片段")
    p.add_argument("--country", default=None, help="强制国家（覆盖离线派生）")
    args = p.parse_args()

    pid = args.id or ("loc-" + args.name)
    s = f'<span class="geo-pin" id="{pid}" data-lat="{args.lat}" data-lng="{args.lng}"'
    if args.country:
        s += f' data-country="{args.country}"'
    s += f'>{args.name}</span>'
    print(s)


if __name__ == "__main__":
    main()
