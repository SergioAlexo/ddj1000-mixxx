#!/usr/bin/env python3
"""Decode the USB configuration + HID report descriptor embedded in a DDJ-1000 main-CPU image."""
import sys, struct
d = open(sys.argv[1], 'rb').read()
cfg = d.find(b'\x09\x02\xa9\x00')
dev = d.find(b'\x12\x01\x00\x02\x00\x00\x00\x40\x73\x2b')
print('device: %s' % d[dev:dev+18].hex(' '))
tot = struct.unpack_from('<H', d, cfg + 2)[0]
p = cfg
CS = {1: 'HEADER', 2: 'IN_JACK/IT', 3: 'OUT_JACK/OT', 4: 'ELEMENT/MIXER', 5: 'SELECTOR', 6: 'FEATURE', 0x0a: 'CLOCK_SRC', 0x0b: 'CLOCK_SEL'}
while p < cfg + tot:
    l, t = d[p], d[p+1]
    b = d[p:p+l]
    if t == 2: s = 'CONFIG total=%d nIf=%d attr=%02x maxpower=%dmA' % (struct.unpack_from('<H', b, 2)[0], b[4], b[7], b[8]*2)
    elif t == 4: s = 'INTERFACE #%d alt=%d nEP=%d class=%02x sub=%02x proto=%02x' % (b[2], b[3], b[4], b[5], b[6], b[7])
    elif t == 5: s = 'ENDPOINT %02x (%s) attr=%02x maxpkt=%d interval=%d' % (b[2], 'IN' if b[2] & 0x80 else 'OUT', b[3], struct.unpack_from('<H', b, 4)[0] & 0x7ff, b[6])
    elif t == 0x21: s = 'HID bcd=%04x country=%d nDesc=%d type=%02x reportLen=%d' % (struct.unpack_from('<H', b, 2)[0], b[4], b[5], b[6], struct.unpack_from('<H', b, 7)[0])
    elif t == 0x0b: s = 'IAD first=%d count=%d class=%02x sub=%02x' % (b[2], b[3], b[4], b[5])
    elif t == 0x24: s = 'CS_INTERFACE %s' % CS.get(b[2], hex(b[2]))
    elif t == 0x25: s = 'CS_ENDPOINT'
    else: s = 'type %02x' % t
    print('  %-60s %s' % (s, b.hex(' ')))
    p += l
# HID report descriptor: search backwards from device desc for the vendor page
rd = d.find(b'\x06\xa0\xff\x09\x01\xa1\x01')
print('\nHID report descriptor @%06x' % rd)
ITEMS = {0x04: 'UsagePage', 0x08: 'Usage', 0xa0: 'Collection', 0xc0: 'EndCollection', 0x14: 'LogMin', 0x24: 'LogMax',
         0x34: 'PhysMin', 0x44: 'PhysMax', 0x74: 'ReportSize', 0x94: 'ReportCount', 0x84: 'ReportID',
         0x80: 'Input', 0x90: 'Output', 0xb0: 'Feature', 0x18: 'UsageMin', 0x28: 'UsageMax', 0x54: 'UnitExp', 0x64: 'Unit'}
q = rd; depth = 0; cur = {}
while True:
    pre = d[q]; sz = [0, 1, 2, 4][pre & 3]; tag = pre & 0xfc
    val = int.from_bytes(d[q+1:q+1+sz], 'little') if sz else 0
    name = ITEMS.get(tag, 'tag%02x' % tag)
    if tag == 0xc0: depth -= 1
    extra = ''
    if tag in (0x80, 0x90, 0xb0):
        extra = '   -> %d x %d bits = %d bytes (id 0x%02x)' % (cur.get(0x94, 0), cur.get(0x74, 0), cur.get(0x94, 0) * cur.get(0x74, 0) // 8, cur.get(0x84, 0))
    print('  %s%-12s %s%s' % ('  ' * depth, name, hex(val) if sz else '', extra))
    cur[tag] = val
    if tag == 0xa0: depth += 1
    q += 1 + sz
    if tag == 0xc0 and depth == 0: break
    if q - rd > 1024: break
