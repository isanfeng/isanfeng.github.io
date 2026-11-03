#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/serve.py — moments + travel-map 统一本地写作后台。

合并原 moments.py / travel_map.py 各自的 serve 后台为单一服务：
  - 同时托管 /api/moments 与 /api/markers 读写接口
  - 新增 /api/publish：自动 jekyll build + git commit（本地，不 push）
  - 托管 _site/ 静态资源
仅监听 127.0.0.1 + 随机 token。线上 GitHub Pages 静态站无此后端、拿不到 token，管理 UI 不激活。

用法：
  bundle exec jekyll build          # 先生成 _site
  python3 scripts/serve.py          # 启动统一后台（默认端口 8000）
  # 兼容入口：python3 scripts/moments.py serve / python3 scripts/travel_map.py serve 也都会委托到这里
管理页面：
  moments： http://127.0.0.1:8000/moments?admin=TOKEN
  travel：  http://127.0.0.1:8000/travel-map?admin=TOKEN
发布：     前端「发布」按钮（Step 2 接入）或 curl -X POST "/api/publish?token=TOKEN"
"""

import argparse
import os
import re
import secrets
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import serve_common as sc
import moments
import travel_map

_serve_cfg = sc._serve_cfg


def _require_token(handler, q):
    if not sc.check_token(q):
        sc.send_json(handler, {"error": "unauthorized"}, 403)
        return False
    return True


def _moments_add(data):
    m = {"text": moments.normalize_text(str(data.get("text", "")))}
    if not m["text"].strip():
        return None, "text 不能为空"
    for key in ("title", "date", "image", "video", "link"):
        v = data.get(key)
        if v not in (None, ""):
            m[key] = str(v).strip()
    return m, None


def _markers_add(data):
    title = str(data.get("title", "")).strip()
    if not title:
        return None, "title 不能为空"
    try:
        lat = float(data.get("latitude"))
        lng = float(data.get("longitude"))
    except (TypeError, ValueError):
        return None, "latitude / longitude 必须是数字"
    country = str(data.get("country") or "").strip() or None
    url = str(data.get("url") or "").strip() or None
    return {"title": title, "country": country, "latitude": lat, "longitude": lng, "url": url}, None


def _moments_list():
    """读 moments.yml，返回前端 admin 用的列表（倒序：#total 最新在顶部）。"""
    _, dicts = moments.load()
    total = len(dicts)
    out = []
    for i, d in enumerate(dicts):
        out.append({
            "index": total - i,
            "text": d.get("text") or "",
            "title": d.get("title"),
            "date": d.get("date"),
            "video": d.get("video"),
            "image": d.get("image"),
            "link": d.get("link"),
        })
    return out


def _markers_list():
    """读 travel_markers.yml，返回前端 admin 用的列表（文件顺序：#1 在最上方）。"""
    _, dicts = travel_map.load()
    out = []
    for i, d in enumerate(dicts):
        out.append({
            "index": i + 1,
            "title": d.get("title"),
            "country": d.get("country"),
            "latitude": d.get("latitude"),
            "longitude": d.get("longitude"),
            "url": d.get("url"),
        })
    return out


