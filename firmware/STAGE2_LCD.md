# DDJ-1000 v1.12 — Stage 2: jog-display (LCD) CPU and its protocol

> **Firmware notes from the original analysis (2026-10-13/14).** Written before the live work; anything marked [inferred] or [guess] may since have been confirmed or disproven. [`../JOG_DISPLAY_PROTOCOL.md`](../JOG_DISPLAY_PROTOCOL.md) wins on any conflict. Paths and tools: see [`README.md`](README.md).

Source: `LCD_M` v1.060 (`LCD_M_Ver.1060.bin` from `tools/updsplit.py`), analysed in Ghidra 12.1.4
(project `DDJ1000`, program `LCD_M_Ver.1060.bin`; function names below are in `annotations/LCD_M_Ver.1060.tsv`).

Legend: **[verified]** read directly from code; **[inferred]** strong evidence; **[guess]** to be confirmed on hardware.

---

## 1. Bottom line for "show my own waveform"

The stock firmware already accepts a **host-supplied overview waveform** (600 points, 2 heights + 2 RGB565
colours per point) and draws it on the jog screen as a 288×40 bitmap. **[verified]** It also accepts
**80×80 artwork** (JPEG/PNG/GIF, ≤10 KB), a **beat grid**, cue lists and deck status. No firmware
modification should be needed to draw a custom waveform, as long as it fits that model.

Not available in stock firmware: a raw framebuffer or arbitrary drawing channel. Free-form graphics would mean
either (a) abusing the 80×80 artwork slot (any JPEG/PNG works, so arbitrary content at 80×80) or
(b) modified firmware.

**Update (Stage 3):** confirmed that `p[0..63]` is the PC's 64-byte HID OUT report byte for byte. See `STAGE3_HOST.md`.

**Open gap (original):** this stage documents the LCD CPU side. What the **PC** actually sends (USB HID report IDs and sizes)
and how the main CPU repackages it is *inferred* from the payload layout below and needs Stage 3 (USB1 image)
or a USB capture to confirm.

---

## 2. Hardware view [inferred]

- CPU: Renesas SH-2A, SH7268/SH7269 class (VDC4 at `0xFFFF7400`, JCU at `0xE8017000`, SCIF at `0xE8007000+`,
  SPIBSC at `0xFFFC1C00`).
- Boots from serial flash: `LCD_B` at `0x18000000`, settings sector at `0x1803F000`, `LCD_M` at `0x18040000`.
  The `LCD_M` header holds 8 section-copy descriptors; code runs from on-chip RAM at `0x1C200000`.
  The ~1.5 MB tail of the image is UI assets read directly from flash.
- Display: **320×240**, driven by the on-chip VDC4. Graphics library with PNG/GIF decoders plus the hardware JPEG codec.
- RTOS: µITRON-4-style (`acre_tsk` etc.). Tasks: `root, cpu, serial_flash, gui, sh1, sh2, system, midi, hid, lcd, led`.
- Upstream links: **SCIF0 → `sh1`, SCIF1 → `sh2`**, both clock-synchronous with the LCD CPU as clock **slave**
  (SCSCR.CKE=10, external clock), DMA, full duplex. SCIF4 (`lcd_scif4_init`) is local (panel/peripheral).
- A RAM flag at `0x1C21B07C` selects one of two pin-mux layouts → probably the same image runs on two
  display CPUs (left/right jog; test-mode names `LCD1`/`LCD2`). **[guess]**

## 3. Link layer: main CPU ↔ LCD CPU (`task_sh`, `sh_rx_dispatch`, `task_system`) [verified]

Fixed **80-byte frames**, exchanged continuously in both directions on each link:

