"""Draw the DDJ-1000 pad colour flyer (docs/pad-colours.svg).

usage: python tools/pad_colour_flyer.py [out.svg]

The colours are the pad colour numbers the Mixxx mapping sends
(res/controllers/Pioneer-DDJ-1000-scripts.js in the fork, branch
ddj-1000-jog-displays), drawn with the same hue table the mapping uses
(PALETTE_HUES in Pioneer-DDJ-1000-jog-lib.js): 1-63 bright, 64-127 the same
colour dim, 127 white. The hue of each number is the mapping's table, not a
measurement of the unit's LEDs, so treat the swatches as close, not exact.
Update the tables below when the mapping changes and run this again.
"""
import colorsys
import html
import sys
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "docs" / "pad-colours.svg"

# --- palette, as in the mapping -------------------------------------------
PALETTE_HUES = [
    (1, 240), (5, 228), (9, 216), (13, 200), (17, 180), (21, 120), (25, 85),
    (29, 60), (33, 45), (37, 30), (41, 0), (45, 350), (49, 340), (53, 330),
    (57, 300), (61, 275),
]


def hue_of(step):
    """Hue of bright palette step 1-63, interpolated like the mapping."""
    anchors, last = [], float("inf")
    for v, h in PALETTE_HUES:
        while h > last:
            h -= 360
        last = h
        anchors.append((v, h))
    step = max(1, min(61, step))
    for (v0, h0), (v1, h1) in zip(anchors, anchors[1:]):
        if v0 <= step <= v1:
            return (h0 + (h1 - h0) * (step - v0) / (v1 - v0)) % 360
    return anchors[-1][1] % 360


def rgb(value):
    """CSS colour of a pad colour number."""
    if value == 0:
        return "#26262b"
    if value == 127:
        return "#f4f4f6"
    dim = value >= 64
    h = hue_of(value - 64 if dim else value) / 360
    r, g, b = colorsys.hsv_to_rgb(h, 1.0 if not dim else 0.85, 1.0 if not dim else 0.42)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def text_on(value):
    if value == 0:
        return "#8a8a94"
    if value == 127:
        return "#1a1a1a"
    if value >= 64:
        return "#f2f2f2"
    h = hue_of(value)
    return "#1a1a1a" if 35 <= h <= 200 else "#ffffff"


# --- what each mode shows -------------------------------------------------
# A pad is (label, colour number) or (label, colour number, "blink").
OFF = 0
W = 127

