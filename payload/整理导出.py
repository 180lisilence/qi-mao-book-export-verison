# -*- coding: utf-8 -*-
"""
整理 App 导出的章节文件。

用法:
    python 整理导出.py                       # 默认从 /sdcard/Download/QimaoBooks 拉取并整理
    python 整理导出.py --src D:\导出\QimaoBooks --out D:\小说

产出:
    <out>/<book_id>/0001_第一章xxx.txt
    <out>/<book_id>/<book_id>.txt            (整本合并稿)
    <out>/_report.txt                        (整理报告)
"""
import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import glob


def adb_pull(src_remote, dst_local, adb=None):
    if adb is None:
        return False
    try:
        subprocess.run([adb, "pull", src_remote, dst_local],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
        return True
    except Exception as e:
        print("[!] adb pull 失败:", e)
        return False


def sanitize(s, maxlen=120):
    if not s:
        return "untitled"
    s = re.sub(r"[\\/:*?\"<>|\r\n\t]", "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:maxlen] if len(s) > maxlen else s


def load_meta(meta_path):
    """返回 {chapter_id: (book_id, chapter_name, sort)}"""
    meta = {}
    if not os.path.exists(meta_path):
        return meta
    with open(meta_path, "r", encoding="utf-8", errors="replace") as f:
        rd = csv.reader(f)
        header = next(rd, None)
        for row in rd:
            if len(row) < 4:
                continue
            cid, bid, cname, sort = row[0], row[1], row[2], row[3]
            if not cid:
                continue
            try:
                s = int(sort)
            except ValueError:
                s = 99999
            meta[cid] = (bid or "unknown", cname or "", s)
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=None, help="本地已拉取的 QimaoBooks 目录")
    ap.add_argument("--remote", default="/sdcard/Download/QimaoBooks", help="设备上的导出目录")
    ap.add_argument("--out", default="./QimaoBooks_整理", help="整理输出目录")
    ap.add_argument("--adb", default=None, help="adb 可执行文件路径")
    ap.add_argument("--no-pull", action="store_true", help="跳过 adb pull, 直接用 --src")
    args = ap.parse_args()

    src = args.src
    if not args.no_pull:
        adb = args.adb
        if adb is None:
            for c in ["adb", "build/platform-tools/adb.exe"]:
                if shutil.which(c) or os.path.exists(c):
                    adb = c
                    break
        if src is None:
            src = "./QimaoBooks_raw"
        print("[+] 从设备拉取:", args.remote)
        if not adb_pull(args.remote, src, adb):
            print("    改用本地目录:", src)

    chap_dir = os.path.join(src, "chapters")
    if not os.path.isdir(chap_dir):
        print("[!] 找不到 chapters 目录:", chap_dir)
        print("    请确认 App 已经打开过书(章节正文才会被拉取并导出)")
        return 1

    meta = load_meta(os.path.join(src, "_meta.csv"))
    print("[+] 元数据条目:", len(meta))

    files = sorted(glob.glob(os.path.join(chap_dir, "*.txt")))
    print("[+] 章节文件:", len(files))
    if not files:
        print("    还没有导出任何章节。")
        return 1

    out = args.out
    os.makedirs(out, exist_ok=True)

    books = {}
    ok = 0
    nometacount = 0
    for p in files:
        cid = os.path.splitext(os.path.basename(p))[0]
        m = meta.get(cid)
        if m:
            bid, cname, sort = m
        else:
            nometacount += 1
            bid, cname, sort = "unknown", cid, 99999
        try:
            body = open(p, "r", encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        if not body.strip():
            continue

        book_dir = os.path.join(out, sanitize(bid))
        os.makedirs(book_dir, exist_ok=True)
        num = "%04d" % sort if sort != 99999 else "9999"
        title = sanitize(cname)
        dst = os.path.join(book_dir, "%s_%s.txt" % (num, title))
        with open(dst, "w", encoding="utf-8") as f:
            f.write(title + "\n\n" + body.strip() + "\n")
        books.setdefault(bid, []).append((sort, title, dst))
        ok += 1

    # 每本书生成合并稿
    for bid, items in books.items():
        items.sort(key=lambda x: x[0])
        book_dir = os.path.join(out, sanitize(bid))
        merge_path = os.path.join(book_dir, "%s_全集.txt" % sanitize(bid))
        with open(merge_path, "w", encoding="utf-8") as f:
            for sort, title, dst in items:
                f.write("\n\n\n" + "=" * 20 + "\n" + title + "\n" + "=" * 20 + "\n\n")
                f.write(open(dst, "r", encoding="utf-8", errors="replace").read())
        print("[+] 合并稿:", merge_path, "(%d 章)" % len(items))

    # 报告
    rep = os.path.join(out, "_report.txt")
    with open(rep, "w", encoding="utf-8") as f:
        f.write("整理完成\n")
        f.write("章节总数: %d\n" % ok)
        f.write("书籍数  : %d\n" % len(books))
        f.write("缺少元数据的章节: %d (文件名为 chapter_id)\n" % nometacount)
        f.write("\n各书籍:\n")
        for bid, items in books.items():
            f.write("  %s : %d 章\n" % (bid, len(items)))

    print()
    print("=" * 50)
    print("整理完成 ->", os.path.abspath(out))
    print("章节总数:", ok, " 书籍数:", len(books))
    if nometacount:
        print("提示: 有 %d 章没有元数据(文件名是 chapter_id)。" % nometacount)
        print("      在 App 里多翻几次目录/章节列表即可补齐(_meta.csv)。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
