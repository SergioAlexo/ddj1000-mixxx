# DDJ-1000 protocol reference

Every SysEx and HID message found in the rekordbox USB captures, byte by byte,
including the bytes we have not decoded yet. Companion to
[`JOG_DISPLAY_PROTOCOL.md`](JOG_DISPLAY_PROTOCOL.md), which explains how the
messages are used together (unlock chain, ordering, Mixxx notes) and contains
only facts confirmed on the unit.

**Status tags used in every table**

| Tag | Meaning |
|---|---|
| **confirmed** | tested on the DDJ-1000 and behaves as described |
| **capture** | meaning inferred from the captures (or firmware), not tested on the unit |
| **unknown** | the byte varies (or exists) but its meaning is not known |
| **zero** | always `00` in every capture |

Counts (`n=`) are the number of messages of that kind across all five decoded
captures (see [Sources](#6-sources-and-method)).

---

## 1. Transports

| Channel | USB endpoint | Direction | Carries |
|---|---|---|---|
| USB-MIDI | `0x04` bulk OUT | host → unit | SysEx (§2), LED/pad MIDI (not covered here) |
| USB-MIDI | `0x85` bulk IN | unit → host | SysEx replies (§2), controls as Note/CC |
| HID interface 3 | `0x06` interrupt OUT | host → unit | jog-screen reports (§3) |
| HID interface 3 | `0x87` interrupt IN | unit → host | state report (§4) |
| Control | `0x00` / `0x80` | both | standard USB only (descriptors, SET_CONFIGURATION, SET_INTERFACE, UAC sample rate) — **no vendor requests** |

HID interface 3: usage page `0xFFA0`, usage 1, **64-byte reports, no report ID**.

---

## 2. SysEx messages

All Pioneer SysEx share one envelope:

```
F0  00 40 05  00 00 02 00 00  <type…>  F7
    └Pioneer┘ └─ fixed ─────┘
```

Two type styles exist: a single type byte (`50`, `03`, `11`–`15`) and a `00`
prefix + type byte (`00 0A`/`0B`/`0C`).

| Type | Direction | Length | n | Purpose | Status |
|---|---|---|---|---|---|
| `50 01` | host → unit | 12 | 3602 | arm poll / session keepalive | confirmed |
| `03 01` | host → unit | 12 | 15 | request control-position dump | confirmed |
| `11 02` | unit → host | 12 | 6 | handshake: ready | confirmed |
| `12` | host → unit | 52 | 3 | handshake: host challenge | confirmed |
| `13` | unit → host | 52 | 3 | handshake: unit reply | confirmed |
| `14` | host → unit | 66 | 3 | handshake: host response | confirmed |
| `15 02` | unit → host | 12 | 3 | handshake: accepted | confirmed |
| `00 0A` | host → unit | 54 | 27 | BEAT FX screen: effect name | confirmed |
| `00 0B` | host → unit | 18 | 360 | BEAT FX screen: beat value | confirmed |
| `00 0C` | host → unit | 20 | 361 | BEAT FX screen: BPM | confirmed |

No other SysEx appears in the captures, in either direction.

### 2.1 `50 01` — arm poll / keepalive

```
F0 00 40 05 00 00 02 00 00 50 01 F7
```

| Byte | Value | Meaning | Status |
|---|---|---|---|
| 9 | `50` | type | confirmed |
| 10 | `01` | sub-type / length (only `01` seen) | unknown |

rekordbox sends it ~5×/s. The unit arms the handshake and beacons `11 02`
once per second; performance mode drops ~1 s after the polls stop.

### 2.2 `03 01` — control-position request

```
F0 00 40 05 00 00 02 00 00 03 01 F7
```

| Byte | Value | Meaning | Status |
|---|---|---|---|
| 9 | `03` | type: position request | confirmed |
| 10 | `01` | only `01` seen | unknown |

**Reply** (within ~1 ms): plain 14-bit Control Changes, not SysEx — every
absolute control on all four decks (channels `B0`–`B3`) and the mixer
(`B4`/`B6`), MSB on CC `0x00`–`0x1F`, LSB on CC + `0x20`. Also includes the
BEAT FX state on note `94 46`.

| CC (MSB / LSB) | Control (per deck channel) | Status |
|---|---|---|
| `0x00` / `0x20` | TEMPO slider | confirmed |
| `0x04` / `0x24` | channel TRIM | confirmed |
| `0x07` / `0x27` | EQ HI | confirmed |
| `0x0B` / `0x2B` | EQ MID | confirmed |
| `0x0F` / `0x2F` | EQ LOW | confirmed |
| `0x13` / `0x33` | channel fader | confirmed |

### 2.3 Handshake `11`–`15`

```
F0 00 40 05 00 00 02 00 00  <type> <len>  <TLV blocks>  F7
len   = 2 + Σ block lengths
block = <tag> <blocklen = 2 + datalen> <data>
32-bit values are sent as 8 nibbles, MSB first (low 4 bits of each byte)
```

| Type | Tags | Status |
|---|---|---|
| `11 02` | none — ready beacon | confirmed |
| `12` | tag1 `"PioneerDJ"`, tag2 `"rekordbox"`, tag3 = 8-byte host challenge `HC` | confirmed |
| `13` | tag1 `"PioneerDJ"`, tag2 `"DDJ1000"`, tag3 = unit nonce `r`, tag4 = `FNV1a(HC ++ BE(k^r))` | confirmed |
| `14` | tag1, tag2, tag4 = `FNV1a(BE(r) ++ BE(k^r))`, tag5 = `87 a0 8e ea c0 90 34 76 0b 90` (fixed) | confirmed |
| `15 02` | none — accepted, HID channel unlocked | confirmed |

`k = 0x680131FB`. Full derivation in `JOG_DISPLAY_PROTOCOL.md` §3 and
`tools/ddj_cert.py`.

| Open point | Status |
|---|---|
| Meaning of tag5 (fixed block; firmware only checks it against itself) | unknown |
| Any other `11`/`15` second byte than `02` (never seen) | unknown |

### 2.4 `00 0A` — BEAT FX effect name

```
F0 00 40 05 00 00 02 00 00  00 0A  00 28 00 26  <38 packed bytes>  F7
```

| Byte(s) | Value | Meaning | Status |
|---|---|---|---|
| 9–10 | `00 0A` | type | confirmed |
| 11–12 | `00 28` | outer length (n + 2) | confirmed |
| 13–14 | `00 26` | packed data length n | confirmed |
| 15… | 38 bytes | 7-bit packed (LSB-first bit stream): `00` + 32 ASCII, zero-padded | confirmed |
| unpacked byte 0 | `00` | always `00` | unknown |

### 2.5 `00 0B` — BEAT FX beat value

```
F0 00 40 05 00 00 02 00 00  00 0B  <6 packed bytes>  F7
```

| Byte(s) | Meaning | Status |
|---|---|---|
| 11–16 | 7-bit packed, 5 ASCII bytes (`"1"`, `"1/16"`, `"3/4"` …) | confirmed |

### 2.6 `00 0C` — BEAT FX BPM

```
F0 00 40 05 00 00 02 00 00  00 0C  00 00 a b c d 00 00  F7
```

| Byte(s) | Meaning | Status |
|---|---|---|
| 11–12 | `00 00` | zero |
| 13–16 | BPM × 100, one nibble per byte, MSB first (`03 01 0a 06` = 127.10) | confirmed |
| 17 | `00` sets a firmware flag (`fff87eb2[1]`); always `00` from rekordbox | unknown |
| 18 | stored at `fff87eb2[2]`; always `00` from rekordbox | unknown |

---

## 3. HID OUT reports (host → unit, endpoint `0x06`)

Every report is 64 bytes. Bytes 0–1 are the same for all types:

| Byte | Meaning | Status |
|---|---|---|
| 0 | `deck << 4`: `10` / `20` / `30` / `40` for decks 1–4 (low nibble always 0) | confirmed |
| 1 | message type | confirmed |

| Type | Name | n | Decks seen | Status |
|---|---|---|---|---|
| `0x21` | live status | 140260 | 1, 2 only | partly decoded |
| `0x2B` | artwork | 431 pkts | 1–4 | confirmed |
| `0x2C` | waveform | 2466 pkts | 1–4 | confirmed |
| `0x2D` | cue info ("preview"?) | 118 pkts | 1–4 | partly decoded |
| `0x2F` | beat grid | 424 pkts | 1–4 | confirmed |
| `0x30` | hot-cue list | 288 pkts | 1–4 | confirmed |

No other type byte appears in the captures.

### 3.1 Chunked-transfer header (`0x2B`, `0x2C`, `0x2D`, `0x2F`, `0x30`)

| Byte(s) | Meaning | Status |
|---|---|---|
| 0 | deck | confirmed |
| 1 | type | confirmed |
| 2–3 | packet sequence 1..N, u16 LE (byte 3 always `00` in captures) | confirmed |
| 4–5 | N = total packets, u16 LE (byte 5 always `00` in captures) | confirmed |
| 6–63 | 58 bytes of payload; payloads concatenate, last packet zero-padded | confirmed |

A transfer with **N = 1 and an empty payload clears** that item (sent for all
four decks at startup). Seen N values: `0x2B` 16–34, `0x2C` always 73, `0x2D`
always 1, `0x2F` 9–32, `0x30` always 2.

### 3.2 `0x21` — live status (~120/s per deck)

Sent only for decks 1 and 2 in the captures (never 3/4). Example, deck 1:

```
10 21 1a 0a 11 81 00 00 00 b4 00 00 15 be 00 02 3a 50 00 00 00 98 90 3c …
```

"Seen" lists the values found in the captures, most common first.

| Byte(s) | Seen | Meaning | Status |
|---|---|---|---|
| 0 | `10`, `20` | deck | confirmed |
| 1 | `21` | type | confirmed |
| 2 | `1a` `18` `19` `1b` `00` | bit 0 = SLIP (red screen), bit 1 = paused (dimmed platter), bits 3–4 always set except in an all-zero frame | confirmed (bits 0–1), unknown (rest) |
| 3 | `08` `0a` `18` `1a` `00` | bit 1 = ON AIR (bright screen) | confirmed (bit 1) |
| | | **bit 4** (`18`/`1a`, ~500 frames) | unknown |
| 4 | `11` `10` `21` | bit 0 = jog ring light | confirmed (bit 0) |
| | | **bit 5** (`21`, 50 frames) | unknown |
| 5 | `01` `81` `80` `00` | bit 7 labelled "playing", but stays set on a still deck — unreliable | capture |
| | | **bit 0** | unknown |
| 6–8 | `00` | — | zero |
| 9 | `b4` `bc` `10` `b6` `12` | `b4` = track loaded, `10` = no track | confirmed (b4/10) |
| | | **bit 3** (`bc`, ~11 000 frames), **bit 1** (`b6`, `12`) | unknown |
| 10 | `00` `0d` `06` `0a` `08` | `0d` appears exactly when bytes 25–30 hold an active loop → probably loop state | capture |
| 11–14 | — | elapsed position: min, sec, ms (u16 LE) | confirmed |
| | | byte 11 = `80` in 14 frames: sign bit (position before track start?) | unknown |
| 15–18 | — | track length: min, sec, ms (u16 LE) | confirmed |
| 19–20 | `00` | — | zero |
| 21–22 | — | BPM, u16 LE `(tenths << 12) \| whole` | capture |
| 23–24 | — | pitch, s16 LE, 0.01 % units | capture |
| 25–27 | — | u24 LE ms; equals the CUE point when a loop is active, else CUE + bit 23 set (`… 80`) → probably **loop in**, bit 23 = loop inactive | capture |
| 28–30 | — | u24 LE ms; always loop-in + 870 ms in the captures → probably **loop out** | capture |
| 31–33 | — | CUE point, u24 LE ms | confirmed |
| 34–37 | `00` | — | zero |
| 38–39 | — | copy of BPM (21–22) | capture |
| 40–54 | `00` | — | zero |
| 55–57 | — | active cue, u24 LE ms | confirmed |
| 58 | `01` `00` `03` | cue flags: `01` cue set, `03` hot cue, `00` none | confirmed |
| 59 | `00` `16` `24` | `16` = rekordbox default hot-cue green → probably active hot-cue colour | capture |
| 60 | 15 values (`02` `10` `06` `08` `0f` …) | changes with track/position | unknown |
| 61 | `0d` `0e` `00` `11` `0f` … | mostly `0d` | unknown |
| 62–63 | `00` | — | zero |

### 3.3 `0x2B` — artwork

| Payload offset | Meaning | Status |
|---|---|---|
| 0–1 | JPEG length, u16 LE | confirmed |
| 2… | baseline JPEG, 80×80, ≤ 10240 bytes | confirmed |

### 3.4 `0x2C` — waveform (73 packets, 4201 bytes used)

| Payload offset | Meaning | Status |
|---|---|---|
| 0 | flag: bit 7 `0x80` = show, bit 6 `0x40` = centred (mirrored) | confirmed |
| | rekordbox only sends `80` (track) or `00` (clear); bits 0–5 never seen set | unknown |
| 1… | 600 columns × 7 bytes | confirmed |

Column (7 bytes):

| Offset | Meaning | Status |
|---|---|---|
| 0–1 | colour A (outer), RGB565 u16 LE; `0` = use preset | confirmed |
| 2–3 | colour B (inner), RGB565 u16 LE | confirmed |
| 4 | height A, 0–40 px | confirmed |
| 5 | height B, 0–40 px (≤ A) | confirmed |
| 6 | preset colour 0–7 (when colour A = 0) | confirmed |

### 3.5 `0x2D` — cue info (1 packet)

Payload example:

```
02 1d 21 02  0a 00  9e 2f 27 01 00  ×10
```

| Payload offset | Meaning | Status |
|---|---|---|
| 0–3 | track length (min, sec, ms u16 LE) | confirmed |
| 4–5 | `0a 00` = 10 entries, u16 LE (count is probable) | capture |
| 6–55 | 10 × 5-byte entries, always `9e 2f 27 01 00` | unknown |

Never differs between tracks except the length. Replay verbatim.
`tools/jog_transfers.py` calls this type "preview" and §5 of the jog doc
mentions a "preview" on load — this is the same message (see §5 below).

### 3.6 `0x2F` — beat grid

| Payload offset | Meaning | Status |
|---|---|---|
| 0–1 | beat count, u16 LE | confirmed |
| 2… | count × 4 bytes: beat-in-bar (1–4), position ms (u24 LE) | confirmed |

### 3.7 `0x30` — hot-cue list (2 packets)

| Payload offset | Meaning | Status |
|---|---|---|
| 0–3 | track length (min, sec, ms u16 LE) | confirmed |
| 4… | 16 slots × 6 bytes: `[01] [colour] [4-byte time]`, empty slot = zeros | confirmed |
| slot byte 0 | always `01` when set — slot type? (cue / loop?) | unknown |

---

## 4. HID IN report (unit → host, endpoint `0x87`)

64 bytes, no report ID. Two heads appear:

| Head (bytes 0–1) | n | Mode | Status |
|---|---|---|---|
| `00 00` | 190 827 | MIDI / standard — **whole report is zeros**, no byte ever changes | confirmed |
| `00 20` | 724 316 | HID performance mode | confirmed |

Performance-mode report (example `00 20 12 00 c9 8b 51 b7 a9 d8 00 ff 03 00 00 …`):

| Byte(s) | Seen | Notes | Status |
|---|---|---|---|
| 0–1 | `00 20` | mode head | confirmed |
| 2 | 30 values, `12` mostly; `92` `32` `22` | single bits toggle (bits 4, 5, 7) → flags | unknown |
| 3 | `00` `02` `80` | flags | unknown |
| 4 | `c9` | constant | unknown |
| 5–8 | all 256 values each | a 32-bit value that changes constantly — counter, timer or session value | unknown |
| 9 | `d8` / `00` | two-state flag | unknown |
| 10 | `00` | constant | zero |
| 11–12 | `ff 03`, `00 00`, … up to 1023 | 10-bit u16 LE → possibly a jog / touch value (left?) | unknown |
| 13–14 | `00 00`, `ff 03`, … up to 1023 | same shape → possibly the other side | unknown |
| 15–63 | `00` | constant | zero |

Next step to decode: log this report live after the unlock and turn / touch
each jog, press SLIP, change decks one at a time.

---

## 5. Unknowns and conflicts

**Messages whose content is unknown**

- HID IN report bytes 2–9, 11–14 (§4) — the only message from the unit we cannot read.
- `0x2D` entries (`9e 2f 27 01 00` × 10).

**Unknown bytes in known messages**

- `0x21`: byte 2 bits 3–4, byte 3 bit 4, byte 4 bit 5, byte 5 bits 0 and 7,
  byte 9 bits 1 and 3, byte 10, byte 11 bit 7, bytes 25–30 (loop?), byte 59
  (cue colour?), bytes 60–61.
- `0x2C` flag bits 0–5.
- `0x30` slot byte 0.
- SysEx `50 01` / `03 01` second byte, handshake tag5, `00 0C` bytes 17–18,
  `00 0A` leading `00`.

**Conflicts between our files**

- `0x2D` is "cue info" in `JOG_DISPLAY_PROTOCOL.md` §4 but "preview" in
  `tools/jog_transfers.py`, and §5 says rekordbox sends a "preview (×2)" on
  load. The captures have no separate preview type, so these are the same
  message; one name should go.
- `JOG_DISPLAY_PROTOCOL.md` §4 calls `0x21` byte 5 bit 7 "playing", §7 says
  it is unreliable.

**Not covered here**

- MIDI channel messages from rekordbox (LEDs, pad colours) — compare against
  the official list in `tools/refs/DDJ-1000_MIDI_Message_List_E1.pdf`.

---

## 6. Sources and method

Captures: `captures/decoded`, `decoded2`–`decoded5` (Windows USBPcap,
rekordbox 7, decoded per endpoint by `tools/decode_capture.py`). All HID
reports on `0x06`/`0x87` were grouped by type byte / head, all SysEx on
`0x04`/`0x85` were reassembled from USB-MIDI packets and grouped by type, and
each byte position was checked for the set of values it takes. Every type in
the captures is listed above; nothing was left out.
