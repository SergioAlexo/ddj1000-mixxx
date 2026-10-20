# DDJ-1000 v1.12 — Stage 3c: what GUI state shows the jog waveform panel

> **Firmware notes from the original analysis (2026-10-13/14).** Written before the live work; anything marked [inferred] or [guess] may since have been confirmed or disproven. [`../JOG_DISPLAY_PROTOCOL.md`](../JOG_DISPLAY_PROTOCOL.md) wins on any conflict. Paths and tools: see [`README.md`](README.md).

Source: `LCD_M` v1.060 in Ghidra project `DDJ1000`. Builds on `STAGE2_LCD.md`, `STAGE3_HOST.md` and the
earlier cert notes (not kept; superseded by `../JOG_DISPLAY_PROTOCOL.md` §3).
Legend: **[verified]** read from code; **[inferred]**; **[guess]** / needs hardware.

---

## 1. Bottom line

The jog GUI does **not** test any rekordbox-verification flag before drawing the waveform. It draws the
waveform whenever three conditions hold, all driven by the 80-byte frames the main CPU sends:

1. the jog is on a **deck screen** (not boot/standby/utility), i.e. a deck layout is selected;
2. the deck is marked **"has content"**: `deck_state[deck][0] != 0`; **[verified]**
3. a **waveform blob** has arrived (`0x2C`) and passes position/validity checks. **[verified]**

So whether your waveform shows comes down to whether the controller is in a "deck loaded" screen state —
a main-CPU (USB1) decision — not to verification. This is the thing to confirm on hardware.

## 2. Draw path and the gate [verified]

`task_gui` (`1c20b280`) → screen dispatcher → `gui_draw_deck` (`1c200e20`, renamed) draws one deck panel:

```
gui_draw_deck(canvas, side, deck, layout):
  piVar23 = deck_state[deck]            # base 1c225e54, 0x80 bytes/deck, 0x200/side
  if (*piVar23 == 0):                   # [0] == 0  → deck empty
      gui_draw_deck_idle(...); return   # 1c200c56: idle art, NO waveform
  ... draw title/time/BPM ...
  # layout selected by `layout` arg (param_4): 0, 2, 3 each place a waveform area
  # waveform drawn from the 0x2C blob via wave_render output + gui_draw_image / FUN_1c23f89e / FUN_1c23f8d0
```

- `deck_state[deck][0]` (call it **DECK_PRESENT**) is the master gate. `0` ⇒ idle screen, early return, no waveform. **[verified]**
- `layout` (`param_4`) is the on-screen arrangement. Layouts 0/2/3 include a waveform region; the large
  centred waveform is **layout 3** (`gui_screen_mode2`/`1c20c72c` calls `gui_draw_deck(...,3)`). **[verified]**
- Even inside a waveform layout, the actual bars draw only if the waveform blob pointer is non-null
  (the `0x2C` data) and the play position is in range. **[verified]**

## 3. Where DECK_PRESENT and the layout come from [verified]

`task_system` (LCD, `1c213580`) parses each 80-byte frame. Top-level split on **`frame[0] bit7`**:

- **bit7 == 0** → normal content path. The other `frame[0]` bits drive `sys_deck_control` (`1c20dc70`):
  `0x40`→mode 0, `0x20`→mode 1 (+ BPM range via `1c20dbb0`), `0x10/0x08/0x04`→modes 2/3/4. These set the
  deck→side mapping and deck fields. The payload (`0x21` status, `0x2C` waveform, `0x2B` art, …) fills
  `deck_state` and the blob tables. **[verified]**
- **bit7 == 1** → an alternate branch (`1c211188` + two calls) that does **not** run the deck-content
  handlers — a standby/splash-like path. **[inferred]**

