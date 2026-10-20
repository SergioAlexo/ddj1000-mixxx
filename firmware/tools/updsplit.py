#!/usr/bin/env python3
"""Split a Pioneer DJ DDJ-1000 *.upd firmware container into component images.

Layout (reconstructed from DDJUpdate.exe sub_419280 / sub_4184d0):
  0x00  char[16]  product   "DDJ-1000        "
  0x10  char[16]  version   "Ver.112         "
  0x20  u32 LE    sum of all payload sizes
  0x24  entries[12]:
        +0x00 char[15] name      "DDJ-1000 USB1  "
        +0x0F char     flag      'Y' / 'N'
        +0x10 char[16] version   "Ver.1120        " (4 digits, packed as BCD-ish nibbles by updater)
        +0x20 u32 LE   size
        +0x24 u8[size] payload
        +size u16 LE   CRC-16/XMODEM(payload)  (poly 0x1021, init 0, no reflect, xorout 0)
"""
import struct, sys, os, binascii, hashlib
d = open(sys.argv[1], 'rb').read(); out = sys.argv[2] if len(sys.argv) > 2 else None
print('product=%r version=%r payload_total=0x%x' % (d[:16].decode().strip(), d[16:32].decode().strip(), struct.unpack_from('<I', d, 32)[0]))
p = 36; ok = True; total = 0
print('%-8s %-16s %s %-9s %-9s %-6s %-6s %s' % ('offset', 'name', 'F', 'version', 'size', 'crc', 'calc', 'sha256'))
while p < len(d):
    name = d[p:p+15].decode().strip(); flag = chr(d[p+15]); ver = d[p+16:p+32].decode().strip()
    size = struct.unpack_from('<I', d, p+32)[0]; data = d[p+36:p+36+size]
    crc = struct.unpack_from('<H', d, p+36+size)[0]; calc = binascii.crc_hqx(data, 0)
    ok &= crc == calc; total += size
    print('0x%06x %-16s %s %-9s 0x%06x  %04x   %04x%s %s' % (p, name, flag, ver, size, crc, calc, '' if crc == calc else ' BAD', hashlib.sha256(data).hexdigest()[:16]))
    if out:
        open(os.path.join(out, '%s_%s.bin' % (name.split(' ', 1)[1].strip(), ver)), 'wb').write(data)
    p += 38 + size
assert p == len(d), 'trailing garbage'
assert total == struct.unpack_from('<I', d, 32)[0], 'payload_total mismatch'
print('all CRCs OK' if ok else 'CRC FAILURES'); sys.exit(0 if ok else 1)
