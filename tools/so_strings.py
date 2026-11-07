#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 ELF 中提取可打印字符串（ASCII + UTF-16LE），可按关键词过滤"""
import sys, re, os

MIN = 4

def extract(data):
    out = []
    # ASCII
    for m in re.finditer(rb'[\x20-\x7e]{%d,}' % MIN, data):
        out.append((m.start(), m.group().decode('ascii', 'replace')))
    # UTF-16LE (CJK)
    for m in re.finditer(rb'(?:[\x20-\x7e]\x00){%d,}' % MIN, data):
        try:
            s = m.group().decode('utf-16-le')
        except Exception:
            continue
        out.append((m.start(), s))
    # CJK UTF-8
    for m in re.finditer(rb'[\xe0-\xef][\x80-\xbf]{2}(?:[\x20-\x7e]|[\xe0-\xef][\x80-\xbf]{2}){2,}', data):
        try:
            s = m.group().decode('utf-8')
        except Exception:
            continue
        out.append((m.start(), s))
    out.sort()
    return out

if __name__ == '__main__':
    path = sys.argv[1]
    data = open(path, 'rb').read()
    pat = sys.argv[2] if len(sys.argv) > 2 else None
    seen = set()
    for off, s in extract(data):
        if pat and not re.search(pat, s, re.I):
            continue
        key = s
        if key in seen:
            continue
        seen.add(key)
        print('%08x  %s' % (off, s))
    print('\n[unique %d]' % len(seen))
