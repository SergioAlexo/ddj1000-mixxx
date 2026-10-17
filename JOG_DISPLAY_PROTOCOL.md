# DDJ-1000 jog display protocol

How the Pioneer DDJ-1000 draws artwork, a beat grid and an overview **waveform**
on its two jog-wheel screens, and how to drive them with open software — no
rekordbox, no firmware flash.

**Status: solved and confirmed live** (macOS, Apple Silicon, firmware v1.12,
2026-10-15). A custom waveform renders on a jog screen end-to-end from open code.
Reverse-engineered from the owner's own hardware and firmware
(`USB1_Ver.1120.bin`) plus Windows USBPcap captures of rekordbox 7.2.18
(`captures/`). Reference implementation in [`tools/`](tools/) (the `ddj_*.py`
scripts); see [`tools/ddj_jog_live.py`](tools/ddj_jog_live.py) for the whole chain.

> Earlier revisions of this document concluded the display handshake depended on
> an unknowable secret and gave up on the screens. That was wrong: the handshake
> is FNV-1a + XOR with a universal constant, **no secret** (§3). This revision
> supersedes that conclusion.

## 1. Two operating modes

The jog screens have two modes; read the **HID interface-3 input report head** to
tell them apart:

| Mode | HID input head | Jog shows |
|---|---|---|
| MIDI / standard | `00 00` | platter/clock view: ring, time, BPM, cue, position |
| HID / performance | `00 20` + live data | artwork + **waveform** + full performance UI |

Performance mode **does not latch** — stop feeding it and the head reverts
`00 20` → `00 00` within ~1 s. Internally this is the firmware's `model` value:
`0x102` = MIDI/standard, `0x202` = HID/performance.

The MIDI-mode platter view is fully driveable over MIDI alone (ring, time, BPM,
cue, position — the official *DDJ-1000 MIDI Message List*). The waveform/artwork
live only in HID performance mode, which the §3 handshake unlocks.

## 2. The full chain to a waveform on screen (all steps proven)

1. **Go live.** Open the DDJ USB audio device **full-duplex** and stream silence;
   this clears the "no audio driver" screen and makes the unit live. (Pioneer
   VersionViewer must be running — see §6.)
2. **Arm the cert.** Send the SysEx poll **`50 01`**
   (`F0 00 40 05 00 00 02 00 00 50 01 F7`). The unit replies `11 02` (ready) and
   beacons it every 1 s. This is rekordbox's arming poll; sending it ourselves
   arms the unit identically.
3. **Handshake** (§3): `0x12` → `0x13` → `0x14` → `0x15`. On accept, the HID input
   head flips `00 00` → `00 20` (performance mode).
4. **Leave the logo.** Replay rekordbox's post-handshake MIDI init burst (~413
   short messages on channels `0x90`–`0x9F`), which takes the jog off the idle
   Pioneer logo into the deck view.
5. **Render.** Send a real beat grid (`0x2F`), artwork (`0x2B`), a playing status
   (`0x21`), then the `0x2C` waveform. A real beat grid is required — it is the
   waveform's time axis; an empty one is not enough.
6. **Hold.** Keep the session alive with the continuous `0x21` status stream
   (~125/s) **plus** the `50 01` keepalive (~5/s). Send the `0x2C` waveform **once**
   — re-sending forces a full redraw (visible blink); the status stream keeps it
   on screen.

## 3. The unlock handshake (FNV-1a, no secret)

Read directly out of the firmware (`cert_on_host_msg` → `FUN_1c081c1c` parser →
`FUN_1c081a02` responder → `FUN_1c081e54` verifier). There is no secret and no
real cryptography — the answers depend only on data on the wire plus fixed
constants baked into firmware:

| Primitive | Firmware addr | What it is |
|---|---|---|
| `cert_calc` | `1c0819a4` | `a ^ b` (XOR) |
| FNV-1a | `1c08a000` | `h = (h ^ byte) * 0x01000193`, init `0x811c9dc5` |
| key derive | `1c08192c` | first 8 bytes of a string, each bitwise-NOT'd, then FNV-1a |
| tag-5 checks | `1c089fec` + `1c08a048` | word-sum + transform vs a fixed 16-byte constant; input is only the tag-5 block itself |

**Universal constant** (same on every unit): `k = FNV1a(~"PioneerD") = 0x680131FB`.

