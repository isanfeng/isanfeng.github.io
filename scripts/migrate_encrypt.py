#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
迁移旧「prompt 弹窗」加密文章到新的轻量门禁方案。

旧文章顶部有一段内联 <script>（含 function password()），用 prompt() 要密码、
比对明文硬编码密码，且正文其实仍渲染在页面源码里。本脚本：

  1. 删掉那一段 <script>...</script>（只删含 function password 的，不碰其它 <script>）
  2. 在 front-matter 加 `encrypt: true`（若已有 encrypt: 则保留、不重复加）
  3. 正文原样保留

密码统一用 _config.yml 的 encrypt_password（全局单把），旧文章朋友用新钥匙即可解锁。

用法：
  python scripts/migrate_encrypt.py            # dry-run，只打印将迁移的文件
  python scripts/migrate_encrypt.py --apply    # 真正改写文件
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_DIR = os.path.join(ROOT, "_posts")

# 只匹配含 function password 的 <script> 块（DOTALL 让 . 跨行）
SCRIPT_SIG = re.compile(r"<script[^>]*>.*?function\s+password.*?</script>", re.DOTALL)
# front-matter：文件开头 ---\n ... \n---\n
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def front_matter_has_encrypt(fm_text):
    return re.search(r"(?m)^encrypt\s*:", fm_text) is not None


def migrate_file(path, apply_changes):
    with open(path, encoding="utf-8") as f:
        text = f.read()

    m = FM_RE.match(text)
    if not m:
        return None, "无 front-matter，跳过"
    fm = m.group(1)
    body = text[m.end():]

    if not SCRIPT_SIG.search(body):
        return None, "无旧加密脚本，跳过"

    new_body = SCRIPT_SIG.sub("", body)
    # 删掉脚本块后，把 front-matter 结束符之后多余的前导空行压成一个换行
    new_body = new_body.lstrip("\n")
    new_body = ("\n" + new_body) if new_body else ""

    notes = []
    if not front_matter_has_encrypt(fm):
        fm = fm + "\nencrypt: true"
        notes.append("+encrypt:true")
    else:
        notes.append("encrypt 已存在(保留)")

    new_text = "---\n" + fm + "\n---\n" + new_body

    if apply_changes:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_text)

    return True, ", ".join(notes)


def main():
    apply_changes = "--apply" in sys.argv
    files = sorted(glob.glob(os.path.join(POSTS_DIR, "**", "*.md"), recursive=True))

    migrated = 0
    skipped = 0
    for p in files:
        rel = os.path.relpath(p, ROOT)
        ok, note = migrate_file(p, apply_changes)
        if ok is True:
            migrated += 1
            if not apply_changes:
                print(f"[dry-run] {rel}  ({note})")
        elif ok is None and apply_changes is False:
            # dry-run 时也顺便统计非加密文，但不打印（太吵）
            skipped += 1
    if not apply_changes:
        print(f"\n将迁移 {migrated} 篇（dry-run，未改动文件；非加密文 {skipped} 篇跳过）")
        print("加 --apply 真正执行。")
    else:
        print(f"\n已迁移 {migrated} 篇（已写回文件）")


if __name__ == "__main__":
    main()
