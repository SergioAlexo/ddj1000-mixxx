"""Install the DDJ-1000 effect chain presets into Mixxx.

The DDJ-1000 mapping in the Mixxx fork (see README) selects BEAT FX, PAD FX and
SOUND COLOR FX by preset position. This writes the DDJ presets into Mixxx's
effects/chains folder and puts them first in both preset lists, which fixes
those positions. effects.xml is backed up first.

Mixxx must be closed (it rewrites effects.xml when it quits) and must have been
started once, so that effects/defaults and effects.xml exist.

Run:  python tools/install_effects.py                  (install)
      python tools/install_effects.py --dry-run        (show what would change)
      python tools/install_effects.py --settings DIR   (use another settings folder)

Settings folder by default: Windows %LOCALAPPDATA%\\Mixxx; macOS the sandboxed
container folder when it exists, else ~/Library/Application Support/Mixxx;
Linux ~/.mixxx.
"""

import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path


def mixxx_settings_dir():
    if "--settings" in sys.argv:
        return Path(sys.argv[sys.argv.index("--settings") + 1]).expanduser()
    if sys.platform == "win32":
        return Path(os.environ["LOCALAPPDATA"]) / "Mixxx"
    if sys.platform == "darwin":
        container = Path.home() / "Library/Containers/org.mixxx.mixxx/Data/Library/Application Support/Mixxx"
        if container.exists():
            return container
        return Path.home() / "Library/Application Support/Mixxx"
    return Path.home() / ".mixxx"


MIXXX = mixxx_settings_dir()
DRY_RUN = "--dry-run" in sys.argv

# ---------------------------------------------------------------------------
# Effect chain presets. Order matters: the mapping refers to them by position.
# Each effect: (effect id, {parameter: value or (value, link type)}, meta)
# ---------------------------------------------------------------------------

UNIT_PRESETS = [
    ("DDJ Beat - Low Cut Echo", [
        ("echo", {"delay_time": 1.0, "feedback_amount": 0.6, "send_amount": (1.0, "NONE")}),
        ("filter", {"lpf": (22050, "NONE"), "hpf": (350, "NONE")}),
    ]),
    ("DDJ Beat - Echo", [
        ("echo", {"delay_time": 1.0, "feedback_amount": 0.6, "send_amount": (1.0, "NONE")}),
    ]),
    ("DDJ Beat - MT Delay", [
        ("echo", {"delay_time": 1.0, "feedback_amount": 0.45, "pingpong_amount": 0.8,
                  "send_amount": (1.0, "NONE")}),
    ]),
    ("DDJ Beat - Spiral", [
        ("echo", {"delay_time": 0.5, "feedback_amount": 0.85, "send_amount": (1.0, "NONE")}),
        ("reverb", {"decay": 0.6, "send_amount": (0.4, "NONE")}),
    ]),
    ("DDJ Beat - Reverb", [
        ("reverb", {"decay": 0.75, "damping": 0.3, "send_amount": (1.0, "NONE")}),
    ]),
    ("DDJ Beat - Trans", [
        ("tremolo", {"depth": (1.0, "NONE"), "rate": 1.0, "width": 0.5, "waveform": 0.0}),
    ]),
    ("DDJ Beat - Enigma Jet", [
        ("flanger", {"speed": 4.0, "regen": 0.7, "mix": (1.0, "NONE")}),
        ("filter", {"lpf": (22050, "NONE"), "hpf": (180, "NONE")}),
    ]),
    ("DDJ Beat - Flanger", [
        ("flanger", {"speed": 8.0, "regen": 0.5, "mix": (1.0, "NONE")}),
    ]),
    ("DDJ Beat - Phaser", [
        ("phaser", {"lfo_period": 1.0, "feedback": 0.5, "depth": (0.8, "NONE")}),
    ]),
    ("DDJ Beat - Pitch", [
        ("pitchshift", {"pitch": (0.0, "LINKED")}),
    ]),
    ("DDJ Beat - Mobius Saw", [
        ("phaser", {"lfo_period": 8.0, "feedback": 0.6, "stages": 12, "depth": (1.0, "NONE"), "stereo": 1}),
    ]),
    ("DDJ Beat - Mobius Tri", [
        ("flanger", {"speed": 16.0, "regen": 0.8, "mix": (1.0, "NONE")}),
    ]),
    ("DDJ Pad - HPF", [
        ("filter", {"lpf": (22050, "NONE"), "q": 1.2, "hpf": (1200, "NONE")}),
    ]),
    ("DDJ Pad - LPF", [
        ("filter", {"lpf": (600, "NONE"), "q": 1.2, "hpf": (13, "NONE")}),
    ]),
    ("DDJ Pad - Crush", [
        ("bitcrusher", {"bit_depth": (6, "NONE"), "downsample": (0.25, "NONE")}),
    ]),
    ("DDJ Pad - Noise", [
        ("whitenoise", {"dry_wet": (0.35, "NONE")}),
        ("filter", {"lpf": (22050, "NONE"), "hpf": (800, "NONE")}),
    ]),
]

