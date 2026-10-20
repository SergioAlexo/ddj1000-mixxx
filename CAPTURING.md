# Capturing and analysing DDJ-1000 USB traffic

How the rekordbox ↔ DDJ-1000 captures behind this repo were made, how to decode
them, and the tools for poking the unit directly. The captures themselves are
not committed (`captures/` is in `.gitignore`; they are hundreds of MB each).

## 1. Recording a capture (Windows)

All captures so far were made on Windows with USBPcap. On macOS there is no
practical equivalent: a second CoreMIDI client sees what the unit sends, but not
what rekordbox sends to it, and the HID traffic is not visible at all.

1. Install **USBPcap** (1.5.4 used, signed installer from
   [github.com/desowin/usbpcap](https://github.com/desowin/usbpcap)).
2. Make sure USBPcap is attached to the controller the DDJ-1000 is on. On the
   PC used here it sat on an Intel xHCI controller that USBPcap had not attached
   to; restarting that root hub as admin made `USBPcap2` appear (it briefly drops
   every USB device on that controller, and may be needed again after a reboot):
   ```
   pnputil /restart-device "USB\ROOT_HUB30\<instance id>"
   ```
3. **Quit rekordbox completely** (tray icon and any `rekordboxAgent` processes in
   Task Manager). Otherwise the capture misses the startup handshake.
4. Run the capture script. It self-elevates, finds the hub the DDJ-1000 is on,
   and writes `captures/<name>-<timestamp>.pcap`:
   ```
   powershell -ExecutionPolicy Bypass -File tools\usb_capture.ps1 -Name rekordbox-cues
   ```
   Use `-Hub N` to force a hub. Press **Enter** to stop.
5. Start rekordbox and do what you want recorded. Note the times of each action;
   the decoded logs are in seconds from the start of the capture.

`tools/make_test_tracks.py` generates `testtracks/wavetest-120s.wav`: 20 segments
of 6 s with known tones and levels, so each of the 600 waveform columns can be
matched to known audio. Load it in rekordbox during a capture.

## 2. Decoding

```
python tools/decode_capture.py captures/<file>.pcap captures/<outdir>
```

Works on Windows and macOS, standard library only. It writes one text file per
endpoint, one packet per line as `<seconds> <hex payload>`. Audio (isochronous)
is skipped. The suffix is the USB transfer type (`t1` interrupt, `t2` control,
`t3` bulk).

| File | Endpoint | Contents |
|---|---|---|
| `ep_04_t3.txt` | bulk OUT | USB-MIDI host → unit (4-byte USB-MIDI events) |
| `ep_85_t3.txt` | bulk IN | USB-MIDI unit → host |
| `ep_06_t1.txt` | interrupt OUT | HID interface 3, host → unit (jog screens) |
| `ep_87_t1.txt` | interrupt IN | HID interface 3, unit → host |
| `ep_00_t2.txt` / `ep_80_t2.txt` | control | standard USB requests only |

## 3. Existing captures

All recorded on 2026-10-10 with rekordbox 7.2.18, firmware v1.12.

| Decoded folder | pcap | What happens in it |
|---|---|---|
| `decoded` | `ddj1000-20261010-013854.pcap` | first long session |
| `decoded2` | `rekordbox-full-20261010-014911.pcap` | rekordbox start-up and use |
| `decoded3` | `rekordbox-clean-20261010-015224.pcap` | fresh rekordbox start, track loaded on deck 1 at ~80 s; SLIP, pause, deck 2 load (the main reference capture) |
| `decoded4` | `rekordbox-cues-20261010-020438.pcap` | setting and clearing hot cues, pad presses |
| `decoded5` | `wavetest-20261010-022855.pcap` | the wave-test track; channel-fader toggles at 118–135 s, end-of-track ring blink at ~166–172 s |

Matched by re-decoding each pcap and comparing HID packet counts.

## 4. Analysis tools

All take a decoded folder and use only the standard library.

| Tool | What it prints |
|---|---|
| `midi_summary.py <dir>` | every SysEx (de-duplicated, counted) and the distinct MIDI status/data pairs per direction with value ranges |
| `pad_colors.py <dir> [channel] [t_from]` | pad-LED colours per pad note over time, with mode-button and pad-press events |
| `jog_transfers.py <dir> [outdir]` | reassembles the chunked HID transfers (`0x2B` artwork, `0x2C` waveform, `0x2D`, `0x2F` beat grid) into `.bin` files |
| `usbmidi_timeline.py <dir> [window_s]` | the host → unit MIDI and HID traffic just before the unit's first `11 02` (used to find the `50 01` arm poll) |

## 5. Talking to the unit directly (Windows only)

These send recorded or hand-made messages without Mixxx or rekordbox, using
`ctypes` with winmm / hid.dll (no packages to install). **Close Mixxx and
rekordbox first**: only one program can open the DDJ-1000 MIDI port on Windows.

| Tool | What it does |
|---|---|
| `midi_send.py 90 5D 7F …` | send short MIDI messages |
| `sysex_send.py <delay_s> F0…F7 …` | send SysEx messages and print everything the unit sends back |
| `replay_rekordbox.py <dir> <stage> [t_from] [t_to]` | replay part of a recorded session (stages `pads`, `globals`, `undoc`, `all`) to see which messages change the unit |
| `jog_replay.py info` / `replay <dir> <t_from> <t_to> [deck]` | open HID interface 3 and replay recorded jog-screen transfers |
| `probe_position_request.py` | which startup message makes the unit report its control positions (found `03 01`) |
| `list_audio_devices.py [filter]` | list audio devices as Mixxx sees them (uses Mixxx's own `portaudio.dll`) |

For macOS and Windows, use the cross-platform reference driver instead (see the
README): `ddj_jog_live.py` with `python-rtmidi`, `hidapi` and `sounddevice`.

## 6. Open capture work

- **HID IN report**: decoding its unknown bytes (see
  [`PROTOCOL_REFERENCE.md`](PROTOCOL_REFERENCE.md) §4) needs a capture with
  notes of each jog turn and touch, one at a time.
- **Hot-cue colours**: only two of rekordbox's palette colours (22 and 37) have
  been captured. Stepping pad 1 through all 16 palette colours would give the full
  table ([`REKORDBOX_LEDS.md`](REKORDBOX_LEDS.md)).
- Startup messages `9F 40`–`4E` and `BF 41`–`4A` are undocumented and were never
  tested on their own (`replay_rekordbox.py … undoc`).
- Loops, memory cues, KEYBOARD mode and loaded-sampler states are not in any
  capture yet.
