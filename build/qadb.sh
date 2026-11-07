#!/usr/bin/env bash
# 稳定的 adb 封装: 每次自动 start-server + connect, 取第一个在线设备
ADB="E:/workaddress/qimao/build/platform-tools/adb.exe"
"$ADB" start-server >/dev/null 2>&1
for p in 7555 16384 21503; do
  "$ADB" connect 127.0.0.1:$p >/dev/null 2>&1
done
DEV=$("$ADB" devices 2>/dev/null | awk 'NR>1 && $2=="device" {print $1; exit}')
if [ -z "$DEV" ]; then
  sleep 2
  "$ADB" connect 127.0.0.1:7555 >/dev/null 2>&1
  DEV=$("$ADB" devices 2>/dev/null | awk 'NR>1 && $2=="device" {print $1; exit}')
fi
if [ -z "$DEV" ]; then
  echo "QADB_ERR: no device" >&2
  exit 9
fi
exec "$ADB" -s "$DEV" "$@"