| Offset | Size | Meaning |
|---|---|---|
| 0x00 | 1 | system control bits (only honoured on link 0): `0x80` reset, `0x40`, `0x20` = display settings (with 0x04/0x06), `0x10`, `0x08` (uses bit7 of 0x03), `0x04`; bits 0–1 = selected deck on this side |
| 0x01–0x07 | | system/status bytes; 0x04 high nibble `0x9` + 0x06 two nibbles (0–8, default 4/4, stored in flash `0x1803F000`) = display level settings **[inferred]**; 0x07 bits 4–6 = timer period selector (100/250/500/900/1500 ms), bits 0–3 two 2-bit fields |
| 0x08 | 1 | bit7 = payload present |
| 0x09 | 1 | bit7 = payload type: 0 → HID route, 1 → MIDI route |
| 0x0A–0x0B | 2 | payload sequence number; payload is only processed when it changes |
| 0x0C–0x4D | 66 | **payload** (see §4), `p[0..65]` below |
| 0x4E–0x4F | 2 | CRC-16/CCITT-FALSE over bytes 0x00–0x4D (poly 0x1021, init 0xFFFF, no reflection, xorout 0), big-endian; the receiver checks that the CRC over all 0x50 bytes is 0 |

## 4. Payload: HID route (`route_hid` → `task_hid`) [verified unless marked]

`p[0]` high nibble = **deck number 1–4**; low nibble unused. `p[1]` = **report ID** (an ASCII character in the code).
A message is dropped unless the deck matches the deck currently assigned to this side (`frame[0]&3`).
Multi-byte integers are **little-endian**.

### 4.1 `0x21 '!'` deck status (single packet)

| p[] | Field |
|---|---|
| 2 | flag bits 0x10, 0x08, 0x02, 0x01 (play/cue/sync/master-type flags) **[guess]** |
| 3 | flag bits 0x10, 0x08, 0x02 **[guess]** |
| 4 | bits 4–6: tempo-range index + 1 **[inferred]** |
| 5 | bit7 flag, bits 4–5 2-bit mode |
| 9 | *validity mask*: 0x80 times, 0x20 BPM, 0x10 tempo, 0x08 position/length, 0x04 extra position |
| 10 | 0–22 index (key or similar) |
| 11 | bit7 flag, bits 0–6 elapsed minutes |
| 12, 13–14 | elapsed seconds (<60), milliseconds (u16, <1000) |
| 15, 16, 17–18 | remaining minutes, seconds, ms |
| 21–22 | BPM: `(u16 & 0x0FFF)*10 + (p[22]>>4)` → BPM×10 (tenths in the top nibble), clamped 999.9 |
| 23–24 | tempo, s16, 0.01 % units, clamped ±10000 (±100.00 %) |
| 25–27 | 24-bit value, bit7 of p[27] = flag (position) **[guess]** |
| 28–30 | 24-bit value (track length) **[guess]** |
| 31–33 | 24-bit value (valid if mask 0x04) **[guess]** |
| 55–57 | 24-bit value |
| 58 | byte |
| 59 | colour index 1–64 (0 → default) |
| 60 | bit7 flag + key 1–24 **[inferred]** |
| 61 | 1–25 → key shift −12…+12 **[inferred]** |

### 4.2 Multi-packet framing (`0x2B`, `0x2C`, `0x2F`)

```
p[1]   = report ID
p[2-3] = packet index, 1-based (u16 LE)
p[4-5] = packet count (u16 LE)
packet 1:   header bytes, then data
packet n≥2: p[6..63] = 58 data bytes at blob offset 58*n − 60 (0x2B/0x2F) or 58*n − 59 (0x2C)
The blob is committed when index == count.
```

### 4.3 `0x2C ','` **overview waveform** → `wave_init`, `wave_store`, `wave_render`, `wave_publish`

Packet 1: `p[6]` = flags: **bit7 = waveform present**, **bit6 = style** (0 = bottom-aligned, 1 = centred/mirrored);
`p[7..63]` = first 57 data bytes. Packets ≥2 carry 58 bytes each. Total data is **4200 bytes = 600 points × 7 bytes**,
so 73 packets.

Per point (7 bytes):

