# DDJ-1000 jog display protocol (work in progress)

Derived by us from USB captures of rekordbox 7.2.18 talking to the unit (`captures/rekordbox-clean-*.pcap`,
decoded with `tools/decode_capture.py` and `tools/jog_transfers.py`). Not copied from any other project.

Channel: HID interface #3 (usage page 0xFFA0, usage 1), interrupt OUT endpoint 0x06, 64-byte reports.
Mixxx 2.5 already lists this device as a HID device (`2b73:0020`), so a `.hid.xml` + script can use
`controller.send(data, length, reportId)`. The first byte of every captured packet (0x10, 0x20, 0x30, 0x40 =
deck 1..4) is probably the HID report ID.

## Chunked transfers (types 0x2b, 0x2c, 0x2d, 0x2f)

    byte 0   deck << 4            (0x10 deck 1 ... 0x40 deck 4)
    byte 1   type
    byte 2   sequence number, 1..N
    byte 3   0
    byte 4-5 N = total number of packets of this transfer, little endian
    byte 6.. 58 payload bytes (last packet zero padded); payloads are concatenated across the packets

| type | meaning | payload |
|---|---|---|
| 0x2b | artwork | u16 LE length, then a baseline **JPEG, 80x80** (1.5-2 KB, sent as 27-34 packets) |
| 0x2f | beat grid | u16 LE count, then count x 4 bytes: beat in bar (1..4), position in **milliseconds** (u24 LE). Verified: size = 2 + 4*count exactly, gaps give 135.00 and 122.00 BPM. Only the first ~2 min / 275-342 beats seen |
| 0x2c | waveform | 1 byte (0x80), then **600 columns x 7 bytes**: RGB565 colour A (u16 LE), RGB565 colour B (u16 LE), two heights (e.g. 12 and 1), 0x00. 73 packets, 4201 bytes used. Silence at the end is `f7 bd ff ff 01 01 00` (grey, white, 1, 1). Meaning of the heights and colours still to be decoded |
| 0x2d | preview / track info (1 packet) | `02 <u24> 0a 00` then ten 5-byte entries `9e 2f 27 01 00`. The u24 looks like the track length in ms (01 39 03 = 211201 ms for the 3:31 track on deck 1) - to confirm |

Order rekordbox uses when a track is loaded: beat grid, preview (twice), artwork, then the waveform about 0.4 s
later. All four decks are cleared with empty transfers at startup.

## Live status packets, type 0x21 (partly decoded)

`deck<<4, 0x21, ...`, about 120 per second per deck (bursts up to 1 kHz while the platter moves). Confirmed by replaying
them to deck 1 from outside rekordbox: **the unit shows position and BPM from them with no handshake**, so this channel
works for a Mixxx-side driver. Byte meanings found so far (indexes into the 64-byte packet):

| byte | observed | meaning (hypothesis) |
|---|---|---|
| 2 | 0x18 normal; 0x19/0x1a/0x1b while scratching/seeking | flags, bit 0/1 = jog movement/direction |
| 3 | 0x08 / 0x0a, 0x1a occasionally | bit 1 pulses with the beat (about every beat/bar) |
| 4 | 0x11, 0x10 while the platter is touched, 0x21 at startup | bit 0 = platter not touched |
| 5 | 0x00 / 0x01, 0x80 / 0x81 | bit 7 = playing, bit 0 = other flag (set from startup in one session) |
| 9 | 0x10 no track, 0xb4 track loaded | track-loaded flag (0xbc seen too) |
| 11 | 0, 1, 2 | small counter/state (changes when hot cues/loops are used?) |
| 12-14 | 12 grows 1/s while playing, 13 and 14 low-order bits | playback position (multi-byte, exact encoding not worked out; 3 bytes) |
| 15-18 | `02` then u24 LE, e.g. 01 39 03 = 211201 | track length in ms, same value as in the 0x30 packet; 0 if unknown |
| 21-33, 38-39, 55-61 | change with loops, cues, jog | markers / loop points / BPM-pitch, not decoded |

