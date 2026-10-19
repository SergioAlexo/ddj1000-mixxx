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

### Control-position dump (`03 01`) — fader/knob sync on launch

The unit does **not** report fader/knob positions on its own, so software that
only listens starts out of sync with the hardware. rekordbox sends one SysEx on
connect — **`F0 00 40 05 00 00 02 00 00 03 01 F7`** (`0x03` position request,
same Pioneer envelope as the `50 01` arm) — and the unit answers **within ~1 ms**
with a Control-Change dump of every absolute control on **all four decks** (MIDI
channels `B0`–`B3`) and the mixer (`B4`/`B6`). Each is 14-bit: MSB on CC
`0x00`–`0x1F`, LSB on CC +`0x20`. This is how rekordbox syncs its faders at
startup. Works in plain MIDI mode — no handshake/performance-mode needed.

Per-deck CC map (channel `B0` = deck 1), MSB / LSB:

| CC (MSB/LSB) | Control |
|---|---|
| `0x00`/`0x20` | TEMPO slider |
| `0x04`/`0x24` | channel TRIM (gain) |
| `0x07`/`0x27` | EQ HI |
| `0x0B`/`0x2B` | EQ MID |
| `0x0F`/`0x2F` | EQ LOW |
| `0x13`/`0x33` | channel fader (volume) |

Decoded from `captures/decoded{3,4}/ep_85_t3.txt` (MIDI IN) against
`ep_04_t3.txt` (MIDI OUT): the `03 01` request immediately precedes the dump in
both captures (~0.7 ms apart).

### BEAT FX screen (`0a` name, `0b` beat, `0c` BPM) — confirmed on the unit

The FX screen above BEAT FX runs on its own with no software connected. Once a
host is connected it shows **only what the host sends**: without these messages
it freezes (FX SELECT no longer changes it). USB1 dispatches them in
`FUN_1c091944` (byte 9 = `00`, byte 10 = type). All three carry a `00` before
the type byte (unlike `03 01` / `50 01`):

```
F0 00 40 05 00 00 02 00 00  00 0A  00 <n+2> 00 <n>  <n packed bytes>  F7   effect name
F0 00 40 05 00 00 02 00 00  00 0B  <6 packed bytes>                   F7   beat value
F0 00 40 05 00 00 02 00 00  00 0C  00 00 a b c d 00 00                F7   BPM
```

- **7-bit packing** (`0a`, `0b`; unpacker `FUN_1c091af0`): the 8-bit data is one
  LSB-first bit stream cut into 7-bit bytes (byte *i* of the data = bits
  7*i*..7*i*+7 of the stream).
- **`0a` name**: data = `00` + 32 ASCII bytes, zero-padded (33 bytes → n = 38
  packed, header `00 28 00 26`). Stored at `fff87e88`. rekordbox's captured `0a`
  unpacks to `"LOW CUT ECHO"`. We send the FX SELECT position's name
  (LOW CUT ECHO, ECHO, MT DELAY, SPIRAL, REVERB, TRANS, ENIGMA JET, FLANGER,
  PHASER, PITCH, SLIP ROLL, ROLL, MOBIUS SAW, MOBIUS TRI).
- **`0b` beat**: data = 5 ASCII bytes (`"1"` → `31 00 00 00 00 00`). We send
  `1/16 1/8 1/4 1/2 3/4 1 2 4 8 16 32`; these display correctly.
- **`0c` BPM**: `a b c d` = **BPM × 100**, one nibble per byte, MSB first
  (`03 01 0a 06` = 127.10, `02 0f 09 04` = 121.80); stored at `fff87eae`. Byte 17
  = `00` sets a flag (`fff87eb2[1]`), byte 18 goes to `fff87eb2[2]`; meaning
  unknown, send `00 00` as rekordbox does.
- The BPM is that of the deck **CH SELECT** points at (capture: CH SELECT on
  CH2; deck 1 played at ~134 while the screen stayed 120.00, then deck 2 loaded
  and `0c` went to 121.80 within 25 ms). An empty deck is sent as **120.00**.
  rekordbox sends `0b` + `0c` together, beat first, on every change.
- Works in plain MIDI mode as well. The jog init burst contains one
  `0a`/`0b`/`0c` set (LOW CUT ECHO, 1, 120.00), so resend all three after it.
- Our Mixxx mapping uses the CH SELECT deck; for MASTER/MIC/SAMPLER it uses the
  sync leader, else the first playing deck (rekordbox's choice there is not
  captured).

### BEAT FX ON/OFF is `94 46` (latched state) — confirmed on the unit

