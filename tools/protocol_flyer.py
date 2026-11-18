"""Draw the DDJ-1000 jog-screen protocol flyer (docs/protocol.svg).

usage: python tools/protocol_flyer.py [out.svg]

A one-page picture of JOG_DISPLAY_PROTOCOL.md: the three USB channels, the
steps from the Pioneer logo to a waveform, which message draws which part of
the jog screen, the waveform column layout and the BEAT FX screen. Same look
as tools/pad_colour_flyer.py. Update it when the protocol notes change.
"""
import html
import sys
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "docs" / "protocol.svg"

W, H = 1280, 1790
FONT = "Inter, Segoe UI, Helvetica, Arial, sans-serif"
MONO = "JetBrains Mono, Consolas, Menlo, monospace"
FG, DIM, PANEL, CARD, LINE = "#ececf1", "#9a9aa6", "#18181d", "#222229", "#33333d"
ORANGE, BLUE, GREEN, PURPLE, RED = "#ff8a1f", "#3d8bff", "#2fd18a", "#a970ff", "#ff4d55"

out = []


def t(x, y, s, size=13, weight="normal", fill=FG, anchor="start", font=FONT):
    out.append(
        f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}">{html.escape(s)}</text>'
    )


def rect(x, y, w, h, fill, rx=10, extra=""):
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" {extra}/>')


def code(x, y, s, fill=ORANGE, size=13, anchor="start"):
    t(x, y, s, size=size, weight="700", fill=fill, font=MONO, anchor=anchor)


def badge(cx, cy, n, fill=ORANGE):
    out.append(f'<circle cx="{cx}" cy="{cy}" r="13" fill="{fill}"/>')
    t(cx, cy + 5, str(n), size=13, weight="700", fill="#111114", anchor="middle")


def section(y, h, title, sub=""):
    rect(24, y, W - 48, h, PANEL, rx=14)
    t(40, y + 32, title, size=19, weight="700")
    if sub:
        t(40 + len(title) * 12.2 + 16, y + 32, sub, size=13, fill=DIM)


def arrow(x1, y1, x2, y2, color=DIM, width=2.5):
    out.append(
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" '
        f'marker-end="url(#arrow-{color[1:]})"/>'
    )


MARKER_COLOURS = [DIM, ORANGE, BLUE, GREEN, PURPLE]

# --- header ---------------------------------------------------------------
t(40, 66, "DDJ-1000 in Mixxx: how the jog screens are driven", size=30, weight="700")
t(40, 92, "The open protocol behind the jog-wheel screens, decoded from the unit and confirmed live "
  "(JOG_DISPLAY_PROTOCOL.md, fork branch ddj-1000-jog-displays).", size=14, fill=DIM)

# --- 1. channels ----------------------------------------------------------
y0 = 120
section(y0, 300, "ONE USB CABLE, THREE CHANNELS")
rect(48, y0 + 58, 200, 220, CARD, rx=12)
t(148, y0 + 160, "Mixxx", size=24, weight="700", anchor="middle")
t(148, y0 + 186, "MIDI mapping", size=12, fill=DIM, anchor="middle")
t(148, y0 + 204, "+ HID mapping", size=12, fill=DIM, anchor="middle")
rect(W - 248, y0 + 58, 200, 220, CARD, rx=12)
t(W - 148, y0 + 160, "DDJ-1000", size=24, weight="700", anchor="middle")
t(W - 148, y0 + 186, "controller", size=12, fill=DIM, anchor="middle")
t(W - 148, y0 + 204, "+ 2 jog screens", size=12, fill=DIM, anchor="middle")