MODES = [
    {
        "title": "HOT CUE",
        "how": "HOT CUE button. Two pages of 8 hot cues.",
        "rules": [
            "A hot cue lights in its Mixxx colour (nearest of the pad's 61 colours). Bright.",
            "A saved loop is always ORANGE, and blinks while it runs. Orange means loop, nothing else.",
            "New hot cues get a random colour (never orange, never the same twice in a row). Empty pads are off.",
        ],
        "pages": [
            ("example", [("Cue", 22), ("Cue", 5), ("Cue", 41), ("Loop", 37),
                         ("Cue", 61), ("Loop", 37, "blink"), ("", OFF), ("", OFF)]),
        ],
        "held": None,
    },
    {
        "title": "BEAT JUMP",
        "how": "BEAT JUMP button. PAGE < / > steps through 3 pages; starts on page 2.",
        "rules": [
            "Each size has two pads: left jumps back, right jumps forward.",
            "Red and orange checkerboard, dim at rest; a held pad lights bright.",
        ],
        "pages": [
            ("page 1", [("FINE <", 106), ("FINE >", 106), ("1/8 <", 101), ("1/8 >", 101),
                        ("1/4 <", 101), ("1/4 >", 101), ("1/2 <", 106), ("1/2 >", 106)]),
            ("page 2", [("1 <", 106), ("1 >", 106), ("2 <", 101), ("2 >", 101),
                        ("4 <", 101), ("4 >", 101), ("8 <", 106), ("8 >", 106)]),
            ("page 3", [("16 <", 106), ("16 >", 106), ("32 <", 101), ("32 >", 101),
                        ("64 <", 101), ("64 >", 101), ("128 <", 106), ("128 >", 106)]),
        ],
        "held": [("rest", 106), ("held", 42), ("rest", 101), ("held", 38)],
    },
    {
        "title": "BEAT LOOP",
        "how": "SHIFT + BEAT JUMP. Two pages.",
        "rules": [
            "Page 1 yellowish, page 2 orange, dim at rest.",
            "The running loop's pad, and a held pad, light bright. Press the lit pad again to leave the loop.",
        ],
        "pages": [
            ("page 1", [("1/64", 100), ("1/32", 100), ("1/16", 100), ("1/8", 100),
                        ("1/4", 100), ("1/2", 100), ("1", 100), ("2", 100)]),
            ("page 2", [("4", 102), ("8", 102), ("16", 102), ("32", 102),
                        ("64", 102), ("128", 102), ("256", 102), ("512", 102)]),
        ],
        "held": [("rest", 100), ("running", 37), ("rest", 102), ("running", 38)],
    },
    {
        "title": "PAD FX 1",
        "how": "PAD FX button. Two pages; effects play while the pad is held.",
        "rules": [
            "Colours follow rekordbox: dim at rest, bright while held.",
            "R = release FX: V.BRAKE / BACKSPIN stop the deck; the R echoes ring out for 8 beats after you let go.",
        ],
        "pages": [
            ("page 1", [("ROLL 1/2", 73), ("SWEEP", 78), ("FLANGER", 78), ("V.BRAKE R", 65),
                        ("ECHO 1/4", 69), ("ECHO 1/2", 69), ("REVERB", 86), ("ECHO 1/2 R", 65)]),
            ("page 2", [("TRANS 1/2", 73), ("CRUSH", 120), ("FILTER LFO", 78), ("BACKSPIN R", 65),
                        ("MT DELAY", 69), ("DUB ECHO", 69), ("SPACE", 86), ("ECHO 1 R", 65)]),
        ],
        "held": [("rest", 73), ("held", 9), ("rest", 86), ("held", 22), ("rest", 120), ("held", 56)],
    },
    {
        "title": "PAD FX 2",
        "how": "SHIFT + PAD FX. Two pages; each column is 1/16, 1/8, 1/4, 1/2 beat.",
        "rules": [
            "SLIP LOOP: loop roll with slip. REV ROLL: the same roll played backwards.",
            "Dim at rest, bright while held.",
        ],
        "pages": [
            ("page 1", [("SLIP 1/16", 73), ("SLIP 1/8", 73), ("SLIP 1/4", 73), ("SLIP 1/2", 73),
                        ("REV 1/16", 73), ("REV 1/8", 73), ("REV 1/4", 73), ("REV 1/2", 73)]),
            ("page 2", [("TRANS 1/16", 73), ("TRANS 1/8", 73), ("TRANS 1/4", 73), ("TRANS 1/2", 73),
                        ("MT 1/16", 69), ("MT 1/8", 69), ("MT 1/4", 69), ("MT 1/2", 69)]),
        ],
        "held": [("rest", 73), ("held", 9), ("rest", 69), ("held", 5)],
    },
    {
        "title": "KEY SHIFT",
        "how": "SHIFT + KEYBOARD. PAGE < / > steps through 5 pages; starts on page 1.",
        "rules": [
            "Shifts up orange, shifts down blue. The deck's current shift blinks (0 blinks with no shift).",
            "Page 4: KEY SYNC green, KEY RESET yellow, SEMITONE UP / DOWN amber, dim; bright while held.",
        ],
        "pages": [
            ("page -1", [("+12", 39), ("", OFF), ("", OFF), ("", OFF),
                         ("+8", 39), ("+9", 39), ("+10", 39), ("+11", 39)]),
            ("page 1", [("+4", 39), ("+5", 39), ("+6", 39), ("+7", 39),
                        ("0", 39, "blink"), ("+1", 39), ("+2", 39), ("+3", 39)]),
            ("page 2", [("-4", 9), ("-3", 9), ("-2", 9), ("-1", 9),
                        ("-8", 9), ("-7", 9), ("-6", 9), ("-5", 9)]),
            ("page 3", [("-12", 9), ("-11", 9), ("-10", 9), ("-9", 9),
                        ("", OFF), ("", OFF), ("", OFF), ("", OFF)]),
            ("page 4", [("KEY SYNC", 85), ("SEMI UP", 97), ("+7", 39), ("+12", 39),
                        ("KEY RESET", 93), ("SEMI DOWN", 97), ("-5", 9), ("-12", 9)]),
        ],
        "held": None,
    },
    {
        "title": "SAMPLER",
        "how": "SAMPLER button. SHIFT + PAGE < / > changes the bank of 8.",
        "rules": [
            "A loaded slot is magenta and blinks white while it plays. Empty slots are off.",
        ],
        "pages": [
            ("example", [("loaded", 57), ("playing", 57, "blink"), ("loaded", 57), ("", OFF),
                         ("", OFF), ("loaded", 57), ("", OFF), ("", OFF)]),
        ],
        "held": None,
    },
]

LOOP_BUTTONS = [
    ("No loop", "lit", "lit", "lit"),
    ("LOOP IN pressed", "blink", "lit", "lit"),
    ("Loop running", "blink", "blink", "blink"),
    ("Moving loop in (SHIFT + LOOP IN)", "blink", "lit", "lit"),
]

