#!/usr/bin/env python3
"""DDJ-1000 jog-display unlock handshake, reimplemented from the unit's own firmware
(USB1_Ver.1120.bin: cert_on_host_msg / FUN_1c081c1c / FUN_1c081a02 / FUN_1c081e54).

No secret is involved: the whole scheme is FNV-1a + XOR + a fixed tag-5 block.
This lets open software (e.g. a Mixxx mapping) pass the same handshake rekordbox does,
which unlocks the HID waveform/artwork channel on the jog screens.

SysEx wire format (over USB-MIDI):
    F0 00 40 05 00 00 02 00 00  <type> <len>  <TLV blocks...>  F7
      type 0x12 host->unit challenge, 0x13 unit->host reply, 0x14 host->unit response,
      0x11 unit idle/ready, 0x15 unit accepted.
    len = 2 + sum(block lengths).
    block = <tag> <blocklen = 2 + datalen> <data...>
      tag1 = "PioneerDJ", tag2 = "rekordbox"/"DDJ1000", tag3/tag4 = 32-bit value as 8
      nibbles (MSB nibble first, one nibble per byte, low 4 bits), tag5 = fixed 10-byte block.
"""
import struct

FNV_OFF = 0x811C9DC5
FNV_PRIME = 0x01000193

# Universal constant k = FNV1a(~"PioneerD"). Same on every DDJ-1000 (derived, not per-unit).
K = 0x680131FB

# Fixed tag-5 block rekordbox sends in the 0x14 response, unchanged every session.
# Its firmware checks (word-sum + a transform against a fixed 16-byte constant) touch only
# this block, so a captured-valid block is universally valid. 10 bytes.
TAG5 = bytes.fromhex("87a08eeac09034760b90")

HDR = bytes([0xF0, 0x00, 0x40, 0x05, 0x00, 0x00, 0x02, 0x00, 0x00])


def fnv1a(data):
    h = FNV_OFF
    for b in data:
        h = ((h ^ b) * FNV_PRIME) & 0xFFFFFFFF
    return h


def _k_const():
    """Recompute k from the string, to prove it is not a magic number."""
    s = b"PioneerDJ"[:8]
    return fnv1a(bytes((~c) & 0xFF for c in s))


def nibbles_of(value, nbytes):
    """big-endian value -> one nibble per byte (low 4 bits), MSB nibble first."""
    out = []
    for by in value.to_bytes(nbytes, "big"):
        out.append((by >> 4) & 0xF)
        out.append(by & 0xF)
    return bytes(out)


def value_from_nibbles(nb):
    v = 0
    for n in nb:
        v = (v << 4) | (n & 0xF)
    return v


def _block(tag, data):
    return bytes([tag, len(data) + 2]) + data


def _wrap(msg_type, blocks):
    payload = bytes([msg_type, 2 + len(blocks)]) + blocks
    return HDR + payload + bytes([0xF7])


def build_12(host_challenge):
    """host_challenge: 8 random bytes (not all-00, not all-FF)."""
    assert len(host_challenge) == 8
    hc = int.from_bytes(host_challenge, "big")
    blocks = (_block(1, b"PioneerDJ") + _block(2, b"rekordbox") +
              _block(3, nibbles_of(hc, 8)))
    return _wrap(0x12, blocks)


def parse_13(sysex):
    """Return dict with unit nonce r and the unit's answer, or None if not a 0x13."""
    body = _strip(sysex)
    if body is None or body[0] != 0x13:
        return None
    blocks = body[2:]
    fields = _tlv(blocks)
    r = value_from_nibbles(fields[3]) if 3 in fields else None
    unit_ans = value_from_nibbles(fields[4]) if 4 in fields else None
    return {"r": r, "unit_answer": unit_ans,
            "str1": fields.get(1), "str2": fields.get(2)}


def host_answer(host_challenge, r):
    """Our answer to the unit nonce r. = FNV1a( BE(r) ++ BE(k^r) )."""
    kr = (K ^ r) & 0xFFFFFFFF
    return fnv1a(struct.pack(">I", r) + struct.pack(">I", kr))


def predict_unit_answer(host_challenge, r):
    """What the unit must have put in 0x13 tag4: FNV1a( HC(8) ++ BE(k^r) ). Self-check."""
    kr = (K ^ r) & 0xFFFFFFFF
    return fnv1a(host_challenge + struct.pack(">I", kr))


def build_14(host_challenge, r):
    ans = host_answer(host_challenge, r)
    blocks = (_block(1, b"PioneerDJ") + _block(2, b"rekordbox") +
              _block(4, nibbles_of(ans, 4)) + _block(5, nibbles_of(int.from_bytes(TAG5, "big"), 10)))
    return _wrap(0x14, blocks)


def is_accept(sysex):
    body = _strip(sysex)
    return body is not None and body[0] == 0x15


def is_ready(sysex):
    body = _strip(sysex)
    return body is not None and body[0] == 0x11


def msg_type(sysex):
    body = _strip(sysex)
    return None if body is None else body[0]


def _strip(sysex):
    """Validate the Pioneer header/footer and return the [type][len][blocks] payload."""
    s = bytes(sysex)
    if len(s) < 12 or s[0] != 0xF0 or s[-1] != 0xF7:
        return None
    if s[1:4] != bytes([0x00, 0x40, 0x05]) or s[4:8] != bytes([0x00, 0x00, 0x02, 0x00]):
        return None
    return s[9:-1]


def _tlv(blocks):
    out = {}
    i = 0
    while i + 1 < len(blocks):
        tag = blocks[i]
        blen = blocks[i + 1]
        if blen < 2:
            break
        out[tag] = blocks[i + 2:i + blen]
        i += blen
    return out


if __name__ == "__main__":
    assert _k_const() == K, "k mismatch"
    print("k (recomputed from \"PioneerD\") = %08x  OK" % _k_const())
    # round-trip sanity
    hc = bytes(range(1, 9))
    m12 = build_12(hc)
    print("0x12:", m12.hex())
    r = 0x11223344
    print("predict unit answer(r=%08x) = %08x" % (r, predict_unit_answer(hc, r)))
    print("host answer       (r=%08x) = %08x" % (r, host_answer(hc, r)))
    print("0x14:", build_14(hc, r).hex())
