"""Replay part of a recorded rekordbox session to the DDJ-1000 (Windows, winmm), to find out
which startup messages change how the unit looks.  Close Mixxx and rekordbox first.

usage: python replay_rekordbox.py decoded_dir stage [t_from=61.0] [t_to=64.0]
stages:
  pads     only pad-channel writes (0x97-0x9E) - what a plain mapping sends
  globals  only the non-pad channel messages (0x90-0x96, 0x9F, 0xB0-0xBF) of the same window
  undoc    only the undocumented 0x9F 0x40-0x4E and 0xBF messages
  all      both, in recorded order
Messages are short MIDI only (no SysEx), paced like the recording.
"""
import ctypes, sys, time
from ctypes import wintypes

d, stage = sys.argv[1], sys.argv[2]
t_from = float(sys.argv[3]) if len(sys.argv) > 3 else 61.0
t_to = float(sys.argv[4]) if len(sys.argv) > 4 else 64.0

msgs = []
for line in open(d + '/ep_04_t3.txt'):
    ts, hx = line.split()
    t = float(ts)
    if not (t_from <= t <= t_to):
        continue
    r = bytes.fromhex(hx)
    for i in range(0, len(r) - 3, 4):
        cin = r[i] & 15
        if cin in (8, 9, 0xB):
            m = r[i + 1:i + 4]
            is_pad = 0x97 <= m[0] <= 0x9E
            if m[0] == 0xB0 and m[1] == 2 or m[0] == 0xB1 and m[1] == 2:
                continue                                   # level meters
            if stage == 'pads' and not is_pad or stage == 'globals' and is_pad:
                continue
            if stage == 'undoc' and not (m[0] == 0xBF or m[0] == 0x9F and m[1] >= 0x40):
                continue
            msgs.append((t, m[0] | m[1] << 8 | m[2] << 16))
print('%d messages in %.1f-%.1f s, stage %s' % (len(msgs), t_from, t_to, stage))

winmm = ctypes.WinDLL('winmm')


class CAPS(ctypes.Structure):
    _fields_ = [('mid', wintypes.WORD), ('pid', wintypes.WORD), ('ver', wintypes.UINT), ('name', ctypes.c_wchar * 32),
                ('tech', wintypes.WORD), ('voices', wintypes.WORD), ('notes', wintypes.WORD), ('mask', wintypes.WORD),
                ('support', wintypes.DWORD)]


dev = None
for i in range(winmm.midiOutGetNumDevs()):
    c = CAPS()
    winmm.midiOutGetDevCapsW(i, ctypes.byref(c), ctypes.sizeof(c))
    print('  out %d: %s' % (i, c.name))
    if 'DDJ-1000' in c.name and dev is None:
        dev = i
if dev is None:
    sys.exit('DDJ-1000 output not found')
h = wintypes.HANDLE()
r = winmm.midiOutOpen(ctypes.byref(h), dev, 0, 0, 0)
if r:
    sys.exit('midiOutOpen failed (%d) - is Mixxx/rekordbox still running?' % r)
t0 = msgs[0][0]
start = time.perf_counter()
for t, packed in msgs:
    while time.perf_counter() - start < t - t0:
        pass
    winmm.midiOutShortMsg(h, packed)
winmm.midiOutClose(h)
print('done')
