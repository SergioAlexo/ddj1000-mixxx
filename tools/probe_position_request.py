"""Which startup messages make the DDJ-1000 report its knob/fader positions?
Close Mixxx and rekordbox first.  usage: python probe_position_request.py"""
import ctypes, sys, time
from ctypes import wintypes

winmm = ctypes.WinDLL('winmm')
CALLBACK_FUNCTION = 0x30000
MIM_DATA = 0x3C3


class OCAPS(ctypes.Structure):
    _fields_ = [('mid', wintypes.WORD), ('pid', wintypes.WORD), ('ver', wintypes.UINT), ('name', ctypes.c_wchar * 32),
                ('tech', wintypes.WORD), ('voices', wintypes.WORD), ('notes', wintypes.WORD), ('mask', wintypes.WORD),
                ('support', wintypes.DWORD)]


class ICAPS(ctypes.Structure):
    _fields_ = [('mid', wintypes.WORD), ('pid', wintypes.WORD), ('ver', wintypes.UINT), ('name', ctypes.c_wchar * 32),
                ('support', wintypes.DWORD)]


def find(num, caps_t, getcaps):
    for i in range(num()):
        c = caps_t()
        getcaps(i, ctypes.byref(c), ctypes.sizeof(c))
        if 'DDJ-1000' in c.name:
            return i
    sys.exit('DDJ-1000 not found')


received = []
CB = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.UINT, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t)


def on_midi(h, msg, inst, p1, p2):
    if msg == MIM_DATA:
        received.append(p1 & 0xFFFFFF)


cb = CB(on_midi)
hin, hout = wintypes.HANDLE(), wintypes.HANDLE()
r = winmm.midiInOpen(ctypes.byref(hin), find(winmm.midiInGetNumDevs, ICAPS, winmm.midiInGetDevCapsW), cb, 0, CALLBACK_FUNCTION)
if r:
    sys.exit('midiInOpen failed %d (Mixxx/rekordbox still open?)' % r)
r = winmm.midiOutOpen(ctypes.byref(hout), find(winmm.midiOutGetNumDevs, OCAPS, winmm.midiOutGetDevCapsW), 0, 0, 0)
if r:
    sys.exit('midiOutOpen failed %d' % r)
winmm.midiInStart(hin)


def send(*b):
    winmm.midiOutShortMsg(hout, b[0] | b[1] << 8 | b[2] << 16)
    time.sleep(0.004)


def trial(name, fn, wait=1.5):
    received.clear()
    fn()
    time.sleep(wait)
    cc = [m for m in received if (m & 0xF0) == 0xB0]
    print('%-46s -> %4d incoming (%d CC)' % (name, len(received), len(cc)))


def request():
    for ch in range(4):
        send(0x90 + ch, 0x21, 0x20)


def rb_globals():
    for m in ((0x9F, 0x40, 0x7F), (0x9F, 0x41, 0), (0x9F, 0x42, 0x7F), (0xBF, 0x46, 0x30)):
        send(*m)


class MIDIHDR(ctypes.Structure):
    _fields_ = [('data', ctypes.c_char_p), ('buflen', wintypes.DWORD), ('recorded', wintypes.DWORD),
                ('user', ctypes.c_size_t), ('flags', wintypes.DWORD), ('next', ctypes.c_void_p),
                ('reserved', ctypes.c_size_t), ('offset', wintypes.DWORD), ('res2', ctypes.c_size_t * 4)]


def sysex(*b):
    raw = bytes(b)
    buf = ctypes.create_string_buffer(raw, len(raw))
    h = MIDIHDR(ctypes.cast(buf, ctypes.c_char_p), len(raw), 0, 0, 0, None, 0, 0, (ctypes.c_size_t * 4)())
    winmm.midiOutPrepareHeader(hout, ctypes.byref(h), ctypes.sizeof(h))
    winmm.midiOutLongMsg(hout, ctypes.byref(h), ctypes.sizeof(h))
    time.sleep(0.05)
    winmm.midiOutUnprepareHeader(hout, ctypes.byref(h), ctypes.sizeof(h))


HDR = (0xF0, 0x00, 0x40, 0x05, 0x00, 0x00, 0x02, 0x00, 0x00)
trial('SysEx 03 01 (request state)', lambda: sysex(*HDR, 0x03, 0x01, 0xF7), 2.0)
trial('idle (nothing sent)', lambda: None, 1.0)
trial('request 90..93 21 20 only', request)
trial('9F40/41/42 + BF46 then request', lambda: (rb_globals(), request()))
trial('request again', request)
winmm.midiInStop(hin)
winmm.midiInClose(hin)
winmm.midiOutClose(hout)