From the earlier cert notes: the main CPU's `lcd_build_frame` sets `frame[0] bit7 = (cert_struct[0x15] == 1)` and
feeds `frame[7]` from `cert_struct[0x14]`. So the cert/active state only influences this **one top-level
bit**, and (per the branch above) bit7 **set** steers *away* from the deck-content path. The waveform
content path runs when **bit7 is clear**. Which cert state produces bit7=0 vs 1 is not fully pinned —
`cert_struct[0x15]` is an active/indicator field, not the `[0]==2` verified flag itself. **[open]**

Net: the waveform is gated by *deck-loaded* state and *screen layout*, both produced by the main CPU from
its deck state (fed by host MIDI/HID), with at most an indirect influence from one cert-derived frame bit.

## 3a. Static resolution of the last unknown (USB1 + LCD) [verified]

Traced end to end; the waveform chain is **host-driven and not cert-gated**:

- **Payload forwarding (main CPU).** `lcd_build_frame` decides to pop & forward a HID report for a deck via
  `hid_deck_has_data(deck)`, which is literally `ring_wr[deck] != ring_rd[deck]` (`1c09bf60`/`1c09bf64`).
  i.e. "did the host send a HID report for this deck." No cert check, no loaded-track check. **[verified]**
- **frame[0] content bits** come from the per-side deck-state array `fff871d0` (`+side*0x20`); `frame[0] bit7`
  alone comes from the cert struct `fff87be4[0x15]`. The content bits select screen *layout*, not the waveform data. **[verified]**
- **DECK_PRESENT on the LCD.** `FUN_1c20d93a(side,deck,src)` copies a host-provided 0x80-byte struct into
  `deck_state[side][deck]` at base `1c225e54` — the **same** base `gui_draw_deck` reads. The LCD `0x21` ('!')
  handler builds that struct with its first word = **1** and passes it here. So **sending a `0x21` status
  report sets `deck_state[deck][0] = 1` (DECK_PRESENT) directly**, over HID. **[verified]**

**Conclusion:** the host can set DECK_PRESENT (via `0x21`) and supply the waveform (via `0x2C`) entirely over
HID. Nothing on that path reads the rekordbox-verification result. The only main-CPU-controlled variable left
is which top-level *screen* and *layout* the jog is in (boot/standby vs deck view) — and the DDJ-1000 jogs show
the deck view in normal operation. So custom waveforms should not require verification; confirm with §4. **[verified static; pending hardware]**

## 4. How to make the panel appear (hardware test) [now expected to work via §3a]

In order, stopping when the waveform shows:

1. **Baseline:** `ddj_jog.py wave --deck 1 --pattern bars` with nothing else. If the jog is already on a deck
   screen showing a (blank) waveform area, it should fill in.
2. **Mark the deck loaded:** send a `0x21` status first (`ddj_jog.py status --deck 1 --bpm 128 --elapsed 30
   --remain 200`), then the waveform. Status is what populates `deck_state[deck]` fields; a plausible path to
   DECK_PRESENT != 0.
3. **Standalone vs PC session:** try with (a) just a USB cable and our tool, (b) a track playing from a USB
   stick in the deck, (c) rekordbox connected. If only (c) shows it, the main CPU gates the "deck loaded +
   waveform layout" control bits on a PC/verified session; if (b) shows it, it's standalone-capable.
4. If the panel shows but the waveform doesn't track playback, send `0x21` position/BPM alongside `0x2C`.

Capture which step works (a jog photo helps). That distinguishes the two remaining possibilities:
- **GUI-only gate** (likely): waveform shows whenever a deck is loaded in any mode → our tool is sufficient.
- **Main-CPU session gate**: the controller only emits the loaded/waveform-layout frames during a
  rekordbox/PC-active session → then the lever is the USB1 deck-state logic (next investigation), not the
  LCD image.

## 5. Named functions added to the Ghidra project

`gui_draw_deck` (1c200e20), `gui_draw_deck_idle` (1c200c56), `gui_screen_mode2` (1c20c72c),
`sys_deck_control` (1c20dc70), plus Stage 2/3 names. Deck-state base `1c225e54` (0x80 B/deck, [0] = DECK_PRESENT).
