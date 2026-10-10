"""Reassemble the chunked jog-display transfers rekordbox sends on interrupt endpoint 0x06.

Packet layout (64 bytes): [deck*16][type][seq][0][total packets, 16 bit LE] + 58 payload bytes.
Types seen: 0x2b artwork (JPEG), 0x2c waveform, 0x2d waveform preview, 0x2f beat grid; 0x21/0x30/0x31... status.
usage: python jog_transfers.py decoded_dir [outdir]   (writes <outdir>/jog_<t>_<deck>_<type>.bin)
"""
import os, sys

d = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else d
rows = [(float(l.split()[0]), bytes.fromhex(l.split()[1])) for l in open(d + '/ep_06_t1.txt')]

BULK = {0x2b: 'artwork', 0x2c: 'waveform', 0x2d: 'preview', 0x2f: 'beatgrid'}
cur = {}
done = []
for t, r in rows:
    deck, typ, seq = r[0] >> 4, r[1], r[2]
    if typ not in BULK:
        continue
    n = r[4] | r[5] << 8
    key = (deck, typ)
    c = cur.get(key)
    if seq == 1 or c is None or c['n'] != n:
        c = cur[key] = {'t': t, 'n': n, 'seq': 0, 'data': bytearray()}
    c['seq'] = seq
    c['data'] += r[6:]
    if seq == n:
        done.append((c['t'], deck, typ, n, bytes(c['data'])))
        del cur[key]

for t, deck, typ, n, data in done:
    name = 'jog_%07.2f_d%d_%s.bin' % (t, deck, BULK[typ])
    open(os.path.join(out, name), 'wb').write(data)
    print('t=%7.2f deck %d %-8s packets=%-3d bytes=%-5d head=%s' % (t, deck, BULK[typ], n, len(data), data[:16].hex()))
