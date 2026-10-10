"""Generate the DDJ-1000 Mixxx MIDI mapping XML.

Every address comes from AlphaTheta's "DDJ-1000 List of MIDI message
version 1.00". Handlers live in the script file; the mixer knobs that map
one-to-one onto a Mixxx control are bound directly.

Run:  python tools/gen_mapping.py                       (personal, rekordbox-exact build)
      python tools/gen_mapping.py --upstream <mixxx repo> (the version for mixxxdj/mixxx)
"""

import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "--upstream" in sys.argv

if UPSTREAM:
    REPO = Path(sys.argv[sys.argv.index("--upstream") + 1])
    OUT = REPO / "res" / "controllers" / "Pioneer-DDJ-1000.midi.xml"
    PREFIX = "PioneerDDJ1000"
    SCRIPT = "Pioneer-DDJ-1000-scripts.js"
else:
    OUT = ROOT / "controllers" / "Pioneer-DDJ-1000-Complete.midi.xml"
    PREFIX = "DDJ1000"
    SCRIPT = "Pioneer-DDJ-1000-Complete-scripts.js"

# Options shown in Preferences > Controllers for the upstream mapping.
UPSTREAM_SETTINGS = """\
    <settings>
        <group label="Mixer">
            <option variable="hardwareHeadphoneMix" type="boolean" default="true"
                label="Let the controller mix cue and main in the headphones">
                <description>
                    The DDJ-1000 blends the cue mix (outputs 3-4) with main (outputs 1-2) using its
                    HEADPHONES MIX knob. When on, Mixxx's own headphone mix is set to cue only so the
                    knob on the controller behaves as labelled.
                </description>
            </option>
            <option variable="tempoRange" type="enum" label="Tempo range when the mapping starts">
                <value label="Keep Mixxx preference" default="true">preferences</value>
                <value label="±6 %">6</value>
                <value label="±10 %">10</value>
                <value label="±16 %">16</value>
                <value label="WIDE (±100 %)">100</value>
            </option>
        </group>
        <group label="SOUND COLOR FX">
            <option variable="colorFxNeedsButton" type="boolean" default="false"
                label="COLOR knobs only work while a SOUND COLOR FX button is on">
                <description>
                    Off: the COLOR knobs always control each deck's Quick Effect.
                    On: they do nothing until a SOUND COLOR FX button is lit, as in rekordbox.
                </description>
            </option>
            <option variable="colorFxPreset1" type="integer" min="0" max="99" default="0"
                label="DUB ECHO button: Quick Effect preset number (0 = keep)"/>
            <option variable="colorFxPreset2" type="integer" min="0" max="99" default="0"
                label="PITCH button: Quick Effect preset number (0 = keep)"/>
            <option variable="colorFxPreset3" type="integer" min="0" max="99" default="0"
                label="NOISE button: Quick Effect preset number (0 = keep)"/>
            <option variable="colorFxPreset4" type="integer" min="0" max="99" default="0"
                label="FILTER button: Quick Effect preset number (0 = keep)"/>
        </group>
    </settings>
"""

controls = []


def script(status, midino, handler, group, description):
    controls.append((status, midino, group, f"{PREFIX}.{handler}", description, ["script-binding"]))


def direct14(status, msb, group, key, description):
    # Pioneer sends MSB then LSB; Mixxx combines the pair.
    controls.append((status, msb, group, key, description + " (MSB)", ["fourteen-bit-msb"]))
    controls.append((status, msb + 0x20, group, key, description + " (LSB)", ["fourteen-bit-lsb"]))


# ---------------------------------------------------------------------------
# Decks: MIDI channels 1-4 (status 0x90-0x93 / 0xB0-0xB3)
# ---------------------------------------------------------------------------