# --- drawing --------------------------------------------------------------
WIDTH = 1280
MARGIN = 40
PAD_W, PAD_H, GAP = 50, 38, 6
GRID_W = 4 * PAD_W + 3 * GAP
PAGE_GAP = 22
BG, CARD, INK, MUTED, ACCENT = "#0f0f12", "#18181d", "#ececf1", "#9a9aa6", "#ff8a1f"

out = []


def esc(s):
    return html.escape(s, quote=True)


def text(x, y, s, size=13, fill=INK, weight="normal", anchor="start", family="Inter, Segoe UI, Helvetica, Arial, sans-serif"):
    out.append(f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
               f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{esc(s)}</text>')


def pad(x, y, label, value, blink=False, w=PAD_W, h=PAD_H):
    colour = rgb(value)
    if blink:
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{rgb(0)}"/>')
        out.append(f'<path d="M{x + 6},{y} H{x + w - 6} Q{x + w},{y} {x + w},{y + 6} V{y + h - 6} '
                   f'Q{x + w},{y + h} {x + w - 6},{y + h} Z" fill="{colour}"/>')
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="none" '
                   f'stroke="#ffffff" stroke-width="1.5" stroke-dasharray="4 3"/>')
    else:
        glow = "" if value in (0,) or value >= 64 and value != 127 else ' filter="url(#glow)"'
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{colour}"{glow}/>')
    if label:
        size = 9 if len(label) > 8 else 10
        if blink:
            # Readable on both halves: white text with a dark outline.
            out.append(f'<text x="{x + w / 2}" y="{y + h / 2 + 3.5}" font-family="Inter, Segoe UI, Helvetica, Arial, '
                       f'sans-serif" font-size="{size}" font-weight="700" fill="#ffffff" stroke="#000000" '
                       f'stroke-width="2.5" paint-order="stroke" text-anchor="middle">{esc(label)}</text>')
        else:
            text(x + w / 2, y + h / 2 + 3.5, label, size=size, fill=text_on(value), weight="600", anchor="middle")


def page_grid(x, y, name, pads):
    text(x, y - 8, name, size=11, fill=MUTED, weight="600")
    for i, p in enumerate(pads):
        col, row = i % 4, i // 4
        pad(x + col * (PAD_W + GAP), y + row * (PAD_H + GAP), p[0], p[1], len(p) > 2 and p[2] == "blink")
    return 2 * PAD_H + GAP


y = 0
body = []


def section_height(mode):
    return 34 + 18 * len(mode["rules"]) + 26 + 2 * PAD_H + GAP + (44 if mode["held"] else 0) + 24


# header
y = MARGIN
header = []
out_header_start = len(out)
text(MARGIN, y + 26, "DDJ-1000 in Mixxx: what the pads mean", size=30, weight="700")
text(MARGIN, y + 52, "Pad colours of the rekordbox-style mapping (fork branch ddj-1000-jog-displays). "
     "Pads read top row first, left to right.", size=14, fill=MUTED)
y += 76

# legend
legend = [("Bright", 37, False, "active / held / hot cue"), ("Dim", 101, False, "at rest"),
          ("Blink", 37, True, "running / current"), ("Off", 0, False, "empty / unused")]
lx = MARGIN
for name, value, blink, note in legend:
    pad(lx, y, "", value, blink, w=40, h=26)
    text(lx + 50, y + 12, name, size=13, weight="700")
    text(lx + 50, y + 27, note, size=11, fill=MUTED)
    lx += 270
y += 50
text(MARGIN, y, "In HOT CUE mode, orange always means a saved loop: regular hot cues never light orange.",
     size=13, fill=ACCENT, weight="600")
y += 26

