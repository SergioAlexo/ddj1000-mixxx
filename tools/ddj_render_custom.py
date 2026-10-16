#!/usr/bin/env python3
"""Replay the REAL track-load-and-play bundle (t~80) over our session: init burst to leave the
logo, then the real beatgrid/artwork/waveform + PLAYING status, held continuously."""
import os, sys, time, random, threading
sys.path.insert(0, os.path.dirname(__file__))  # co-located ddj_cert.py / ddj_jog.py
import ddj_cert as C
import ddj_jog as J
import rtmidi, sounddevice as sd

CAP = "/Users/danil/Downloads/DDJ-1000_v112_WIN/ddj1000-mixxx-repo/captures/decoded3"
DECK = 0x10
ARM = list(C.HDR) + [0x50, 0x01, 0xF7]
_stop = threading.Event()

def usbmidi(path):
    out = []; sx = bytearray()
    for line in open(path):
        p = line.split()
        if len(p) != 2: continue
        t = float(p[0]); raw = bytes.fromhex(p[1])
        for i in range(0, len(raw) - 3, 4):
            cin = raw[i] & 0x0F; b = raw[i+1:i+4]
            if cin == 0x4: sx += b
            elif cin in (0x5, 0x6, 0x7): sx += b[:cin-4]; out.append((t, bytes(sx))); sx = bytearray()
            elif cin in (0x8, 0x9, 0xA, 0xB, 0xE): out.append((t, b[:3]))
            elif cin in (0xC, 0xD): out.append((t, b[:2]))
    return out

def pad64(b): b = b[:64]; return b + b"\x00" * (64 - len(b))

def main():
    midi = usbmidi(CAP + "/ep_04_t3.txt")
    def midi_window(a, b):
        out = []
        for t, m in midi:
            if a <= t <= b:
                if m and m[0] == 0xF0 and (C.msg_type(m) if len(m) >= 11 else 0) in (0x50, 0x03, 0x12, 0x13, 0x14):
                    continue
                out.append(m)
        return out
    burst = midi_window(60.0, 62.45)       # leave the logo
    load_midi = midi_window(79.5, 82.0)    # any MIDI at real track load

    hid = [(float(p[0]), bytes.fromhex(p[1])) for p in (l.split() for l in open(CAP + "/ep_06_t1.txt")) if len(p) == 2]
    d1 = [(t, b) for t, b in hid if b and b[0] == DECK]
    load_hid = [b for t, b in d1 if 80.0 <= t <= 82.0]      # real load+play sequence, in order
    wave = [b for t, b in d1 if b[1] == 0x2c and 80.2 <= t <= 81.0]  # the real waveform set
    custom = J.wave_packets(1, J.pattern_points("rainbow"), centered=False, enable=True)  # OUR pattern
    play_status = next((b for t, b in d1 if b[1] == 0x21 and len(b) > 9 and b[9] == 0xb4 and b[5] == 0x81), None)
    print("burst=%d load_midi=%d load_hid=%d wave=%d play_status=%s"
          % (len(burst), len(load_midi), len(load_hid), len(wave), bool(play_status)), flush=True)

    try: sd._terminate(); sd._initialize()
    except Exception: pass
    idx = next(i for i, d in enumerate(sd.query_devices()) if "DDJ" in d["name"] and d["max_output_channels"] >= 2)
    di = sd.query_devices(idx)
    st = sd.Stream(device=idx, samplerate=int(di["default_samplerate"]), blocksize=256, dtype="float32",
                   channels=(int(di["max_input_channels"]), int(di["max_output_channels"])),
                   callback=lambda i, o, f, t, s: o.__setitem__(slice(None), 0.0)); st.start()
    time.sleep(1.0)
    mo, mi = rtmidi.MidiOut(), rtmidi.MidiIn()
    mo.open_port(next(i for i, n in enumerate(mo.get_ports()) if "DDJ" in n))
    mi.open_port(next(i for i, n in enumerate(mi.get_ports()) if "DDJ" in n))
    mi.ignore_types(sysex=False, timing=True, active_sense=True)

    def wait(want, secs):
        t = time.time()
        while time.time() - t < secs:
            m = mi.get_message()
            if m and m[0] and m[0][0] == 0xF0:
                b = bytes(m[0])
                if want is None or C.msg_type(b) == want: return b
            time.sleep(0.001)
        return None
    while mi.get_message(): pass
    t0 = time.time(); ok = False
    while time.time() - t0 < 8:
        mo.send_message(ARM)
        if wait(0x11, 0.2): ok = True; break
    if not ok: print("no 11 02"); return
    hc = bytes(random.randrange(256) for _ in range(8)); mo.send_message(list(C.build_12(hc)))
    rep = wait(0x13, 1.5)
    if not rep: print("no 0x13"); return
    r = C.parse_13(rep)["r"]; mo.send_message(list(C.build_14(hc, r)))
    acc = wait(None, 1.5)
    if not (acc and C.is_accept(acc)): print("no 0x15"); return
    print("0x15 ACCEPT", flush=True)
    threading.Thread(target=lambda: ([ (mo.send_message(ARM), time.sleep(0.2)) for _ in iter(lambda: not _stop.is_set(), False)]), daemon=True).start()

    for m in burst: mo.send_message(list(m)); time.sleep(0.003)
    print("logo-leave burst sent", flush=True)
    dev = J.open_device()
    for m in load_midi: mo.send_message(list(m)); time.sleep(0.003)
    for b in load_hid:
        if b[1] == 0x2c: continue          # skip captured waveform
        dev.write(b"\x00" + pad64(b)); time.sleep(0.003)
    for p in custom: dev.write(b"\x00" + pad64(p)); time.sleep(0.003)   # send OUR waveform
    print("real beatgrid/artwork + CUSTOM waveform (rainbow) sent; HOLDING 90s", flush=True)
    t = time.time(); lastw = 0; lastl = 0
    while time.time() - t < 90:
        if play_status: dev.write(b"\x00" + pad64(play_status))
        now = time.time()
        if now - lastw > 1.0:
            for b in custom: dev.write(b"\x00" + pad64(b))
            lastw = now
        if now - lastl > 5: print("  holding %.0fs" % (now - t), flush=True); lastl = now
        time.sleep(0.008)
    _stop.set(); dev.close(); time.sleep(0.2)
    mi.close_port(); mo.close_port(); st.stop(); st.close(); print("done", flush=True)

if __name__ == "__main__":
    main()
