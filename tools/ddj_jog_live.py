#!/usr/bin/env python3
"""Standalone DDJ-1000 jog-waveform driver — OPEN SOFTWARE ONLY, no rekordbox, no capture at runtime.

Drives the whole chain and shows a custom waveform on a jog screen:
  1. go live  : open the USB audio device full-duplex, stream silence (clears "no audio driver")
  2. arm      : poll SysEx `50 01` -> unit emits `11 02`
  3. handshake: ddj_cert FNV-1a  0x12/0x13/0x14 -> 0x15 ACCEPT  (HID performance mode)
  4. leave logo + render context: replay the bundled init burst (MIDI) + a real beatgrid/artwork/
     playing status (from ddj_jog_initdata, extracted once from a capture — generic, not track data)
  5. stream our OWN generated 0x2C waveform, keeping the session alive (`50 01` + status) continuously.

Usage:  python3 -I stage4/ddj_jog_live.py --deck 1 --pattern square --hold 60
Patterns: square (default), sine, bars, ramp, rainbow.  Needs: python-rtmidi, sounddevice, hidapi.
Pioneer VersionViewer must be running so the unit is operational (clears "no audio driver").
"""
import os, sys, math, struct, time, random, threading, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "stage3", "tools"))
sys.path.insert(0, os.path.dirname(__file__))
import ddj_cert as C
import ddj_jog as J
import ddj_jog_initdata as D
import rtmidi, sounddevice as sd

ARM = list(C.HDR) + [0x50, 0x01, 0xF7]
_stop = threading.Event()


# ------------------------------------------------- waveform patterns (600 cols x 7 bytes)
def rgb565(r, g, b): return J.rgb565(r, g, b)

def make_points(name):
    if name == "square":
        pts = []
        half = 25            # columns per half-period -> visible square blocks
        for i in range(J.WAVE_POINTS):
            on = (i // half) % 2 == 0
            h = J.WAVE_MAX_H if on else 3
            inner = h * 0.5 if on else 1
            col = rgb565(0, 255, 140) if on else rgb565(30, 30, 70)
            pts.append(J.wave_point(h, inner, col, rgb565(255, 255, 255)))
        return pts
    return J.pattern_points(name)   # sine / bars / ramp / rainbow from ddj_jog


# ------------------------------------------------- session helpers
def go_live():
    try: sd._terminate(); sd._initialize()
    except Exception: pass
    idx = next(i for i, d in enumerate(sd.query_devices())
               if "DDJ" in d["name"] and d["max_output_channels"] >= 2)
    di = sd.query_devices(idx)
    nin, nout, sr = int(di["max_input_channels"]), int(di["max_output_channels"]), int(di["default_samplerate"])
    st = sd.Stream(device=idx, samplerate=sr, blocksize=256, dtype="float32", channels=(nin, nout),
                   callback=lambda i, o, f, t, s: o.__setitem__(slice(None), 0.0))
    st.start()
    print("1. audio live (full-duplex %d/%d @ %g)" % (nin, nout, sr))
    return st

def wait(mi, want, secs):
    t = time.time()
    while time.time() - t < secs:
        m = mi.get_message()
        if m and m[0] and m[0][0] == 0xF0:
            b = bytes(m[0])
            if want is None or C.msg_type(b) == want: return b
        time.sleep(0.001)
    return None

def keepalive(mo):
    while not _stop.is_set():
        try: mo.send_message(ARM)
        except Exception: pass
        time.sleep(0.2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck", type=int, default=1)
    ap.add_argument("--pattern", default="square", choices=["square", "sine", "bars", "ramp", "rainbow"])
    ap.add_argument("--hold", type=float, default=60.0)
    args = ap.parse_args()
    deck_nib = args.deck << 4

    points = make_points(args.pattern)
    custom = J.wave_packets(args.deck, points, centered=False, enable=True)

    def retarget(hexlist):   # bundled data is deck-1 (0x1x); set high nibble to our deck
        out = []
        for h in hexlist:
            b = bytearray.fromhex(h); b[0] = deck_nib | (b[0] & 0x0F); out.append(bytes(b))
        return out
    beatgrid = retarget(D.BEATGRID); artwork = retarget(D.ARTWORK)
    status = bytearray.fromhex(D.PLAY_STATUS); status[0] = deck_nib | (status[0] & 0x0F); status = bytes(status)

    st = go_live(); time.sleep(1.0)
    mo, mi = rtmidi.MidiOut(), rtmidi.MidiIn()
    mo.open_port(next(i for i, n in enumerate(mo.get_ports()) if "DDJ" in n))
    mi.open_port(next(i for i, n in enumerate(mi.get_ports()) if "DDJ" in n))
    mi.ignore_types(sysex=False, timing=True, active_sense=True)

    print("2. arming (50 01)...")
    while mi.get_message(): pass
    t0 = time.time(); ok = False
    while time.time() - t0 < 8:
        mo.send_message(ARM)
        if wait(mi, 0x11, 0.2): ok = True; break
    if not ok: print("   FAILED: no 11 02 (is VersionViewer running?)"); return
    hc = bytes(random.randrange(256) for _ in range(8)); mo.send_message(list(C.build_12(hc)))
    rep = wait(mi, 0x13, 1.5)
    if not rep: print("3. FAILED: no 0x13"); return
    r = C.parse_13(rep)["r"]; ok = C.predict_unit_answer(hc, r) == C.parse_13(rep)["unit_answer"]
    mo.send_message(list(C.build_14(hc, r)))
    acc = wait(mi, None, 1.5)
    if not (acc and C.is_accept(acc)): print("3. FAILED: no 0x15"); return
    print("3. handshake OK (0x13 %s) -> 0x15 performance mode" % ("MATCH" if ok else "??"))
    threading.Thread(target=keepalive, args=(mo,), daemon=True).start()

    print("4. leave-logo MIDI burst (%d msgs)..." % len(D.INIT_BURST))
    for h in D.INIT_BURST:
        mo.send_message(list(bytes.fromhex(h))); time.sleep(0.003)

    dev = J.open_device()
    def send(pkts, gap=0.003):
        for p in pkts: dev.write(b"\x00" + (p if len(p) == 64 else p.ljust(64, b"\0"))); time.sleep(gap)
    print("5. render context (beatgrid/artwork/status) + CUSTOM '%s' waveform on deck %d" % (args.pattern, args.deck))
    send(beatgrid); send(artwork)
    for _ in range(20): dev.write(b"\x00" + status); time.sleep(0.003)
    send(custom)
    print("   holding %.0fs (session kept alive) - watch the jog" % args.hold)
    # The waveform persists once sent; keep the session alive with the status stream + 50 01 only.
    # Re-sending the waveform forces a full redraw (visible blink), so we do NOT re-send it.
    t = time.time()
    while time.time() - t < args.hold:
        dev.write(b"\x00" + status)
        time.sleep(0.008)
    _stop.set(); dev.close(); time.sleep(0.2)
    mi.close_port(); mo.close_port(); st.stop(); st.close()
    print("done")


if __name__ == "__main__":
    main()