lanes = [
    (GREEN, "USB AUDIO, FULL DUPLEX",
     "Mixxx must open an output and an input on the DDJ. That alone wakes the unit from “no audio driver”."),
    (BLUE, "MIDI + SYSEX",
     "Pads, buttons, faders and LEDs. SysEx drives the BEAT FX screen and asks for every fader position at launch (03 01)."),
    (ORANGE, "HID, INTERFACE 3, 64-BYTE REPORTS",
     "Artwork, waveform, beat grid, cue list and a live status stream for each deck. Unlocked by the handshake below."),
]
for i, (col, name, desc) in enumerate(lanes):
    ly = y0 + 92 + i * 72
    out.append(f'<line x1="256" y1="{ly}" x2="{W - 262}" y2="{ly}" stroke="{col}" stroke-width="4" '
               f'stroke-linecap="round" marker-end="url(#arrow-{col[1:]})" marker-start="url(#arrowb-{col[1:]})"/>')
    rect(300, ly - 17, 680, 52, "#141418", rx=8)
    t(316, ly + 2, name, size=13, weight="700", fill=col)
    t(316, ly + 24, desc, size=12, fill=DIM)

# --- 2. the chain -----------------------------------------------------------
y1 = y0 + 320
section(y1, 250, "FROM PIONEER LOGO TO WAVEFORM", "six steps, all confirmed on the unit")
steps = [
    ("Go live", ["Open DDJ audio", "full duplex,", "stream silence"], None),
    ("Arm", ["SysEx poll"], "50 01"),
    ("Handshake", ["host and unit", "swap 4 messages"], "12→13→14→15"),
    ("Leave the logo", ["replay the", "~413-message", "MIDI init burst"], None),
    ("Render", ["grid, artwork,", "status, then", "waveform"], "2F 2B 21 2C"),
    ("Hold", ["status ~120/s", "+ keepalive ~5/s"], "21 + 50 01"),
]
bw, gap = 180, 24
for i, (name, lines, c) in enumerate(steps):
    bx = 48 + i * (bw + gap)
    by = y1 + 56
    rect(bx, by, bw, 168, CARD, rx=12)
    badge(bx + 26, by + 28, i + 1)
    t(bx + 48, by + 33, name, size=15, weight="700")
    for j, line in enumerate(lines):
        t(bx + 18, by + 70 + j * 19, line, size=12, fill=DIM)
    if c:
        code(bx + 18, by + 150, c, size=13)
    if i < len(steps) - 1:
        arrow(bx + bw + 3, by + 84, bx + bw + gap - 3, by + 84, ORANGE)

# --- 3. the jog screen ------------------------------------------------------
y2 = y1 + 270
section(y2, 520, "WHAT DRAWS WHAT ON THE JOG SCREEN", "HID message types, one deck per report (byte 0 = deck × 16)")
cx, cy, r = 300, y2 + 280, 200
out.append(f'<circle cx="{cx}" cy="{cy}" r="{r + 26}" fill="#101014" stroke="{LINE}" stroke-width="3"/>')
out.append(f'<circle cx="{cx}" cy="{cy}" r="{r + 14}" fill="none" stroke="{ORANGE}" stroke-width="7" '
           f'stroke-dasharray="26 14" opacity=".9" filter="url(#glow)"/>')
