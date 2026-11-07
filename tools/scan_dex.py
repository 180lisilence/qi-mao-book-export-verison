#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描所有 dex 的类型名 / 字符串，按关键词过滤"""
import struct, sys, os, re, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dexdump import Dex, mutf8_decode

def load(path):
    return Dex(open(path, 'rb').read())

def types_of(dx):
    return [dx.type_at(i) for i in range(dx.type_ids_size)]

def main():
    root = sys.argv[1]
    pattern = sys.argv[2] if len(sys.argv) > 2 else None
    files = sorted(glob.glob(os.path.join(root, 'classes*.dex')),
                   key=lambda p: int(re.search(r'(\d+)', os.path.basename(p)).group(1))
                   if re.search(r'(\d+)', os.path.basename(p)) else 1)
    hits = {}
    for f in files:
        name = os.path.basename(f)
        try:
            dx = load(f)
        except Exception as e:
            print('!! %s: %s' % (name, e)); continue
        for t in types_of(dx):
            if t is None: continue
            if pattern and not re.search(pattern, t, re.I): continue
            hits.setdefault(t, []).append(name)
    for t in sorted(hits):
        print('%s   <- %s' % (t.replace('\x00', '\\0'), ','.join(hits[t])))
    print('\n[total %d]' % len(hits))

if __name__ == '__main__':
    main()
