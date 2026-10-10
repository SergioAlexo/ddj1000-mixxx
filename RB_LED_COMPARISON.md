# rekordbox vs. our mapping: pad colours and LEDs

Source: `captures/rekordbox-clean-20261010-0152xx.pcap`, rekordbox 7.2.18 started fresh, DDJ-1000, no hot cues set,
no sample loaded, a track loaded on deck 1 around t=80 s. Tools: `tools/pad_colors.py`, `tools/decode_capture.py`.
Pad note = `mode*16 + (page-1)*8 + (pad-1)`; deck 1/2 pads = channels 0x97/0x98, deck 1/2 SHIFT pads = 0x99/0x9A,
decks 3/4 = 0x9B-0x9E (rekordbox sends 0 there).

## Static pad colours (what rekordbox sends at init, colour number 1-127)

| Mode | Page | rekordbox pads 1-8 | our mapping pads 1-8 |
|---|---|---|---|
| PAD FX 1 | 1 | 73 78 78 65 69 69 86 65 | 1 1 61 57 21 21 21 21 |
| PAD FX 1 | 2 | 73 120 78 65 69 69 86 65 | 29 29 17 17 9 9 13 53 |
| PAD FX 2 | 1 | 73 73 73 73 73 73 73 73 | 37 37 41 45 33 33 33 25 |
| PAD FX 2 | 2 | 73 73 73 73 69 69 69 69 | 1 1 61 29 21 21 21 25 |
| BEAT JUMP | 1 | 106 106 101 101 101 101 106 106 | 9 or 17 per direction |
| BEAT JUMP | 2 | 63 x8 | same as page 1 |
| SAMPLER | 1 | 63 x8 (nothing loaded) | off / 57 when loaded |
| SAMPLER | 2 | 63 109 109 109 63 109 109 109 | off / 57 when loaded |
| BEAT LOOP | 1 | 100 x8 | 21 x8 |
| BEAT LOOP | 2 | 102 x8 | 21 x8 |
| KEY SHIFT | 1 | 39 39 39 39 (0x74 blinks 64/0) 39 39 39 | 53, centre 29 |
| KEY SHIFT | 2 | 9 x8 | 53 |
| KEYBOARD | - | not lit in this capture (mode never entered) | 61, centre 29 |
| HOT CUE | - | 0 (no cues set; colours not captured) | RGB converted by `rgbToPad` |

Observations
* Our numbers come from a guessed hue wheel (1 blue ... 61 purple). rekordbox uses a different set of numbers,
  mostly >= 64. The values 106/42, 101/38, 73/9 (differences of 64) suggest bit 6 is a brightness flag, but
  Pioneer's list only says "colour number 1-127", so copying rekordbox's numbers is safer than relying on that.
* Pressing a pad does not make rekordbox write that pad's colour (no write on pad channels at press time);
  our mapping flashes pressed pads white.
* Key-shift centre pad (note 0x74) blinks 64/0 about every 0.4 s.
* On a mode-button press rekordbox lights the button with value 59 (0x1B/0x1E/0x20/0x22 on 0x90/0x91),
  our mapping sends 127. The unit switches mode itself on press.

## Non-pad LEDs and init writes seen from rekordbox
* 0x90-0x93: 0x0B (CUE) and 0x0C (PLAY) blink 127/0 when no track is loaded, 0x47 blinks with them (0x94 0x47 is FX on).
* Init writes on 0x90-0x93: 0x10, 0x11, 0x14, 0x15, 0x17, 0x1A, 0x35, 0x40, 0x4D, 0x50, 0x54, 0x58, 0x5C, 0x63, 0x65, 0x6A,
  0x6C, 0x6E, 0x74-0x76 (values 0, 16, 32 or 127). 0x21, 0x63, 0x6A, 0x6C, 0x74 get 32; 0x75 on decks 2 and 4 gets 16.
* 0x9F 0x40-0x4E = 127 at init (mixer/FX section), 0x9F 0x24-0x27 and 0x00-0x07 pulse early.
* 0xBF 0x41-0x4A: CCs at init (10, 0, 0, 64, -, 48, 16, 64, 32, 32), meaning not yet known.
* 0xB0/0xB1 CC 0x02: level meters, values roughly 65-94 while playing.
* SysEx: heartbeat `50 01`, plus the `0A`, `0B`, `0C` families (not in Pioneer's list).

## Second capture (`rekordbox-cues-*.pcap`, decoded4)
* Pressed-pad feedback DOES exist: while a pad is held rekordbox writes a different colour, then restores the idle one.
  Idle -> pressed: PAD FX1 73->9, 78->14, 65->1; Beat Jump 106->42, 101->38; PAD FX2 73->9; Beat Loop 100->37.
  The pressed value is the idle one minus 64 (63 for the Beat Loop and 101 cases), i.e. the same hue from the low
  half of the palette. Which of the two halves looks brighter on the unit still has to be checked by eye.
* Sampler: 63 = empty slot, 120 = loaded slot.
* Key Shift pads flicker 39 <-> 0 while pads are pressed (pressed pad goes dark).
* Hot cues: set one by one (about 0.65 s apart) as value 22 on pads 1-8 of both decks (0x97 and 0x98 identical), cleared to 0,
  then set again as 37. Only two palette colours were used, so the full hot cue palette is still unknown. A third capture
  that steps pad 1 through all 16 rekordbox palette colours in order would give the exact table.
* Deck 1 and deck 2 pad channels always receive identical writes in this capture (0x97 = 0x98), the SHIFT channels
  (0x99-0x9E) are only touched at init and for the key-shift pads.

## Not yet captured
* Hot cue colours (rekordbox palette to colour number), memory cues, loops.
* Keyboard mode, loaded-sampler states, pad FX pressed state.
* Where the CUE/PLAY/SYNC/LOOP LEDs go when a track plays (little data in this run).
