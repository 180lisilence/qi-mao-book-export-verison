#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DEX 字符串/常量完整 dump（修正 MUTF-8 解码 + 反汇编方法字节码）
针对 classes18.dex 这种小型注入 dex
"""
import struct, sys, os

MAGIC = b'dex\n035\x00'

# ---------------- MUTF-8 ----------------
def mutf8_decode(data):
    out = []
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b == 0:
            out.append('\x00'); i += 1; continue
        if b < 0x80:
            out.append(chr(b)); i += 1
        elif b & 0xE0 == 0xC0:
            if i + 1 < n:
                out.append(chr(((b & 0x1F) << 6) | (data[i+1] & 0x3F)))
            i += 2
        elif b & 0xF0 == 0xE0:
            if i + 2 < n:
                out.append(chr(((b & 0x0F) << 12) | ((data[i+1] & 0x3F) << 6) | (data[i+2] & 0x3F)))
            i += 3
        else:
            out.append('?'); i += 1
    return ''.join(out)


def uleb128(d, pos):
    result = 0; shift = 0
    while True:
        b = d[pos]; pos += 1
        result |= (b & 0x7f) << shift
        if not (b & 0x80): break
        shift += 7
    return result, pos

def sleb128(d, pos):
    result = 0; shift = 0
    while True:
        b = d[pos]; pos += 1
        result |= (b & 0x7f) << shift
        shift += 7
        if not (b & 0x80):
            if b & 0x40:
                result -= (1 << shift)
            break
    return result, pos


class Dex:
    def __init__(self, data):
        self.d = data
        assert data[:8] == MAGIC, data[:8]
        self.string_ids_size, = struct.unpack_from('<I', data, 0x38)
        self.string_ids_off,  = struct.unpack_from('<I', data, 0x3c)
        self.type_ids_size,   = struct.unpack_from('<I', data, 0x40)
        self.type_ids_off,    = struct.unpack_from('<I', data, 0x44)
        self.proto_ids_size,  = struct.unpack_from('<I', data, 0x48)
        self.proto_ids_off,   = struct.unpack_from('<I', data, 0x4c)
        self.field_ids_size,  = struct.unpack_from('<I', data, 0x50)
        self.field_ids_off,   = struct.unpack_from('<I', data, 0x54)
        self.method_ids_size, = struct.unpack_from('<I', data, 0x58)
        self.method_ids_off,  = struct.unpack_from('<I', data, 0x5c)
        self.class_defs_size, = struct.unpack_from('<I', data, 0x60)
        self.class_defs_off,  = struct.unpack_from('<I', data, 0x64)

    def str_at(self, idx):
        if idx == 0xFFFFFFFF: return None
        off, = struct.unpack_from('<I', self.d, self.string_ids_off + idx*4)
        ln, p = uleb128(self.d, off)
        return mutf8_decode(self.d[p:p+ln])

    def type_at(self, idx):
        if idx == 0xFFFFFFFF: return None
        didx, = struct.unpack_from('<I', self.d, self.type_ids_off + idx*4)
        return self.str_at(didx)

    def method_at(self, idx):
        c, p, n = struct.unpack_from('<HHI', self.d, self.method_ids_off + idx*8)
        s, rt, po = struct.unpack_from('<III', self.d, self.proto_ids_off + p*12)
        params = []
        if po:
            cnt, = struct.unpack_from('<I', self.d, po)
            for i in range(cnt):
                t, = struct.unpack_from('<H', self.d, po+4+i*2)
                params.append(self.type_at(t))
        return self.type_at(c), self.str_at(n), self.type_at(rt), params

    def field_at(self, idx):
        c, t, n = struct.unpack_from('<HHI', self.d, self.field_ids_off + idx*8)
        return self.type_at(c), self.str_at(n), self.type_at(t)

    def class_defs(self):
        out = []
        for i in range(self.class_defs_size):
            b = self.class_defs_off + i*32
            vals = struct.unpack_from('<IIIIIIII', self.d, b)
            out.append(dict(zip(
                ['class','flags','super','ifaces','source','ann','data','static'], vals)))
        return out


# ---------------- 反汇编 ----------------
OPS = {
 0x00:('nop',0),0x01:('move vA,vB','12x'),0x02:('move/from16 vAA,vBBBB','22x'),
 0x03:('move/16','32x'),0x04:('move-wide','12x'),0x05:('move-wide/from16','22x'),
 0x06:('move-wide/16','32x'),0x07:('move-object vA,vB','12x'),
 0x08:('move-object/from16 vAA,vBBBB','22x'),0x09:('move-object/16','32x'),
 0x0a:('move-result vAA','11x'),0x0b:('move-result-wide vAA','11x'),
 0x0c:('move-result-object vAA','11x'),0x0d:('move-exception vAA','11x'),
 0x0e:('return-void','10x'),0x0f:('return vAA','11x'),
 0x10:('return-wide vAA','11x'),0x11:('return-object vAA','11x'),
 0x12:('const/4 vA,#+B','11n'),0x13:('const/16 vAA,#+BBBB','21s'),
 0x14:('const vAA,#+BBBBBBBB','31i'),0x15:('const/high16 vAA,#+BBBB0000','21ih'),
 0x16:('const-wide/16 vAA,#+BBBB','21s'),0x17:('const-wide/32 vAA,#+BBBBBBBB','31i'),
 0x18:('const-wide vAA,#+BBBBBBBBBBBBBBBB','51l'),
 0x19:('const-wide/high16 vAA,#+BBBB000000000000','21lh'),
 0x1a:('const-string vAA,string@BBBB','21c'),
 0x1b:('const-string/jumbo vAA,string@BBBBBBBB','31c'),
 0x1c:('const-class vAA,type@BBBB','21c'),
 0x1d:('monitor-enter vAA','11x'),0x1e:('monitor-exit vAA','11x'),
 0x1f:('check-cast vAA,type@BBBB','21c'),
 0x20:('instance-of vA,vB,type@CCCC','22c'),
 0x21:('array-length vA,vB','12x'),
 0x22:('new-instance vAA,type@BBBB','21c'),
 0x23:('new-array vA,vB,type@CCCC','22c'),
 0x24:('filled-new-array {vC..}','35c'),0x25:('filled-new-array/range','3rc'),
 0x26:('fill-array-data vAA,+BBBBBBBB','31t'),
 0x27:('throw vAA','11x'),
 0x28:('goto','10t'),0x29:('goto/16','20t'),0x2a:('goto/32','30t'),
 0x2b:('packed-switch vAA,+BBBBBBBB','31t'),
 0x2c:('sparse-switch vAA,+BBBBBBBB','31t'),
 0x2d:('cmpl-float','23x'),0x2e:('cmpg-float','23x'),
 0x2f:('cmpl-double','23x'),0x30:('cmpg-double','23x'),0x31:('cmp-long','23x'),
 0x32:('if-eq vA,vB,+CCCC','22t'),0x33:('if-ne vA,vB,+CCCC','22t'),
 0x34:('if-lt vA,vB,+CCCC','22t'),0x35:('if-ge vA,vB,+CCCC','22t'),
 0x36:('if-gt vA,vB,+CCCC','22t'),0x37:('if-le vA,vB,+CCCC','22t'),
 0x38:('if-eqz vAA,+BBBB','21t'),0x39:('if-nez vAA,+BBBB','21t'),
 0x3a:('if-ltz vAA,+BBBB','21t'),0x3b:('if-gez vAA,+BBBB','21t'),
 0x3c:('if-gtz vAA,+BBBB','21t'),0x3d:('if-lez vAA,+BBBB','21t'),
 0x44:('aget vA,vB,vC','23x'),0x45:('aget-wide','23x'),0x46:('aget-object vA,vB,vC','23x'),
 0x47:('aget-boolean','23x'),0x48:('aget-byte','23x'),0x49:('aget-char','23x'),
 0x4a:('aget-short','23x'),
 0x4b:('aput vA,vB,vC','23x'),0x4c:('aput-wide','23x'),0x4d:('aput-object vA,vB,vC','23x'),
 0x4e:('aput-boolean','23x'),0x4f:('aput-byte','23x'),0x50:('aput-char','23x'),
 0x51:('aput-short','23x'),
 0x52:('iget vA,vB,field@CCCC','22c'),0x53:('iget-wide','22c'),
 0x54:('iget-object vA,vB,field@CCCC','22c'),0x55:('iget-boolean','22c'),
 0x56:('iget-byte','22c'),0x57:('iget-char','22c'),0x58:('iget-short','22c'),
 0x59:('iput vA,vB,field@CCCC','22c'),0x5a:('iput-wide','22c'),
 0x5b:('iput-object vA,vB,field@CCCC','22c'),0x5c:('iput-boolean','22c'),
 0x5d:('iput-byte','22c'),0x5e:('iput-char','22c'),0x5f:('iput-short','22c'),
 0x60:('sget vAA,field@BBBB','21c'),0x61:('sget-wide','21c'),
 0x62:('sget-object vAA,field@BBBB','21c'),0x63:('sget-boolean','21c'),
 0x64:('sget-byte','21c'),0x65:('sget-char','21c'),0x66:('sget-short','21c'),
 0x67:('sput vAA,field@BBBB','21c'),0x68:('sput-wide','21c'),
 0x69:('sput-object vAA,field@BBBB','21c'),0x6a:('sput-boolean','21c'),
 0x6b:('sput-byte','21c'),0x6c:('sput-char','21c'),0x6d:('sput-short','21c'),
 0x6e:('invoke-virtual {..},meth@BBBB','35c'),
 0x6f:('invoke-super {..},meth@BBBB','35c'),
 0x70:('invoke-direct {..},meth@BBBB','35c'),
 0x71:('invoke-static {..},meth@BBBB','35c'),
 0x72:('invoke-interface {..},meth@BBBB','35c'),
 0x74:('invoke-virtual/range','3rc'),0x75:('invoke-super/range','3rc'),
 0x76:('invoke-direct/range','3rc'),0x77:('invoke-static/range','3rc'),
 0x78:('invoke-interface/range','3rc'),
 0x7b:('neg-int','12x'),0x7c:('not-int','12x'),0x7d:('neg-long','12x'),
 0x7e:('not-long','12x'),0x7f:('neg-float','12x'),0x80:('neg-double','12x'),
 0x81:('int-to-long','12x'),0x82:('int-to-float','12x'),0x83:('int-to-double','12x'),
 0x84:('long-to-int','12x'),0x85:('long-to-float','12x'),0x86:('long-to-double','12x'),
 0x87:('float-to-int','12x'),0x88:('float-to-long','12x'),0x89:('float-to-double','12x'),
 0x8a:('double-to-int','12x'),0x8b:('double-to-long','12x'),0x8c:('double-to-float','12x'),
 0x8d:('int-to-byte','12x'),0x8e:('int-to-char','12x'),0x8f:('int-to-short','12x'),
 0x90:('add-int vA,vB,vC','23x'),0x91:('sub-int','23x'),0x92:('mul-int','23x'),
 0x93:('div-int','23x'),0x94:('rem-int','23x'),0x95:('and-int','23x'),
 0x96:('or-int','23x'),0x97:('xor-int','23x'),0x98:('shl-int','23x'),
 0x99:('shr-int','23x'),0x9a:('ushr-int','23x'),
 0x9b:('add-long','23x'),0x9c:('sub-long','23x'),0x9d:('mul-long','23x'),
 0x9e:('div-long','23x'),0x9f:('rem-long','23x'),0xa0:('and-long','23x'),
 0xa1:('or-long','23x'),0xa2:('xor-long','23x'),0xa3:('shl-long','23x'),
 0xa4:('shr-long','23x'),0xa5:('ushr-long','23x'),
 0xa6:('add-float','23x'),0xa7:('sub-float','23x'),0xa8:('mul-float','23x'),
 0xa9:('div-float','23x'),0xaa:('rem-float','23x'),
 0xab:('add-double','23x'),0xac:('sub-double','23x'),0xad:('mul-double','23x'),
 0xae:('div-double','23x'),0xaf:('rem-double','23x'),
 0xb0:('add-int/2addr vA,vB','12x'),0xb1:('sub-int/2addr','12x'),
 0xb2:('mul-int/2addr','12x'),0xb3:('div-int/2addr','12x'),0xb4:('rem-int/2addr','12x'),
 0xb5:('and-int/2addr','12x'),0xb6:('or-int/2addr','12x'),0xb7:('xor-int/2addr','12x'),
 0xb8:('shl-int/2addr','12x'),0xb9:('shr-int/2addr','12x'),0xba:('ushr-int/2addr','12x'),
 0xbb:('add-long/2addr','12x'),0xbc:('sub-long/2addr','12x'),0xbd:('mul-long/2addr','12x'),
 0xbe:('div-long/2addr','12x'),0xbf:('rem-long/2addr','12x'),0xc0:('and-long/2addr','12x'),
 0xc1:('or-long/2addr','12x'),0xc2:('xor-long/2addr','12x'),0xc3:('shl-long/2addr','12x'),
 0xc4:('shr-long/2addr','12x'),0xc5:('ushr-long/2addr','12x'),
 0xc6:('add-float/2addr','12x'),0xc7:('sub-float/2addr','12x'),0xc8:('mul-float/2addr','12x'),
 0xc9:('div-float/2addr','12x'),0xca:('rem-float/2addr','12x'),
 0xcb:('add-double/2addr','12x'),0xcc:('sub-double/2addr','12x'),0xcd:('mul-double/2addr','12x'),
 0xce:('div-double/2addr','12x'),0xcf:('rem-double/2addr','12x'),
 0xd0:('add-int/lit16 vA,vB,#+CCCC','22s'),0xd1:('rsub-int','22s'),
 0xd2:('mul-int/lit16','22s'),0xd3:('div-int/lit16','22s'),0xd4:('rem-int/lit16','22s'),
 0xd5:('and-int/lit16','22s'),0xd6:('or-int/lit16','22s'),0xd7:('xor-int/lit16','22s'),
 0xd8:('add-int/lit8 vA,vB,#+CC','22b'),0xd9:('rsub-int/lit8','22b'),
 0xda:('mul-int/lit8','22b'),0xdb:('div-int/lit8','22b'),0xdc:('rem-int/lit8','22b'),
 0xdd:('and-int/lit8','22b'),0xde:('or-int/lit8','22b'),0xdf:('xor-int/lit8','22b'),
 0xe0:('shl-int/lit8','22b'),0xe1:('shr-int/lit8','22b'),0xe2:('ushr-int/lit8','22b'),
}
INVOKE = {0x6e,0x6f,0x70,0x71,0x72,0x74,0x75,0x76,0x77,0x78}
CONST_STR = {0x1a,0x1b}
FIELD_REF = {0x52,0x53,0x54,0x55,0x56,0x57,0x58,0x59,0x5a,0x5b,0x5c,0x5d,0x5e,0x5f,
             0x60,0x61,0x62,0x63,0x64,0x65,0x66,0x67,0x68,0x69,0x6a,0x6b,0x6c,0x6d}
TYPE_REF = {0x1c,0x1f,0x20,0x22,0x23,0x24,0x25}


class CodeItem:
    def __init__(self, dx, off):
        d = dx.d
        self.registers_size, = struct.unpack_from('<H', d, off)
        self.ins_size,  = struct.unpack_from('<H', d, off+2)
        self.outs_size, = struct.unpack_from('<H', d, off+4)
        self.tries_size,= struct.unpack_from('<H', d, off+6)
        self.debug_off, = struct.unpack_from('<I', d, off+8)
        self.insns_size,= struct.unpack_from('<I', d, off+12)
        self.insns_off = off + 16
        self.dx = dx


def disasm(dx, ci):
    d = dx.d
    out = []
    p = ci.insns_off
    end = ci.insns_off + ci.insns_size*2
    while p < end:
        bu = d[p] | (d[p+1] << 8)
        op = bu & 0xFF
        base = p
        if op == 0x00 and (bu >> 8) != 0:
            # payload
            kind = bu >> 8
            txt = '  ; payload %s' % {0x100:'fill-array-data',0x200:'packed-switch',
                                      0x300:'sparse-switch'}.get(kind, hex(kind))
            out.append((base, txt))
            p += 2 + ((struct.unpack_from('<H', d, p+2)[0]-2)*2 if kind==0x100 else 0)
            if kind == 0x100:
                esize, = struct.unpack_from('<H', d, p+2)
                cnt, = struct.unpack_from('<I', d, p+4)
                p += 8 + esize*cnt
                continue
            elif kind == 0x200:
                cnt, = struct.unpack_from('<H', d, p+2)
                p += 4 + cnt*4
                continue
            elif kind == 0x300:
                cnt, = struct.unpack_from('<H', d, p+2)
                p += 4 + cnt*8
                continue
            else:
                p += 2; continue
        name, fmt = OPS.get(op, ('unknown-0x%02x' % op, '10x'))
        args = []
        # parse per format
        if fmt == '10x':
            p += 2
        elif fmt == '11x':
            a = d[p+1]; p += 2; args = ['v%d' % a]
        elif fmt == '11n':
            a = d[p+1] & 0xF; b = (d[p+1] >> 4) & 0xF; p += 2
            args = ['v%d' % a, '#%d' % (b - (16 if b > 7 else 0))]
        elif fmt == '12x':
            a = d[p+1] & 0xF; b = (d[p+1] >> 4) & 0xF; p += 2
            args = ['v%d' % a, 'v%d' % b]
        elif fmt == '21c':
            aa = d[p+1]
            idx, = struct.unpack_from('<H', d, p+2)
            p += 4
            if op in CONST_STR:
                args = ['v%d' % aa, '"%s"' % clean(dx.str_at(idx))]
            elif op in TYPE_REF:
                args = ['v%d' % aa, clean(dx.type_at(idx))]
            else:
                args = ['v%d' % aa, 'field@%d %s' % (idx, ' '.join(dx.field_at(idx)))]
        elif fmt == '31c':
            aa = d[p+1]
            idx, = struct.unpack_from('<I', d, p+2)
            p += 6
            args = ['v%d' % aa, '"%s"' % clean(dx.str_at(idx))]
        elif fmt == '22c':
            a = d[p+1] & 0xF; b = (d[p+1] >> 4) & 0xF
            idx, = struct.unpack_from('<H', d, p+2)
            p += 4
            if op in TYPE_REF:
                args = ['v%d' % a, 'v%d' % b, clean(dx.type_at(idx))]
            else:
                c, n, t = dx.field_at(idx)
                args = ['v%d' % a, 'v%d' % b, '%s->%s:%s' % (clean(c), clean(n), clean(t))]
        elif fmt == '21s':
            aa = d[p+1]
            v, = struct.unpack_from('<h', d, p+2)
            p += 4; args = ['v%d' % aa, '#%d' % v]
        elif fmt == '21t':
            aa = d[p+1]
            v, = struct.unpack_from('<h', d, p+2)
            p += 4; args = ['v%d' % aa, '+%d' % v]
        elif fmt == '21ih':
            aa = d[p+1]
            v, = struct.unpack_from('<H', d, p+2)
            p += 4; args = ['v%d' % aa, '#0x%X' % (v << 16)]
        elif fmt == '21lh':
            aa = d[p+1]
            v, = struct.unpack_from('<H', d, p+2)
            p += 4; args = ['v%d' % aa, '#0x%X' % (v << 48)]
        elif fmt == '31i':
            aa = d[p+1]
            v, = struct.unpack_from('<i', d, p+2)
            p += 6; args = ['v%d' % aa, '#%d (0x%x)' % (v, v & 0xFFFFFFFF)]
        elif fmt == '51l':
            aa = d[p+1]
            v, = struct.unpack_from('<q', d, p+2)
            p += 10; args = ['v%d' % aa, '#%d (0x%x)' % (v, v & 0xFFFFFFFFFFFFFFFF)]
        elif fmt == '31t':
            aa = d[p+1]
            v, = struct.unpack_from('<i', d, p+2)
            p += 6; args = ['v%d' % aa, '+%d' % v]
        elif fmt == '22x':
            aa = d[p+1]
            bb, = struct.unpack_from('<H', d, p+2)
            p += 4; args = ['v%d' % aa, 'v%d' % bb]
        elif fmt == '32x':
            a, = struct.unpack_from('<H', d, p+2)
            b, = struct.unpack_from('<I', d, p+4)
            p += 8; args = ['v%d' % a, 'v%d' % b]
        elif fmt == '23x':
            aa = d[p+1]; bb = d[p+2]; cc = d[p+3]
            p += 4; args = ['v%d' % aa, 'v%d' % bb, 'v%d' % cc]
        elif fmt == '22t':
            a = d[p+1] & 0xF; b = (d[p+1] >> 4) & 0xF
            v, = struct.unpack_from('<h', d, p+2)
            p += 4; args = ['v%d' % a, 'v%d' % b, '+%d' % v]
        elif fmt == '22s':
            a = d[p+1] & 0xF; b = (d[p+1] >> 4) & 0xF
            v, = struct.unpack_from('<h', d, p+2)
            p += 4; args = ['v%d' % a, 'v%d' % b, '#%d' % v]
        elif fmt == '22b':
            aa = d[p+1]; bb = d[p+2]; cc = struct.unpack_from('<b', d, p+3)[0]
            p += 4; args = ['v%d' % aa, 'v%d' % bb, '#%d' % cc]
        elif fmt == '35c':
            cnt = (d[p+1] >> 4) & 0xF
            regs = [d[p+1] & 0xF, (d[p+2] >> 4) & 0xF, d[p+2] & 0xF,
                    (d[p+3] >> 4) & 0xF, d[p+3] & 0xF][:cnt]
            idx, = struct.unpack_from('<H', d, p+4)
            p += 6
            if op in INVOKE:
                c, n, rt, params = dx.method_at(idx)
                args = ['{%s}' % ','.join('v%d' % r for r in regs),
                        '%s->%s(%s)%s' % (clean(c), clean(n), ','.join(params or []), clean(rt))]
            else:
                args = ['{%s}' % ','.join('v%d' % r for r in regs), clean(dx.type_at(idx))]
        elif fmt == '3rc':
            cnt = d[p+1]
            aa, = struct.unpack_from('<H', d, p+2)
            idx, = struct.unpack_from('<H', d, p+4)
            p += 6
            if op in INVOKE:
                c, n, rt, params = dx.method_at(idx)
                args = ['{v%d..v%d}' % (aa, aa+cnt-1),
                        '%s->%s(%s)%s' % (clean(c), clean(n), ','.join(params or []), clean(rt))]
            else:
                args = ['{v%d..v%d}' % (aa, aa+cnt-1), clean(dx.type_at(idx))]
        elif fmt == '10t':
            v = struct.unpack_from('<b', d, p+1)[0]
            p += 2; args = ['+%d' % v]
        elif fmt == '20t':
            v, = struct.unpack_from('<h', d, p+2)
            p += 4; args = ['+%d' % v]
        elif fmt == '30t':
            v, = struct.unpack_from('<i', d, p+2)
            p += 6; args = ['+%d' % v]
        else:
            p += 2
        out.append((base, '%-28s %s' % (name, ' '.join(str(a) for a in args))))
    return out


def parse_class_data(dx, off):
    """返回 (fields, direct_methods, virtual_methods)"""
    d = dx.d
    if off == 0: return [], [], []
    sf, im, dm, vm = 0, 0, 0, 0
    p = off
    sf, p = uleb128(d, p); im, p = uleb128(d, p)
    dm, p = uleb128(d, p); vm, p = uleb128(d, p)
    def read_enc(p, n, prev_static, prev_inst):
        fields = []
        prev = 0
        for _ in range(n):
            delta, p = uleb128(d, p)
            acc, p = uleb128(d, p)
            prev += delta
            fields.append((prev, acc))
        return fields, p
    st_fields, p = read_enc(p, sf, 0, 0)
    inst_fields, p = read_enc(p, im, 0, 0)
    direct = []
    prev = 0
    for _ in range(dm):
        delta, p = uleb128(d, p)
        acc, p = uleb128(d, p)
        code, p = uleb128(d, p)
        prev += delta
        direct.append((prev, acc, code))
    virtual = []
    prev = 0
    for _ in range(vm):
        delta, p = uleb128(d, p)
        acc, p = uleb128(d, p)
        code, p = uleb128(d, p)
        prev += delta
        virtual.append((prev, acc, code))
    return (st_fields + inst_fields), direct, virtual


def clean(s):
    if s is None: return 'None'
    return s.replace('\x00','\\0')

def main():
    path = sys.argv[1]
    only = sys.argv[2] if len(sys.argv) > 2 else None
    dx = Dex(open(path, 'rb').read())
    print('### STRING TABLE (%d) ###' % dx.string_ids_size)
    for i in range(dx.string_ids_size):
        s = dx.str_at(i)
        print('[%5d] %s' % (i, clean(s)))
    print()
    for c in dx.class_defs():
        cname = clean(dx.type_at(c['class']))
        if only and only not in cname:
            continue
        print('=' * 78)
        print('CLASS %s  super=%s' % (cname, clean(dx.type_at(c['super']))))
        fields, direct, virtual = parse_class_data(dx, c['data'])
        for mid, acc, code in direct + virtual:
            cls, name, rt, params = dx.method_at(mid)
            cls=clean(cls); name=clean(name); rt=clean(rt); params=[clean(x) for x in (params or [])]
            print('  .method %s %s->%s(%s)%s  [acc=0x%x]' % (
                'direct' if (mid, acc, code) in direct else 'virtual',
                cls, name, ','.join(params or []), rt, acc))
            if code:
                ci = CodeItem(dx, code)
                for off, txt in disasm(dx, ci):
                    print('      %04x| %s' % (off, txt))
            print()

if __name__ == '__main__':
    main()
