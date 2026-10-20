# DDJ-1000 firmware analysis

Tools and notes for reading the DDJ-1000 firmware: how to get the CPU images out
of Pioneer's updater, load them into Ghidra, and the findings so far. The
handshake in [`../JOG_DISPLAY_PROTOCOL.md`](../JOG_DISPLAY_PROTOCOL.md) §3 and
the HID message layouts were derived this way. It is also the route for the open
protocol questions (the HID IN report, `0x2D`, unknown `0x21` bytes — see
[`../PROTOCOL_REFERENCE.md`](../PROTOCOL_REFERENCE.md) §5).

**No firmware is committed.** The images, the CAB contents and the Ghidra
project are Pioneer's code; `images/`, `cab/` and `ghidra-project/` in this
folder are ignored by git. Only the tools, notes and exported annotations are kept.

## 1. Get the firmware

Download the **DDJ-1000 firmware v1.12** updater for Windows from AlphaTheta's
DDJ-1000 support page. Everything here was done on this exact file:

```
DDJ-1000_v112.exe   1,772,632 bytes
sha256 adee21697b7a02e9f8e7dd08b644ab57e9822898523ca4a5cd7419ed4632d1ba
```

## 2. Extract the CPU images

Standard-library Python, works on Windows, macOS and Linux:

```
python tools/cabx.py DDJ-1000_v112.exe firmware/cab
python tools/updsplit.py firmware/cab/DDJ-1000_UP.upd firmware/images > firmware/images/MANIFEST.txt
```

(paths relative to the repo root; create `firmware/cab` and `firmware/images` first.)

`updsplit.py` checks every CRC; [`MANIFEST_v112.txt`](MANIFEST_v112.txt) is the
expected output, with a sha256 prefix per image. The images that matter:

| Image | CPU | Flash base | What it is |
|---|---|---|---|
| `USB1_Ver.1120.bin` | SH-2A, big-endian | `0x70000` | main CPU: USB-MIDI, HID, the handshake (`cert_*`) |
| `LCD_M_Ver.1060.bin` | SH-2A, big-endian | `0x18040000` | jog-screen CPU: renderer for waveform, artwork, beat grid |

Container and image details: [`STAGE1.md`](STAGE1.md).

## 3. Quick looks without Ghidra

| Tool | Usage | Prints |
|---|---|---|
| `tools/usbdesc.py` | `usbdesc.py <USB1 image>` | USB device and configuration descriptors, including the HID interface |
| `tools/tasks.py` | `tasks.py <image> <flash_base> <groups>` — USB1: `0x70000 4`, LCD_M: `0x18040000 8` | the RTOS tasks (name, entry, priority, stack) |

## 4. Ghidra

Tested with **Ghidra 12.1.4** headless. The wrappers in `ghidra/` are POSIX
shell (macOS, Linux, or Git Bash / WSL on Windows). Settings, all optional:

| Variable | Default |
|---|---|
| `GHIDRA_HOME` | `~/Applications/ghidra_12.1.4_PUBLIC` |
| `DDJ_GHIDRA_PROJECT` | `firmware/ghidra-project` (the project is called `DDJ1000`) |
| `DDJ_FW_IMAGES` | `firmware/images` |

```
firmware/ghidra/import_main.sh USB1_Ver.1120.bin 0x70000      # import + set up USB1
firmware/ghidra/import_lcd.sh                                  # import + set up LCD_M
firmware/ghidra/apply_annotations.sh USB1_Ver.1120.bin         # restore our names
firmware/ghidra/apply_annotations.sh LCD_M_Ver.1060.bin
firmware/ghidra/q.sh USB1_Ver.1120.bin "dec cert_on_host_msg"  # decompile, xrefs, … (see Q.java)
firmware/ghidra/export_annotations.sh                          # save names/comments back to annotations/
```

On Windows without a POSIX shell, run `support\analyzeHeadless.bat` with the
same arguments as in the `.sh` files.

| File | What it does |
|---|---|
| `SetupSH2AImage.java` | pre-script for a raw SH-2A image: builds the RAM blocks from the startup copy table and marks the entry point |
| `Q.java` | headless query helper: `dec`, `dis`, `xr`, `lit`, `callers`, `callees`, `funcs`, `ren`, `cmt`, `sweep`, … (list at the top of the file) |
| `ExportAnnotations.java` / `ApplyAnnotations.java` | save the hand-made function names, labels and comments to `annotations/<program>.tsv` and put them back on a fresh import |

**Annotations.** [`annotations/`](annotations/) holds the names given during the
analysis (46 functions in USB1, e.g. `cert_on_host_msg`, `cert_calc`; 40 in
LCD_M, e.g. `task_led`, `wave_render`, `route_hid`). After renaming things in
Ghidra, run `export_annotations.sh` and commit the `.tsv` files; that is how the
work is kept, since the project itself is not committed.

## 5. Notes

| File | Covers |
|---|---|
| [`STAGE1.md`](STAGE1.md) | updater → CAB → `.upd` container format, the 12 CPU images, open questions |
| [`STAGE2_LCD.md`](STAGE2_LCD.md) | the jog-screen CPU: how the host's HID reports reach it, waveform/artwork/beat-grid storage and rendering |
| [`STAGE3_HOST.md`](STAGE3_HOST.md) | the USB1 side: HID dispatch, message types, what the main CPU forwards to the LCD CPU |
| [`STAGE3_GUI.md`](STAGE3_GUI.md) | which state makes the jog screen show the waveform panel |

These were written before anything was tested on the unit. Where they disagree
with `../JOG_DISPLAY_PROTOCOL.md`, the protocol doc is right.
