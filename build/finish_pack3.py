# -*- coding: utf-8 -*-
"""最终打包 v2 (静态注入 + 悬浮球 UI + 解密导出)

基线: 原始 APK 全部条目(字节级保持)
  - classes3.dex  <- build/mini3.apk   (ChapterContentEntity.getContent / KMChapter.getChapterName)
  - classes10.dex <- build/mini10.apk  (SophixStubApplication.attachBaseContext -> Boot.install(p0))
  - classes19.dex <- build/dex040/classes.dex (com.kmxs.export.Boot v2)
"""
import zipfile, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)

ORIG = "七猫免费小说_7.80.apk"
C3 = "build/mini3.apk"
C10 = "build/mini10.apk"
D19 = "build/dex040/classes.dex"
DST = "build/final_v2.apk"

zo = zipfile.ZipFile(ORIG)
z3 = zipfile.ZipFile(C3)
z10 = zipfile.ZipFile(C10)
new3 = z3.read("classes.dex")
new10 = z10.read("classes.dex")
dex19 = open(D19, "rb").read()

orig_names = [i.filename for i in zo.infolist()]
print("原始条目:", len(orig_names))
print("classes3 :", len(new3))
print("classes10:", len(new10))
print("classes19:", len(dex19))


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
print("输出:", DST, os.path.getsize(DST))

# ---------------- 自检 ----------------
sys.path.insert(0, 'tools')
from dexdump import Dex


def stats(d):
    try:
        dx = Dex(d)
        return len(list(dx.class_defs())), dx.method_ids_size
    except BaseException as e:
        return ("raw", len(d), str(e)[:40])


def clean(s):
    s = (s or '').replace('\x00', '\\0')
    try:
        s.encode('utf-8')
    except UnicodeEncodeError:
        s = s.encode('utf-8', 'replace').decode('utf-8', 'replace')
    return s


z = zipfile.ZipFile(DST)
names = set(i.filename for i in z.infolist())
orig_set = set(orig_names)
print()
print("缺失条目:", len(orig_set - names))
print("新增条目:", len(names - orig_set))
print()
print("与原始不一致的 dex:")
for n in sorted(orig_set):
    if not n.endswith('.dex'):
        continue
    a = stats(zo.read(n))
    b = stats(z.read(n))
    if a != b:
        print("   %-16s %s -> %s" % (n, a, b))
print("classes19:", stats(z.read("classes19.dex")))

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

dx = Dex(z.read("classes9.dex"))
hit = any('TTMultiProvider' in clean(dx.type_at(c['class'])) for c in dx.class_defs())
print("classes9 TTMultiProvider 存在:", hit)

# Boot v2 关键方法
raw19 = z.read("classes19.dex")
print("classes19 大小:", len(raw19), "magic:", raw19[:8])
try:
    dx = Dex(raw19)
    need = {"install", "dumpRaw", "noteMeta", "exportCached", "organize", "decrypt", "redecrypt"}
    have = set()
    for i in range(dx.method_ids_size):
        c, m, rt, p = dx.method_at(i)
        if 'kmxs/export' in (c or ''):
            have.add(clean(m))
    print("Boot 关键方法齐备:", need <= have, sorted(need - have))
except BaseException as e:
    print("classes19 dex 解析跳过:", e)
