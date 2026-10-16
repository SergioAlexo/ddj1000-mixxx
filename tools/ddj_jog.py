#!/usr/bin/env python3
"""
ddj_jog.py — push data to the Pioneer DDJ-1000 jog-wheel displays over USB HID.

Protocol (reverse-engineered from firmware v1.12, see stage3/STAGE3_HOST.md):
  * USB 2B73:0020, interface 3 (HID, vendor page 0xFFA0), 64-byte OUT reports, no report ID.
  * byte 0 high nibble = deck 1..4, byte 1 = message type.
  * 0x2C ','  overview waveform: 600 points x 7 bytes, 73 packets
  * 0x2B '+'  artwork: JPEG/PNG/GIF (<=10240 bytes), drawn 80x80
  * 0x21 '!'  deck status (subset implemented)

Examples:
  python3 ddj_jog.py list
  python3 ddj_jog.py wave --deck 1 --pattern sine --dry-run
  python3 ddj_jog.py wave --deck 1 --wav track.wav
  python3 ddj_jog.py art  --deck 1 cover_80x80.jpg
  python3 ddj_jog.py selftest

Requires: pip install hidapi   (numpy only for --wav)
"""
import argparse, math, struct, sys, time

VID, PID, HID_IFACE = 0x2B73, 0x0020, 3
REPORT_LEN = 64

MSG_STATUS, MSG_ART, MSG_WAVE, MSG_BEATGRID, MSG_CUES, MSG_HOTCUES = 0x21, 0x2B, 0x2C, 0x2F, 0x2D, 0x30
WAVE_POINTS, WAVE_POINT_LEN, WAVE_MAX_H = 600, 7, 40
WAVE_BYTES = WAVE_POINTS * WAVE_POINT_LEN          # 4200 (firmware buffer 0x1068)
ART_MAX = 0x2800                                   # 10240


# ---------------------------------------------------------------- encoding

def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def wave_point(h_outer, h_inner, col_outer, col_inner, preset=0):
    """One 7-byte waveform point. Heights 0..40 px; inner bar is drawn over outer and clamped <= outer.
    Colours are RGB565; col_outer == 0 selects firmware preset colour `preset` (0..7)."""
    h_outer = max(0, min(WAVE_MAX_H, int(h_outer)))
    h_inner = max(0, min(h_outer, int(h_inner)))
    return struct.pack('<HHBBB', col_outer & 0xFFFF, col_inner & 0xFFFF, h_outer, h_inner, preset & 7)


def _hdr(deck, msg, idx, total):
    if not 1 <= deck <= 4:
        raise ValueError('deck must be 1..4')
    return bytes([deck << 4, msg]) + struct.pack('<HH', idx, total)


def wave_packets(deck, points, centered=False, enable=True):
    """Split 600 points into the 0x2C packet stream.
    packet 1: hdr(6) + flags(1) + data[0:57]; packet n>=2: hdr(6) + data[57+58*(n-2) : +58]  (fw offset 58n-59)."""
    data = b''.join(points)
    if len(data) != WAVE_BYTES:
        raise ValueError('need exactly %d points' % WAVE_POINTS)
    first, rest = 57, 58
    total = 1 + math.ceil((len(data) - first) / rest)
    flags = (0x80 if enable else 0) | (0x40 if centered else 0)
    pkts = [_hdr(deck, MSG_WAVE, 1, total) + bytes([flags]) + data[:first]]
    for n in range(2, total + 1):
        off = rest * n - 59
        pkts.append(_hdr(deck, MSG_WAVE, n, total) + data[off:off + rest])
    return [p.ljust(REPORT_LEN, b'\0') for p in pkts]


def art_packets(deck, blob):
    """0x2B artwork: packet 1: hdr(6) + size u16 + data[0:56]; packet n>=2: hdr + data[58n-60 : +58]."""
    if len(blob) > ART_MAX:
        raise ValueError('artwork must be <= %d bytes (got %d)' % (ART_MAX, len(blob)))
    first, rest = 56, 58
    total = 1 + max(0, math.ceil((len(blob) - first) / rest))
    pkts = [_hdr(deck, MSG_ART, 1, total) + struct.pack('<H', len(blob)) + blob[:first]]
    for n in range(2, total + 1):
        off = rest * n - 60
        pkts.append(_hdr(deck, MSG_ART, n, total) + blob[off:off + rest])
    return [p.ljust(REPORT_LEN, b'\0') for p in pkts]