The MIDI spec lists BEAT FX ON/OFF as note `94 47`. The unit never sends that.
It latches the button itself and sends its **state** on **`94 46`**: `7F` =
on, `00` = off, once per press. The `03 01` position dump includes it, so
software learns the state at launch. rekordbox sends `94 46 00` at startup
(never `0x47`), so send the button light on `0x46` too. FX SELECT (`94 20`–`2D`),
CH SELECT (`94 10`–`16`), LEVEL/DEPTH (`B4 02`/`22`) and BEAT ◀ ▶ (`94 4A`/`4B`)
match the spec.

**Mixxx:** effect slots in a standard unit start switched off, and chain presets
don't store that switch. A mapping that only toggles the unit's `enabled` stays
silent: also turn `[EffectRack1_EffectUnit1_EffectN],enabled` on. Mixxx also
starts unit 1 on and routed to deck 1, so set it off at init. A paused deck is
not processed, so echo/reverb tails stop with the track, unlike rekordbox.

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
| `0x2D` cue info | 1 pkt | **track length** (4-byte time, see `0x21`) + `0a 00` + ten × `9e 2f 27 01 00` (identical in every capture; meaning unknown, replay verbatim). Sent right after `0x30`. |
| `0x30` hot-cue list | 2 pkts | **track length** (4-byte time) + **16 slots × 6 bytes** `[01][colour][4-byte time]`; empty slot = zeros. Colour = unit pad-colour number (rekordbox default green `0x16`). Sent after the beat grid on every load **and again on every cue change**. |

### `0x2C` waveform column (7 bytes) — decoded
```
offset 0-1  colour A  RGB565, u16 LE   (outer bar)   — 0 selects firmware preset `preset`
offset 2-3  colour B  RGB565, u16 LE   (inner bar)
offset 4    height A  0..40 px         (outer bar, bottom-aligned)
offset 5    height B  0..40 px         (inner bar, drawn over A, clamped ≤ A)
offset 6    preset    0..7             (firmware preset colour when colour A == 0)
```
Flag byte (packet 1, offset 6): bit7 `0x80` = enable/show, bit6 `0x40` = centered
(mirrored bars) vs bottom-aligned.

**Colour scheme (confirmed on the unit).** rekordbox's own `0x2C` uses saturated
hues: colour A's brightest channel is always **189**, colour B is the same hue at
**255**, and the inner bar is short (median ≈ 0.23 × the outer height). Raw,
unnormalized band levels come out nearly black in RGB565, and a white inner bar
hides the colour. What works from Mixxx's 3-band overview: normalize each band
(low→R, mid→G, high→B) to its own track peak, subtract ~0.6 × the smallest
channel for saturation, then scale so the max channel = 189 (outer) / 255 (inner);
inner height 0.5 × outer. Builders in
[`tools/ddj_jog.py`](tools/ddj_jog.py) (`wave_point`, `wave_packets`, `rgb565`).

### `0x21` live status (~120/s per deck)
`[deck<<4][0x21]…`. Partly decoded; confirmed fields in **bold**:

| byte | value | meaning |
|---|---|---|
| 2 | `0x18` normal, **`0x19` SLIP**, **`0x1a` paused**, **`0x1b` SLIP + paused** | **bit 0 = SLIP on**: the unit draws the jog screen red (rekordbox sets it for as long as SLIP is on). **bit 1 = deck paused/at rest**: the unit dims the platter. rekordbox sends `0x1a` while stopped and during the brake to a stop, `0x18` while playing (also during a CUE preview from pause). |
| 3 | **`0x0a` on air**, **`0x08` off air** | **bit 1 = ON AIR**: the jog screen is bright while set and dimmed while clear. rekordbox follows the channel fader (set while it is above 0), whether or not the deck plays. (An earlier note "pulses with the beat" was wrong.) |
| 4 | **`0x11` ring lit**, **`0x10` ring dark** | **bit 0 = jog ring light**: the jog CPU's LED task (`route_hid` → `task_led` in `LCD_M`) lights the ring at the user brightness while it is set. rekordbox toggles it to blink the ring near the end of a track: ~1 s per step with 20–25 s left, ~0.2 s in the last second (decoded5 166–172 s). It sends no other message for the warning. (An earlier note "`0x10` while touched" was wrong.) |
| 5 | bit 7 | **playing** (bit 7 set = playing) |
| 9 | **`0xb4` track loaded**, `0x10` none | track-loaded flag |
| 11–14 | 4-byte time | **elapsed position**: `min, sec, ms (u16 LE)`, e.g. `00 09 84 01` = 0:09.388. Drives the time display and the spinning platter. |
| 15–18 | 4-byte time | **track length**, same format (e.g. `03 31 c9 00` = 3:49.201). |
| 21–22 | u16 LE | BPM `(tenths << 12) \| whole` (copy in 38–39); from capture |
| 23–24 | s16 LE | pitch in 0.01 % units; from capture |
| 31–33 | u24 LE | **CUE point, ms** |
| 55–57 | u24 LE | **active cue, ms** |
| 58 | `01` cue set, `03` hot cue, `00` none | **cue flags** |
| others | change with loops/jog | markers / loop points |

