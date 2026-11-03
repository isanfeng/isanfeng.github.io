#!/usr/bin/env python3
# 图片压缩 + WebP 副本生成脚本（可复用 / 可定时）
# 递归扫描 images/ 下所有 jpg/jpeg/png/webp：
#   - 仅处理 > MIN_BYTES 的图（避免反复处理已优化图）做【同格式压缩】
#   - 宽度 > MAX_W 则缩放到 MAX_W
#   - JPEG: optimize + progressive; WebP: lossy
#   - 仅当结果确实更小（且缩小 >= MIN_SAVE_RATIO）才替换原图
#   --webp: 补齐【缺失】的同名 .webp 副本（jpg/jpeg/png 且尚无 webp 的才生成），
#           已存在的 webp 默认跳过；加 --force 才重生成。
#           供前端 <picture><source webp> 使用，避免 404 与重复生成。
# 用法：python3 scripts/optimize_images.py [--dir images] [--dry-run] [--webp] [--force]
import os, sys, argparse
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DIR = os.path.join(ROOT, "images")
MAX_W        = 1600      # 最大宽度（px），超过则缩放（同格式压缩用）
MAX_EDGE_WEBP = 2048     # WebP 副本最长边上限（卡片最大约 800px@2x，2048 足够）
QUALITY      = 72        # JPEG 质量
QUALITY_WEBP = 85        # WebP 质量
MIN_BYTES    = 500 * 1024   # 仅处理大于 500KB 的图（同格式压缩用）
MIN_SAVE_RATIO = 0.05  # 至少省 5% 才替换

# 需要为它们生成 webp 的源格式（大小写都列，macOS 上 .JPG/.jpg 是两个文件）
SRC_EXTS = (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")
WEBP_EXTS = (".webp", ".WEBP")


def _open(path):
    im = Image.open(path)
    if im.mode in ("RGBA", "P", "LA"):
        im = im.convert("RGB")
    return im


def _open_for_webp(path):
    """生成 webp 用：先按 EXIF 摆正方向，并保留透明通道。"""
    im = ImageOps.exif_transpose(Image.open(path))
    return im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")


def _resize_edge(im, max_edge):
    w, h = im.size
    if max(w, h) <= max_edge:
        return im
    s = max_edge / max(w, h)
    return im.resize((round(w * s), round(h * s)), Image.LANCZOS)


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


def gen_webp(path, dry_run, force=False):
    """为缺少 webp 副本的图生成同名 .webp（不覆盖已有副本，除非 force）。
    q85 若比原图还大，逐级降质重试；最小仍大于原图则放弃（生成更大的副本没有意义）。"""
    try:
        webp_path = os.path.splitext(path)[0] + ".webp"
        if os.path.exists(webp_path) and not force:
            return (webp_path, 0, 0, "SKIP(exists)")
        im = _resize_edge(_open_for_webp(path), MAX_EDGE_WEBP)
        tmp = webp_path + ".opt.tmp"
        before = os.path.getsize(path)   # 原图大小
        after = 0
        for q in (QUALITY_WEBP, 80, 75):
            im.save(tmp, "WEBP", quality=q, method=6)
            after = os.path.getsize(tmp)
            if after <= before:
                break
        else:
            os.remove(tmp)
            return (webp_path, before, after, "SKIP(bigger)")
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
                    help="为缺少同名 .webp 副本的 jpg/jpeg/png 生成 WebP（已存在则跳过）")
    ap.add_argument("--optimize", action="store_true",
                    help="同格式压缩（与 --webp 一起用时才同时执行）")
    ap.add_argument("--force", action="store_true",
                    help="配合 --webp：已存在的 webp 也重新生成（覆盖）")
    args = ap.parse_args()
    exts = (".jpg", ".jpeg", ".JPG", ".JPEG", ".webp", ".WEBP")
    targets = []
    # 带 --webp 时默认只补副本、不做同格式压缩（压缩会改写原图，避免误操作）；
    # 需要两者都做时显式加 --optimize。
    if args.optimize or not args.webp:
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
        # 只补缺失：目录里没有同名 .webp 的源图才生成（大小写不敏感，.JPG/.jpg 视为同名）
        webp_targets = {}
        skipped = 0
        for root, _, files in os.walk(args.dir):
            existing = {f.lower() for f in files}
            for f in files:
                if not f.endswith(SRC_EXTS) or f.endswith(".opt.tmp"):
                    continue
                wp = os.path.splitext(os.path.join(root, f))[0] + ".webp"
                if os.path.basename(wp).lower() in existing and not args.force:
                    skipped += 1
                    continue
                p = os.path.join(root, f)
                # 同一 stem 可能同时存在 .jpg 和 .JPG，只保留较大的那张，避免互相覆盖
                if wp not in webp_targets or os.path.getsize(p) > os.path.getsize(webp_targets[wp]):
                    webp_targets[wp] = p
        print(f"缺失 WebP 副本: {len(webp_targets)} 张（已存在跳过 {skipped} 张）{flag}")
        gen = gerr = 0
        gtb = gta = 0
        gen_list = []  # (relpath_webp, before_src, after_webp)
        for wp, p in sorted(webp_targets.items()):
            wp2, b, a, st = gen_webp(p, args.dry_run, args.force)
            rel = os.path.relpath(wp2, ROOT)
            if st.startswith("GEN") or st.startswith("WOULD"):
                gen += 1; gtb += b; gta += a
                gen_list.append((rel, b, a))
            elif st.startswith("ERROR"):
                gerr += 1
                print(f"  {st:14s} {os.path.relpath(p, ROOT)}")
            elif st.startswith("SKIP(bigger)"):
                gerr += 1
                print(f"  {'SKIP(bigger)':14s} {rel}（webp 比原图大，已放弃）")
        print(f"WebP 完成: 生成 {gen} 张, 失败 {gerr} 张" +
              (f", 合计 {(gtb-gta)//1024}KB（原图 {gtb//1024}KB -> webp {gta//1024}KB）" if gen else ""))
        if gen_list:
            print("  WebP 生成明细:")
            for rel, b, a in gen_list:
                print(f"    - {rel}: {b//1024}KB -> {a//1024}KB (省 {(b-a)//1024}KB)")


if __name__ == "__main__":
    main()
