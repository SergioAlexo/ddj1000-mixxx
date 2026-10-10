"""List PortAudio devices exactly as Mixxx enumerates them (uses Mixxx's own portaudio.dll).
usage: python list_audio_devices.py [name filter]"""
import ctypes, os, sys

os.add_dll_directory(r'C:\Program Files\Mixxx')
pa = ctypes.CDLL(r'C:\Program Files\Mixxx\portaudio.dll')


class DevInfo(ctypes.Structure):
    _fields_ = [('structVersion', ctypes.c_int), ('name', ctypes.c_char_p), ('hostApi', ctypes.c_int),
                ('maxIn', ctypes.c_int), ('maxOut', ctypes.c_int), ('lowIn', ctypes.c_double), ('lowOut', ctypes.c_double),
                ('highIn', ctypes.c_double), ('highOut', ctypes.c_double), ('rate', ctypes.c_double)]


class HostInfo(ctypes.Structure):
    _fields_ = [('structVersion', ctypes.c_int), ('type', ctypes.c_int), ('name', ctypes.c_char_p),
                ('deviceCount', ctypes.c_int), ('defIn', ctypes.c_int), ('defOut', ctypes.c_int)]


pa.Pa_GetDeviceInfo.restype = ctypes.POINTER(DevInfo)
pa.Pa_GetHostApiInfo.restype = ctypes.POINTER(HostInfo)
pa.Pa_Initialize()
flt = sys.argv[1].lower() if len(sys.argv) > 1 else ''
for i in range(pa.Pa_GetDeviceCount()):
    d = pa.Pa_GetDeviceInfo(i).contents
    h = pa.Pa_GetHostApiInfo(d.hostApi).contents
    name = d.name.decode('mbcs', 'replace')
    if flt in name.lower() or flt in h.name.decode().lower():
        print('%3d  %-24s %-48s out=%d in=%d' % (i, h.name.decode(), name, d.maxOut, d.maxIn))
pa.Pa_Terminate()
