"""Send short MIDI messages to the DDJ-1000 (Windows winmm).  Close Mixxx and rekordbox first.
usage: python midi_send.py 90 5D 7F [95 00 01 ...]     (hex bytes, groups of three)"""
import ctypes, sys
from ctypes import wintypes

winmm = ctypes.WinDLL('winmm')


class CAPS(ctypes.Structure):
    _fields_ = [('mid', wintypes.WORD), ('pid', wintypes.WORD), ('ver', wintypes.UINT), ('name', ctypes.c_wchar * 32),
                ('tech', wintypes.WORD), ('voices', wintypes.WORD), ('notes', wintypes.WORD), ('mask', wintypes.WORD),
                ('support', wintypes.DWORD)]


dev = None
for i in range(winmm.midiOutGetNumDevs()):
    c = CAPS()
    winmm.midiOutGetDevCapsW(i, ctypes.byref(c), ctypes.sizeof(c))
    if 'DDJ-1000' in c.name:
        dev = i
if dev is None:
    sys.exit('DDJ-1000 output not found')
h = wintypes.HANDLE()
if winmm.midiOutOpen(ctypes.byref(h), dev, 0, 0, 0):
    sys.exit('midiOutOpen failed - is Mixxx/rekordbox still running?')
b = [int(x, 16) for x in sys.argv[1:]]
for i in range(0, len(b) - 2, 3):
    winmm.midiOutShortMsg(h, b[i] | b[i + 1] << 8 | b[i + 2] << 16)
    print('sent %02X %02X %02X' % tuple(b[i:i + 3]))
winmm.midiOutClose(h)
