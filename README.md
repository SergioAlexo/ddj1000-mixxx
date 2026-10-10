# Pioneer DDJ-1000 → Mixxx 2.5 (complete mapping)

A four-deck mapping that makes the DDJ-1000 behave in Mixxx the way it does in
rekordbox. It is built from three sources:

1. AlphaTheta's **DDJ-1000 List of MIDI message v1.00**, which says what every control sends.
2. rekordbox 7's own **`MidiMappings/DDJ-1000.midi.csv`**, which says what rekordbox does with each message.
3. The **DDJ-1000 Operating Instructions**, for SHIFT functions and button behaviour.

## Install

1. **Quit Mixxx.** It rewrites its settings when it quits.
2. Run `python install.py`. It backs up `effects.xml`, `mixxx.cfg` and
   `soundconfig.xml` to `%LOCALAPPDATA%\Mixxx\ddj1000-backup-<date>` first.
3. Start Mixxx. The mapping loads automatically as **Pioneer DDJ-1000 (Complete)**.

### Audio: recommended change

The installer keeps your current audio device and adds **Headphones on outputs
3-4** next to **Main on outputs 1-2**. The DDJ-1000 mixes those two in hardware:
the HEADPHONES MIX and LEVEL knobs are analogue, and so are MASTER, BOOTH, MASTER
CUE and the mics. rekordbox leaves all of those unmapped for the same reason.

For scratching, switch to ASIO in **Preferences → Sound Hardware**:
Sound API **ASIO**, Main → **DDJ-1000 ASIO** channels 1-2, Headphones → **DDJ-1000 ASIO** channels 3-4,
and the lowest latency that plays without crackles (5-10 ms).

## What does what

### Deck
| Control | Press | SHIFT + press |
|---|---|---|
| PLAY/PAUSE | play / pause | play / pause |
| CUE | CDJ cue: set, back cue, cue preview | jump to track start |
| BEAT SYNC | sync on/off | make this deck the sync master |
| MASTER TEMPO | key lock | TEMPO RANGE ±6 → ±10 → ±16 → WIDE |
| TEMPO slider | tempo (soft takeover when switching decks 1/3, 2/4) | same |
| KEY SYNC | match key to the master deck | – |
| KEY RESET | original key | – |
| QUANTIZE | quantize, all decks | – |
| SLIP | slip mode | VINYL mode (jog scratch on/off) |
| SLIP REVERSE | reverse while held, auto-release after 8 beats | REVERSE on/off |
| LOOP IN / 1/2X | loop in; halves the loop while looping | loop-in adjust with the jog |
| LOOP OUT / 2X | loop out; doubles the loop while looping | loop-out adjust while looping, else RELOOP |
| 4 BEAT LOOP/EXIT | 4-beat loop / exit loop | active loop on/off |
| SEARCH ◀◀ ▶▶ | tap: start of track / next track · hold: fast search | CUE/LOOP CALL ◀ ▶ |
| MEMORY | store memory cue (or the running loop) | DELETE memory cue |
| Headphones CUE | cue | TAP BPM |
| Fader start | SHIFT + fader up plays, fader down returns to cue | |

**Jog:** touching the top in VINYL mode scratches, and a spun-and-released platter
keeps playing until it slows. With VINYL off, or on the outer ring, it bends pitch.
SHIFT + jog searches the track. SEARCH + jog searches fast. While a loop point
is being adjusted, the jog moves it.

