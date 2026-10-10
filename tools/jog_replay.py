"""Open the DDJ-1000 jog-display HID interface (#3) and replay recorded jog transfers to it.
Close Mixxx and rekordbox first.   No third-party packages (ctypes + hid.dll/setupapi).

usage: python jog_replay.py info
       python jog_replay.py replay decoded_dir t_from t_to [deck_filter=1]
"""
import ctypes, sys, time
from ctypes import wintypes

k32, hid, setupapi = ctypes.WinDLL('kernel32', use_last_error=True), ctypes.WinDLL('hid'), ctypes.WinDLL('setupapi')
HID_GUID = (ctypes.c_ubyte * 16)(*bytes.fromhex('b2551e4d6ff1cf1188cb001111000030'))
INVALID = ctypes.c_void_p(-1).value


class SPDID(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('guid', ctypes.c_ubyte * 16), ('flags', wintypes.DWORD), ('res', ctypes.c_void_p)]


class CAPS(ctypes.Structure):
    _fields_ = [('Usage', wintypes.USHORT), ('UsagePage', wintypes.USHORT), ('InLen', wintypes.USHORT), ('OutLen', wintypes.USHORT),
                ('FeatLen', wintypes.USHORT), ('Reserved', wintypes.USHORT * 17), ('NumLinkColl', wintypes.USHORT),
                ('NumInBtn', wintypes.USHORT), ('NumInVal', wintypes.USHORT), ('NumInData', wintypes.USHORT),
                ('NumOutBtn', wintypes.USHORT), ('NumOutVal', wintypes.USHORT), ('NumOutData', wintypes.USHORT),
                ('NumFeatBtn', wintypes.USHORT), ('NumFeatVal', wintypes.USHORT), ('NumFeatData', wintypes.USHORT)]


setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(SPDID)]
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SPDID), ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
k32.CreateFileW.restype = ctypes.c_void_p
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
k32.WriteFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]


def paths():
    h = setupapi.SetupDiGetClassDevsW(ctypes.byref(HID_GUID), None, None, 0x12)   # PRESENT | DEVICEINTERFACE
    i = 0
    while True:
        d = SPDID(); d.cb = ctypes.sizeof(SPDID)
        if not setupapi.SetupDiEnumDeviceInterfaces(h, None, ctypes.byref(HID_GUID), i, ctypes.byref(d)):
            break
        i += 1
        n = wintypes.DWORD()
        setupapi.SetupDiGetDeviceInterfaceDetailW(h, ctypes.byref(d), None, 0, ctypes.byref(n), None)
        buf = ctypes.create_string_buffer(n.value)
        ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = 8   # cbSize on x64
        if setupapi.SetupDiGetDeviceInterfaceDetailW(h, ctypes.byref(d), buf, n.value, None, None):
            yield ctypes.wstring_at(ctypes.addressof(buf) + 4)


def open_ddj():
    for p in paths():
        if 'vid_2b73' in p.lower() and 'pid_0020' in p.lower():
            h = k32.CreateFileW(p, 0xC0000000, 3, None, 3, 0, None)       # GENERIC_READ|WRITE, share RW, OPEN_EXISTING
            err = ctypes.get_last_error()
            pre = ctypes.c_void_p()
            caps = CAPS()
            if h != INVALID and hid.HidD_GetPreparsedData(ctypes.c_void_p(h), ctypes.byref(pre)):
                hid.HidP_GetCaps(pre, ctypes.byref(caps))
            print('%s\n   open=%s err=%d usagePage=0x%04X usage=0x%X in=%d out=%d' % (p, h != INVALID, err, caps.UsagePage, caps.Usage, caps.InLen, caps.OutLen))
            if h != INVALID and caps.UsagePage == 0xFFA0:
                return h, caps
            if h != INVALID:
                k32.CloseHandle(ctypes.c_void_p(h))
    return None, None


if sys.argv[1] == 'info':
    h, caps = open_ddj()
    print('jog interface found' if h else 'jog interface NOT opened')
elif sys.argv[1] == 'replay':
    d, t_from, t_to = sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
    deck = int(sys.argv[5]) if len(sys.argv) > 5 else 1
    h, caps = open_ddj()
    if not h:
        sys.exit('could not open the jog interface (is Mixxx/rekordbox still running?)')
    pk = [(float(l.split()[0]), bytes.fromhex(l.split()[1])) for l in open(d + '/ep_06_t1.txt')]
    every = len(sys.argv) > 6 and sys.argv[6] == 'all'      # also the live status packets (0x21 etc.)
    as_deck = int(sys.argv[7]) if len(sys.argv) > 7 else deck  # re-address the recorded packets to this deck
    pk = [(t, r) for t, r in pk if t_from <= t <= t_to and r[0] >> 4 == deck and (every or r[1] in (0x2b, 0x2c, 0x2d, 0x2f))]
    print('replaying %d transfer packets to deck %d' % (len(pk), deck))
    start, t0 = time.perf_counter(), pk[0][0]
    for t, r in pk:
        while time.perf_counter() - start < t - t0:
            pass
        r = bytes([as_deck << 4 | r[0] & 15]) + r[1:]
        data = b'\x00' + r          # no report IDs on this interface: Windows wants a leading 0 byte (OutLen 65)
        buf = ctypes.create_string_buffer(data, len(data))
        w = wintypes.DWORD()
        ok = k32.WriteFile(ctypes.c_void_p(h), buf, len(data), ctypes.byref(w), None)
        if not ok:
            sys.exit('WriteFile failed, error %d at packet type 0x%02x seq %d' % (ctypes.get_last_error(), r[1], r[2]))
    print('done')
