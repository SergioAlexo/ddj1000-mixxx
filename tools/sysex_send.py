"""Send raw SysEx messages to the DDJ-1000 with delays, and print everything the unit sends back meanwhile.
Close Mixxx and rekordbox first.
usage: python sysex_send.py <delay_s> hex1 [hex2 ...]        (each hex = one full F0 ... F7 message)"""
import ctypes, sys, time
from ctypes import wintypes

winmm = ctypes.WinDLL('winmm')
CALLBACK_FUNCTION = 0x30000
MIM_DATA, MIM_LONGDATA = 0x3C3, 0x3C4


class OCAPS(ctypes.Structure):
    _fields_ = [('mid', wintypes.WORD), ('pid', wintypes.WORD), ('ver', wintypes.UINT), ('name', ctypes.c_wchar * 32),
                ('tech', wintypes.WORD), ('voices', wintypes.WORD), ('notes', wintypes.WORD), ('mask', wintypes.WORD),
                ('support', wintypes.DWORD)]


class ICAPS(ctypes.Structure):
    _fields_ = [('mid', wintypes.WORD), ('pid', wintypes.WORD), ('ver', wintypes.UINT), ('name', ctypes.c_wchar * 32),
                ('support', wintypes.DWORD)]


class MIDIHDR(ctypes.Structure):
    _fields_ = [('data', ctypes.c_void_p), ('buflen', wintypes.DWORD), ('recorded', wintypes.DWORD),
                ('user', ctypes.c_size_t), ('flags', wintypes.DWORD), ('next', ctypes.c_void_p),
                ('reserved', ctypes.c_size_t), ('offset', wintypes.DWORD), ('res2', ctypes.c_size_t * 4)]


def find(num, caps_t, getcaps):
    for i in range(num()):
        c = caps_t()
        getcaps(i, ctypes.byref(c), ctypes.sizeof(c))
        if 'DDJ-1000' in c.name:
            return i
    sys.exit('DDJ-1000 not found')


HDR_SIZE = ctypes.sizeof(MIDIHDR)
inbufs = []
log = []
CB = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.UINT, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t)


def on_midi(h, msg, inst, p1, p2):
    if msg == MIM_DATA:
        log.append(('short', (p1 & 0xFFFFFF).to_bytes(3, 'little').hex()))
    elif msg == MIM_LONGDATA:
        hdr = ctypes.cast(p1, ctypes.POINTER(MIDIHDR)).contents
        if hdr.recorded:
            log.append(('sysex', ctypes.string_at(hdr.data, hdr.recorded).hex()))
            winmm.midiInAddBuffer(hin, ctypes.cast(p1, ctypes.c_void_p), HDR_SIZE)


cb = CB(on_midi)
hin, hout = wintypes.HANDLE(), wintypes.HANDLE()
if winmm.midiInOpen(ctypes.byref(hin), find(winmm.midiInGetNumDevs, ICAPS, winmm.midiInGetDevCapsW), cb, 0, CALLBACK_FUNCTION):
    sys.exit('midiInOpen failed - Mixxx/rekordbox still running?')
if winmm.midiOutOpen(ctypes.byref(hout), find(winmm.midiOutGetNumDevs, OCAPS, winmm.midiOutGetDevCapsW), 0, 0, 0):
    sys.exit('midiOutOpen failed')
for _ in range(4):
    buf = ctypes.create_string_buffer(512)
    h = MIDIHDR(ctypes.cast(buf, ctypes.c_void_p), 512, 0, 0, 0, None, 0, 0, (ctypes.c_size_t * 4)())
    inbufs.append((buf, h))
    winmm.midiInPrepareHeader(hin, ctypes.byref(h), HDR_SIZE)
    winmm.midiInAddBuffer(hin, ctypes.byref(h), HDR_SIZE)
winmm.midiInStart(hin)

delay = float(sys.argv[1])
for hx in sys.argv[2:]:
    raw = bytes.fromhex(hx)
    buf = ctypes.create_string_buffer(raw, len(raw))
    h = MIDIHDR(ctypes.cast(buf, ctypes.c_void_p), len(raw), 0, 0, 0, None, 0, 0, (ctypes.c_size_t * 4)())
    winmm.midiOutPrepareHeader(hout, ctypes.byref(h), HDR_SIZE)
    winmm.midiOutLongMsg(hout, ctypes.byref(h), HDR_SIZE)
    print('sent   ', hx)
    time.sleep(delay)
    winmm.midiOutUnprepareHeader(hout, ctypes.byref(h), HDR_SIZE)
time.sleep(1.0)
winmm.midiInStop(hin)
winmm.midiInReset(hin)
print('--- received from the unit meanwhile:')
for kind, hx in log:
    print('  %-5s %s' % (kind, hx))
print('  (%d messages)' % len(log))
winmm.midiOutClose(hout)