### Wire format
`F0 00 40 05 00 00 02 00 00  <type> <len>  <TLV blocks>  F7`, with
`len = 2 + Σ block lengths` and `block = <tag><blocklen=2+datalen><data>`. A 32-bit
value is sent as **8 nibbles** (MSB first, one nibble in the low 4 bits of each
byte). Types: `0x11` ready, `0x12` host challenge, `0x13` unit reply, `0x14` host
response, `0x15` accepted; `0x50` arm poll; `0x03` position request.

### Exchange
1. Unit → `11 02` (ready), beaconed once armed (§2.2).
2. Host → `12`: tag1 `"PioneerDJ"`, tag2 `"rekordbox"`, tag3 = 8-byte random challenge `HC`.
3. Unit → `13`: tag1 `"PioneerDJ"`, tag2 `"DDJ1000"`, tag4 = `FNV1a(HC ++ BE(k^r))`, tag3 = unit nonce `r`.
   tag4 is **predictable** from `HC`, `k`, `r` — a self-check that the model is correct.
4. Host → `14`: tag1, tag2, tag4 = **`FNV1a( BE(r) ++ BE(k^r) )`**, tag5 = fixed 10-byte block
   `87 a0 8e ea c0 90 34 76 0b 90` (identical every session — its checks touch only itself).
5. Unit → `15 02` = **accepted**; the HID artwork/waveform channel is unlocked for the session.

Implemented in [`tools/ddj_cert.py`](tools/ddj_cert.py) (run it for a self-test).

## 4. HID channel

Interface **3** (usage page `0xFFA0`, usage 1), 64-byte OUT reports, no report ID.
`byte0` = `deck << 4` (`0x10`..`0x40` for decks 1–4), `byte1` = message type.

### Chunked transfers (`0x2B`, `0x2C`, `0x2D`, `0x2F`)
```
byte 0    deck << 4
byte 1    type
byte 2-3  sequence number (1..N), u16 LE
byte 4-5  N = total packets of this transfer, u16 LE
byte 6..  payload; payloads are concatenated across packets, last one zero-padded
```
(`0x2C` packet 1 carries one flag byte at offset 6, then payload from offset 7.)

| Type | Meaning | Payload |
|---|---|---|
| `0x2B` artwork | 27–34 pkts | u16 LE length, then a baseline **JPEG, 80×80** (≤ 10240 bytes). |
| `0x2F` beat grid | — | u16 LE count, then count × 4 bytes: `beat-in-bar` (1..4), `position_ms` (u24 LE). Confirmed: size = `2 + 4·count`. |
| `0x2C` waveform | 73 pkts, 4201 B | 1 flag byte, then **600 columns × 7 bytes** (see below). |
| `0x2D` preview / track info | 1 pkt | `02 <u24 track length ms> 0a 00` then ten 5-byte entries. |
| `0x30` track info | 2 pkts | `[deck<<4][0x30][seq][0][02 00]` + `02 <u24 track length ms> 00 00`. |

### `0x2C` waveform column (7 bytes) — decoded
```
offset 0-1  colour A  RGB565, u16 LE   (outer bar)   — 0 selects firmware preset `preset`
offset 2-3  colour B  RGB565, u16 LE   (inner bar)
offset 4    height A  0..40 px         (outer bar, bottom-aligned)
offset 5    height B  0..40 px         (inner bar, drawn over A, clamped ≤ A)
offset 6    preset    0..7             (firmware preset colour when colour A == 0)
```
Flag byte (packet 1, offset 6): bit7 `0x80` = enable/show, bit6 `0x40` = centered
(mirrored bars) vs bottom-aligned. Builders in
[`tools/ddj_jog.py`](tools/ddj_jog.py) (`wave_point`, `wave_packets`, `rgb565`).

### `0x21` live status (~120/s per deck)
`[deck<<4][0x21]…`. Partly decoded; confirmed fields in **bold**:

| byte | value | meaning |
|---|---|---|
| 2 | `0x18` normal; `0x19/1a/1b` scratching | jog movement/direction flags |
| 3 | `0x08`/`0x0a` | pulses with the beat |
| 4 | `0x11`; `0x10` while touched | bit 0 = platter not touched |
| 5 | bit 7 | **playing** (bit 7 set = playing) |
| 9 | **`0xb4` track loaded**, `0x10` none | track-loaded flag |
| 11–13 | 24-bit **big-endian**, e.g. `00 00 7e` | **playback position** = elapsed_seconds × 256 (unit = 1/256 s). Decoded from the capture; byte 12 ticks once per track-second, field advances at 256/s scaled by deck tempo. Drives the jog's time/cursor. |
| 14 | `0`–`3` | beat-in-bar phase |
| 15 | `0x02` marker | precedes the track length |
| 16–18 | u24 LE, e.g. `01 39 03` = 211201 | **track length in ms** |
| 21–22 | `86 40` | BPM / pitch (not fully decoded) |
| others | change with loops/cues/jog | markers / loop points |

