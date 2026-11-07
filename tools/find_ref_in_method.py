#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描 dex 中所有方法体，找出引用了指定符号（子串）的方法"""
import sys, os, glob, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dexdump import Dex, parse_class_data, disasm, CodeItem

def clean(s):
    s = (s or '').replace('\x00', '\\0')
    try: s.encode('utf-8')
    except UnicodeEncodeError: s = s.encode('utf-8','replace').decode('utf-8','replace')
    return s

def scan(dexpath, needle):
    dx = Dex(open(dexpath, 'rb').read())
    n = 0
    for c in dx.class_defs():
        cname = clean(dx.type_at(c['class']))
        fields, direct, virtual = parse_class_data(dx, c['data'])
        for mid, acc, code in direct + virtual:
            if not code: continue
            try:
                items = disasm(dx, CodeItem(dx, code))
            except Exception:
                continue
            hit = [ (o,t) for o,t in items if needle in t ]
            if hit:
                cls, name, rt, params = dx.method_at(mid)
                print('=' * 76)
                print('%s' % dexpath)
                print('  CLASS  : %s' % cname)
                print('  METHOD : %s->%s(%s)%s  [acc=0x%x]' % (
                    clean(cls), clean(name),
                    ','.join(clean(p) for p in params or []), clean(rt), acc))
                for o, t in items:
                    mark = '>>>' if needle in t else '   '
                    print('      %s %04x| %s' % (mark, o, t))
                print()
                n += 1
    return n

if __name__ == '__main__':
    target = sys.argv[1]
    needle = sys.argv[2]
    if os.path.isdir(target):
        files = sorted(glob.glob(os.path.join(target, 'classes*.dex')))
    else:
        files = [target]
    total = 0
    for f in files:
        try:
            total += scan(f, needle)
        except Exception as e:
            print('!! %s: %s' % (f, e))
    print('\n[total methods matched: %d]' % total)
