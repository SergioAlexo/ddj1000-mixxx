"""Summarise decoded USB-MIDI endpoint logs (output of decode_capture.py).

usage: python midi_summary.py decoded_dir
Prints SysEx messages (all, de-duplicated with counts) and, per direction, the distinct
(status, data1) pairs with counts and the value range.
"""
import os, sys
from collections import Counter, defaultdict

d = sys.argv[1]
CIN_LEN = {2: 2, 3: 3, 5: 1, 6: 2, 7: 3, 8: 3, 9: 3, 0xA: 3, 0xB: 3, 0xC: 2, 0xD: 2, 0xE: 3, 0xF: 1}


def parse(fn):
    """yield (time, bytes) MIDI messages (SysEx reassembled)"""
    sysex, t_sx = None, 0
    for line in open(fn):
        ts, hx = line.split()
        raw = bytes.fromhex(hx)
        for i in range(0, len(raw) - 3, 4):
            cin = raw[i] & 0xF
            b = raw[i + 1:i + 4]
            if cin == 4:
                if sysex is None:
                    sysex, t_sx = bytearray(), float(ts)
                sysex += b
            elif cin in (5, 6, 7) and (sysex is not None or b[0] == 0xF0 or cin != 5 or b[0] == 0xF7):
                n = {5: 1, 6: 2, 7: 3}[cin]
                if sysex is None:
                    sysex, t_sx = bytearray(), float(ts)
                sysex += b[:n]
                yield t_sx, bytes(sysex)
                sysex = None
            elif cin in CIN_LEN:
                yield float(ts), bytes(b[:CIN_LEN[cin]])


for name, label in (('ep_04_t3.txt', 'PC -> DDJ (rekordbox output)'), ('ep_85_t3.txt', 'DDJ -> PC (controller input)')):
    fn = os.path.join(d, name)
    print('=' * 20, label)
    msgs = list(parse(fn))
    print('messages:', len(msgs))
    sx = Counter()
    first = {}
    for t, m in msgs:
        if m[0] == 0xF0:
            sx[m.hex()] += 1
            first.setdefault(m.hex(), t)
    print('SysEx (%d distinct):' % len(sx))
    for h, c in sorted(sx.items(), key=lambda kv: first[kv[0]])[:80]:
        print('  t=%8.3f x%-4d %s' % (first[h], c, h))
    stat = defaultdict(lambda: [0, 255, 0])
    for t, m in msgs:
        if m[0] < 0xF0 and len(m) >= 2:
            k = (m[0], m[1])
            s = stat[k]
            s[0] += 1
            if len(m) > 2:
                s[1] = min(s[1], m[2]); s[2] = max(s[2], m[2])
    print('distinct (status,data1): %d' % len(stat))
    by_status = Counter()
    for (s, _), v in stat.items():
        by_status[s] += v[0]
    for s, c in sorted(by_status.items()):
        print('  status 0x%02X: %d msgs, %d distinct data1' % (s, c, sum(1 for (st, _) in stat if st == s)))
