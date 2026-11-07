"""把 classes19.dex 塞进 APK，产出用于 apktool 反编译的中间包。"""
import zipfile, sys, os

src = "七猫免费小说_7.80.apk"
dex = "build/dex035/classes.dex"
dst = "build/stage.apk"

os.makedirs("build", exist_ok=True)

names_in = []
with zipfile.ZipFile(src) as zin:
    for i in zin.infolist():
        names_in.append(i.filename)
    print("原始条目数:", len(names_in))

# 位置：classes18.dex 之后插入 classes19.dex
order = list(names_in)
if "classes19.dex" in order:
    order.remove("classes19.dex")
insert_at = order.index("classes18.dex") + 1 if "classes18.dex" in order else len(order)
order.insert(insert_at, "classes19.dex")

with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zout:
    for name in order:
        if name == "classes19.dex":
            data = open(dex, "rb").read()
            zi = zipfile.ZipInfo(name, (2001, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(zi, data)
            print("+ 注入 classes19.dex (%d 字节)" % len(data))
        else:
            info = zin.getinfo(name)
            data = zin.read(name)
            zi = zipfile.ZipInfo(name, (2001, 1, 1, 0, 0, 0))
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zi.internal_attr = info.internal_attr
            zi.create_system = info.create_system
            zout.writestr(zi, data)

print("输出:", dst, os.path.getsize(dst), "字节")
