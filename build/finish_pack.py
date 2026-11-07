"""最终打包: 以原始 APK 为基线, 只替换 classes10.dex(已打补丁) + 新增 classes19.dex。
   其余 dex / 资源 / so 全部保持原始字节, 避免 apktool 重编译 dex 时丢类。
"""
import zipfile, os

ORIG = "七猫免费小说_7.80.apk"
PATCHED_C10 = "build/unsigned.apk"      # 来源: 里面那个 classes10.dex 已含 Boot->install
NEW_DEX19 = "build/dex035/classes.dex"
DST = "build/final.apk"

zo = zipfile.ZipFile(ORIG)
zu = zipfile.ZipFile(PATCHED_C10)

orig_names = [i.filename for i in zo.infolist()]
patched10 = zu.read("classes10.dex")
dex19 = open(NEW_DEX19, "rb").read()

print("原始条目:", len(orig_names))
print("patched classes10.dex:", len(patched10), "字节")
print("classes19.dex:", len(dex19), "字节")

def write_info(zout, name, data, ref_info=None, compress=None):
    zi = zipfile.ZipInfo(name, (2001, 1, 1, 0, 0, 0))
    if ref_info is not None and compress is None:
        zi.compress_type = ref_info.compress_type
        zi.external_attr = ref_info.external_attr
        zi.internal_attr = ref_info.internal_attr
        zi.create_system = ref_info.create_system
    else:
        zi.compress_type = compress or zipfile.ZIP_DEFLATED
    zout.writestr(zi, data)

added19 = False
replaced10 = False
with zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zd:
    for name in orig_names:
        info = zo.getinfo(name)
        if name == "classes10.dex":
            write_info(zd, name, patched10, info)
            replaced10 = True
        else:
            write_info(zd, name, zo.read(name), info)
        # classes18 之后紧跟我们的 dex
        if name == "classes18.dex" and "classes19.dex" not in orig_names:
            write_info(zd, "classes19.dex", dex19, None, zipfile.ZIP_DEFLATED)
            added19 = True
    if not added19 and "classes19.dex" not in orig_names:
        write_info(zd, "classes19.dex", dex19, None, zipfile.ZIP_DEFLATED)
        added19 = True

zo.close(); zu.close()
print("替换 classes10:", replaced10, " 注入 classes19:", added19)
print("输出:", DST, os.path.getsize(DST), "字节")

# ---- 自检 ----
z = zipfile.ZipFile(DST)
names = set(i.filename for i in z.infolist())
zo2 = zipfile.ZipFile(ORIG)
orig_set = set(i.filename for i in zo2.infolist())
print()
print("相对原始缺失:", len(orig_set - names))
import sys
sys.path.insert(0, 'tools')
from dexdump import Dex
def clean(s):
    s = (s or '').replace('\x00', '\\0')
    try: s.encode('utf-8')
    except UnicodeEncodeError: s = s.encode('utf-8','replace').decode('utf-8','replace')
    return s
def stats(data):
    dx = Dex(data)
    return len(list(dx.class_defs())), dx.method_ids_size
print("%-16s %-18s %-18s" % ('dex', '原始', '最终'))
ok = True
for n in sorted(orig_set | {'classes19.dex'}):
    if not n.endswith('.dex'): continue
    try: a = stats(zo2.read(n))
    except KeyError: a = None
    b = stats(z.read(n))
    mark = ''
    if a is not None and a != b:
        mark = ' <<< 变化'
        if n != 'classes10.dex': ok = False
    print("%-16s %-18s %-18s%s" % (n, str(a), str(b), mark))
print()
print("classes9 保持完整:", stats(z.read('classes9.dex')) == stats(zo2.read('classes9.dex')))
# TTMultiProvider
hit = False
data = z.read('classes9.dex')
dx = Dex(data)
for c in dx.class_defs():
    if 'TTMultiProvider' in clean(dx.type_at(c['class'])):
        hit = True
print("TTMultiProvider 存在:", hit)