**Jog screen:** the position bar spins at 33⅓. The screen also shows remaining or
elapsed time (following Mixxx's time setting), BPM, tempo %, key, key shift, the
cue marker and sync / master state.

### Pad modes
| Mode | Page 1 | Page 2 | SHIFT + pad |
|---|---|---|---|
| HOT CUE | hot cues 1-8 in their colours | hot cues 9-16 | delete |
| PAD FX1 | Echo ½, Echo ¾, Reverb, Spiral / Roll 1/16, 1/8, ¼, ½ | Trans ¼, Trans ½, Flanger, Phaser / Low Cut Echo, MT Delay, Enigma Jet, Pitch | same |
| PAD FX2 | HPF, LPF, Crush, Noise / Vinyl Brake, Backspin, Reverse, Roll 1/32 | Echo 1, Echo 2, Long Reverb, Trans ⅛ / Roll 1, 2, 4, ¾ | same |
| BEAT JUMP | ◀1 ▶1 ◀2 ▶2 / ◀4 ▶4 ◀8 ▶8. PAGE ◀ ▶ halve or double the range | | same |
| SAMPLER | play slot 1-8 of the bank (empty slot loads the selected track) · PAGE ◀ ▶ change bank | | stop |
| KEYBOARD | plays the hot cue at +4…+7 / 0…+3 semitones | −4…−1 / −8…−5 | choose which hot cue |
| BEAT LOOP | ¼ ½ 1 2 / 4 8 16 32 | 1/32 1/16 ⅛ ¼ / ½ 1 2 4 | – |
| KEY SHIFT | key +4…+7 / 0…+3 (press again for 0) | −4…−1 / −8…−5 | – |

SHIFT + PAGE ◀ ▶ changes the sampler bank in every mode, as in rekordbox.

### Mixer and effects
- TRIM, EQ HI/MID/LOW, channel faders and the crossfader go straight to Mixxx.
  The CROSSFADER ASSIGN switches set each deck's crossfader side.
- **SOUND COLOR FX**: DUB ECHO, PITCH, NOISE, FILTER. With none selected the COLOR
  knobs do nothing, as in rekordbox. With one selected, 12 o'clock is dry.
- **BEAT FX**: all 14 FX SELECT positions, CH SELECT (CH1-4 / MASTER / SAMPLER),
  LEVEL/DEPTH, BEAT ◀ ▶ (1/16 to 32 beats) and ON/OFF. SLIP ROLL and ROLL use
  Mixxx's loop rolls. SHIFT + ON/OFF is RELEASE FX (vinyl brake).
- SAMPLER VOL and SAMPLER CUE control all Mixxx samplers.

### Browser
Rotary: scroll. Press: load to that side's deck, or open the folder when the tree
has focus. Press twice quickly for an instant double. SHIFT + rotary: waveform zoom.
BACK: tree ↔ track list. VIEW: big library. Hold VIEW: add to the Auto DJ queue
(Mixxx's nearest thing to rekordbox's tag list).

## Where Mixxx can't match rekordbox exactly
- **Jog screen artwork and waveform** are drawn over a private Pioneer USB (HID)
  protocol that only rekordbox speaks. Everything the MIDI spec allows is shown.
- **Effects sound different.** Mixxx has no Enigma Jet, Spiral or Mobius, so
  those are built from the closest Mixxx effects.
- **The FX display** above BEAT FX shows what the unit knows itself (effect name
  and beat). Mixxx cannot write BPM or parameter values there.
- **Memory cues** are stored as Mixxx hot cues 17-36 (red), so they show on the waveform.
- **Related Tracks** (SHIFT + VIEW) and the **playlist palette** (SHIFT + BACK)
  have no Mixxx equivalent and do nothing.

## Tuning
The top of `controllers/Pioneer-DDJ-1000-Complete-scripts.js` has a `settings`
block. `jogTicksPerRevolution` sets scratch speed, and you can also change the
tempo ranges, search speed and the slip reverse length. Set `padPaletteTest: true`
to check the pad colours: deck 1 PAGE ◀ ▶ steps through all 127 colour numbers.

## Developing
- `python tools/gen_mapping.py` regenerates the XML from the address table.
- `node tools/test_mapping.js` runs the script against a mock Mixxx engine. It
  replays all 1,457 script bindings, checks the jog display values against the
  spec (all 24 key codes), and walks through every pad mode, loops, jog, Beat FX,
  Color FX and memory cues.
