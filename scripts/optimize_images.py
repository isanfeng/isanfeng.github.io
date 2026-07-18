#!/usr/bin/env python3
# 图片压缩 + WebP 副本生成脚本（可复用 / 可定时）
# 递归扫描 images/ 下所有 jpg/jpeg/webp：
#   - 仅处理 > MIN_BYTES 的图（避免反复处理已优化图）做【同格式压缩】
#   - 宽度 > MAX_W 则缩放到 MAX_W
#   - JPEG: optimize + progressive; WebP: lossy
#   - 仅当结果确实更小（且缩小 >= MIN_SAVE_RATIO）才替换原图
#   --webp: 额外为【所有】jpg/jpeg 生成同名 .webp 副本（覆盖全站），
#           不论原图大小，确保前端 <picture><source webp> 不会 404。
# 用法：python3 scripts/optimize_images.py [--dir images] [--dry-run] [--webp]
import os, sys, argparse
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DIR = os.path.join(ROOT, "images")
MAX_W        = 1600      # 最大宽度（px），超过则缩放
QUALITY      = 72        # JPEG/WebP 质量
MIN_BYTES    = 500 * 1024   # 仅处理大于 500KB 的图（同格式压缩用）
MIN_SAVE_RATIO = 0.05  # 至少省 5% 才替换


def _open(path):
    im = Image.open(path)
    if im.mode in ("RGBA", "P", "LA"):
        im = im.convert("RGB")
    return im


def _resize(im):
    w, h = im.size
    if w > MAX_W:
        im = im.resize((MAX_W, round(h * MAX_W / w)), Image.LANCZOS)
    return im


def optimize_one(path, dry_run):
    """同格式压缩（jpg->更小jpg，webp->更小webp）。"""
    try:
        im = _resize(_open(path))
        tmp = path + ".opt.tmp"
        if path.lower().endswith(".webp"):
            im.save(tmp, "WEBP", quality=QUALITY)
        else:
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


def gen_webp(path, dry_run):
    """为 jpg/jpeg 生成同名 .webp 副本（覆盖全站，供 <picture> 优先使用）。"""
    try:
        im = _resize(_open(path))
        webp_path = os.path.splitext(path)[0] + ".webp"
        tmp = webp_path + ".opt.tmp"
        im.save(tmp, "WEBP", quality=QUALITY)
        before = os.path.getsize(path)   # 原 jpg 大小（参考）
        after = os.path.getsize(tmp)        # webp 大小
        if dry_run:
            os.remove(tmp)
            return (webp_path, before, after, "WOULD-GEN")
        os.replace(tmp, webp_path)
        return (webp_path, before, after, "GEN")
    except Exception as e:
        _t = os.path.splitext(path)[0] + ".webp.opt.tmp"
        if os.path.exists(_t):
            os.remove(_t)
        return (path, 0, 0, f"ERROR:{e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DEFAULT_DIR)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--webp", action="store_true",
                    help="为所有 jpg/jpeg 额外生成同名 .webp 副本")
    args = ap.parse_args()
    exts = (".jpg", ".jpeg", ".JPG", ".JPEG", ".webp", ".WEBP")
    targets = []
    for root, _, files in os.walk(args.dir):
        for f in files:
            if f.lower().endswith(exts):
                p = os.path.join(root, f)
                if os.path.getsize(p) > MIN_BYTES:
                    targets.append(p)
    flag = " [DRY-RUN]" if args.dry_run else ""
    print(f"扫描目录: {args.dir}")
    print(f"待压缩(>{MIN_BYTES//1024}KB): {len(targets)} 张{flag}")
    saved = kept = err = 0
    tb = ta = 0
    saved_list = []  # (relpath, before, after)
    for p in sorted(targets):
        _, b, a, st = optimize_one(p, args.dry_run)
        rel = os.path.relpath(p, ROOT)
        if st.startswith("SAVE") or st.startswith("WOULD"):
            saved += 1; tb += b; ta += a
            saved_list.append((rel, b, a))
        elif st.startswith("KEEP"):
            kept += 1
        else:
            err += 1
            print(f"  {st:14s} {rel}")
    print(f"压缩完成: 已压缩 {saved} 张, 保留 {kept} 张, 失败 {err} 张" +
          (f", 共节省 {(tb-ta)//1024}KB" if saved else ""))
    if saved_list:
        print("  压缩文件明细:")
        for rel, b, a in saved_list:
            print(f"    - {rel}: {b//1024}KB -> {a//1024}KB (省 {(b-a)//1024}KB)")

    if args.webp:
        webp_targets = []
        for root, _, files in os.walk(args.dir):
            for f in files:
                if f.lower().endswith((".jpg", ".jpeg", ".JPG", ".JPEG")):
                    webp_targets.append(os.path.join(root, f))
        print(f"待生成 WebP 副本: {len(webp_targets)} 张{flag}")
        gen = gerr = 0
        gtb = gta = 0
        gen_list = []  # (relpath_webp, before_jpg, after_webp)
        for p in sorted(webp_targets):
            wp, b, a, st = gen_webp(p, args.dry_run)
            rel = os.path.relpath(wp, ROOT)
            if st.startswith("GEN") or st.startswith("WOULD"):
                gen += 1; gtb += b; gta += a
                gen_list.append((rel, b, a))
            elif st.startswith("ERROR"):
                gerr += 1
                print(f"  {st:14s} {os.path.relpath(p, ROOT)}")
        print(f"WebP 完成: 生成 {gen} 张, 失败 {gerr} 张" +
              (f", 共节省 {(gtb-gta)//1024}KB（vs 原 jpg）" if gen else ""))
        if gen_list:
            print("  WebP 生成明细:")
            for rel, b, a in gen_list:
                print(f"    - {rel}: {b//1024}KB jpg -> {a//1024}KB webp (省 {(b-a)//1024}KB)")


if __name__ == "__main__":
    main()
