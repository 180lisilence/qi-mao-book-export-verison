#!/usr/bin/env bash
# 一键: 连接 MuMu -> 启 App -> 抓日志 -> 打印关键行
cd "E:/workaddress/qimao"
ADB="build/platform-tools/adb.exe"

"$ADB" start-server >/dev/null 2>&1
for p in 7555 16384 21503; do
  "$ADB" connect 127.0.0.1:$p >/dev/null 2>&1
done

# 取第一个在线设备
DEV=$("$ADB" devices 2>/dev/null | awk 'NR>1 && $2=="device" {print $1; exit}')
if [ -z "$DEV" ]; then
  echo "[!] 没有可用设备"
  exit 1
fi
echo "[+] 设备: $DEV"

A="$ADB -s $DEV"
$A logcat -c >/dev/null 2>&1
echo "[+] 启动 App..."
$A shell monkey -p com.kmxs.reader -c android.intent.category.LAUNCHER 1 2>&1 | grep -E "Events injected|No activities|Error" | head -2
sleep 14
echo "[+] 抓日志..."
$A logcat -d -v threadtime > analysis/last_boot.log 2>&1
LINES=$(wc -l < analysis/last_boot.log)
echo "[+] 日志行数: $LINES"
echo
echo "=========== 崩溃数 ==========="
grep -icE "FATAL|beginning of crash" analysis/last_boot.log
echo
echo "=========== QMExport ==========="
grep -i "QMExport" analysis/last_boot.log | head -20
echo
echo "=========== 崩溃堆栈(若有) ==========="
sed -n '/beginning of crash/,+18p' analysis/last_boot.log | head -25