def status_packet(deck, bpm=None, tempo_pct=None, elapsed_ms=None, remain_ms=None, color=0):
    """Minimal 0x21 deck status. Only fields whose meaning is verified are set; everything else 0.
    p[9] validity mask: 0x80 times, 0x20 BPM, 0x10 tempo."""
    r = bytearray(REPORT_LEN)
    r[0], r[1] = deck << 4, MSG_STATUS
    r[2:6] = b'\x01\x00\x01\x00'
    mask = 0
    if elapsed_ms is not None and remain_ms is not None:
        mask |= 0x80
        for base, ms in ((11, elapsed_ms), (15, remain_ms)):
            m, rem = divmod(int(ms), 60000)
            r[base], r[base + 1] = min(m, 127), rem // 1000
            struct.pack_into('<H', r, base + 2, rem % 1000)
    if bpm is not None:
        mask |= 0x20
        t = int(round(bpm * 10))
        struct.pack_into('<H', r, 21, ((t % 10) << 12) | (t // 10 & 0xFFF))
    if tempo_pct is not None:
        mask |= 0x10
        struct.pack_into('<h', r, 23, max(-10000, min(10000, int(round(tempo_pct * 100)))))
    r[9] = mask
    r[59] = color
    return bytes(r)


# ---------------------------------------------------------------- waveform sources

def pattern_points(name):
    pts = []
    for i in range(WAVE_POINTS):
        x = i / WAVE_POINTS
        if name == 'sine':
            o = 20 + 18 * math.sin(2 * math.pi * 4 * x); n = o * 0.5
            col = rgb565(int(127 + 127 * math.sin(2 * math.pi * x)), 80, int(127 - 127 * math.sin(2 * math.pi * x)))
            pts.append(wave_point(o, n, col, rgb565(255, 255, 255)))
        elif name == 'ramp':
            pts.append(wave_point(x * 40, x * 20, rgb565(0, 160, 255), rgb565(255, 255, 255)))
        elif name == 'bars':   # every 25th point full height: checks the 600->288 column mapping
            pts.append(wave_point(40 if i % 25 == 0 else 8, 4, rgb565(255, 64, 0), rgb565(255, 255, 0)))
        elif name == 'rainbow':
            h = x * 6; c = int(255 * (1 - abs(h % 2 - 1)))
            r, g, b = [(255, c, 0), (c, 255, 0), (0, 255, c), (0, c, 255), (c, 0, 255), (255, 0, c)][min(5, int(h))]
            pts.append(wave_point(36, 12, rgb565(r, g, b), rgb565(255, 255, 255)))
        else:
            raise ValueError(name)
    return pts


def wav_points(path):
    import wave, numpy as np
    with wave.open(path, 'rb') as w:
        ch, sw, n = w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n); sr = w.getframerate()
    if sw == 2:
        a = np.frombuffer(raw, '<i2').astype(np.float32) / 32768
    elif sw == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        a = ((b[:, 0].astype(np.int32) | b[:, 1].astype(np.int32) << 8 | b[:, 2].astype(np.int32) << 16) << 8 >> 8) / 8388608.0
    else:
        raise ValueError('only 16/24-bit PCM WAV supported')
    a = a.reshape(-1, ch).mean(axis=1)
    seg = np.array_split(a, WAVE_POINTS)
    peak = np.array([np.abs(s).max() if len(s) else 0 for s in seg])
    rms = np.array([np.sqrt((s ** 2).mean()) if len(s) else 0 for s in seg])
    # crude 3-band colour: low/mid/high energy ratio via first-difference proxies
    hi = np.array([np.abs(np.diff(s)).mean() if len(s) > 1 else 0 for s in seg])
    norm = peak.max() or 1
    pts = []
    for p, r, h in zip(peak, rms, hi):
        bright = min(1.0, h / (r + 1e-9) / 2)
        col_o = rgb565(int(255 * bright), int(100 + 100 * bright), int(255 * (1 - bright)))
        pts.append(wave_point(40 * p / norm, 40 * r / norm, col_o, rgb565(255, 255, 255)))
    return pts


# ---------------------------------------------------------------- transport

def open_device():
    import hid
    cands = [d for d in hid.enumerate(VID, PID) if d.get('interface_number', HID_IFACE) in (HID_IFACE, -1)]
    if not cands:
        sys.exit('DDJ-1000 (2B73:0020) HID interface not found')
    dev = hid.device()
    dev.open_path(cands[0]['path'])
    return dev


def send(pkts, dry_run, interval, verbose=False, no_report_id=False, repeat=1):
    if dry_run:
        for i, p in enumerate(pkts):
            print('%3d %s' % (i + 1, p.hex(' ')))
        return
    dev = open_device()
    try:
        info = dev.get_manufacturer_string()
        print('opened: %s / %s' % (info, dev.get_product_string()))
    except Exception as e:
        print('opened (string read failed: %s)' % e)
    total = 0; errors = 0
    try:
        for _ in range(repeat):
            for i, p in enumerate(pkts):
                buf = p if no_report_id else (b'\x00' + p)   # macOS hidapi: 0x00 = no report ID
                try:
                    n = dev.write(buf)
                except Exception as e:
                    print('write[%d] raised: %s' % (i, e)); errors += 1; n = -1
                if n is not None and n >= 0:
                    total += 1
                else:
                    errors += 1
                if verbose:
                    print('write[%2d] -> %r  %s' % (i, n, p[:8].hex(' ')))
                time.sleep(interval)
    finally:
        dev.close()
    print('sent %d packets, %d errors (report_id_prefix=%s)' % (total, errors, not no_report_id))


# ---------------------------------------------------------------- self test (mirrors firmware reassembly)

def selftest():
    pts = pattern_points('sine')
    pk = wave_packets(1, pts, centered=True)
    assert len(pk) == 73 and all(len(p) == 64 for p in pk)
    buf = bytearray(WAVE_BYTES); got = bytearray(WAVE_BYTES)
    for p in pk:                                        # == task_hid ',' branch + wave_store()
        idx, total = struct.unpack_from('<HH', p, 2)
        src, ln, off = (p[7:], 0x39, 0) if idx == 1 else (p[6:], 0x3A, idx * 0x3A - 0x3B)
        ln = min(ln, WAVE_BYTES - off) if off < WAVE_BYTES else 0
        buf[off:off + ln] = src[:ln]; got[off:off + ln] = b'\1' * ln
    assert bytes(buf) == b''.join(pts) and all(got), 'waveform reassembly mismatch'
    blob = bytes(range(256)) * 20 + b'end'
    pk = art_packets(2, blob)
    buf = bytearray(ART_MAX)
    for p in pk:                                        # == task_hid '+' branch + art_store()
        idx = struct.unpack_from('<H', p, 2)[0]
        if idx == 1:
            size = struct.unpack_from('<H', p, 6)[0]; buf[0:0x38] = p[8:8 + 0x38]
        else:
            off = idx * 0x3A - 0x3C; buf[off:off + 0x3A] = p[6:6 + 0x3A]
    assert bytes(buf[:size]) == blob, 'artwork reassembly mismatch'
    s = status_packet(1, bpm=128.5, tempo_pct=-3.25, elapsed_ms=61234, remain_ms=120500)
    v = struct.unpack_from('<H', s, 21)[0]
    assert (v & 0xFFF) * 10 + (s[22] >> 4) == 1285 and struct.unpack_from('<h', s, 23)[0] == -325
    print('selftest OK: waveform 73 pkts, artwork %d pkts, status encoding' % len(pk))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list')
    sub.add_parser('selftest')
    for name in ('wave', 'art', 'status'):
        s = sub.add_parser(name)
        s.add_argument('--deck', type=int, default=1, help='deck 1..4 (left jog shows 1/3, right 2/4)')
        s.add_argument('--dry-run', action='store_true', help='print packets instead of sending')
        s.add_argument('--interval', type=float, default=0.008, help='seconds between reports (default 8 ms)')
        s.add_argument('--verbose', action='store_true', help='print each write and its byte count')
        s.add_argument('--no-report-id', action='store_true', help='do NOT prepend the 0x00 report-ID byte')
        s.add_argument('--repeat', type=int, default=1, help='send the whole burst N times (keeps it on screen)')
        if name == 'wave':
            g = s.add_mutually_exclusive_group()
            g.add_argument('--pattern', choices=['sine', 'ramp', 'bars', 'rainbow'], default='sine')
            g.add_argument('--wav', help='16/24-bit PCM WAV file (needs numpy)')
            s.add_argument('--centered', action='store_true', help='mirrored bars instead of bottom-aligned')
            s.add_argument('--clear', action='store_true', help='send "no waveform" (enable bit cleared)')
        if name == 'art':
            s.add_argument('image', help='JPEG/PNG/GIF file, <=10240 bytes, ideally 80x80')
        if name == 'status':
            s.add_argument('--bpm', type=float); s.add_argument('--tempo', type=float)
            s.add_argument('--elapsed', type=float, help='seconds'); s.add_argument('--remain', type=float, help='seconds')
    a = ap.parse_args()
    if a.cmd == 'selftest':
        return selftest()
    if a.cmd == 'list':
        import hid
        for d in hid.enumerate(VID, PID):
            print(d)
        return
    if a.cmd == 'wave':
        pts = [wave_point(0, 0, 0, 0)] * WAVE_POINTS if a.clear else (wav_points(a.wav) if a.wav else pattern_points(a.pattern))
        pk = wave_packets(a.deck, pts, centered=a.centered, enable=not a.clear)
    elif a.cmd == 'art':
        pk = art_packets(a.deck, open(a.image, 'rb').read())
    else:
        pk = [status_packet(a.deck, a.bpm, a.tempo,
                            None if a.elapsed is None else a.elapsed * 1000,
                            None if a.remain is None else a.remain * 1000)]
    send(pk, a.dry_run, a.interval, verbose=a.verbose, no_report_id=a.no_report_id, repeat=a.repeat)


if __name__ == '__main__':
    main()
