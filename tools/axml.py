#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Android Binary XML (AXML) 解析器"""
import struct, sys

RES_STRING_POOL_TYPE = 0x0001
RES_XML_TYPE = 0x0003
RES_XML_START_NAMESPACE = 0x0100
RES_XML_END_NAMESPACE = 0x0101
RES_XML_START_ELEMENT = 0x0102
RES_XML_END_ELEMENT = 0x0103
RES_XML_CDATA_TYPE = 0x0104
RES_XML_RESOURCE_MAP_TYPE = 0x0180

TYPE_REFERENCE = 0x01
TYPE_STRING = 0x03
TYPE_INT_DEC = 0x10
TYPE_INT_HEX = 0x11
TYPE_INT_BOOLEAN = 0x12
TYPE_INT_COLOR_ARGB8 = 0x1c


class AXML:
    def __init__(self, data):
        self.d = data
        self.strings = []
        self.resmap = []
        self.parse()

    def parse(self):
        d = self.d
        t, hs, size = struct.unpack_from('<HHI', d, 0)
        assert t == RES_XML_TYPE, hex(t)
        p = hs
        while p < size:
            ctype, chead, csize = struct.unpack_from('<HHI', d, p)
            if ctype == RES_STRING_POOL_TYPE:
                self.strings = self._string_pool(p)
            elif ctype == RES_XML_RESOURCE_MAP_TYPE:
                cnt = (csize - chead) // 4
                self.resmap = list(struct.unpack_from('<%dI' % cnt, d, p + chead))
            if csize == 0:
                break
            p += csize

    def _string_pool(self, off):
        d = self.d
        (ctype, chead, csize, scount, stylecount, flags,
         strstart, styletart) = struct.unpack_from('<HHIIIIII', d, off)
        out = []
        is_utf8 = (flags & 0x100) != 0
        for i in range(scount):
            so, = struct.unpack_from('<I', d, off + chead + i * 4)
            pos = off + strstart + so
            if is_utf8:
                # u16len (varint), u8len (varint)
                def rv(p):
                    r = 0; s = 0
                    while True:
                        b = d[p]; p += 1
                        r |= (b & 0x7f) << s
                        if not (b & 0x80): break
                        s += 7
                    return r, p
                def rv2(p):
                    # 高位为符号扩展的 16bit 长度
                    b = d[p]; p += 1
                    if b & 0x80:
                        r = ((b & 0x7f) << 8) | d[p]; p += 1
                        if r & 0x8000:
                            r -= 0x10000
                        return r, p
                    return b, p
                ulen, p1 = rv(pos)
                blen, p2 = rv(p1)
                out.append(d[p2:p2 + blen].decode('utf-8', 'replace'))
            else:
                ln, = struct.unpack_from('<H', d, pos)
                out.append(d[pos + 2:pos + 2 + ln * 2].decode('utf-16-le', 'replace'))
        return out

    def _attr_value(self, tv):
        dtype = tv[0]
        data = tv[1]
        if dtype == TYPE_STRING:
            return self.strings[data] if data < len(self.strings) else '<?>'
        if dtype == TYPE_INT_BOOLEAN:
            return 'true' if data != 0 else 'false'
        if dtype == TYPE_REFERENCE:
            return '@0x%x' % data
        if dtype in (TYPE_INT_DEC, TYPE_INT_HEX):
            return hex(data) if dtype == TYPE_INT_HEX else str(data)
        return '0x%x' % data

    def walk(self):
        d = self.d
        t, hs, size = struct.unpack_from('<HHI', d, 0)
        p = hs
        depth = 0
        out = []
        while p < size - 4:
            ctype, chead, csize = struct.unpack_from('<HHI', d, p)
            if csize == 0: break
            if ctype == RES_XML_START_ELEMENT:
                (line, comment, ns, name,
                 attr_start, attr_size, attr_count, id_idx, cls_idx, sty_idx) = \
                    struct.unpack_from('<IIIIHHHHHH', d, p + 8)
                nm = self.strings[name] if name < len(self.strings) else '?'
                attrs = []
                for i in range(attr_count):
                    ap = p + chead + i * attr_size
                    ans, aname, araw = struct.unpack_from('<III', d, ap)
                    _sz, _r0, atype = struct.unpack_from('<HBB', d, ap + 12)
                    adata, = struct.unpack_from('<I', d, ap + 16)
                    ans = ans & 0xFFFFFFFF
                    an = self.strings[aname] if aname < len(self.strings) else '?'
                    nsstr = self.strings[ans] if ans < len(self.strings) else None
                    raw = self.strings[araw] if araw < len(self.strings) else None
                    val = self._attr_value((atype, adata))
                    full = ('%s:%s' % (nsstr, an)) if nsstr else an
                    attrs.append((full, val, raw))
                out.append((depth, 'START', nm, attrs, line))
                depth += 1
            elif ctype == RES_XML_END_ELEMENT:
                depth -= 1
                (line, comment, ns, name) = struct.unpack_from('<IIII', d, p + 8)
                nm = self.strings[name] if name < len(self.strings) else '?'
                out.append((depth, 'END', nm, None, line))
            elif ctype == RES_XML_CDATA_TYPE:
                (line, comment, d_, dt, dd) = struct.unpack_from('<IIBBI', d, p + 8)
                out.append((depth, 'TEXT', self._attr_value((dt, dd)), None, line))
            p += csize
        return out


def main():
    ax = AXML(open(sys.argv[1], 'rb').read())
    filt = sys.argv[2] if len(sys.argv) > 2 else None
    for depth, kind, name, attrs, line in ax.walk():
        if filt and filt.lower() not in (name or '').lower():
            if not attrs: continue
        ind = '  ' * depth
        if kind == 'START':
            print('%s<%s' % (ind, name))
            if attrs:
                for k, v, raw in attrs:
                    extra = '  (raw="%s")' % raw if (raw is not None and raw != v) else ''
                    print('%s    %s = %s%s' % (ind, k, v, extra))
            print('%s>' % ind)
        elif kind == 'END':
            print('%s</%s>' % (ind, name))
        else:
            print('%s%s' % (ind, name))


if __name__ == '__main__':
    main()
