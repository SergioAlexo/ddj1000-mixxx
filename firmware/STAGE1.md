# DDJ-1000 v1.12 firmware — Stage 1: extraction

> **Firmware notes from the original analysis (2026-10-13/14).** Written before the live work; anything marked [inferred] or [guess] may since have been confirmed or disproven. [`../JOG_DISPLAY_PROTOCOL.md`](../JOG_DISPLAY_PROTOCOL.md) wins on any conflict. Paths and tools: see [`README.md`](README.md).

Input: `DDJ-1000_v112.exe` (sha256 `adee2169…32d1ba`, 1,772,632 bytes)

Legend: **[verified]** = checked by tool/round-trip; **[inferred]** = strong evidence, not proven; **[guess]** = hypothesis for later stages.

## 1. Outer wrapper (`DDJ-1000_v112.exe`)

- 32-bit PE self-extractor stub (MSVC). `file` mislabels it as InstallShield.
- PE image ends at file offset `0x44000`. The overlay holds a small blob followed by a
  **Microsoft Cabinet** (`MSCF`) at file offset **`0x4553C`**: 1 folder, MSZIP, 161 blocks, 3 files. **[verified]**
  (every block's decompressed size matched its header)

| File | Size | DOS date | Role |
|---|---|---|---|
| `DDJ-1000_UP.upd` | 4,440,556 | 2021-01-27 17:32 | firmware container |
| `DDJUpdate.exe` | 790,016 | 2021-01-27 17:39 | GUI updater (JUCE-style, OpenGL) |
| `pcupdate.dll` | 19,968 | 2017-09-22 10:54 | Pioneer HID transport library |

Tool: `tools/cabx.py <exe> <outdir>` (pure-Python CAB/MSZIP extractor) → `cab/`.

## 2. Container format (`DDJ-1000_UP.upd`)

Reconstructed from the file and confirmed against the updater's parser
(`DDJUpdate.exe` `sub_419280`, CRC in `sub_4184d0`). **[verified]**

```
0x00  char[16]  product  "DDJ-1000        "
0x10  char[16]  version  "Ver.112         "      -> updater parses 3 digits -> 112
0x20  u32 LE    sum of all entry payload sizes   (0x43C000, checked)
0x24  entry[12], back to back:
      +0x00 char[15] name     "DDJ-1000 USB1  "     (matched against "DDJ-1000 ")
      +0x0F char     flag     'Y' | 'N'             (stored per image by updater; meaning TBD)
      +0x10 char[16] version  "Ver.1120        "     (4 digits -> nibble-packed 0x1120)
      +0x20 u32 LE   size
      +0x24 u8[size] payload  (raw, unencrypted, uncompressed)
      +size u16 LE   CRC-16/XMODEM(payload)  poly 0x1021, init 0, refin/refout false, xorout 0
```

The updater implements the CRC as a 24-bit shift register (`xor 0x1102100`) with 2 zero bytes
of augmentation, which is mathematically CRC-16/XMODEM. Note the CRC is stored **little-endian**.

The parse consumes the file exactly to EOF, and the payload total matches the header. All 12 CRCs pass.

Tool: `tools/updsplit.py <upd> <outdir>` → `images/` + `MANIFEST.txt`.

## 3. Component images

| Image | Flag | Ver | Size | CPU | Evidence / notes |
|---|---|---|---|---|---|
| `USB1` | Y | 1.120 | 512 KB | Renesas **SH-2A** (big-endian) | vector[0]=PC `0x1C08DFCA`, vector[1]=SP `0xFFF81CA0` → runs from on-chip large RAM `0x1C0xxxxx`; SH726x-family memory map **[inferred]** |
| `USB2` | Y | 1.120 | 512 KB | SH-2A | PC `0x1C09133E`, same SP. Different code from USB1, same link base. **[guess]** dual-bank A/B or two builds; to resolve in Stage 2 |
| `BOOT` | N | 1.000 | 8 KB | SH-2A | starts `mov.l @(..,pc),r15; mov.l ..,r0; jmp @r0` → SH726x serial-flash boot loader (8 KB loaded to `0xFFF80000`) **[inferred]** |
| `UPDATE` | N | 1.000 | 440 KB | SH-2A | PC `0x1C045CAA` → separate updater-mode firmware for the main CPU **[inferred]** |
| `DSP_P` | Y | 1.040 | 184 KB | DSP, **unidentified** | contains tag `PIONEER DJ` / `DDJ-TOP` at +0xF80; program memory |
| `DSP_D` | Y | 1.020 | 128 KB | same DSP | data/coefficient memory **[guess]** |
| `LCD_M` | Y | 1.060 | 1.75 MB | SH-2A | PC `0x1C20F738`, SP `0xFFF81D60`; large tail = graphics for the jog-wheel displays **[inferred]** |
| `LCD_B` | N | 1.060 | 248 KB | SH-2A | same boot stub as `BOOT` → boot loader of the LCD CPU(s) |
| `DECK` | N | 1.000 | 128 KB | Renesas **R8C/M16C** (LE, 20-bit) | variable vector table of 4-byte ptrs `0x0C37ED…` → app at `0xC0000` |
| `D_BOOT` | N | 1.000 | 128 KB | R8C/M16C | fixed vector table at image end = `0xFFFDC–0xFFFFF` with ID-code bytes → boot at `0xE0000` |
| `MIXER` | Y | 1.020 | 128 KB | R8C/M16C | app at `0xC0000` (vectors `0x0C040F…`) |
| `M_BOOT` | N | 1.020 | 128 KB | R8C/M16C | boot at `0xE0000` |

So the hardware is roughly 1–2 main SH-2A CPUs (USB/audio/MIDI), one display SH-2A system, one DSP,
and two R8C panel MCUs (deck and mixer surface scanning). **[inferred]**

## 4. Leads gathered for the protocol stages

- **Transport.** `pcupdate.dll` is a HID library (`HID_Initialize/Start/Write/Input/GetFirmwareVersion/
  GetDeviceType/EnumHIDno`, SetupAPI + HID.DLL). The updater also imports WinMM MIDI in/out.
- **Update protocol names.** These come from debug strings in `DDJUpdate.exe`:
  `HID_UPDATE_COM_MODE_CHANGE`, `HID_UPDATE_COM_START`, `HID_UPDATE_COM_BLOCK_SEND`,
  `HID_UPDATE_COM_DATA_SEND`, `HID_UPDATE_COM_PROGRESS_CHK`, and replies `HID_UPDATE_ANS_DL_OK`,
  `ANS_REQ_NEXT`, `ANS_RCV_OK`, `ANS_PRGRESS_CHK`, `ANS_COMPLETE`.
- **Control names.** `USB1` contains a test-mode name table at file offset `0x43BFC`: subsystem
  names (`SYSTEM USB1 USB2 BOOT UPDATE DSP-P DSP-D PANEL1 PANEL2 LCD1 LCD2 CLB1-x …`) followed by every
  control name (`PLAY L`, `CUE R`, `PAD1 L`, `JOG L TOUCH`, `CFX FILTER`, …). This is useful for
  mapping MIDI/HID control IDs in a later stage.

## 5. Open questions

1. Meaning of the `Y`/`N` flag. It correlates with "app vs boot/updater", except `DECK` is `N` while `MIXER` is `Y`.
2. USB1 vs USB2: why two different 512 KB SH-2A images with the same link base?
3. The DSP architecture.
4. Contents of the ~5 KB blob in the exe overlay before the CAB (probably stub resources; not firmware).

## Proposed next stages

- **Stage 2 — PC↔device update protocol (HID).** Reverse `pcupdate.dll` and the updater's state machine:
  report IDs and sizes, command/answer opcodes, block/data framing, how CRCs and versions are sent,
  device identification (VID/PID, `GetDeviceType`, `GetFirmwareVersion`).
- **Stage 3 — runtime control protocol.** Load `USB1` into a disassembler (SH-2A BE, base `0x1C080000`),
  find the USB descriptors, the MIDI message tables and HID reports, and map them to the control-name table.
  This yields the MIDI/HID mapping that DJ software uses.
- **Stage 4 — internal buses (optional).** SH↔R8C panel protocol, SH↔LCD, SH↔DSP.
