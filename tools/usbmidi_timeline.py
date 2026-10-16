#!/usr/bin/env python3
"""Reconstruct a startup timeline from decoded DDJ capture dir: find the first unit->host
'11 02' (cert ready) and show every host->device message (MIDI OUT ep_04, HID OUT ep_06)
in the window just before it, to identify what arms the cert."""
import sys, os

D = sys.argv[1]
WIN = float(sys.argv[2]) if len(sys.argv) > 2 else 2.5

def parse_usbmidi(path):
    """Yield (t, sysex_or_short_bytes) reassembling SysEx from 4-byte USB-MIDI events."""
    out = []
    sx = bytearray()
    if not os.path.exists(path):
        return out
    for line in open(path):
        parts = line.split()
        if len(parts) != 2:
            continue
        t = float(parts[0]); raw = bytes.fromhex(parts[1])
        for i in range(0, len(raw) - 3, 4):
            cin = raw[i] & 0x0F
            b = raw[i+1:i+4]
            if cin == 0x4:            # sysex start/continue (3 bytes)
                sx += b
            elif cin in (0x5, 0x6, 0x7):  # sysex end with 1/2/3 bytes
                nb = cin - 4
                sx += b[:nb]
                out.append((t, bytes(sx))); sx = bytearray()
            elif cin == 0xF:
                out.append((t, b[:1]))
            elif cin in (0x8, 0x9, 0xA, 0xB, 0xE):  # 3-byte channel msgs
                out.append((t, b[:3]))
            elif cin in (0xC, 0xD):   # 2-byte
                out.append((t, b[:2]))
            # cin 0,1 reserved; 2,3 system common (skip)
    return out

def parse_hid(path, limit_t):
    out = []
    if not os.path.exists(path):
        return out
    for line in open(path):
        parts = line.split()
        if len(parts) != 2:
            continue
        t = float(parts[0])
        if t > limit_t:
            break
        out.append((t, bytes.fromhex(parts[1])))
    return out

midi_in = parse_usbmidi(os.path.join(D, "ep_85_t3.txt"))
midi_out = parse_usbmidi(os.path.join(D, "ep_04_t3.txt"))

# first 11 02 on MIDI IN
T = None
for t, msg in midi_in:
    if msg and msg[0] == 0xF0 and len(msg) >= 11 and msg[9] == 0x11:
        T = t; break
if T is None:
    # fallback: any sysex in
    print("no 11 02 found in MIDI IN. First few IN sysex:")
    for t, msg in midi_in[:10]:
        if msg and msg[0] == 0xF0:
            print("  %.4f %s" % (t, msg.hex()))
    sys.exit(0)

print("=== %s : first unit->host 11 02 at t=%.4f ===" % (D, T))
hid_out = parse_hid(os.path.join(D, "ep_06_t1.txt"), T + 0.5)

print("\n--- HID OUT (ep_06) BEFORE 11 02 (host->device; candidate arming) ---")
hid_before = [(t, r) for t, r in hid_out if t <= T]
print("  count before 11 02: %d" % len(hid_before))
for t, r in hid_before[:40]:
    print("  %.4f  %s" % (t, r[:16].hex()))

print("\n--- MIDI OUT (ep_04) in [T-%.1f, T+0.5] (host->device) ---" % WIN)
for t, msg in midi_out:
    if T - WIN <= t <= T + 0.5:
        tag = ""
        if msg and msg[0] == 0xF0:
            tag = " <SYSEX>"
        print("  %.4f  %s%s" % (t, msg.hex(), tag))

print("\n--- MIDI IN (ep_85) handshake sysex around T ---")
for t, msg in midi_in:
    if T - 0.5 <= t <= T + 1.0 and msg and msg[0] == 0xF0:
        print("  %.4f  %s" % (t, msg.hex()))
