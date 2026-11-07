# -*- coding: utf-8 -*-
"""最终打包(静态注入版):
   原始 APK 全部条目为基线
   - classes3.dex  <- build/mini3.apk  (注入 dumpRaw / noteMeta)
   - classes10.dex <- build/mini10.apk (注入 Boot.install)
   - classes19.dex <- build/dex035/classes.dex (纯 Java 导出器, 无 Xposed/Pine)
   其余 dex / 资源 / so / assets 全部保持原始字节。
"""
import zipfile, os, sys

ORIG = "七猫免费小说_7.80.apk"
C3 = "build/mini3.apk"
C10 = "build/mini10.apk"
D19 = "build/dex035/classes.dex"
DST = "build/final_static.apk"

zo = zipfile.ZipFile(ORIG)
z3 = zipfile.ZipFile(C3)
z10 = zipfile.ZipFile(C10)
new3 = z3.read("classes.dex")
new10 = z10.read("classes.dex")
dex19 = open(D19, "rb").read()

orig_names = [i.filename for i in zo.infolist()]
print("原始条目:", len(orig_names))
print("classes3 :", len(new3), "字节")
print("classes10:", len(new10), "字节")
print("classes19:", len(dex19), "字节")

def put(zout, name, data, ref=None):
    zi = zipfile.ZipInfo(name, (2001, 1, 1, 0, 0, 0))
    if ref is not None:
        zi.compress_type = ref.compress_type
        zi.external_attr = ref.external_attr
        zi.internal_attr = ref.internal_attr
        zi.create_system = ref.create_system
    else:
        zi.compress_type = zipfile.ZIP_DEFLATED
    zout.writestr(zi, data)

n3 = n10 = n19 = 0
with zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zout:
    for name in orig_names:
        info = zo.getinfo(name)
        if name == "classes3.dex":
            put(zout, name, new3, info); n3 += 1
        elif name == "classes10.dex":
            put(zout, name, new10, info); n10 += 1
        else:
            put(zout, name, zo.read(name), info)
        if name == "classes18.dex":
            put(zout, "classes19.dex", dex19); n19 += 1
    if n19 == 0:
        put(zout, "classes19.dex", dex19); n19 += 1

print("替换 classes3=%d classes10=%d 注入 classes19=%d" % (n3, n10, n19))
print("输出:", DST, os.path.getsize(DST), "字节")

# ---------------- 自检 ----------------
sys.path.insert(0, 'tools')
from dexdump import Dex
def stats(d):
    dx = Dex(d); return len(list(dx.class_defs())), dx.method_ids_size
z = zipfile.ZipFile(DST)
names = set(i.filename for i in z.infolist())
orig_set = set(orig_names)
print()
print("相对原始缺失条目:", len(orig_set - names))
changed = []
for n in sorted(orig_set):
    if not n.endswith('.dex'): continue
    a = stats(zo.read(n)); b = stats(z.read(n))
    if a != b:
        changed.append((n, a, b))
print("与原始不一致的 dex:")
for n, a, b in changed:
    print("   %-16s %s -> %s" % (n, a, b))
print("classes19:", stats(z.read("classes19.dex")))

def clean(s):
    s = (s or '').replace('\x00', '\\0')
    try: s.encode('utf-8')
    except UnicodeEncodeError: s = s.encode('utf-8','replace').decode('utf-8','replace')
    return s
print()
print("注入点检查:")
for n in ["classes3.dex", "classes10.dex"]:
    dx = Dex(z.read(n))
    hs = set()
    for i in range(dx.method_ids_size):
        c, m, rt, p = dx.method_at(i)
        if 'kmxs/export' in (c or ''):
            hs.add(clean(m))
    print("   %-14s %s" % (n, sorted(hs)))
# TTMultiProvider 完整性
dx = Dex(z.read("classes9.dex"))
hit = any('TTMultiProvider' in clean(dx.type_at(c['class'])) for c in dx.class_defs())
print("classes9 TTMultiProvider 存在:", hit)