DECK_NOTES = [
    (0x0B, "play", "PLAY/PAUSE"),
    (0x47, "play", "SHIFT + PLAY/PAUSE"),
    (0x0C, "cue", "CUE"),
    (0x48, "jumpToStart", "SHIFT + CUE: jump to track start"),
    (0x1A, "masterTempo", "MASTER TEMPO"),
    (0x60, "tempoRange", "SHIFT + MASTER TEMPO: tempo range"),
    (0x58, "sync", "BEAT SYNC"),
    (0x5C, "syncMaster", "SHIFT + BEAT SYNC: sync master"),
    (0x65, "keySync", "KEY SYNC"),
    (0x64, "keyReset", "KEY RESET"),
    (0x10, "loopIn", "LOOP IN"),
    (0x12, "loopHalve", "LOOP IN while looping: LOOP 1/2X"),
    (0x4C, "loopInAdjust", "SHIFT + LOOP IN: loop in adjust"),
    (0x11, "loopOut", "LOOP OUT"),
    (0x13, "loopDouble", "LOOP OUT while looping: LOOP 2X"),
    (0x4D, "loopOutShift", "SHIFT + LOOP OUT: loop out adjust / reloop"),
    (0x14, "beatLoop4", "4 BEAT LOOP / EXIT"),
    (0x50, "loopActive", "SHIFT + 4 BEAT LOOP: active loop"),
    (0x35, "quantize", "QUANTIZE"),
    (0x39, "monoSplit", "SHIFT + QUANTIZE: headphones mono split"),
    (0x40, "slip", "SLIP"),
    (0x17, "vinyl", "SHIFT + SLIP: VINYL"),
    (0x3A, "vinylState", "VINYL state report"),
    (0x15, "slipReverse", "SLIP REVERSE"),
    (0x38, "reverse", "SHIFT + SLIP REVERSE: REVERSE"),
    (0x5E, "searchBack", "SEARCH <<"),
    (0x70, "searchBackLong", "SEARCH << held"),
    (0x51, "cueCallBack", "SHIFT + SEARCH <<: CUE/LOOP CALL <"),
    (0x5F, "searchForward", "SEARCH >>"),
    (0x71, "searchForwardLong", "SEARCH >> held"),
    (0x53, "cueCallForward", "SHIFT + SEARCH >>: CUE/LOOP CALL >"),
    (0x3D, "memory", "MEMORY"),
    (0x3E, "memoryDelete", "SHIFT + MEMORY: DELETE"),
    (0x3F, "shift", "SHIFT"),
    (0x36, "jogTouch", "JOG touch"),
    (0x67, "jogTouch", "SHIFT + JOG touch"),
    (0x54, "headphoneCue", "Headphones CUE"),
    (0x68, "tapBpm", "SHIFT + Headphones CUE: TAP"),
    (0x66, "faderStartPlay", "Fader start: PLAY"),
    (0x52, "faderStartCue", "Fader start: CUE"),
    (0x16, "crossfaderAssign", "CROSSFADER ASSIGN A"),
    (0x1D, "crossfaderAssign", "CROSSFADER ASSIGN THRU"),
    (0x18, "crossfaderAssign", "CROSSFADER ASSIGN B"),
    (0x72, "deckSelect", "DECK 1/3 or 2/4"),
    (0x79, "gridAdjustState", "Beat grid adjust state"),
    (0x0A, "gridSlideState", "Beat grid slide state"),
]

MODE_BUTTONS = [
    (0x1B, "HOT CUE"), (0x1E, "PAD FX1"), (0x20, "BEAT JUMP"), (0x22, "SAMPLER"),
    (0x69, "SHIFT + HOT CUE: KEYBOARD"), (0x6B, "SHIFT + PAD FX1: PAD FX2"),
    (0x6D, "SHIFT + BEAT JUMP: BEAT LOOP"), (0x6F, "SHIFT + SAMPLER: KEY SHIFT"),
]
MODE_NAMES = ["HOT CUE", "PAD FX1", "BEAT JUMP", "SAMPLER", "KEYBOARD", "PAD FX2", "BEAT LOOP", "KEY SHIFT"]
PAGE_PREV = [0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B]
PAGE_NEXT = [0x2C, 0x2D, 0x2E, 0x2F, 0x30, 0x31, 0x32, 0x33]
SHIFT_PAGE_PREV = [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08]
SHIFT_PAGE_NEXT = [0x09, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E, 0x7F, 0x00]

DECK_CCS = [
    (0x00, "tempo", "TEMPO slider (MSB)"),
    (0x20, "tempo", "TEMPO slider (LSB)"),
    (0x05, "tempo", "SHIFT + TEMPO slider (MSB)"),
    (0x25, "tempo", "SHIFT + TEMPO slider (LSB)"),
    (0x22, "jogScratch", "JOG platter, VINYL on"),
    (0x23, "jogBend", "JOG platter, VINYL off"),
    (0x21, "jogRing", "JOG outer ring"),
    (0x1F, "jogShiftTop", "SHIFT + JOG platter"),
    (0x26, "jogShiftRing", "SHIFT + JOG outer ring"),
    (0x29, "jogSearchFast", "SEARCH + JOG platter"),
]

