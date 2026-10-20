# Pioneer DDJ-1000 protocol

Reverse-engineered USB protocol of the Pioneer DDJ-1000, mainly the jog-wheel
screens (artwork, beat grid, waveform), which rekordbox drives over a separate
HID channel behind a SysEx handshake. Everything here is enough to drive the
screens from open software, with no rekordbox and no firmware changes.

This repo is protocol only. The Mixxx mapping that uses it lives in the Mixxx fork:
**[sergioalexo/mixxx, branch `ddj-1000-jog-displays`](https://github.com/sergioalexo/mixxx/tree/ddj-1000-jog-displays)**.

## Documents

| File | What it is |
|---|---|
| [`JOG_DISPLAY_PROTOCOL.md`](JOG_DISPLAY_PROTOCOL.md) | How it all works: the two modes, the unlock chain, the handshake, every message in use, the order rekordbox sends them, and notes for driving it from Mixxx. **Only facts confirmed on the unit.** |
| [`PROTOCOL_REFERENCE.md`](PROTOCOL_REFERENCE.md) | Byte-by-byte tables of every SysEx and HID message found in the captures, including unknown bytes and messages we only know exist. Each byte is tagged confirmed / capture / unknown. |
| [`REKORDBOX_LEDS.md`](REKORDBOX_LEDS.md) | What rekordbox sends to the pad and button LEDs (colour numbers per pad mode, init writes). |
| [`CAPTURING.md`](CAPTURING.md) | How to record and decode USB captures, the list of existing captures, the analysis and probe tools, and what still needs capturing. |
| [`firmware/`](firmware/README.md) | Firmware analysis: extracting the CPU images from Pioneer's updater, Ghidra scripts and saved function names, and the notes the handshake and message layouts came from. |

The ordinary MIDI controls (buttons, knobs, faders, LEDs) are in AlphaTheta's
**[DDJ-1000 List of MIDI messages v1.00](https://downloads.support.alphatheta.com/software_info/dj-controllers/DDJ-1000/DDJ-1000_MIDI_Message_List_E1.pdf)**
(PDF). A copy is in [`tools/refs/`](tools/refs/) (PDF + text extract).

## In short

- **Two channels.** USB-MIDI carries the controls and the SysEx handshake. HID
  interface 3 (vendor page `0xFFA0`, 64-byte reports) carries the jog screens.
- **Unlock.** Poll SysEx `50 01` → the unit sends `11 02` → challenge/response
  `12`/`13`/`14` (FNV-1a + XOR with a fixed constant, no secret) → `15 02`
  accepted → HID performance mode. Keep polling `50 01`, or it drops back.
- **Screens.** HID reports `0x21` (live status, ~120/s), `0x2F` beat grid,
  `0x2B` artwork (80×80 JPEG), `0x2C` waveform (600 columns), `0x30` hot cues.
- The unit must be operational first: Pioneer's audio driver / VersionViewer
  running, and the audio device opened full-duplex.

## Tools

| Tool | Platform | What it does |
|---|---|---|
| `tools/ddj_jog_live.py` | macOS, Windows* | Reference driver: full unlock chain + a generated waveform on one jog. `python tools/ddj_jog_live.py --deck 1 --pattern square --hold 60` |
| `tools/ddj_cert.py` | any | Handshake crypto; run it for a self-test. |
| `tools/ddj_jog.py` | any | HID packet builders; `python tools/ddj_jog.py selftest`. |
| `tools/ddj_jog_initdata.py` | any | Bundled init data used by `ddj_jog_live.py`. |
| `tools/install_effects.py` | Windows, macOS, Linux | Installs the DDJ BEAT FX / PAD FX / SOUND COLOR FX effect presets that the fork's mapping expects. Quit Mixxx first. `python tools/install_effects.py [--dry-run] [--settings DIR]` |
| capture, analysis and probe tools | Windows / any | See [`CAPTURING.md`](CAPTURING.md). |

The live tools need `pip install python-rtmidi hidapi sounddevice`.

\* `ddj_jog_live.py` has been confirmed on macOS (Apple Silicon, firmware
v1.12). The libraries it uses are cross-platform, but it has not been run on
Windows yet.

## Not in this repo

- USB captures (`captures/`, hundreds of MB each; see `CAPTURING.md`).
- The firmware images and the Ghidra project (Pioneer's code). `firmware/README.md` says where to get the updater and how to rebuild both.
