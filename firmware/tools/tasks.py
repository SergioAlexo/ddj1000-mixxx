#!/usr/bin/env python3
"""List µITRON T_CTSK task descriptors (attr, exinf, task, pri, stksz, stk, name*) in a DDJ-1000 SH-2A image.
usage: tasks.py <image> <flash_base_hex> <groups>"""
import struct, sys
d = open(sys.argv[1], 'rb').read(); fbase = int(sys.argv[2], 16); groups = int(sys.argv[3])
mem = {}
for g in range(groups):
    p = 0x10 + g * 0x30
    for t in range(3):
        dst, src, ln = struct.unpack_from('>III', d, p + t * 12)
        if ln and fbase <= src < fbase + len(d): mem[dst] = d[src - fbase:src - fbase + ln]
code = [(b, b + len(v)) for b, v in mem.items()]
def rd(a, n):
    for b, v in mem.items():
        if b <= a < b + len(v): return v[a - b:a - b + n]
def cstr(a):
    s = rd(a, 40)
    return s.split(b'\0')[0].decode('latin1') if s else None
for b, v in sorted(mem.items()):
    for o in range(0, len(v) - 28, 4):
        attr, exinf, task, pri, stksz, stk, name = struct.unpack_from('>7I', v, o)
        if attr & ~0x302 == 0 and any(lo <= task < hi for lo, hi in code) and 0 < pri < 32 and 0x40 <= stksz < 0x10000 and name:
            n = cstr(name)
            if n and n.isprintable() and 2 <= len(n) < 24:
                print('T_CTSK @%08x task=%08x pri=%2d stk=%5x attr=%x name=%r' % (b + o, task, pri, stksz, attr, n))
