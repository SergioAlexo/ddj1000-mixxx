# DDJ-1000 v1.12 — Stage 3: host (USB) side of the jog-display protocol

> **Firmware notes from the original analysis (2026-10-13/14).** Written before the live work; anything marked [inferred] or [guess] may since have been confirmed or disproven. [`../JOG_DISPLAY_PROTOCOL.md`](../JOG_DISPLAY_PROTOCOL.md) wins on any conflict. Paths and tools: see [`README.md`](README.md).

Source: `USB1` v1.120 (`USB1_Ver.1120.bin`, flash base `0x70000`), Ghidra program
`USB1_Ver.1120.bin` in project `DDJ1000` (re-import with `ghidra/import_main.sh USB1_Ver.1120.bin 0x70000`,
then `ghidra/apply_annotations.sh USB1_Ver.1120.bin`). Builds on `STAGE2_LCD.md`.

Legend: **[verified]** read from code/data; **[inferred]**; **[guess]** — needs hardware.

---

## 1. Result

**What the PC writes to the HID interface is exactly the payload the jog-display CPU parses.** [verified]
The Stage 2 tables apply as-is, with `p[n]` = byte *n* of the 64-byte HID OUT report.
`../tools/ddj_jog.py` implements waveform, artwork and status messages. Its self-test reassembles them with
the firmware's own offset rules and offset table.

Nothing has been tested on hardware yet. §6 lists what to check.

## 2. Main-CPU memory/flash layout [verified]

Main-CPU serial flash: `BOOT` @0x00000 (8 KB) · `UPDATE` @0x02000 · `USB1` @0x70000 · `USB2` @0xF0000.
USB1 and USB2 are both linked for `0x1C080000` and carry **identical USB descriptors**. They are either two main
CPUs (one per USB port) or two firmware slots **[open]**. The LCD CPU's two upstream links (`sh1`/`sh2`) and the
main CPU's two LCD links (`lcd0`/`lcd1`) favour "2 main CPUs × 2 jog CPUs, cross-connected" **[inferred]**.

Main-CPU RTOS tasks (USB1): `root cpu idle setup ctrl system share stby test utility serial_flash sh hpi Illumi
lcd0 lcd1 m16c0 m16c1 usbHidHo usbMidiHo usbMidiHi usbAudioClear usbUtility usbAttach usbDetach certified
rekordbox_Active rekordboxVerification`.

## 3. USB device [verified]

`VID 0x2B73 (Pioneer DJ)  PID 0x0020`, USB 2.0, 1 configuration, 4 interfaces:

| If | Class | Endpoints | Use |
|---|---|---|---|
| 0 | vendor (alt 1) | ISO OUT 0x01 / IN 0x82, 1024 B, interval 2 | audio streaming (Pioneer driver) |
| 1 | Audio Control | – | |
| 2 | MIDI Streaming | bulk OUT 0x04 / IN 0x85, 512 B | MIDI (controls, LEDs, MIDI-route display data) |
| 3 | **HID** | **interrupt OUT 0x06** / IN 0x87, 64 B, bInterval 4 | **display data (this doc)** |

HID report descriptor (52 bytes): usage page `0xFFA0`/`0xFFA1`, **no report IDs**, one 64-byte Input and one
64-byte Output report. On hidapi, write `b'\x00' + report64`.

## 4. Path of an OUT report through the main CPU

```
EP06 OUT ──► task_usbHidHo ──► hid_out_parse ──► per-deck ring (16 × 64 B per deck, @0xFFF88688)
                                    │ deck = report[0] >> 4 (1..4, else dropped)
                                    └─ sets deck "updated" flag
task_lcd(lcd0/lcd1) ──► lcd_build_frame ──► 80-byte frame, ONE report per frame ──► SCIF ──► LCD CPU
```

- `hid_out_parse` @1c09c67c [verified]: drops a report unless `report[0]>>4` is 1–4. It copies ≤64 bytes into
  `ring[deck][wr]` and does `wr = (wr+1) & 15`. **The write index is never checked against the read index**, so if
  the host gets 16 or more reports ahead of the link, the ring wraps, `rd == wr`, and that deck's backlog is
  silently lost. → **The host must pace its writes.**
- `lcd_build_frame` @1c08b5c6 [verified], per jog side (0 = left, 1 = right), each frame:
  1. if the deck **currently shown on this side** has HID data: frame[8]=0x80, frame[9]=0x40, seq++, pop one report;
  2. else if the **other deck of this side** (left: decks 1↔3, right: 2↔4) has HID data, pop one of those;
  3. else MIDI-derived data (frame[9]=0xC0, deck written into p[0]).
  Then p[64]=0x11, p[65]=0x20, CRC (CRC-16/CCITT-FALSE) at 0x4E.
  frame[0] bits 0–1 = deck currently shown on that side (0–3).
