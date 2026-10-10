"""Build "PerformanceDark": Mixxx's LateNight skin with a rekordbox-style scheme.

LateNight already has rekordbox's horizontal layout (stacked waveforms on top,
decks and mixer below, browser at the bottom). This script copies it into the
user skins folder and adds a "Performance" colour scheme as the default:
near-black panels, neutral greys, blue selection, orange active states and a
blue / amber / white 3-band waveform. The PaleMoon and Classic schemes remain.

LateNight is by owilliams and ronso0, licensed CC BY-SA 3.0; so is this
derivative.

Run (with Mixxx closed):  python skin/build_skin.py [--activate]
  --activate  also selects the skin, the rekordbox hot cue / track colour
              palettes and the Stacked waveform in mixxx.cfg (backed up first)
"""

import colorsys
import os
import re
import shutil
import sys
import time
from pathlib import Path

SOURCE = Path(r"C:\Program Files\Mixxx\skins\LateNight")
NAME = "PerformanceDark"
MIXXX = Path(os.environ["LOCALAPPDATA"]) / "Mixxx"
DEST = MIXXX / "skins" / NAME

# 3-band waveform: rekordbox draws lows blue, mids amber, highs white.
WAVEFORM = {"Low": "#1f5bff", "Mid": "#e0922f", "High": "#f2f2f2"}
BLUE_HUE = 212 / 360   # rekordbox selection / accent blue
ORANGE_HUE = 30 / 360  # rekordbox active-state orange

HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def recolor_hex(match):
    text = match.group(1)
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    r, g, b = (int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < 0.3:
        # Greys and PaleMoon's warm beiges -> neutral greys; dark panels
        # a little darker, as rekordbox is nearly black.
        s = 0
        if v < 0.25:
            v *= 0.8
    elif 75 / 360 <= h < 165 / 360:
        h, s = ORANGE_HUE, max(s, 0.85)      # green "on" states -> orange
    elif 165 / 360 <= h < 250 / 360:
        h = BLUE_HUE                         # teal / cyan accents -> blue
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def recolor(text):
    return HEX.sub(recolor_hex, text)


LIBRARY_QSS = """

/**********************************************************************
  Performance scheme: rekordbox-style browser (appended, overrides above)
**********************************************************************/
WTrackTableView,
WLibrarySidebar {
  background-color: #111214;
  alternate-background-color: #16171a;
  color: #d4d4d4;
  selection-background-color: #1d5aa3;
  selection-color: #ffffff;
}
WLibrarySidebar::item:selected,
WTrackTableView::item:selected {
  background-color: #1d5aa3;
  color: #ffffff;
}
WTrackTableViewHeader::section {
  background-color: #1b1c1f;
  color: #9c9c9c;
  border: none;
  border-right: 1px solid #0b0b0c;
  padding: 2px 5px;
}
#SkinContainer {
  background-color: #000000;
}
"""


def scheme_block(skin_xml):
    start = skin_xml.index("    <Scheme>\n      <Name>PaleMoon</Name>")
    end = skin_xml.index("</Scheme><!-- PaleMoon -->") + len("</Scheme><!-- PaleMoon -->")
    return start, end, skin_xml[start:end]


def set_variable(block, name, value):
    pattern = re.compile(rf'(<SetVariable name="{name}">)[^<]*(</SetVariable>)')
    if pattern.search(block):
        return pattern.sub(rf"\g<1>{value}\g<2>", block)
    return block.replace("</Scheme>", f'  <SetVariable name="{name}">{value}</SetVariable>\n    </Scheme>', 1)


def build():
    if DEST.exists():
        shutil.rmtree(DEST)
    shutil.copytree(SOURCE, DEST)

    # Point every template, style and image at the copy. Mixxx resolves
    # "skins:" only in its install folder; a skin in the user skins folder
    # refers to itself with "skin:" (stylesheet urls need "skin:/").
    for path in list(DEST.rglob("*.xml")) + list(DEST.rglob("*.qss")):
        text = path.read_text(encoding="utf-8")
        text = text.replace("url(skins:LateNight/", "url(skin:/").replace("skins:LateNight/", "skin:")
        path.write_text(text, encoding="utf-8")

    # Recoloured image set for the new scheme.
    shutil.copytree(DEST / "palemoon", DEST / "performance")
    for svg in (DEST / "performance").rglob("*.svg"):
        svg.write_text(recolor(svg.read_text(encoding="utf-8")), encoding="utf-8")

    qss = (DEST / "style_palemoon.qss").read_text(encoding="utf-8")
    qss = recolor(qss).replace("skin:/palemoon/", "skin:/performance/")
    (DEST / "style_performance.qss").write_text(qss + LIBRARY_QSS, encoding="utf-8")

    skin_path = DEST / "skin.xml"
    skin = skin_path.read_text(encoding="utf-8")
    start, end, palemoon = scheme_block(skin)
    perf = palemoon.replace("<Name>PaleMoon</Name>", "<Name>Performance</Name>")
    perf = perf.replace("</Scheme><!-- PaleMoon -->", "</Scheme><!-- Performance -->")
    perf = perf.replace("style_palemoon.qss", "style_performance.qss")
    perf = perf.replace("skin:/palemoon/", "skin:/performance/")
    perf = re.sub(r'(<SetVariable name="(Btn|Knob|Slider|Style)Scheme">)palemoon', r"\1performance", perf)
    for name, value in {
        "BgColorOverview_12": "#0c0c0d", "BgColorOverview_34": "#0c0c0d",
        "BgColorWaveform_12": "#050505", "BgColorWaveform_34": "#050505",
        "SignalColor_12": "#2f6bff", "SignalColor_34": "#2f6bff",
        "AxesColor": "#3a3a3a", "BeatColor": "#8a8a8a",
        "PlayPosColor": "#f2f2f2", "CueColor": "#ff8a00", "LoopColor": "#ff8a00",
        "SlipBorderOutlineColor": "#e23c3c", "PlayedOverlayColor": "#aa050505",
        "ArcColorGain": "#1d6fd1", "ArcColorFx12Quick": "#1d6fd1", "ArcColorFx34": "#1d6fd1",
        "BarColorVolume": "#1d6fd1", "BarColorCrossfader": "#1d6fd1", "BarColorPitch": "#9a9a9a",
        "BarBgColor": "#000000",
        "ArcColorGainLow": "#8a8a8a", "ArcColorMstBal": "#1d6fd1", "ArcColorFxMix": "#1d6fd1",
    }.items():
        perf = set_variable(perf, name, value)
    for band, color in WAVEFORM.items():
        perf = set_variable(perf, f"WaveformRGB{band}Color", color)
    # Existing schemes keep Mixxx's default waveform colours.
    rest = skin[start:]
    for band in WAVEFORM:
        rest = re.sub(r"(\s*)(</Scheme><!-- (PaleMoon|Classic) -->)",
                      rf'\1  <SetVariable name="WaveformRGB{band}Color"></SetVariable>\1\2', rest)
    # Performance first, so it is the default scheme.
    skin = skin[:start] + perf + "\n" + rest
    skin = skin.replace("<title>LateNight</title>", f"<title>{NAME}</title>")
    skin = skin.replace('config_key="[Skin],show_effectrack">1<', 'config_key="[Skin],show_effectrack">0<')
    skin = re.sub(r"<author>[^<]*</author>",
                  "<author>owilliams, ronso0 (LateNight); Performance scheme by Serhii O. Pashchenko</author>", skin, 1)
    skin = re.sub(r"<description>[^<]*</description>",
                  "<description>LateNight with a rekordbox-style dark scheme: stacked waveforms on top, "
                  "blue / amber / white 3-band waveforms, near-black panels.</description>", skin, 1)
    skin_path.write_text(skin, encoding="utf-8")

    # Feed the scheme's band colours to the waveforms and overviews.
    for xml in DEST.rglob("*.xml"):
        text = xml.read_text(encoding="utf-8")
        new = text
        for band in WAVEFORM:
            for tag in (f"SignalRGB{band}Color", f"Signal{band}Color"):
                new = new.replace(f"<{tag}></{tag}>",
                                  f'<{tag}><Variable name="WaveformRGB{band}Color"/></{tag}>')
        if new != text:
            xml.write_text(new, encoding="utf-8")

    for preview in DEST.glob("skin_preview_*.png"):
        preview.unlink() if "Classic" in preview.name else None
    print(f"built {DEST}")


def activate():
    cfg = MIXXX / "mixxx.cfg"
    backup = cfg.with_name(f"mixxx.cfg.skin-backup-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(cfg, backup)
    wanted = {
        "[Config]": {"ResizableSkin": NAME, "Scheme": "Performance",
                     "HotcueColorPalette": "Rekordbox COLORFUL Hotcue Colors",
                     "TrackColorPalette": "Rekordbox Track Colors"},
        "[Waveform]": {"WaveformType": "26"},  # Stacked (all-shaders)
        # rekordbox shows decks, mixer and browser; FX, samplers and mics on demand.
        "[Skin]": {"show_effectrack": "0", "show_samplers": "0", "show_microphones": "0"},
    }
    lines, section, out = cfg.read_text(encoding="utf-8").splitlines(), None, []
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s
        elif section in wanted and s.split(" ", 1)[0] in wanted[section]:
            key = s.split(" ", 1)[0]
            line = f"{key} {wanted[section].pop(key)}"
        out.append(line)
    for section_name, keys in wanted.items():
        if keys:
            index = out.index(section_name) + 1 if section_name in out else len(out)
            if section_name not in out:
                out += ["", section_name]
                index = len(out)
            for key, value in keys.items():
                out.insert(index, f"{key} {value}")
    cfg.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"activated (backup: {backup.name})")


if __name__ == "__main__":
    if "--activate" in sys.argv and "mixxx.exe" in os.popen('tasklist /FI "IMAGENAME eq mixxx.exe"').read().lower():
        raise SystemExit("Quit Mixxx first: it rewrites mixxx.cfg when it closes.")
    build()
    if "--activate" in sys.argv:
        activate()