for deck in range(1, 5):
    n = deck - 1
    group = f"[Channel{deck}]"
    note, cc = 0x90 + n, 0xB0 + n
    for midino, handler, desc in DECK_NOTES:
        script(note, midino, handler, group, f"Deck {deck} {desc}")
    for midino, desc in MODE_BUTTONS:
        script(note, midino, "padMode", group, f"Deck {deck} pad mode {desc}")
    for mode in range(8):
        script(note, PAGE_PREV[mode], "pagePrev", group, f"Deck {deck} {MODE_NAMES[mode]} PAGE <")
        script(note, PAGE_NEXT[mode], "pageNext", group, f"Deck {deck} {MODE_NAMES[mode]} PAGE >")
        script(note, SHIFT_PAGE_PREV[mode], "bankPrev", group, f"Deck {deck} {MODE_NAMES[mode]} SHIFT + PAGE <")
        script(note, SHIFT_PAGE_NEXT[mode], "bankNext", group, f"Deck {deck} {MODE_NAMES[mode]} SHIFT + PAGE >")
    for midino, handler, desc in DECK_CCS:
        script(cc, midino, handler, group, f"Deck {deck} {desc}")
    direct14(cc, 0x04, group, "pregain", f"CH{deck} TRIM")
    direct14(cc, 0x13, group, "volume", f"CH{deck} fader")
    eq = f"[EqualizerRack1_{group}_Effect1]"
    direct14(cc, 0x07, eq, "parameter3", f"CH{deck} EQ HI")
    direct14(cc, 0x0B, eq, "parameter2", f"CH{deck} EQ MID")
    direct14(cc, 0x0F, eq, "parameter1", f"CH{deck} EQ LOW")

# Performance pads: channels 8-15, every note (mode * 16 + page * 8 + pad).
for deck in range(1, 5):
    for shifted in (0, 1):
        status = 0x97 + (deck - 1) * 2 + shifted
        for midino in range(0x80):
            mode, page, pad = midino >> 4, 2 if midino & 8 else 1, (midino & 7) + 1
            desc = f"Deck {deck} {'SHIFT + ' if shifted else ''}{MODE_NAMES[mode]} page {page} pad {pad}"
            script(status, midino, "pad", f"[Channel{deck}]", desc)

# ---------------------------------------------------------------------------
# BEAT FX: MIDI channel 5 (0x94 / 0xB4)
# ---------------------------------------------------------------------------

FX = "[EffectRack1_EffectUnit1]"
script(0x94, 0x4A, "beatDown", FX, "BEAT <")
script(0x94, 0x4B, "beatUp", FX, "BEAT >")
script(0x94, 0x66, "beatAuto", FX, "SHIFT + BEAT <: AUTO")
script(0x94, 0x6B, "beatTap", FX, "SHIFT + BEAT >: TAP")
for i, name in enumerate(["LOW CUT ECHO", "ECHO", "MT DELAY", "SPIRAL", "REVERB", "TRANS", "ENIGMA JET",
                          "FLANGER", "PHASER", "PITCH", "SLIP ROLL", "ROLL", "MOBIUS SAW", "MOBIUS TRI"]):
    script(0x94, 0x20 + i, "beatFxSelect", FX, f"BEAT FX SELECT: {name}")
for i, name in enumerate(["CH1", "CH2", "CH3", "CH4", "MASTER", "MIC", "SAMPLER"]):
    script(0x94, 0x10 + i, "beatFxChannel", FX, f"BEAT FX CH SELECT: {name}")
script(0x94, 0x47, "beatFxOn", FX, "BEAT FX ON/OFF")
script(0x94, 0x43, "releaseFx", FX, "SHIFT + BEAT FX ON/OFF: RELEASE FX")
script(0xB4, 0x02, "beatFxLevel", FX, "BEAT FX LEVEL/DEPTH (MSB)")
script(0xB4, 0x22, "beatFxLevel", FX, "BEAT FX LEVEL/DEPTH (LSB)")

