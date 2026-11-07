#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在指定 dex 中查找类名（支持子串），打印真实类名(repr)并反汇编其方法"""
import sys, os, glob, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dexdump import Dex, parse_class_data, disasm, CodeItem, mutf8_decode

def clean(s):
    if s is None: return 'None'
    return s.replace('\x00', '\\0')

def run(dexpath, needle, deep=True):
    dx = Dex(open(dexpath, 'rb').read())
    found = 0
    for c in dx.class_defs():
        raw = dx.type_at(c['class'])
        if raw is None: continue
        if needle not in raw: continue
        found += 1
        print('=' * 78)
        print('DEX   : %s' % dexpath)
        print('CLASS : %s' % clean(raw))
        print('RAW   : %r' % raw)
        print('SUPER : %s' % clean(dx.type_at(c['super'])))
        ifaces = []
        if c['ifaces']:
            cnt, = __import__('struct').unpack_from('<I', dx.d, c['ifaces'])
            for i in range(cnt):
                t, = __import__('struct').unpack_from('<H', dx.d, c['ifaces'] + 4 + i*2)
                ifaces.append(clean(dx.type_at(t)))
        print('IFACES: %s' % ifaces)
        fields, direct, virtual = parse_class_data(dx, c['data'])
        for mid, acc, code in direct:
            cls, name, rt, params = dx.method_at(mid)
            print('  .method direct [0x%x] %s->%s(%s)%s' % (
                acc, clean(cls), clean(name), ','.join(clean(p) for p in params or []), clean(rt)))
            if code and deep:
                for off, txt in disasm(dx, CodeItem(dx, code)):
                    print('      %04x| %s' % (off, txt))
        for mid, acc, code in virtual:
            cls, name, rt, params = dx.method_at(mid)
            print('  .method virtual [0x%x] %s->%s(%s)%s' % (
                acc, clean(cls), clean(name), ','.join(clean(p) for p in params or []), clean(rt)))
            if code and deep:
                for off, txt in disasm(dx, CodeItem(dx, code)):
                    print('      %04x| %s' % (off, txt))
        print()
    if found == 0:
        print('  (no match in %s)' % dexpath)

if __name__ == '__main__':
    dexpath = sys.argv[1]
    needle = sys.argv[2]
    deep = '--nodisasm' not in sys.argv
    if os.path.isdir(dexpath):
        for f in sorted(glob.glob(os.path.join(dexpath, 'classes*.dex'))):
            run(f, needle, deep)
    else:
        run(dexpath, needle, deep)