Type 0x30 (2 packets, seq 1 and 2, sent at load): `[deck<<4][0x30][seq][0][02 00]` + `02 <u24 track length ms> 00 00`.

Open question: nothing in these bytes looks like a "show waveform" switch. Replaying the real track's artwork, beat grid,
waveform and 0x30/0x2d packets together with the status stream still only lit position and BPM on the screen, so the display
mode is probably chosen somewhere else (a rekordbox setting sent in another message, or a mode of the unit itself).

## Findings about the display layers (2026-10-10)

* MIDI `9n 5D` = "display information" (0x00) / "hide information" (0x7F), per Pioneer's list. With it hidden the screen
  falls back to the idle Pioneer DJ logo, even while the full HID stream is replayed.
* Replaying everything rekordbox sent (clear, artwork, beat grid, waveform, 0x30, status packets) over HID to deck 1,
  with no handshake, only ever drew **position and BPM**, never the waveform or artwork that rekordbox shows.
* rekordbox always starts with a SysEx exchange: unit `11 02`, host `03 01` (position request, works on its own),
  host `12 2A ...PioneerDJ...rekordbox... 03 <9 bytes>`, unit `13 2A ...PioneerDJ...DDJ1000... 04 <data>`,
  host `14 38 ...rekordbox... 04 <data>`, unit `15 02`. The tokens differ in every session (three sessions compared), so it is a
  challenge/response, not a fixed message. Replaying a recorded handshake got no reply from the unit.
* Most likely the rich view (waveform + artwork) is only unlocked after that handshake. Not proven. Reproducing it would
  mean working out how rekordbox derives its answer, which needs rekordbox's internals, and was deliberately not attempted.

### Handshake structure and black-box result (2026-10-10)

Parsed from three sessions as TLV records (tag, length incl. the 2 header bytes, value; tokens are nibble-per-byte):
* host `12 2A`: 1 "PioneerDJ", 2 "rekordbox", 3 = 8-byte random host challenge
* unit `13 2A`: 1 "PioneerDJ", 2 "DDJ1000", 4 = 4-byte answer to the host challenge, 3 = 4-byte unit challenge
* host `14 38`: 1, 2, 4 = 4-byte answer to the unit challenge, 5 = 10-byte block `87a08eeac09034760b90`, identical in all sessions
* unit `15 02`: accepted

The four-byte answers were tested (6 challenge/answer pairs) against crc32, adler32, md5, sha1/256/512, blake2, sha3, byte xor/add
variants, with and without the visible strings and constant block as extra input: **no match**. The answers therefore depend on a
secret that is not visible on the wire. Without that secret the handshake cannot be reproduced; getting it would mean extracting it from
rekordbox (or the unit's firmware), which was deliberately not done.

Experiments that did work: with a real rekordbox session running, the recorded artwork/beat grid/waveform transfers re-addressed to deck 3
(`jog_replay.py replay ... 1 all 3`, left jog on deck 3) draw the waveform and artwork. Without rekordbox nothing is drawn.
Mixxx also cannot run next to rekordbox here: Pioneer's ASIO driver (`ddj-1000_asio64.dll`) crashes Mixxx while rekordbox owns the device,
even with Mixxx's audio on the Scarlett.

## Still open
* Waveform column fields (what the two heights and the two colours mean, how they scale with amplitude/frequency).
* Status packet layout, 0x2d entries, other types (0x30/0x31, 0x40 seen on decks 3/4 only at startup).
* Whether the unit needs the SysEx handshake before it accepts jog data (rekordbox always does it first).
* Whether Mixxx can open the HID interface for output on Windows next to the MIDI mapping.

Plan: generate test tracks with a known envelope (`tools/make_test_tracks.py`), load them in rekordbox, capture, and
compare the column bytes with the known amplitude and frequency of each segment.
