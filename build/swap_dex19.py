"""把新的 classes19.dex 替换进 final.apk(其余 dex/资源保持原始), 输出 frankenstein.apk"""
import zipfile, os, sys

BASE = "build/final.apk"
NEW19 = "build/dex035/classes.dex"
DST = "build/final2.apk"

zin = zipfile.ZipFile(BASE)
data19 = open(NEW19, "rb").read()
names = [i.filename for i in zin.infolist()]
print("基础条目:", len(names))

with zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zout:
    for name in names:
        info = zin.getinfo(name)
        if name == "classes19.dex":
            data = data19
        else:
            data = zin.read(name)
        zi = zipfile.ZipInfo(name, (2001, 1, 1, 0, 0, 0))
        zi.compress_type = info.compress_type
        zi.external_attr = info.external_attr
        zi.internal_attr = info.internal_attr
        zi.create_system = info.create_system
        zout.writestr(zi, data)
zin.close()
print("替换 classes19.dex ->", len(data19), "字节")
print("输出:", DST, os.path.getsize(DST), "字节")

# 自检 dex 完整性
sys.path.insert(0, 'tools')
from dexdump import Dex
zo = zipfile.ZipFile("七猫免费小说_7.80.apk")
z = zipfile.ZipFile(DST)
def stats(d):
    dx = Dex(d); return len(list(dx.class_defs())), dx.method_ids_size
diff = []
for n in [i.filename for i in zo.infolist()]:
    if not n.endswith('.dex'): continue
    if stats(zo.read(n)) != stats(z.read(n)) and n != 'classes10.dex':
        diff.append(n)
print("与原始不一致的 dex(排除已知的 classes10):", diff or "无")
print("classes19:", stats(z.read('classes19.dex')))
