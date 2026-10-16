#!/usr/bin/env python3
"""THE test: send rekordbox's 50 01 arming poll ourselves and see if the unit emits 11 02,
then run our handshake to 0x15 and check HID head flips to 0020. No rekordbox."""
import os, sys, time, random
sys.path.insert(0, os.path.dirname(__file__))  # co-located ddj_cert.py / ddj_jog.py
import ddj_cert as C
import ddj_jog as J
import rtmidi

ARM = list(C.HDR) + [0x50, 0x01, 0xF7]

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

def hid_head(secs=1.0):
    d = J.open_device(); d.set_nonblocking(True)
    heads = {}; t = time.time()
    while time.time() - t < secs:
        r = d.read(64)
        if r: h = bytes(r)[:2].hex(); heads[h] = heads.get(h, 0) + 1
        time.sleep(0.001)
    d.close(); return heads

def main():
    mo, mi = rtmidi.MidiOut(), rtmidi.MidiIn()
    mo.open_port(next(i for i, n in enumerate(mo.get_ports()) if "DDJ" in n))
    mi.open_port(next(i for i, n in enumerate(mi.get_ports()) if "DDJ" in n))
    mi.ignore_types(sysex=False, timing=True, active_sense=True)
    print("MIDI open. HID head before:", hid_head(0.8), flush=True)

    print("sending 50 01 arming poll (~5/s), watching for 11 02...", flush=True)
    while mi.get_message():
        pass
    ready = None
    t0 = time.time()
    while time.time() - t0 < 10:
        mo.send_message(ARM)
        r = wait(mi, None, 0.2)
        if r and C.msg_type(r) == 0x11:
            ready = r; print("  >>> 11 02 RECEIVED at %.2fs - CERT ARMED BY 50 01" % (time.time()-t0), flush=True)
            break
    if not ready:
        print("  no 11 02 after 10s of 50 01 (arming needs more than 50 01)", flush=True)
        mi.close_port(); mo.close_port(); return

    # full handshake
    while mi.get_message():
        pass
    hc = bytes(random.randrange(256) for _ in range(8))
    print("send 0x12 HC=%s" % hc.hex(), flush=True)
    mo.send_message(list(C.build_12(hc)))
    rep = wait(mi, 0x13, 1.5)
    if not rep:
        print("  no 0x13", flush=True); mi.close_port(); mo.close_port(); return
    info = C.parse_13(rep); r = info["r"]; ua = info["unit_answer"]
    pred = C.predict_unit_answer(hc, r)
    print("  0x13 r=%08x ua=%08x  pred=%08x -> %s" % (r, ua, pred, "MATCH" if pred==ua else "MISMATCH"), flush=True)
    mo.send_message(list(C.build_14(hc, r)))
    acc = wait(mi, None, 1.5)
    print("  reply to 0x14: %s" % ("0x%02x" % C.msg_type(acc) if acc else "none"), flush=True)
    if acc and C.is_accept(acc):
        print("  *** 0x15 ACCEPT - UNLOCKED WITHOUT REKORDBOX ***", flush=True)
    # keep arming a moment, then check HID head
    for _ in range(10):
        mo.send_message(ARM); time.sleep(0.1)
    print("HID head after handshake:", hid_head(1.0), flush=True)
    mi.close_port(); mo.close_port()
    print("done", flush=True)

if __name__ == "__main__":
    main()