class Handler(sc.BaseHandler):
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/admin", "/admin/"):
            if "admin" not in q:
                self.send_response(302)
                self.send_header("Location", f"/admin?admin={_serve_cfg['token']}")
                self.end_headers()
                return
            sc.serve_static(self, "/admin")
            return
        if u.path == "/api/moments":
            if not _require_token(self, q):
                return
            sc.send_json(self, _moments_list())
            return
        if u.path == "/api/markers":
            if not _require_token(self, q):
                return
            sc.send_json(self, _markers_list())
            return
        sc.serve_static(self, u.path)

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)

        # 发布：build + commit（本地，不 push）
        if u.path == "/api/publish":
            if not _require_token(self, q):
                return
            build_ok = sc.run_build()
            res = sc.run_commit()
            sc.send_json(self, {"ok": True, "build": build_ok,
                                "committed": res.get("committed", False),
                                "detail": res.get("detail", "")}, 200)
            return

        # moments 重排
        if u.path == "/api/moments/reorder":
            if not _require_token(self, q):
                return
            data = self.body_json()
            header, dicts = moments.load()
            r = moments.do_reorder(data.get("order"), dicts, header, False)
            if "error" in r:
                sc.send_json(self, r, 400)
                return
            ok = sc.run_build()
            sc.send_json(self, {"ok": True, "build": ok, "total": r["total"]})
            return

        # moments 新增
        if u.path == "/api/moments":
            if not _require_token(self, q):
                return
            data = self.body_json()
            m, err = _moments_add(data)
            if err:
                sc.send_json(self, {"error": err}, 400)
                return
            prepend = str(data.get("prepend", "true")).lower() not in ("0", "false", "no")
            moments.do_add([m], prepend, False, inbox_path=None, clear=False)
            ok = sc.run_build()
            _, dicts = moments.load()
            sc.send_json(self, {"ok": True, "build": ok, "total": len(dicts),
                                "admin": f"/moments?admin={_serve_cfg['token']}"})
            return

        # markers 新增
        if u.path == "/api/markers":
            if not _require_token(self, q):
                return
            data = self.body_json()
            m, err = _markers_add(data)
            if err:
                sc.send_json(self, {"error": err}, 400)
                return
            prepend = str(data.get("prepend", "true")).lower() not in ("0", "false", "no")
            travel_map.do_add([m], prepend, False, inbox_path=None, clear=False)
            ok = sc.run_build()
            _, dicts = travel_map.load()
            sc.send_json(self, {"ok": True, "build": ok, "total": len(dicts),
                                "admin": f"/travel-map?admin={_serve_cfg['token']}"})
            return

        self.send_error(404)

    def do_PUT(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)

        m = re.match(r"^/api/moments/(\d+)$", u.path)
        if m:
            if not _require_token(self, q):
                return
            n = int(m.group(1))
            header, dicts = moments.load()
            total = len(dicts)
            if not (1 <= n <= total):
                sc.send_json(self, {"error": f"index {n} 超出范围（共 {total}）"}, 400)
                return
            pos = total - n  # moments 倒序：页面 #N -> 文件第 (total-N) 条
            data = self.body_json()
            sets = {k: str(data[k]) for k in ("text", "title", "date", "video", "image", "link")
                    if k in data and data[k] is not None}
            moments.do_update_cli(pos, dicts, header, sets, False)
            ok = sc.run_build()
            sc.send_json(self, {"ok": True, "build": ok, "index": n})
            return

        m = re.match(r"^/api/markers/(\d+)$", u.path)
        if m:
            if not _require_token(self, q):
                return
            n = int(m.group(1))
            header, dicts = travel_map.load()
            total = len(dicts)
            if not (1 <= n <= total):
                sc.send_json(self, {"error": f"index {n} 超出范围（共 {total}）"}, 400)
                return
            pos = n - 1  # markers 文件顺序：#N -> 第 (N-1) 条
            data = self.body_json()
            sets = {k: str(data[k]) for k in ("title", "country", "latitude", "longitude", "url")
                    if k in data and data[k] is not None}
            travel_map.do_update_cli(pos, dicts, header, sets, False)
            ok = sc.run_build()
            sc.send_json(self, {"ok": True, "build": ok, "index": n})
            return

        self.send_error(404)

    def do_DELETE(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)

        m = re.match(r"^/api/moments/(\d+)$", u.path)
        if m:
            if not _require_token(self, q):
                return
            n = int(m.group(1))
            header, dicts = moments.load()
            total = len(dicts)
            if not (1 <= n <= total):
                sc.send_json(self, {"error": f"index {n} 超出范围（共 {total}）"}, 400)
                return
            pos = total - n
            moments.do_delete({pos}, dicts, header, False, False)
            ok = sc.run_build()
            sc.send_json(self, {"ok": True, "build": ok, "index": n})
            return

        m = re.match(r"^/api/markers/(\d+)$", u.path)
        if m:
            if not _require_token(self, q):
                return
            n = int(m.group(1))
            header, dicts = travel_map.load()
            total = len(dicts)
            if not (1 <= n <= total):
                sc.send_json(self, {"error": f"index {n} 超出范围（共 {total}）"}, 400)
                return
            pos = n - 1
            travel_map.do_delete({pos}, dicts, header, False, False)
            ok = sc.run_build()
            sc.send_json(self, {"ok": True, "build": ok, "index": n})
            return

        self.send_error(404)


def serve(args):
    token = getattr(args, "token", None) or secrets.token_hex(8)
    _serve_cfg["token"] = token
    _serve_cfg["do_build"] = not getattr(args, "no_build", False)
    _serve_cfg["do_commit"] = not getattr(args, "no_commit", False)
    port = getattr(args, "port", 8000) or 8000
    print("=" * 56)
    print("  统一本地写作后台已启动（仅本机 127.0.0.1）")
    if not os.path.isdir(sc.SITE_DIR):
        print("  ⚠️ 未检测到 _site/ 目录！请先在本仓库根目录运行：")
        print("       bundle exec jekyll build")
        print("     否则打开页面会 404。后台仍会启动，但静态资源需要 build 后才存在。")
    print(f"  moments 管理页： http://127.0.0.1:{port}/moments?admin={token}")
    print(f"  travel  管理页： http://127.0.0.1:{port}/travel-map?admin={token}")
    print(f"  Token： {token}   （/api/* 与 /admin 均需 ?token=...）")
    if _serve_cfg["do_build"]:
        print("  保存后将自动 jekyll build；/api/publish 会 build + git commit（不 push）")
    else:
        print("  --no-build：保存只写 YAML，不自动 build")
    if not _serve_cfg["do_commit"]:
        print("  --no-commit：/api/publish 只 build 不提交")
    print("  按 Ctrl-C 停止。")
    print("=" * 56)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    if not getattr(args, "no_open", False):
        admin_url = f"http://127.0.0.1:{port}/admin"
        # 延迟打开，等服务端 serve_forever 开始监听后再让浏览器连，避免连不上
        def _open_browser():
            try:
                webbrowser.open(admin_url)
            except Exception:
                pass  # 无图形环境（如沙箱）时静默跳过，不影响后台运行
        threading.Timer(0.8, _open_browser).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
        httpd.server_close()


def main():
    p = argparse.ArgumentParser(description="moments + travel-map 统一本地写作后台")
    p.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    p.add_argument("--token", default=None, help="访问令牌（不填则随机生成并打印）")
    p.add_argument("--no-build", action="store_true", help="保存后只写 YAML，不自动 jekyll build")
    p.add_argument("--no-commit", action="store_true", help="/api/publish 只 build 不 git commit")
    p.add_argument("--no-open", action="store_true", help="启动后不自动打开浏览器")
    args = p.parse_args()
    serve(args)


if __name__ == "__main__":
    main()