## 5. Order rekordbox uses
On track load: beat grid → preview (×2) → artwork → waveform (~0.4 s later), with
the `0x21` status stream running throughout. All four decks are cleared with empty
transfers at startup.

## 6. Operational gate: VersionViewer
`/Applications/Pioneer/DDJ-1000/VersionViewer.app` (the "DDJ-1000 AutoLauncher")
must be running, or the jog shows "no audio driver" and the cert stays asleep.
VersionViewer alone leaves the unit in MIDI/standard mode; only the `50 01` poll
(§2.2) arms the handshake. (An earlier note calling the AutoLauncher the villain
was wrong — it is the operational gate, confirmed live.)

## 7. Confirmed vs still open
**Confirmed live:** the whole chain §2, the handshake §3 (our predicted `0x13`
matched the unit exactly → `0x15` accept), performance-mode flip, a custom
`0x2C` waveform rendering with a real `0x2F` beat grid, and the `0x21` position
encoding (§4, bytes 11–13).

**Still open:** the spinning-platter graphic does not stay perfectly in sync
(periodic skip) even with a smooth monotonic position stream — likely a separate
platter field or a rate/timing detail; the per-beat-cycling `0x21` bytes
(b21/b22, b31/b32, b55/b56, b3 beat pulse) are candidates. Also the `0x2D` entry
fields and the remaining marker/loop bytes.

## 8. Driving this from Mixxx (confirmed 2.7.0, live)

A Mixxx mapping exists in the `sergioalexo/mixxx` fork, branch
`ddj-1000-jog-displays` (rebased onto Mixxx `main`). The waveform renders live.
Non-obvious things that had to be right:

- **Audio go-live gates the screen.** The jog stays on the loading animation
  until Mixxx opens the DDJ **full-duplex** (both an output *and* an input in
  Sound Hardware). Output-only does not wake it. The DDJ exposes 12 input / 6
  output channels; a Master output + any input (e.g. Auxiliary) suffices.
- **Incoming SysEx needs an XML binding.** Mixxx only passes SysEx to a script's
  `incomingData` when the `.midi.xml` declares a `<control>` with
  `<status>0xF0</status>` and `<Script-Binding/>`. Without it the cert replies
  (`0x11/0x13/0x15`) never reach the script and the handshake stalls after arming.
- **HID output FIFO holds 32 reports**, drained one per IO-thread loop. Dumping
  the 73-packet `0x2C` waveform at once overflows it; pace the burst in chunks.
  Re-sending the waveform repeatedly floods the IO thread and makes the whole
  jog display lag — send the beat grid once and the waveform as few times as
  possible (the no-blink rule in §2.6 is also a performance requirement here).
- **Suppress MIDI-mode jog-display writes in performance mode.** Streaming the
  MIDI clock/time and platter-angle (`9n`/`Bn` position) while in HID performance
  mode fights the HID display and reverts the unit to the loading view.

## 9. Tools (`tools/`)
| Script | What it does |
|---|---|
| `ddj_jog_live.py` | Standalone driver: full chain + a custom waveform, no capture at runtime. `python3 -I tools/ddj_jog_live.py --deck 1 --pattern square --hold 60` |
| `ddj_cert.py` | Handshake crypto (FNV-1a, `k`, build/parse `0x12/0x13/0x14`); self-test when run directly. |
| `ddj_jog.py` | HID packet builders (`wave_packets`, `art_packets`, `status_packet`, …); `python3 tools/ddj_jog.py selftest`. |
| `ddj_jog_initdata.py` | Bundled init data (leave-logo burst + a real beat grid/artwork/status), retargetable to any deck. |
| `ddj_full_unlock.py` | Minimal go-live + arm + handshake. |
| `ddj_arm_test.py` | Minimal proof that `50 01` arms the cert and the handshake reaches `0x15`. |
| `ddj_render_custom.py` / `ddj_render_capture.py` | Unlock + draw a custom / the captured waveform, context sourced live from a capture. |
| `usbmidi_timeline.py` | Capture decoder (USB-MIDI reassembly + timeline). |

Needs `python-rtmidi`, `sounddevice`, `hidapi` (`numpy` only for `--wav`).
