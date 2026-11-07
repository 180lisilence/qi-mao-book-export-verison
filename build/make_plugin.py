# -*- coding: utf-8 -*-
"""编译 -> dex -> 打包 -> 签名 一键脚本"""
import os, subprocess, zipfile, sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
JBR = r"D:/TOOL/devecostudio/devecostudioapp/DevEco Studio/jbr/bin"
JAVAC = os.path.join(JBR, "javac.exe")
JAVA = os.path.join(JBR, "java.exe")
SRC = os.path.join(BASE, "src/main/com/kmxs/export/Boot.java")
CLASSES = os.path.join(BASE, "classes2")
AJAR = os.path.join(BASE, "android.jar")
R8 = os.path.join(BASE, "r8-8.2.47.jar")
JARF = os.path.join(BASE, "boot40.jar")
DEXDIR = os.path.join(BASE, "dex040")


def run(cmd, cwd=None):
    print("+", " ".join(cmd))
    r = subprocess.call(cmd, cwd=cwd or BASE)
    if r != 0:
        print("!! 失败 exit=%d" % r)
        sys.exit(r)


# 1) 清理 + 编译
for d in (CLASSES, DEXDIR):
    if os.path.isdir(d):
        for root, dirs, files in os.walk(d, topdown=False):
            for f in files:
                os.remove(os.path.join(root, f))
            for dd in dirs:
                os.rmdir(os.path.join(root, dd))
    else:
        os.makedirs(d)
run([JAVAC, "-encoding", "UTF-8", "--release", "11", "-nowarn",
     "-classpath", AJAR, "-d", CLASSES, SRC])

# 2) 打 jar
with zipfile.ZipFile(JARF, "w", zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(CLASSES):
        for f in files:
            if f.endswith(".class"):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, CLASSES).replace(os.sep, "/")
                z.write(full, rel)
print("jar:", os.path.getsize(JARF))

# 3) dex
run([JAVA, "-cp", R8, "com.android.tools.r8.D8", "--min-api", "24",
     "--classpath", AJAR, "--output", DEXDIR, JARF])
dex = open(os.path.join(DEXDIR, "classes.dex"), "rb").read()
print("dex:", len(dex), "bytes, 含-CC:", b"-CC;" in dex)
assert b"-CC;" not in dex, "仍然生成了 -CC 脱糖类"

# 4) 打包 + 签名
os.chdir(ROOT)
run([sys.executable, "build/finish_pack3.py"], cwd=ROOT)
apk = os.path.join(BASE, "final_v2.apk")
out = os.path.join(BASE, "final_v2-aligned-debugSigned.apk")
if os.path.exists(out):
    os.remove(out)
run([JAVA, "-jar", os.path.join(BASE, "uber-apk-signer.jar"), "-a", apk, "-o", BASE])
dst = os.path.join(ROOT, "out", "七猫免费小说_7.80_导出插件v3.apk")
import shutil
shutil.copyfile(out, dst)
print()
print("=== 完成 ===")
print(dst, os.path.getsize(dst))