- Frame exchange is **requested by the LCD CPU** through an external IRQ line (IRQ4/IRQ5 → `FUN_1c08b4c2` releases
  the `lcd0`/`lcd1` semaphore). On the LCD side, `task_sh` is woken by alarm handlers `sh_timer0/1`. The exact
  frame period has not been extracted yet **[open]**. Practical rule: keep fewer than 16 reports in flight per deck.
  `ddj_jog.py` defaults to 8 ms between reports (73-packet waveform ≈ 0.6 s).
- The LCD CPU keeps only reports for the deck currently shown on that jog, or (via its deck-mapping helper) its
  partner deck. **Send to deck 1 for the left jog, deck 2 for the right** (defaults after power-on **[guess]**).

### Certification / rekordbox verification

`rekordboxVerification`, `rekordbox_Active` and `certified` exist (callback- and mailbox-driven). **None of
them are on the HID → ring → LCD path above** [verified for the code shown]. Whether the jog **GUI** shows the
waveform panel only in a "PC/rekordbox active" display state (frame[0] bit 7 = a main-CPU state flag) is
**[open]** and needs testing.

## 5. Message reference (host view; byte n = report[n])

All messages: `[0] = deck<<4`, `[1] = type`. Multi-packet types: `[2:4]` packet index (1-based, LE),
`[4:6]` packet count (LE); a blob is committed when index == count.

| Type | Packets | Layout | Notes |
|---|---|---|---|
| `0x2C` waveform | 73 | pkt1: `[6]` flags (0x80 present, 0x40 centred) + 57 data B; pktN: 58 data B at offset 58N−59 | 600 × 7-byte points (see Stage 2 §4.3) |
| `0x2B` artwork | ⌈(size−56)/58⌉+1 | pkt1: `[6:8]` size (LE, ≤10240) + 56 B; pktN: 58 B at 58N−60 | JPEG/PNG/GIF, drawn 80×80 at (120, 6) |
| `0x2F` beat grid | like 0x2B | | ≤ 0x2584 bytes |
| `0x21` status | 1 | Stage 2 §4.1 | `[9]` validity mask |
| `0x2D` cue list | 1 | Stage 2 §4.6 | |
| `0x30` hot cues | 2 | Stage 2 §4.7 | |

## 6. Hardware test plan

1. `pip install hidapi`, then `python3 ddj_jog.py list` → expect one entry 2B73:0020 interface 3.
   (On macOS no driver is needed. With the Pioneer driver or rekordbox running, close rekordbox first, because
   it also writes these reports.)
2. `python3 ddj_jog.py selftest`.
3. `python3 ddj_jog.py wave --deck 1 --pattern bars` → expect 24 tall orange spikes (every 25th of 600 points) on
   the left jog. This also shows the 600→288 column mapping.
4. Repeat with `--centered`, `--pattern rainbow`, `--deck 2` (right jog), then `--wav file.wav`.
5. If nothing shows: send `status --deck 1 --bpm 128 --elapsed 30 --remain 200` first (the GUI may need a
   "loaded deck"), and try a shorter `--interval` / longer `--interval`.
6. `python3 ddj_jog.py art --deck 1 cover.jpg` (80×80 baseline JPEG ≤10 KB).

Report what you see (photo of the jog screen helps), especially for steps 3 and 5. That decides whether the
next stage is "decode the remaining 0x21 fields / GUI states" or "find what gates the display".

## 7. Open questions

- Frame rate of the LCD link (bounds the safe write rate); whether the LCD→main frames give the host any ack via HID IN.
- Remaining `0x21` field semantics (flags in `[2]`, `[3]`, `[5]`, 24-bit values `[25..33]`, `[55..58]`).
- Which GUI state shows the waveform panel; meaning of the preset-colour table (byte 6 of a point).
- USB1 vs USB2 roles; the MIDI route (SysEx layout for the same status data).

## Files

- `tools/usbdesc.py` — decode USB config + HID report descriptor from an image.
- `tools/tasks.py` — list RTOS task descriptors of an image.
- `../tools/ddj_jog.py` — host tool (waveform / artwork / status, dry-run, selftest).
- `ghidra/import_main.sh` — import a main-CPU image into the Ghidra project.
