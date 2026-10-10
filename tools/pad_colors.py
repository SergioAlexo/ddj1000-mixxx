"""Pad-LED analysis of a decoded DDJ-1000 capture (output of decode_capture.py).

usage: python pad_colors.py decoded_dir [channel_hex=97] [t_from=0]
Prints, for one pad channel, the colour value of every pad note (mode*16 + page*8 + pad) at the end of
the init sweep, every later change with time, and the mode-button / pad-press events seen on the way
in, so colours can be tied to what the user was doing.
"""
import sys
from collections import defaultdict

d = sys.argv[1]
ch = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x97
t_from = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
MODES = ['HOTCUE', 'PADFX1', 'BEATJUMP', 'SAMPLER', 'KEYBOARD', 'PADFX2', 'BEATLOOP', 'KEYSHIFT']


def load(fn):
    msgs = []
    for line in open(fn):
        ts, hx = line.split()
        r = bytes.fromhex(hx)
        for i in range(0, len(r) - 3, 4):
            if r[i] & 15 in (8, 9, 0xB):
                msgs.append((float(ts), bytes(r[i + 1:i + 4])))
    return msgs


out = [(t, m) for t, m in load(d + '/ep_04_t3.txt') if t >= t_from]
inn = [(t, m) for t, m in load(d + '/ep_85_t3.txt') if t >= t_from]

# start of rekordbox traffic: first note-on of the init sweep (0x90 0x40 0x00)
start = next((t for t, m in out if m[0] == 0x90 and m[1] == 0x40), 0)
print('init sweep starts at t=%.3f' % start)

# colour table at +1.5 s after the start of the sweep, then changes
state, changes = {}, []
for t, m in out:
    if m[0] == ch and t >= start:
        if m[1] in state and state[m[1]] != m[2] and t > start + 1.5:
            changes.append((t, m[1], state[m[1]], m[2]))
        state[m[1]] = m[2]
print('\nchannel 0x%02X colour of each pad note at the end (mode: page1 pads 1-8 | page2 pads 1-8)' % ch)
for mode in range(8):
    row = []
    for page in (0, 1):
        row.append(' '.join('%3s' % state.get(mode * 16 + page * 8 + p, '-') for p in range(8)))
    print('  %-9s mode=%d  %s  |  %s' % (MODES[mode], mode, row[0], row[1]))
extra = sorted(n for n in state if n >= 0x80 or (n & 0x0F) > 0x0F)
print('\nchanges after init (%d):' % len(changes))
for t, n, a, b in changes[:120]:
    print('  t=%8.3f note 0x%02X (%s page%d pad%d) %s -> %s' % (t, n, MODES[(n >> 4) & 7], ((n >> 3) & 1) + 1, (n & 7) + 1, a, b))

print('\ncontroller input events of interest (mode buttons, pad presses on this channel family):')
MODEB = {0x1B: 'HOTCUE', 0x1E: 'PADFX1', 0x20: 'BEATJUMP', 0x22: 'SAMPLER', 0x69: 'KEYBOARD', 0x6B: 'PADFX2', 0x6D: 'BEATLOOP', 0x6F: 'KEYSHIFT'}
for t, m in inn:
    if m[0] in (0x90, 0x91, 0x92, 0x93) and m[1] in MODEB and m[2]:
        print('  t=%8.3f deck%d mode button %s' % (t, (m[0] & 0xF) + 1, MODEB[m[1]]))
