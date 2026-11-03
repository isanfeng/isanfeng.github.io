#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/serve_common.py — moments / travel-map 统一写作后台的共享 HTTP 原语。

被 scripts/serve.py 引用；包含：
  - 站点路径常量（ROOT / SITE_DIR）
  - jekyll build 封装 run_build()
  - git commit 封装 run_commit()（只提交，不 push；push 永远留给用户本机）
  - token 校验、JSON 响应、静态文件托管、基础 Handler（_body_json）

仅本机 127.0.0.1 使用，绝不暴露公网。
"""

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_DIR = os.path.join(ROOT, "_site")
BUILD_CMD = ["bundle", "exec", "jekyll", "build"]

# 全局运行时配置（由 serve.py 启动时填充）
_serve_cfg = {"token": "", "do_build": True, "do_commit": True}


def run_build():
    """写接口 / publish 后触发 jekyll 重建；失败仅记录，不阻断。"""
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


def run_commit(msg=None, push=False):
    """把工作树改动 git add -A + commit（默认不 push）。无改动时返回 committed=False。

    设计约束：沙箱推 GitHub 必 502，且发布流程要求 push 由用户本机执行，
    故本函数永远不 push（push 参数保留仅为未来在本机场景扩展）。
    """
    if not _serve_cfg.get("do_commit", True):
        return {"committed": False, "detail": "do_commit=False，跳过提交"}
    try:
        st = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                             capture_output=True, text=True, timeout=30)
    except Exception as e:
        return {"committed": False, "detail": f"git status 异常：{e}"}
    if not st.stdout.strip():
        return {"committed": False, "detail": "无改动，无需提交"}
    try:
        a = subprocess.run(["git", "add", "-A"], cwd=ROOT, capture_output=True, text=True, timeout=60)
        if a.returncode != 0:
            return {"committed": False, "detail": "git add 失败：" + (a.stderr or "")[:500]}
        c = subprocess.run(["git", "commit", "-m", msg or "chore: 本地写作后台自动提交"],
                           cwd=ROOT, capture_output=True, text=True, timeout=60)
        if c.returncode != 0:
            return {"committed": False, "detail": "git commit 失败：" + (c.stderr or "")[:500]}
        return {"committed": True, "detail": (c.stdout or "").strip()[:500]}
    except Exception as e:
        return {"committed": False, "detail": f"git 提交异常：{e}"}


def check_token(q):
    t = q.get("token", [""])[0]
    return t == _serve_cfg["token"]


def send_json(handler, obj, code=200):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


_MIME = {
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
}


def serve_static(handler, path):
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
    handler.send_response(200)
    handler.send_header("Content-Type", _MIME.get(ext, "application/octet-stream"))
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class BaseHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def body_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}
