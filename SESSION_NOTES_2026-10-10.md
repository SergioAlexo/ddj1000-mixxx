# Session notes, 2026-10-10: USB capture setup, pad colours, jog display protocol

Consolidated record of one working session. Captures themselves are not in this repo (see
`.gitignore` - they are hundreds of MB to several GB each); this file plus the scripts in
`tools/` are enough to redo any of it.

## 1. USB capture setup (Windows, this PC)

- Installed USBPcap 1.5.4 (official signed installer, github.com/desowin/usbpcap).
- The DDJ-1000 sits on the Intel xHCI controller that USBPcap did not attach to by default.
  Fix: `pnputil /restart-device "USB\ROOT_HUB30\4&2a25e443&0&0"` (admin; briefly drops every
  USB device on that controller) made `USBPcap2` appear. May need repeating after a reboot.
- `tools/usb_capture.ps1`: self-elevating capture script, auto-detects the right USBPcap hub,
  Enter to stop. **rekordbox must be fully quit first** (check Task Manager/tray and
  `rekordboxAgent` processes), otherwise the capture misses the startup handshake.
- `tools/decode_capture.py`: turns a `.pcap` into per-endpoint hex logs (`captures/decoded*/`).
  Endpoints: bulk 0x04 OUT / 0x85 IN = USB-MIDI; interrupt 0x06 OUT = jog display;
  interrupt 0x87 IN = jog/HID input.
- `tools/midi_summary.py`, `tools/pad_colors.py`: MIDI/SysEx and pad-colour analysis of a
  decoded capture.
- `tools/midi_send.py`, `tools/sysex_send.py`, `tools/replay_rekordbox.py`,
  `tools/jog_replay.py`, `tools/probe_position_request.py`: send recorded or constructed
  MIDI/SysEx/HID messages to the unit directly (Windows winmm/HID, ctypes, no extra packages),
  to test what a given message does without needing Mixxx or rekordbox running.

## 2. Mapping fixes applied (`controllers/Pioneer-DDJ-1000-Complete-scripts.js`)

- **Startup position request**: `90 21 20` (the message previously sent) does nothing. The
  real request is SysEx `F0 00 40 05 00 00 02 00 00 03 01 F7` - verified on hardware, the
  unit answers with ~82 position messages for every knob/fader/switch. Sent once from
  `sendOpeningState()`.
- **Pad colours**: replaced guessed hue-wheel numbers with rekordbox's actual colour numbers,
  captured on hardware (table in `RB_LED_COMPARISON.md`) for Pad FX 1/2, Beat Jump, Beat Loop,
  Sampler and Key Shift. Added `DDJ1000.RB` / `DDJ1000.pressedColor()`. Hot cue and Keyboard
  mode colours are **not yet** rekordbox-matched (not captured).
- Test harness (`tools/test_mapping.js`) got a `sendSysexMsg` mock and an assertion that the
  position-request SysEx is sent at startup.

### Still open on pad colours
- Only 2 of rekordbox's ~16 hot-cue palette colours were captured (values 22 and 37). A
  capture stepping pad 1 through the full rekordbox colour palette would finish this.
- Whether held-pad colours look brighter or dimmer than idle on the real unit was not
  confirmed by eye.
- An undocumented set of startup messages (`0x9F 0x40-0x4E`, `0xBF 0x41-0x4A`) was queued for
  a differential test (`tools/replay_rekordbox.py ... undoc`) but not finished/confirmed as a
  cause of any remaining colour difference.

## 3. Jog display (waveform/artwork) protocol - decoded, but gated

Full protocol write-up: **`JOG_DISPLAY_PROTOCOL.md`**. Summary:

- Separate channel: HID interface #3 (usage page 0xFFA0), interrupt OUT endpoint 0x06,
  64-byte packets. Confirmed reachable from outside rekordbox/Mixxx via raw HID writes
  (`tools/jog_replay.py`, Windows `CreateFileW`/`WriteFile`, no vendor driver needed).
- **Decoded and verified**: artwork (80x80 baseline JPEG), beat grid (beat number + ms
  position, exact), waveform (600 columns x 7 bytes: 2x RGB565 colour + 2 heights - fields not
  fully decoded), a track-info packet, and the ~120/s live status packet (position/BPM/track
  length fields identified, full layout not complete).
- **Proven by experiment**: with a real, already-unlocked rekordbox session running, replaying
  our own recorded artwork/beatgrid/waveform packets to an *unused* deck (re-addressed to
  deck 3, left jog switched to deck 3 on the unit) makes the unit draw them correctly. So the
  packet formats above are correct.
- **Also proven**: once rekordbox is closed, the same replay draws nothing - only position/BPM
  came through in the very first experiments, and even that stopped working once the "unlock"
  requirement was understood to be per-session. The rich view requires an active,
  authenticated rekordbox session on the USB link.
- **The gate**: rekordbox and the unit perform a SysEx challenge/response at startup
  (messages `12 2A` / `13 2A` / `14 38` / `15 02`, structure fully parsed as TLV fields
  including two random 4/8-byte challenges and 4-byte answers). Six challenge/answer pairs
  from three independent sessions were tested against crc32, adler32, md5, sha1, sha256,
  sha512, blake2b/s, sha3-256 (with byte xor/add variants, with/without the visible strings
  and a constant 10-byte block as extra input): **no match**. The answers depend on a secret
  that is not visible on the wire.
- **Also found**: Mixxx cannot run at the same time as rekordbox on this PC - Pioneer's own
  ASIO driver (`ddj-1000_asio64.dll`) crashes Mixxx when rekordbox already owns the device,
  even when Mixxx's audio output is switched to a different interface (Focusrite Scarlett).
  So "run both at once" is not viable here either.

### Decision
Getting the secret needed to pass that handshake would require extracting it from rekordbox's
own files or the unit's firmware. That was explicitly declined - not a technical dead end, a
line not crossed. The jog-screen waveform/artwork is therefore not achievable through the
Mixxx mapping as things stand.

### Realistic paths forward, if revisited
1. Ask AlphaTheta about a partner/SDK programme that issues this handshake secret to
   third-party software (this is presumably how Serato/VirtualDJ support, if any, works).
2. Accept the MIDI-driven info layer only (position bar, time, BPM, key, cue marker, sync) -
   already implemented and working.
3. Run rekordbox for the jog screens and a different program for everything else, if a
   non-conflicting setup can be found (the ASIO conflict above blocks the obvious version of
   this).

## 4. Test track

`testtracks/wavetest-120s.wav` (+ `.txt` segment table), generated by
`tools/make_test_tracks.py`: 20 segments x 6 s of known tones/noise/amplitude, meant for
matching waveform-column bytes to known signal content column-by-column. Used once; the
column fields (two heights, two colours) were partly characterised in
`JOG_DISPLAY_PROTOCOL.md` but not fully solved.
