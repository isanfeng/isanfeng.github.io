#!/usr/bin/env python3
# 图片压缩脚本（可复用 / 可定时）
# 递归扫描 images/ 下所有 jpg/jpeg：
#   - 仅处理 > MIN_BYTES 的图（避免反复处理已优化图）
#   - 宽度 > MAX_W 则缩放到 MAX_W
#   - 用 Pillow 重新编码（optimize + progressive + 指定质量）
#   - 仅当结果确实更小（且缩小 >= MIN_SAVE_RATIO）才替换原图，否则保留
# 用法：python3 scripts/optimize_images.py [--dir images] [--dry-run]
import os, sys, argparse
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DIR = os.path.join(ROOT, "images")
MAX_W        = 1600      # 最大宽度（px），超过则缩放
QUALITY      = 72        # JPEG 质量
MIN_BYTES    = 500 * 1024   # 仅处理大于 500KB 的图
MIN_SAVE_RATIO = 0.05  # 至少省 5% 才替换

def optimize_one(path, dry_run):
    try:
        im = Image.open(path)
        if im.mode in ("RGBA", "P", "LA"):
            im = im.convert("RGB")
        w, h = im.size
        if w > MAX_W:
            im = im.resize((MAX_W, round(h * MAX_W / w)), Image.LANCZOS)
        tmp = path + ".opt.tmp"
        im.save(tmp, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        before = os.path.getsize(path)
        after = os.path.getsize(tmp)
        if before - after >= before * MIN_SAVE_RATIO:
            if dry_run:
                os.remove(tmp)
                return (path, before, after, "WOULD-SAVE")
            os.replace(tmp, path)
            return (path, before, after, "SAVED")
        else:
            os.remove(tmp)
            return (path, before, after, "KEEP(smaller-gain)")
    except Exception as e:
        if os.path.exists(path + ".opt.tmp"):
            os.remove(path + ".opt.tmp")
        return (path, 0, 0, f"ERROR:{e}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DEFAULT_DIR)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    exts = (".jpg", ".jpeg", ".JPG", ".JPEG")
    targets = []
    for root, _, files in os.walk(args.dir):
        for f in files:
            if f.lower().endswith(exts):
                p = os.path.join(root, f)
                if os.path.getsize(p) > MIN_BYTES:
                    targets.append(p)
    print(f"扫描目录: {args.dir}")
    print(f"待处理(>{MIN_BYTES//1024}KB): {len(targets)} 张" + ("  [DRY-RUN]" if args.dry_run else ""))
    saved = 0; kept = 0; err = 0; total_before = 0; total_after = 0
    for p in sorted(targets):
        path, b, a, status = optimize_one(p, args.dry_run)
        if status.startswith("SAVE") or status.startswith("WOULD"):
            saved += 1; total_before += b; total_after += a
            print(f"  {status:14s} {b//1024:6d}KB -> {a//1024:6d}KB  {os.path.relpath(path, ROOT)}")
        elif status.startswith("KEEP"):
            kept += 1
        else:
            err += 1
            print(f"  {status:14s} {os.path.relpath(path, ROOT)}")
    print(f"完成: 已压缩 {saved} 张, 保留 {kept} 张, 失败 {err} 张" +
          (f", 共节省 {(total_before-total_after)//1024}KB" if saved else ""))

if __name__ == "__main__":
    main()