**Time format correction (confirmed on the unit):** an earlier reading of bytes
11–13 as "24-bit BE, 1/256 s" was wrong. It put the 1/256 fraction into the ms
field, so the platter ran 0–255 ms of each second and then jumped: the periodic
platter skip. With `min, sec, ms` the platter spins correctly and the CUE marker
appears (cue fields + `0x30`/`0x2D` sent on load).

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
`0x2C` waveform rendering with a real `0x2F` beat grid, `0x2B` artwork (real
cover art from Mixxx), the `0x21` time format (§4, bytes 11–18: min/sec/ms),
the CUE marker (`0x21` bytes 31–33/55–58 + `0x30` hot-cue list + `0x2D`), a
smoothly spinning platter during playback, the `0x2C` colour scheme (§4), the `0x21` "no track" view (byte 9 =
`0x10`), the ON AIR brightness bit (`0x21` byte 3 bit 1), the jog ring light
(`0x21` byte 4 bit 0, end-of-track blink), `03 01`
fader-position sync (§3), and the BEAT FX screen name/beat/BPM (`0a`/`0b`/`0c`, §3).

**Still open:** the `0x2D` entry fields, the remaining marker/loop bytes, and the
meaning of the BPM/pitch bytes on screen (sent per the capture, not checked by eye).
Byte 5 bit 7 is not simply "playing": it stayed set through a 4-minute still deck
in the capture; use byte 2 bit 1 for paused.

**Decks 3/4 and empty decks (confirmed on the unit).** rekordbox sends **no** `0x21`
for decks 3/4 in any capture, and for an empty deck only about one frame per
second. Deck 3 shares the left jog with deck 1 (deck 4 with 2); streaming deck-3
"no track" frames at a high rate made deck 1's platter stutter. Rule that works:
an empty deck gets a 1 s keepalive, and only while its jog partner (deck ± 2) is
empty too.

## 8. Driving this from Mixxx (confirmed 2.7.0, live)

