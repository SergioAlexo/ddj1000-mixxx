"""Decode a USBPcap .pcap of the DDJ-1000 into per-endpoint text logs.

usage: python decode_capture.py capture.pcap [outdir]

Writes <outdir>/ep_<addr>.txt with lines "<seconds> <hex payload>" for every data-carrying
packet of the DDJ-1000 (bus device with VID 2B73 PID 0020), skipping isochronous (audio).
Bulk 0x04/0x85 are USB-MIDI (4-byte event packets); 0x06/0x87 are interrupt (jog screens / HID).
"""
import mmap, os, struct, sys
from collections import Counter

path = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(path), 'decoded')
os.makedirs(out, exist_ok=True)

f = open(path, 'rb')
m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
magic = struct.unpack_from('<I', m, 0)[0]
assert magic in (0xa1b2c3d4, 0xa1b23c4d), hex(magic)
nano = magic == 0xa1b23c4d
pos = 24

# pass 1 happens inline: find device address from injected descriptors (idVendor 2B73, idProduct 0020)
ddj = None
files, counts, t0 = {}, Counter(), None
n = len(m)
while pos + 16 <= n:
    sec, frac, incl, orig = struct.unpack_from('<IIII', m, pos)
    pos += 16
    pkt = pos
    pos += incl
    if incl < 27:
        continue
    hlen, irp, status, func, info, bus, dev, ep, ttype, dlen = struct.unpack_from('<H Q I H B H H B B I', m, pkt)
    t = sec + frac / (1e9 if nano else 1e6)
    if t0 is None:
        t0 = t
    data = m[pkt + hlen: pkt + incl]
    if ddj is None and ttype == 2 and len(data) >= 12 and data[0] == 18 and data[1] == 1 \
            and data[8:12] == b'\x73\x2b\x20\x00':
        ddj = (bus, dev)
        print('DDJ-1000 at bus %d device %d' % ddj)
    if ddj is None or (bus, dev) != ddj or ttype == 0 or not data:   # ttype 0 = isochronous
        continue
    key = ep
    fh = files.get(key)
    if fh is None:
        fh = files[key] = open(os.path.join(out, 'ep_%02X_t%d.txt' % (ep, ttype)), 'w')
    fh.write('%.6f %s\n' % (t - t0, data.hex()))
    counts[(ep, ttype)] += 1

for fh in files.values():
    fh.close()
print('endpoint/type -> data packets:')
for (ep, tt), c in sorted(counts.items()):
    print('  0x%02X type %d: %d' % (ep, tt, c))
