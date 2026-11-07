#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描所有 dex 的字符串表 / 类型表，按正则过滤"""
import sys, os, glob, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dexdump import Dex

def clean(s):
    s = (s or '').replace('\x00', '\\0')
    try:
        s.encode('utf-8')
    except UnicodeEncodeError:
        s = s.encode('utf-8', 'replace').decode('utf-8', 'replace')
    return s

def main():
    root, pat = sys.argv[1], sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else 'str'   # str | type
    rx = re.compile(pat, re.I)
    for f in sorted(glob.glob(os.path.join(root, 'classes*.dex'))):
        dx = Dex(open(f, 'rb').read())
        hits = []
        if mode == 'str':
            for i in range(dx.string_ids_size):
                s = dx.str_at(i)
                if s and rx.search(s):
                    hits.append(clean(s))
        else:
            for i in range(dx.type_ids_size):
                t = dx.type_at(i)
                if t and rx.search(t):
                    hits.append(clean(t))
        if hits:
            print('### %s  (%d hits)' % (os.path.basename(f), len(hits)))
            seen = set()
            for h in hits:
                if h in seen: continue
                seen.add(h)
                print('   ', h)

if __name__ == '__main__':
    main()