# ---------------------------------------------------------------------------
# Mixer, SOUND COLOR FX and browser: MIDI channel 7 (0x96 / 0xB6)
# ---------------------------------------------------------------------------

for i, name in enumerate(["DUB ECHO", "PITCH", "NOISE", "FILTER"]):
    script(0x96, 0x00 + i, "colorFxButton", "[Master]", f"SOUND COLOR FX {name}")
    script(0x96, 0x08 + i, "colorFxButton", "[Master]", f"SHIFT + SOUND COLOR FX {name}")
    script(0x96, 0x10 + i, "colorFxState", "[Master]", f"SOUND COLOR FX {name} state report")
for deck in range(1, 5):
    direct14(0xB6, 0x16 + deck, f"[QuickEffectRack1_[Channel{deck}]]", "super1", f"CH{deck} COLOR")

direct14(0xB6, 0x1F, "[Master]", "crossfader", "CROSSFADER")
script(0xB6, 0x03, "samplerVolume", "[Master]", "SAMPLER VOL (MSB)")
script(0xB6, 0x23, "samplerVolume", "[Master]", "SAMPLER VOL (LSB)")
script(0x96, 0x69, "samplerCue", "[Master]", "SAMPLER CUE")

script(0xB6, 0x40, "browse", "[Library]", "Rotary selector")
script(0xB6, 0x64, "browseShift", "[Library]", "SHIFT + rotary selector: waveform zoom")
for deck, midino in [(1, 0x46), (2, 0x47), (3, 0x48), (4, 0x49)]:
    script(0x96, midino, "browsePress", "[Library]", f"Rotary selector press: load deck {deck}")
script(0x96, 0x65, "back", "[Library]", "BACK")
script(0x96, 0x7A, "view", "[Library]", "VIEW")
script(0x96, 0x67, "viewLong", "[Library]", "VIEW held: add to Auto DJ")


def render():
    if UPSTREAM:
        info = [
            "        <name>Pioneer DDJ-1000</name>",
            "        <author>Serhii O. Pashchenko</author>",
            "        <description>4-deck mapping for the Pioneer DDJ-1000: all eight pad modes, jog displays, "
            "BEAT FX, SOUND COLOR FX, memory cues and loop adjust.</description>",
            "        <manual>pioneer_ddj_1000</manual>",
        ]
    else:
        info = [
            "        <name>Pioneer DDJ-1000 (Complete)</name>",
            "        <author>Generated for sergioalexo from AlphaTheta's MIDI message list and rekordbox's DDJ-1000 mapping</author>",
            "        <description>Full 4-deck DDJ-1000 mapping for Mixxx 2.5: all 8 pad modes, jog displays, "
            "Beat FX, Sound Color FX, memory cues, loop adjust. Needs the DDJ effect presets from install.py "
            "and Main on outputs 1-2, Headphones on 3-4.</description>",
        ]
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<MixxxControllerPreset mixxxVersion="2.5.0" schemaVersion="1">',
        "    <info>",
        *info,
        "    </info>",
        *([UPSTREAM_SETTINGS.rstrip("\n")] if UPSTREAM else []),
        '    <controller id="DDJ-1000">',
        "        <scriptfiles>",
        f'            <file functionprefix="{PREFIX}" filename="{SCRIPT}"/>',
        "        </scriptfiles>",
        "        <controls>",
    ]
    seen = set()
    for status, midino, group, key, desc, options in controls:
        ident = (status, midino)
        if ident in seen:
            raise SystemExit(f"duplicate MIDI address {status:#04x} {midino:#04x}: {desc}")
        seen.add(ident)
        lines += [
            "            <control>",
            f"                <description>{escape(desc)}</description>",
            f"                <group>{escape(group)}</group>",
            f"                <key>{escape(key)}</key>",
            f"                <status>{status:#04X}</status>".replace("0X", "0x"),
            f"                <midino>{midino:#04X}</midino>".replace("0X", "0x"),
            "                <options>",
            *[f"                    <{option}/>" for option in options],
            "                </options>",
            "            </control>",
        ]
    lines += [
        "        </controls>",
        "        <outputs/>",
        "    </controller>",
        "</MixxxControllerPreset>",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT} ({len(controls)} controls)")
