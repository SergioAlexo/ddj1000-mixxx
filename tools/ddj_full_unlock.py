#!/usr/bin/env python3
"""Complete DDJ-1000 jog-waveform unlock with OPEN SOFTWARE ONLY (no rekordbox).

The full recipe, all reverse-engineered and confirmed live on macOS 2026-10-15:
  1. Go live: open the USB audio device full-duplex, stream silence (clears "no audio driver").
  2. Arm the cert: poll SysEx `50 01` (rekordbox's arming poll, found in the USBPcap capture).
     The unit answers with `11 02` and the cert task wakes.
  3. Handshake (ddj_cert, FNV-1a, no secret): 0x12 -> 0x13 -> 0x14 -> 0x15 ACCEPT.
     -> HID input head flips 0000 (MIDI/standard) -> 0020 (HID/performance).
  4. Stream a custom 0x2C waveform (+0x21 status) over HID interface 3 to the jog screen,
     while continuously re-polling `50 01` to keep the session (performance mode does not latch).

Run:  python3 -I stage4/ddj_full_unlock.py [deck] [hold_s]
Needs: python-rtmidi, sounddevice, hidapi.  Pioneer VersionViewer makes the unit operational.
"""
import os, sys, time, random, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "stage3", "tools"))
sys.path.insert(0, os.path.dirname(__file__))
import ddj_cert as C
import ddj_jog as J
import rtmidi
import sounddevice as sd

DECK = int(sys.argv[1]) if len(sys.argv) > 1 else 1
HOLD = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
ARM = list(C.HDR) + [0x50, 0x01, 0xF7]

_stop = threading.Event()

def go_live():
    try: sd._terminate(); sd._initialize()
    except Exception: pass
    idx = next(i for i, d in enumerate(sd.query_devices())
               if "DDJ" in d["name"] and d["max_output_channels"] >= 2)
    di = sd.query_devices(idx)
    nin, nout, sr = int(di["max_input_channels"]), int(di["max_output_channels"]), int(di["default_samplerate"])
    st = sd.Stream(device=idx, samplerate=sr, blocksize=256, dtype="float32",
                   channels=(nin, nout), callback=lambda i, o, f, t, s: o.__setitem__(slice(None), 0.0))
    st.start()
    print("1. audio live (full-duplex %d/%d @ %g)" % (nin, nout, sr))
    return st

def wait(mi, want, secs):
    t = time.time()
    while time.time() - t < secs:
        m = mi.get_message()
        if m and m[0] and m[0][0] == 0xF0:
            b = bytes(m[0])
            if want is None or C.msg_type(b) == want:
                return b
        time.sleep(0.001)
    return None

def arm_keepalive(mo):
    """Hold the session: keep sending the 50 01 poll until stopped."""
    while not _stop.is_set():
        try: mo.send_message(ARM)
        except Exception: pass
        time.sleep(0.2)

def main():
    st = go_live()
    time.sleep(1.0)
    mo, mi = rtmidi.MidiOut(), rtmidi.MidiIn()
    mo.open_port(next(i for i, n in enumerate(mo.get_ports()) if "DDJ" in n))
    mi.open_port(next(i for i, n in enumerate(mi.get_ports()) if "DDJ" in n))
    mi.ignore_types(sysex=False, timing=True, active_sense=True)

    # 2. arm
    print("2. arming with 50 01 ...")
    while mi.get_message(): pass
    t0 = time.time(); ready = False
    while time.time() - t0 < 8:
        mo.send_message(ARM)
        if wait(mi, 0x11, 0.2):
            ready = True; print("   11 02 -> cert armed"); break
    if not ready:
        print("   FAILED: no 11 02"); _cleanup(st, mi, mo); return

    # 3. handshake
    while mi.get_message(): pass
    hc = bytes(random.randrange(256) for _ in range(8))
    mo.send_message(list(C.build_12(hc)))
    rep = wait(mi, 0x13, 1.5)
    if not rep:
        print("3. FAILED: no 0x13"); _cleanup(st, mi, mo); return
    info = C.parse_13(rep); r = info["r"]
    ok = C.predict_unit_answer(hc, r) == info["unit_answer"]
    print("3. handshake: 0x13 %s" % ("MATCH" if ok else "MISMATCH"))
    mo.send_message(list(C.build_14(hc, r)))
    acc = wait(mi, None, 1.5)
    if not (acc and C.is_accept(acc)):
        print("   FAILED: no 0x15"); _cleanup(st, mi, mo); return
    print("   0x15 ACCEPT -> performance mode unlocked")

    # keep the session alive while we draw
    ka = threading.Thread(target=arm_keepalive, args=(mo,), daemon=True); ka.start()

    # 4. push custom waveform
    dev = J.open_device()
    stat = J.status_packet(DECK, bpm=128.0, tempo_pct=0.0, elapsed_ms=0, remain_ms=180000, color=1)
    pk = J.wave_packets(DECK, J.pattern_points("bars"), centered=False, enable=True)
    print("4. streaming custom 0x2C waveform to deck %d; holding %.0fs (watch the jog)" % (DECK, HOLD))
    t = time.time()
    while time.time() - t < HOLD:
        dev.write(b"\x00" + stat)
        for p in pk:
            dev.write(b"\x00" + p); time.sleep(0.003)
        time.sleep(0.3)
    dev.close()
    _cleanup(st, mi, mo)
    print("done")

def _cleanup(st, mi, mo):
    _stop.set(); time.sleep(0.25)
    try: mi.close_port(); mo.close_port()
    except Exception: pass
    try: st.stop(); st.close()
    except Exception: pass

if __name__ == "__main__":
    main()