| Byte | Field |
|---|---|
| 0–1 | colour A, RGB565 LE (0 → use preset from byte 6) |
| 2–3 | colour B, RGB565 LE |
| 4 | height A (bits 0–5), 0–40 px — outer bar |
| 5 | height B (bits 0–5), 0–40 px — inner bar, drawn over A and clamped ≤ A |
| 6 | preset colour index (bits 0–2), used when colour A == 0 |

Rendering: points are mapped onto **288 columns** through a runtime table (600→288, maximum per column); output is
two 288×40 ARGB1555 bitmaps: the waveform, plus a mask (`0xA000`) drawn clipped to the playback position as the
"played" overlay. Placed at roughly x=16, y=106 on the 320×240 screen. Each packet is accepted
per byte, and a point is used only once all 7 of its bytes have arrived, so packets may arrive out of order.

### 4.4 `0x2B '+'` **artwork** → `art_init`, `art_store`, `art_publish`

Packet 1: `p[6-7]` = total byte size (u16 LE, ≤ 0x2800 = 10240), `p[8..63]` = first 56 bytes. Then 58 bytes per packet.
The blob is a complete image file, format sniffed by `img_detect_format`: `FF D8` JPEG (hardware JCU),
`89 'PNG'`, `'GIF8'`, or a Pioneer raw bitmap (first u32 < 0x100). It is drawn **80×80 at (120, 6)**;
when no artwork has been sent, a built-in default image is drawn.

### 4.5 `0x2F '/'` **beat grid** → `beatgrid_publish`

Same framing as `0x2B`: packet 1 has a u16 at `p[6-7]` (size or count, not yet resolved), then data from `p[8]`.
The GUI reads the stored blob as `u32 count` (must be ≥5) + `u32` entries, each with a 24-bit position in ms plus 8 flag
bits (beat-in-bar), max buffer 0x2584 bytes (~2400 beats) **[inferred]**. Whether the host sends the `count` word itself
or the firmware writes it is not yet checked. The GUI interpolates the current beat/phase from it.

### 4.6 `0x2D '-'` cue list (single packet)

`p[2-3]`, `p[4-5]` = 1/1. `p[6]` min, `p[7]` sec, `p[8-9]` ms = reference time; `p[10]` = n (≤10);
then n × 5 bytes: `[bit7 flag | colour 1–8]`, min, sec, ms u16.

### 4.7 `0x30 '0'` hot/memory cues (2 packets)

Packet 1: time (min, sec, ms u16) at `p[6..9]`, then 9 entries × 6 bytes; packet 2: 7 entries × 6 bytes.
Entry: `[type/flags]`, colour (1–64, 0 → default), min, sec, ms u16.

## 5. Payload: MIDI route (`route_midi` → `task_midi`) [verified layout, semantics inferred]

The same deck-status information, but with every field packed 7 bits per byte (SysEx-safe): minutes/seconds,
14-bit BPM (<10000), 14-bit tempo `v*10 − 10000`, a 14-bit value < 360 (ring angle), and key 1–24 / shift.
So MIDI SysEx can drive the basic jog display. **Waveform, artwork and beat grid exist only on the HID route.**

## 6. Next steps (proposed Stage 3)

1. **Confirm the host-side wire format in `USB1`/`USB2`**: USB descriptors and the HID report descriptor (report
   IDs/lengths for 0x21/0x2B/0x2C/0x2D/0x2F/0x30), and the code that copies HID OUT reports into link frames
   (whether `p[0]` is added by the main CPU or sent by the host).
2. Find any enable/handshake needed (e.g. the deck must be "loaded", or the waveform flag in `0x21`).
3. Write a small host tool (Python + hidapi) that sends a synthetic waveform, then test it on the device.

## Files

- `ghidra/import_lcd.sh` — rebuilds the Ghidra program and applies the base names (`ghidra/apply_annotations.sh` restores all of them).
- `ghidra/SetupSH2AImage.java` — memory map from the section-copy table.
- `ghidra/Q.java`, `ghidra/q.sh` — headless query helper (dec/xr/lit/io/up/callovr/...).
