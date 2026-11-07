#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
轻量 DEX 解析器：提取字符串、类型、方法、类定义
不依赖 Java / 第三方库
"""
import struct, sys, os

MAGIC = b'dex\n035\x00'

class Dex:
    def __init__(self, data):
        self.d = data
        if data[:8] != MAGIC:
            raise ValueError('not a dex035 file: %r' % data[:8])
        self.file_size, = struct.unpack_from('<I', data, 0x20)
        self.header_size, = struct.unpack_from('<I', data, 0x24)
        (self.map_off,) = struct.unpack_from('<I', data, 0x34)
        self.string_ids_size, = struct.unpack_from('<I', data, 0x38)
        self.string_ids_off, = struct.unpack_from('<I', data, 0x3c)
        self.type_ids_size, = struct.unpack_from('<I', data, 0x40)
        self.type_ids_off, = struct.unpack_from('<I', data, 0x44)
        self.proto_ids_size, = struct.unpack_from('<I', data, 0x48)
        self.proto_ids_off, = struct.unpack_from('<I', data, 0x4c)
        self.field_ids_size, = struct.unpack_from('<I', data, 0x50)
        self.field_ids_off, = struct.unpack_from('<I', data, 0x54)
        self.method_ids_size, = struct.unpack_from('<I', data, 0x58)
        self.method_ids_off, = struct.unpack_from('<I', data, 0x5c)
        self.class_defs_size, = struct.unpack_from('<I', data, 0x60)
        self.class_defs_off, = struct.unpack_from('<I', data, 0x64)

    # --- string ---
    def string_at(self, idx):
        off, = struct.unpack_from('<I', self.d, self.string_ids_off + idx * 4)
        # uleb128 length
        pos = off
        result = 0
        shift = 0
        while True:
            b = self.d[pos]
            result |= (b & 0x7f) << shift
            pos += 1
            if not (b & 0x80):
                break
            shift += 7
        n = result
        raw = self.d[pos:pos + n]
        # MUTF-8 -> approx utf8
        try:
            return raw.decode('utf-8', 'replace')
        except Exception:
            return repr(raw)

    def strings(self):
        return [self.string_at(i) for i in range(self.string_ids_size)]

    def type_name(self, idx):
        if idx == 0xFFFFFFFF:
            return None
        didx, = struct.unpack_from('<I', self.d, self.type_ids_off + idx * 4)
        return self.string_at(didx)

    def types(self):
        return [self.type_name(i) for i in range(self.type_ids_size)]

    def field(self, idx):
        c, t, n = struct.unpack_from('<HHI', self.d, self.field_ids_off + idx * 8)
        return (self.type_name(c), self.type_name(t), self.string_at(n))

    def method(self, idx):
        c, p, n = struct.unpack_from('<HHI', self.d, self.method_ids_off + idx * 8)
        return (self.type_name(c), self.string_at(n), self.proto(p))

    def proto(self, idx):
        s, rt, po = struct.unpack_from('<III', self.d, self.proto_ids_off + idx * 12)
        params = []
        if po:
            cnt, = struct.unpack_from('<I', self.d, po)
            for i in range(cnt):
                tidx, = struct.unpack_from('<H', self.d, po + 4 + i * 2)
                params.append(self.type_name(tidx))
        return self.type_name(rt), params

    def class_defs(self):
        out = []
        for i in range(self.class_defs_size):
            base = self.class_defs_off + i * 32
            (class_idx, access_flags, super_idx, ifaces_off,
             src_idx, ann_off, data_off, static_off) = struct.unpack_from('<IIIIIIII', self.d, base)
            out.append({
                'idx': i,
                'class': self.type_name(class_idx),
                'flags': access_flags,
                'super': self.type_name(super_idx) if super_idx != 0xFFFFFFFF else None,
                'source': self.string_at(src_idx) if src_idx != 0xFFFFFFFF else None,
                'data_off': data_off,
            })
        return out

    def access_str(self, f):
        m = []
        if f & 0x1: m.append('PUBLIC')
        if f & 0x2: m.append('PRIVATE')
        if f & 0x4: m.append('PROTECTED')
        if f & 0x8: m.append('STATIC')
        if f & 0x10: m.append('FINAL')
        if f & 0x200: m.append('INTERFACE')
        if f & 0x400: m.append('ABSTRACT')
        if f & 0x20000: m.append('ANNOTATION')
        if f & 0x10000: m.append('ENUM')
        return ' '.join(m)


def main():
    path = sys.argv[1]
    data = open(path, 'rb').read()
    dx = Dex(data)
    print('=' * 70)
    print('FILE :', path)
    print('size :', len(data), 'declared', dx.file_size)
    print('strings:', dx.string_ids_size, 'types:', dx.type_ids_size,
          'methods:', dx.method_ids_size, 'fields:', dx.field_ids_size,
          'classes:', dx.class_defs_size)
    print('=' * 70)

    print('\n--- CLASS DEFS (%d) ---' % dx.class_defs_size)
    for c in dx.class_defs():
        print('  %s  [super=%s] [src=%s] %s' % (
            c['class'], c['super'], c['source'], dx.access_str(c['flags'])))

    print('\n--- METHODS REFERENCED (%d) ---' % dx.method_ids_size)
    for i in range(dx.method_ids_size):
        cls, name, (rt, params) = dx.method(i)
        print('  %s.%s(%s)%s' % (cls, name, ','.join(params or []), rt))

    print('\n--- FIELDS REFERENCED (%d) ---' % dx.field_ids_size)
    for i in range(dx.field_ids_size):
        c, t, n = dx.field(i)
        print('  %s.%s : %s' % (c, n, t))

    print('\n--- STRING TABLE (%d) ---' % dx.string_ids_size)
    for i, s in enumerate(dx.strings()):
        print('  [%5d] %s' % (i, s))


if __name__ == '__main__':
    main()