out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#0b0b0e" stroke="#2a2a33" stroke-width="2"/>')
# artwork
rect(cx - 52, cy - 150, 104, 104, "url(#art)", rx=8)
t(cx, cy - 92, "♫", size=34, fill="#ffffff", anchor="middle")
# time + bpm
t(cx, cy - 18, "-2:41.3", size=26, weight="700", anchor="middle", font=MONO)
# waveform strip
wx0, wy0, ww, wh = cx - 160, cy + 26, 320, 64
rect(wx0 - 6, wy0 - 4, ww + 12, wh + 8, "#141418", rx=6)
import math
for k in range(80):
    x = wx0 + k * 4
    a = 0.35 + 0.65 * abs(math.sin(k * 0.37) * math.cos(k * 0.11))
    ha = a * wh * 0.9
    hb = ha * 0.45
    hue = [BLUE, "#2fb8ff", GREEN, ORANGE][(k // 9) % 4]
    rect(x, wy0 + wh - ha, 3, ha, hue, rx=0, extra='opacity=".55"')
    rect(x, wy0 + wh - hb, 3, hb, hue, rx=0)
# playhead + cue marker
out.append(f'<line x1="{wx0 + 112}" y1="{wy0 - 6}" x2="{wx0 + 112}" y2="{wy0 + wh + 6}" stroke="#ffffff" stroke-width="2"/>')
out.append(f'<polygon points="{wx0 + 60},{wy0 - 6} {wx0 + 68},{wy0 - 16} {wx0 + 52},{wy0 - 16}" fill="{ORANGE}"/>')
out.append(f'<polygon points="{wx0 + 210},{wy0 - 6} {wx0 + 218},{wy0 - 16} {wx0 + 202},{wy0 - 16}" fill="{GREEN}"/>')
# beat ticks
for k in range(0, 17):
    x = wx0 + k * 20
    out.append(f'<line x1="{x}" y1="{wy0 + wh + 10}" x2="{x}" y2="{wy0 + wh + (18 if k % 4 == 0 else 14)}" stroke="{DIM}" stroke-width="1.5"/>')
# badges on the drawing
for n, (bx, by) in enumerate([(cx + 70, cy - 140), (cx + 176, cy + 58), (cx + 176, cy + 104),
                              (cx + 92, cy - 30), (wx0 + 60, cy - 2), (cx - 230, cy - 120)], start=1):
    badge(bx, by, n)

callouts = [
    ("Artwork", "2B", "80×80 baseline JPEG, about 30 reports. Mixxx re-encodes the cover once per load."),
    ("Waveform", "2C", "600 columns × 7 bytes, 73 reports. Send it once: re-sending redraws with a blink."),
    ("Beat grid", "2F", "beat-in-bar + position in ms per beat. It is the waveform’s time axis, so it is required."),
    ("Time, BPM, playing", "21", "~120 per second per deck: elapsed and track length as min/sec/ms, BPM, pitch, cue."),
    ("Cue markers", "30", "16 hot-cue slots: pad-colour number + time. Resent on every cue change."),
    ("Screen state", "21", "flag bits in the status: SLIP turns the screen red, paused or off air dims it, ring blinks near the end."),
]
lx = 600
for i, (name, c, desc) in enumerate(callouts):
    ly = y2 + 74 + i * 72
    rect(lx, ly - 22, 632, 62, CARD, rx=10)
    badge(lx + 24, ly + 9, i + 1)
    t(lx + 48, ly + 4, name, size=14, weight="700")
    code(lx + 612, ly + 4, "0x" + c, size=14, anchor="end")
    t(lx + 48, ly + 26, desc, size=12, fill=DIM)

# --- 4. waveform column + BEAT FX screen -----------------------------------
y3 = y2 + 540
rect(24, y3, 600, 300, PANEL, rx=14)
t(40, y3 + 32, "ONE WAVEFORM COLUMN", size=19, weight="700")
t(40, y3 + 54, "0x2C, 7 bytes, 600 of them per deck", size=13, fill=DIM)
fields = [("colour A", "RGB565", 2, BLUE), ("colour B", "RGB565", 2, "#2fb8ff"),
          ("height A", "0–40 px", 1, GREEN), ("height B", "0–40 px", 1, "#8be8b8"),
          ("preset", "0–7", 1, PURPLE)]
fx = 48
unit = 76
for name, sub, n, col in fields:
    w = unit * n - 6
    rect(fx, y3 + 78, w, 64, col, rx=8, extra='opacity=".22"')
    rect(fx, y3 + 78, w, 64, "none", rx=8, extra=f'stroke="{col}" stroke-width="2"')
    t(fx + w / 2, y3 + 106, name, size=13, weight="700", anchor="middle")
    t(fx + w / 2, y3 + 126, sub, size=11, fill=DIM, anchor="middle")
    fx += unit * n
for b in range(7):
    t(48 + b * unit + (unit - 6) / 2, y3 + 162, str(b), size=11, fill=DIM, anchor="middle", font=MONO)
# a column drawn
bx0, by0 = 72, y3 + 260
rect(bx0, by0 - 70, 30, 70, BLUE, rx=3, extra='opacity=".55"')
rect(bx0, by0 - 30, 30, 30, BLUE, rx=3)
t(bx0 + 44, by0 - 52, "outer bar: colour A, height A", size=12, fill=DIM)
t(bx0 + 44, by0 - 12, "inner bar: colour B, height B (drawn over A)", size=12, fill=DIM)
t(40, y3 + 286, "From Mixxx’s 3-band overview: low → red, mid → green, high → blue, saturated like rekordbox’s.",
  size=11, fill=DIM)

bx = 656
rect(bx, y3, W - 24 - bx, 300, PANEL, rx=14)
t(bx + 16, y3 + 32, "BEAT FX SCREEN", size=19, weight="700")
t(bx + 16, y3 + 54, "SysEx over MIDI, sent ~20 ms apart in this order", size=13, fill=DIM)
sx, sy = bx + 24, y3 + 78
rect(sx, sy, 260, 150, "#0b0b0e", rx=10, extra=f'stroke="{LINE}" stroke-width="2"')
t(sx + 130, sy + 48, "ECHO", size=28, weight="700", anchor="middle")
t(sx + 130, sy + 84, "1/2", size=22, fill="#d8d8de", anchor="middle")
t(sx + 112, sy + 126, "124.00", size=22, weight="700", anchor="middle", font=MONO)
t(sx + 200, sy + 126, "AUTO", size=11, weight="700", fill=GREEN, anchor="middle")
rows = [("0a", "effect name", "only the unit’s own names (ECHO, REVERB…)"),
        ("0b", "beat value", "shown under the name, redrawn after a 0a"),
        ("0c", "BPM × 100", "of the CH SELECT deck; AUTO or TAP flag")]
for i, (c, name, desc) in enumerate(rows):
    ry = sy + 22 + i * 56
    code(sx + 290, ry, c, size=16)
    t(sx + 322, ry, name, size=14, weight="700")
    t(sx + 290, ry + 22, desc, size=12, fill=DIM)
t(bx + 16, y3 + 286, "Back-to-back messages in one USB transfer keep only the last one.", size=11, fill=DIM)

# --- 5. rules ----------------------------------------------------------------
y4 = y3 + 320
section(y4, 170, "RULES LEARNED ON THE HARDWARE")
rules = [
    ("Wait for analysis", "Send the waveform only when Mixxx has finished the whole overview; until then send an empty one."),
    ("Pace the HID burst", "Mixxx holds 32 HID reports. Send the 73-report waveform in chunks, never all at once."),
    ("Quiet empty decks", "An empty deck gets one status frame per second, or the deck sharing its jog stutters."),
    ("Opt-in", "The handshake runs only with the jogDisplays setting on; otherwise the mapping is plain MIDI."),
]
for i, (name, desc) in enumerate(rules):
    col, row = i % 2, i // 2
    rx_, ry_ = 48 + col * 600, y4 + 70 + row * 52
    out.append(f'<circle cx="{rx_ + 6}" cy="{ry_ - 5}" r="5" fill="{ORANGE}"/>')
    t(rx_ + 22, ry_, name, size=14, weight="700")
    t(rx_ + 22, ry_ + 20, desc, size=12, fill=DIM)

t(40, H - 24, "github.com/SergioAlexo/ddj1000-mixxx · protocol decoded by Danylo Cherevashko · mapping by Sergio Alexo",
  size=12, fill=DIM)

# --- assemble ----------------------------------------------------------------
defs = ['<filter id="glow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="2.2" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
        '<linearGradient id="art" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff3d7f"/>'
        '<stop offset="1" stop-color="#3d5bff"/></linearGradient>']
for col in MARKER_COLOURS + [GREEN, BLUE, ORANGE]:
    k = col[1:]
    defs.append(f'<marker id="arrow-{k}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" '
                f'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{col}"/></marker>')
    defs.append(f'<marker id="arrowb-{k}" viewBox="0 0 10 10" refX="2" refY="5" markerWidth="6" markerHeight="6" '
                f'orient="auto"><path d="M10,0 L0,5 L10,10 z" fill="{col}"/></marker>')
defs = list(dict.fromkeys(defs))

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">\n'
       f'<defs>{"".join(defs)}</defs>\n<rect width="{W}" height="{H}" fill="#0f0f12"/>\n'
       + "\n".join(out) + "\n</svg>\n")
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(svg, encoding="utf-8")
print(f"wrote {OUT} ({len(svg)} bytes)")