A Mixxx mapping exists in the `sergioalexo/mixxx` fork, branch
`ddj-1000-jog-displays` (rebased onto Mixxx `main`). The waveform, beat grid and
cover art render live, the faders sync on launch, and empty decks show the
not-loaded view. Non-obvious things that had to be right:

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
- **Wait for the complete overview.** Mixxx's analyser allocates a track's
  overview waveform at full size and fills it in as it goes, so "has data" is
  not "analysed": a track loaded mid-analysis got a partial waveform that was
  never replaced. Treat it as ready only when `getCompletion() == getDataSize()`
  (as `WOverview` does), and keep checking while the track is loaded: analysis
  can take longer than any fixed timeout. Until then send an all-zero `0x2C`
  (draws nothing and clears the previous track's waveform). Confirmed on the unit.
- **Suppress MIDI-mode jog-display writes in performance mode.** Streaming the
  MIDI clock/time and platter-angle (`9n`/`Bn` position) while in HID performance
  mode fights the HID display and reverts the unit to the loading view.
- **The jog handshake is opt-in** via a `jogDisplays` mapping setting, default
  **off**. Off = the MIDI mapping stays plain MIDI exactly as before (no
  handshake, MIDI jog-clock runs normally). The two Mixxx mappings are separate
  controllers and cannot detect each other, so the user ticks this setting
  together with enabling the HID mapping; on its own, performance mode leaves the
  screens blank. Fader sync (`03 01`) is independent of this and always runs.
- **Artwork needs a core hook.** Legacy controller scripts cannot read cover-art
  bytes, so (like the waveform) a C++ `Q_INVOKABLE` was added:
  `engine.getCoverArt(group, size, maxBytes)` in `controllerscriptinterfacelegacy.cpp`.
  It loads the track's cover via `PlayerInfo`→`Track::getCoverInfoWithLocation().loadImage()`,
  crops square, scales to 80×80, and re-encodes a **baseline** JPEG (quality
  stepped down to fit `maxBytes`), returned as a JS byte array. The mapping sends
  it once per load as `0x2B` (after the grid, before the waveform — rekordbox's
  order). Requires a Mixxx rebuild.
- **Empty decks need the "no track" status frame.** Send `0x21` with byte 9 =
  `0x10` (not `0xb4`) for an unloaded deck; otherwise the jog sits on the loading
  spinner forever instead of showing rekordbox's not-loaded view.
- **Fader sync on launch = send `03 01`** (§3). The mapping requests the dump via
  a one-shot ~300 ms after `init()` (MIDI output only opens after `init()`
  returns). EQ/volume/trim are 14-bit XML controls with no soft-takeover, so the
  dump applies directly. Tempo uses soft-takeover, which would swallow the dumped
  value — so rate soft-takeover is armed by a second one-shot (~900 ms), *after*
  the dumped tempo has landed, not in the `init()` loop. Pure mapping JS, no
  rebuild.
- **Smooth platter needs a sample-accurate position.** Mixxx's `playposition`
  control only updates at 15 Hz (`kPlaypositionUpdateRate`); streaming it as-is
  makes the platter step. A third core hook,
  `engine.getEnginePlayPosition(group)` (track fraction 0..1 from
  `VisualPlayPosition::getEnginePlayPos()`, -1 if no track), plus a 5 ms
  `engine.beginTimer` floor with `Qt::PreciseTimer` for an ~8 ms (≈ rekordbox
  120 Hz) status stream, gave a smooth spin during playback (confirmed on the unit).
- **Scratch/nudge lag: `engine.isScratching()` is per-controller.** Scratch state
  lives in each script interface. The MIDI mapping starts the scratch, so the HID
  mapping always saw `false` and kept smoothing during scratches, which lagged
  the platter. Fix: read the shared `scratch2_enable` control instead, and
  hard-bound the smoothed clock to within 12 ms of the engine position (covers
  nudge/pitch-bend, which change speed without a scratch). rekordbox sends no
  special "local render" flag while jogging; it just streams the position.
  Confirmed on the unit.
- **Call `engine.scratchDisable(deck, true)` once per release.** It resets the
  ramp's "last movement" time, so Mixxx's next 1 ms scratch step reads the
  platter as stopped. Called from a 20 ms timer on every tick, it kept the speed
  dipping to ~0.95x and the ramp never got within 1e-5 of playing speed, so the
  scratch never ended (`scratch2_enable` stayed 1) and the track fluttered after
  every scratch. Hand back once; the ramp then ends ~250 ms after release.
  Confirmed on the unit.
- **Pause = brake, like rekordbox.** In the capture rekordbox's pause brakes the
  audio from 1× to 0 in ~0.52 s and the platter just follows the position. From
  Mixxx: PLAY on a playing deck calls `engine.brake(deck, true, 60)` (factor 60 ≈
  0.53 s), PLAY again during the brake cancels it. Send `0x21` byte 2 bit 1 when
  `play == 0` and not scratching, so the platter dims only once stopped. A brake or
  spinback runs as a scratch with the platter untouched, so any "released platter
  ends the scratch" logic must skip it (`engine.isBrakeActive` /
  `isSpinbackActive`), or it cuts the brake off on the next tick. Confirmed on the unit.
- **SLIP needs the mapping to trigger the return.** The unit sends SLIP as a
  plain note (`9n 40 7F` press / `00` release; rekordbox's map agrees) and the
  mapping toggles. But Mixxx only jumps to the slip position when `slip_enabled`
  goes **off**, and it keeps the speed it had when slip went on (zero if SLIP was
  pressed on a paused deck). Mixxx 2.7 loop rolls also always switch slip off when
  they end, even if it was on before. What works: the mapping keeps its own SLIP
  state; when a scratch, pause, loop, REVERSE or PAD FX brake/backspin ends, it
  switches `slip_enabled` off for 50 ms and back on (more than one audio buffer,
  since the engine reads it once per buffer), and switches it on again after a
  roll or track load. On platter release with SLIP on, end the scratch without the
  speed ramp. Confirmed on the unit.
- **Red SLIP screen = `0x21` byte 2 bit 0** (§4). The HID mapping reads
  `slip_enabled` and holds the bit ~150 ms after it goes off, so the 50 ms
  slip-return gap does not flash the screen. Confirmed on the unit.
- **Jog brightness = ON AIR, `0x21` byte 3 bit 1** (§4). Always sending `0x0a`
  keeps the screen bright all the time. The HID mapping sets the bit while the
  channel `volume` is above 0 and the crossfader does not fully cut the deck's
  side (`orientation`), and clears it otherwise. Confirmed on the unit.
- **End-of-track ring blink = `0x21` byte 4 bit 0** (§4). The unit does not
  blink by itself, and the MIDI ring note (`9x 5B`) does nothing in performance
  mode. The HID mapping toggles the bit in the last 30 s of a playing track,
  one step every 1000 ms at 30 s left down to every 200 ms at the end
  (`endWarningSeconds` / `endWarningSlowMs` / `endWarningFastMs`). Confirmed on
  the unit.

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