# SOUND COLOR FX: the COLOR knob drives the chain's super knob; everything is
# linked outward from the centre so 12 o'clock is dry, as on the unit.
QUICK_PRESETS = [
    ("DDJ CFX - Dub Echo", [
        ("filter", {"lpf": (22050, "LINKED_LEFT"), "hpf": (13, "LINKED_RIGHT")}),
        ("echo", {"delay_time": 0.75, "feedback_amount": 0.75, "send_amount": (0.0, "LINKED_LEFT_RIGHT")}),
    ]),
    ("DDJ CFX - Pitch", [
        ("pitchshift", {"pitch": (0.0, "LINKED")}),
    ]),
    ("DDJ CFX - Noise", [
        ("whitenoise", {"dry_wet": (0.0, "LINKED_LEFT_RIGHT")}),
        ("filter", {"lpf": (22050, "LINKED_LEFT"), "hpf": (13, "LINKED_RIGHT")}),
    ]),
    ("DDJ CFX - Filter", [
        ("filter", {"lpf": (22050, "LINKED_LEFT"), "q": 1.0, "hpf": (13, "LINKED_RIGHT")}),
    ]),
]


def log(message):
    print(("[dry run] " if DRY_RUN else "") + message)


def mixxx_running():
    if sys.platform == "win32":
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq mixxx.exe"], capture_output=True, text=True).stdout
        return "mixxx.exe" in out.lower()
    return subprocess.run(["pgrep", "-x", "mixxx"], capture_output=True).returncode == 0


def effect_element(effect_name, overrides):
    """Build an <Effect> from Mixxx's own defaults for that effect, so every
    parameter it expects is present, then apply the overrides."""
    default_file = MIXXX / "effects" / "defaults" / f"org-mixxx-effects-{effect_name}.xml"
    effect = ET.parse(default_file).getroot()
    effect.find("MetaParameterValue").text = "0.5"
    seen = set()
    for parameter in effect.find("Parameters"):
        pid = parameter.find("Id").text
        if pid in overrides:
            value = overrides[pid]
            link = None
            if isinstance(value, tuple):
                value, link = value
            parameter.find("Value").text = repr(float(value)).rstrip("0").rstrip(".") if value % 1 else str(int(value))
            if link:
                parameter.find("LinkType").text = link
            seen.add(pid)
    missing = set(overrides) - seen
    if missing:
        raise SystemExit(f"{effect_name}: unknown parameters {missing}")
    return effect


def chain_element(name, effects):
    chain = ET.Element("EffectChain")
    ET.SubElement(chain, "Name").text = name
    ET.SubElement(chain, "MixMode").text = "DRY/WET"
    ET.SubElement(chain, "SuperParameterValue").text = "0.5"
    container = ET.SubElement(chain, "Effects")
    for effect_name, overrides in effects:
        container.append(effect_element(effect_name, overrides))
    for _ in range(4 - len(effects)):
        ET.SubElement(container, "Effect")
    return chain


def write_xml(element, path):
    ET.indent(element, space=" ")
    data = ET.tostring(element, encoding="unicode")
    if DRY_RUN:
        log(f"would write {path}")
        return
    path.write_text("<?xml version='1.0' encoding='utf-8'?>\n" + data + "\n", encoding="utf-8")


def chain_file_name(name):
    return name.replace("/", "-") + ".xml"


def prepend_names(parent, names):
    for element in list(parent):
        if element.text in names:
            parent.remove(element)
    for index, name in enumerate(names):
        element = ET.Element("ChainPresetName")
        element.text = name
        parent.insert(index, element)


def patch_effects_xml():
    path = MIXXX / "effects.xml"
    tree = ET.parse(path)
    root = tree.getroot()
    unit_list = root.find("ChainPresetList")
    quick_list = root.find("QuickEffectPresetList")
    if unit_list is None or quick_list is None:
        raise SystemExit("effects.xml has no preset lists; start Mixxx once, quit it, and run again")
    prepend_names(unit_list, [name for name, _ in UNIT_PRESETS])
    prepend_names(quick_list, [name for name, _ in QUICK_PRESETS])
    write_xml(root, path)
    log("effects.xml: DDJ presets placed first in both preset lists")


def main():
    if not MIXXX.exists():
        raise SystemExit(f"{MIXXX} not found - is Mixxx installed and started once?")
    if mixxx_running() and not DRY_RUN:
        raise SystemExit("Mixxx is running. Quit Mixxx, then run this again.")

    if not DRY_RUN and (MIXXX / "effects.xml").exists():
        backup = MIXXX / f"ddj1000-backup-{time.strftime('%Y%m%d-%H%M%S')}"
        backup.mkdir()
        shutil.copy2(MIXXX / "effects.xml", backup / "effects.xml")
        log(f"backup: {backup}")

    chains = MIXXX / "effects" / "chains"
    if not DRY_RUN:
        chains.mkdir(parents=True, exist_ok=True)
    for name, effects in UNIT_PRESETS + QUICK_PRESETS:
        write_xml(chain_element(name, effects), chains / chain_file_name(name))
    log(f"{len(UNIT_PRESETS) + len(QUICK_PRESETS)} DDJ effect presets written to {chains}")

    patch_effects_xml()
    log("done. Start Mixxx; FX SELECT positions now load the DDJ presets.")


if __name__ == "__main__":
    main()
