"""把 apktool 产物里缺失的原始文件补回, 保证 lib/assets/META-INF 完整。"""
import zipfile, shutil, os

SRC_ORIG = "七猫免费小说_7.80.apk"
TOOL_APK = "build/unsigned.apk"
DST = "build/merged.apk"

with zipfile.ZipFile(SRC_ORIG) as zo, zipfile.ZipFile(TOOL_APK) as zt:
    tool_names = set(i.filename for i in zt.infolist())
    orig_info = {i.filename: i for i in zo.infolist()}

    missing = [n for n in orig_info if n not in tool_names]
    print("工具产物条目:", len(tool_names))
    print("待补回条目:", len(missing))

    kept = 0
    with zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zd:
        # 1. apktool 产物优先 (含改好的 dex / resources / manifest / res)
        for info in zt.infolist():
            zi = zipfile.ZipInfo(info.filename, (2001, 1, 1, 0, 0, 0))
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zi.internal_attr = info.internal_attr
            zi.create_system = info.create_system
            zd.writestr(zi, zt.read(info.filename))
            kept += 1

        # 2. 补回原始缺失文件
        added = 0
        for n in missing:
            info = orig_info[n]
            zi = zipfile.ZipInfo(n, (2001, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = info.external_attr
            zi.internal_attr = info.internal_attr
            zi.create_system = info.create_system
            zd.writestr(zi, zo.read(n))
            added += 1

print("保留:", kept, " 补回:", added)
print("输出:", DST, os.path.getsize(DST), "字节")