# colour key: every colour the pads use, by name. (name, bright number,
# dim number or None, where it is used). Names follow the hue of each number
# in the mapping's table.
COLOUR_KEY = [
    ("Red", 42, 106, "BEAT JUMP"),
    ("Orange", 38, 101, "BEAT JUMP (dim 101), BEAT LOOP p2 (dim 102)"),
    ("Amber orange", 37, 100, "saved loop hot cues, BEAT LOOP p1"),
    ("Red-orange", 39, None, "KEY SHIFT up"),
    ("Azure", 9, 73, "PAD FX roll / trans / slip, KEY SHIFT down"),
    ("Sky blue", 14, 78, "PAD FX sweep / flanger / filter"),
    ("Blue", 1, 65, "PAD FX release FX (R)"),
    ("Royal blue", 5, 69, "PAD FX echo / delay"),
    ("Green", 22, 86, "PAD FX reverb / space, rekordbox green cue"),
    ("Purple", 56, 120, "PAD FX crush"),
    ("Magenta", 57, None, "SAMPLER loaded"),
    ("Lime green", 21, 85, "KEY SHIFT key sync"),
    ("Yellow", 29, 93, "KEY SHIFT key reset"),
    ("Gold", 33, 97, "KEY SHIFT semitone up / down"),
    ("White", 127, None, "SAMPLER playing (blink), loop buttons"),
]
KEY_COLS = 4
KEY_COL_W = (WIDTH - 2 * MARGIN) // KEY_COLS
key_rows = (len(COLOUR_KEY) + KEY_COLS - 1) // KEY_COLS
h = 44 + key_rows * 50 + 8
out.append(f'<rect x="{MARGIN - 16}" y="{y}" width="{WIDTH - 2 * MARGIN + 32}" height="{h}" rx="14" fill="{CARD}"/>')
text(MARGIN, y + 30, "COLOUR NAMES", size=19, weight="700")
text(MARGIN + 175, y + 30, "bright / dim, with the colour numbers the mapping sends", size=13, fill=MUTED)
for i, (name, bright, dim, where) in enumerate(COLOUR_KEY):
    kx = MARGIN + (i % KEY_COLS) * KEY_COL_W
    ky = y + 48 + (i // KEY_COLS) * 50
    pad(kx, ky, "", bright, w=26, h=26)
    if dim is not None:
        pad(kx + 30, ky, "", dim, w=26, h=26)
    nums = f"{bright}" + (f" / {dim}" if dim is not None else "")
    text(kx + 64, ky + 12, f"{name}  ", size=13, weight="700")
    text(kx + 64 + 8 * len(name) + 10, ky + 12, nums, size=11, fill=MUTED)
    text(kx + 64, ky + 27, where, size=10, fill=MUTED)
y += h + 14

for mode in MODES:
    h = section_height(mode)
    out.append(f'<rect x="{MARGIN - 16}" y="{y}" width="{WIDTH - 2 * MARGIN + 32}" height="{h}" rx="14" fill="{CARD}"/>')
    cy = y + 30
    text(MARGIN, cy, mode["title"], size=19, weight="700")
    text(MARGIN + 150, cy, mode["how"], size=13, fill=MUTED)
    cy += 22
    for rule in mode["rules"]:
        text(MARGIN, cy, "•  " + rule, size=13)
        cy += 18
    cy += 22
    px = MARGIN
    for name, pads in mode["pages"]:
        page_grid(px, cy, name, pads)
        px += GRID_W + PAGE_GAP
    cy += 2 * PAD_H + GAP
    if mode["held"]:
        cy += 18
        text(MARGIN, cy + 14, "rest → held:", size=12, fill=MUTED, weight="600")
        hx = MARGIN + 92
        for i in range(0, len(mode["held"]), 2):
            (a_name, a), (b_name, b) = mode["held"][i], mode["held"][i + 1]
            pad(hx, cy, "", a, w=30, h=20)
            text(hx + 38, cy + 14, "→", size=13, fill=MUTED)
            pad(hx + 54, cy, "", b, w=30, h=20)
            text(hx + 92, cy + 14, b_name, size=11, fill=MUTED)
            hx += 170
    y += h + 14

# loop buttons
h = 40 + 30 * (len(LOOP_BUTTONS) + 1) + 20
out.append(f'<rect x="{MARGIN - 16}" y="{y}" width="{WIDTH - 2 * MARGIN + 32}" height="{h}" rx="14" fill="{CARD}"/>')
cy = y + 30
text(MARGIN, cy, "LOOP BUTTONS", size=19, weight="700")
text(MARGIN + 150, cy, "LOOP IN, LOOP OUT and 4 BEAT / EXIT (and their SHIFT functions).", size=13, fill=MUTED)
cy += 30
cols = [MARGIN + 300, MARGIN + 420, MARGIN + 540]
for x, name in zip(cols, ["LOOP IN", "LOOP OUT", "4 BEAT"]):
    text(x + 30, cy, name, size=12, fill=MUTED, weight="600", anchor="middle")
cy += 10
for state, *leds in LOOP_BUTTONS:
    text(MARGIN, cy + 17, state, size=13)
    for x, led in zip(cols, leds):
        # The buttons' own LED colour is not part of the mapping: drawn neutral.
        pad(x, cy + 2, led, W, led == "blink", w=60, h=22)
    cy += 30
y += h + 14

text(MARGIN, y + 16, "Colours are drawn from the mapping's colour numbers and hue table; the unit's LEDs may look a little "
     "different. Generated by tools/pad_colour_flyer.py.", size=11, fill=MUTED)
y += 40

height = y
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">',
       '<defs><filter id="glow" x="-30%" y="-30%" width="160%" height="160%">'
       '<feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/>'
       '<feMergeNode in="SourceGraphic"/></feMerge></filter></defs>',
       f'<rect width="{WIDTH}" height="{height}" fill="{BG}"/>'] + out + ["</svg>"]
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(svg) + "\n", encoding="utf-8")
print(f"wrote {OUT} ({WIDTH}x{height})")
