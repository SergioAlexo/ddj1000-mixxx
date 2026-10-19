"""Install the DDJ-1000 mapping into Mixxx 2.5 on this PC.

What it does (everything it changes is backed up first):
  1. Copies the mapping into %LOCALAPPDATA%\\Mixxx\\controllers.
  2. Writes the DDJ effect chain presets (Beat FX, Pad FX, Sound Color FX)
     into effects\\chains and puts them first in Mixxx's preset lists, which
     is what fixes their numbers for the mapping.
  3. Selects the mapping for the DDJ-1000, sets CUE mode to Pioneer, and adds
     the Headphones output (DDJ-1000 outputs 3-4) next to Main (1-2).

Mixxx must be closed: it rewrites these files when it quits.

Run:  python install.py                 (install)
      python install.py --dry-run       (show what would change)
      python install.py --effects-only  (step 2 only; for the Mixxx-fork
                                         mapping, which needs the Beat FX
                                         presets but not this mapping)

Works on Windows and macOS (the macOS settings folder is the sandboxed
container one when it exists, as Mixxx 2.7 dev builds also use it).
"""

import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
import os

HERE = Path(__file__).resolve().parent


def mixxx_settings_dir():
    if sys.platform == "win32":
        return Path(os.environ["LOCALAPPDATA"]) / "Mixxx"
    container = Path.home() / "Library/Containers/org.mixxx.mixxx/Data/Library/Application Support/Mixxx"
    if container.exists():
        return container
    return Path.home() / "Library/Application Support/Mixxx"


MIXXX = mixxx_settings_dir()
MAPPING_XML = "Pioneer-DDJ-1000-Complete.midi.xml"
MAPPING_JS = "Pioneer-DDJ-1000-Complete-scripts.js"
DRY_RUN = "--dry-run" in sys.argv
EFFECTS_ONLY = "--effects-only" in sys.argv

# ---------------------------------------------------------------------------
# Effect chain presets. Order matters: the script refers to them by position.
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
        raise SystemExit("effects.xml has no preset lists; start Mixxx 2.5 once, quit it, and run again")
    prepend_names(unit_list, [name for name, _ in UNIT_PRESETS])
    prepend_names(quick_list, [name for name, _ in QUICK_PRESETS])
    write_xml(root, path)
    log("effects.xml: DDJ presets placed first in both preset lists")


def patch_mixxx_cfg():
    path = MIXXX / "mixxx.cfg"
    lines = path.read_text(encoding="utf-8").splitlines()
    mapping_path = (MIXXX / "controllers" / MAPPING_XML).as_posix()
    wanted = {
        "[ControllerPreset]": {"DDJ-1000": mapping_path},
        "[Controller]": {"DDJ-1000": "1"},
        "[Controls]": {"CueDefault": "1"},
    }
    section = None
    done = set()
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            # Add keys still missing from the section we are leaving.
            if section in wanted:
                for key, value in wanted[section].items():
                    if (section, key) not in done:
                        out.append(f"{key} {value}")
                        done.add((section, key))
            section = stripped
        elif section in wanted:
            key = stripped.split(" ", 1)[0]
            if key in wanted[section]:
                line = f"{key} {wanted[section][key]}"
                done.add((section, key))
        out.append(line)
    if section in wanted:
        for key, value in wanted[section].items():
            if (section, key) not in done:
                out.append(f"{key} {value}")
                done.add((section, key))
    for section_name, keys in wanted.items():
        for key, value in keys.items():
            if (section_name, key) not in done:
                out += ["", section_name, f"{key} {value}"]
    if DRY_RUN:
        log("would set mixxx.cfg: mapping, controller enabled, CUE mode Pioneer")
        return
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    log("mixxx.cfg: DDJ-1000 uses the new mapping, CUE mode = Pioneer")


def patch_soundconfig():
    path = MIXXX / "soundconfig.xml"
    tree = ET.parse(path)
    root = tree.getroot()
    device = None
    for candidate in root.findall("SoundDevice"):
        if "DDJ-1000" in candidate.get("name", ""):
            device = candidate
    if device is None:
        log("soundconfig.xml: no DDJ-1000 device configured; set outputs by hand (see README)")
        return
    if any(o.get("type") == "Headphones" for o in device.findall("output")):
        log("soundconfig.xml: headphones output already set")
        return
    ET.SubElement(device, "output", {"channel": "2", "channel_count": "2", "index": "0", "type": "Headphones"})
    if DRY_RUN:
        log("would add Headphones on DDJ-1000 outputs 3-4")
        return
    # ElementTree drops the DOCTYPE line Mixxx writes; put it back.
    path.write_text("<!DOCTYPE SoundManagerConfig>\n" + ET.tostring(root, encoding="unicode") + "\n",
                    encoding="utf-8")
    log("soundconfig.xml: Headphones -> DDJ-1000 outputs 3-4")


def main():
    if not MIXXX.exists():
        raise SystemExit(f"{MIXXX} not found - is Mixxx 2.5 installed and started once?")
    if mixxx_running() and not DRY_RUN:
        raise SystemExit("Mixxx is running. Quit Mixxx, then run this again.")

    backup = MIXXX / f"ddj1000-backup-{time.strftime('%Y%m%d-%H%M%S')}"
    if not DRY_RUN:
        backup.mkdir()
        for name in ["effects.xml", "mixxx.cfg", "soundconfig.xml"]:
            if (MIXXX / name).exists():
                shutil.copy2(MIXXX / name, backup / name)
        log(f"backup: {backup}")

    if not EFFECTS_ONLY:
        controllers = MIXXX / "controllers"
        for name in [MAPPING_XML, MAPPING_JS]:
            if DRY_RUN:
                log(f"would copy {name}")
            else:
                controllers.mkdir(exist_ok=True)
                shutil.copy2(HERE / "controllers" / name, controllers / name)
        log("mapping copied to " + str(controllers))

    chains = MIXXX / "effects" / "chains"
    for name, effects in UNIT_PRESETS + QUICK_PRESETS:
        write_xml(chain_element(name, effects), chains / chain_file_name(name))
    log(f"{len(UNIT_PRESETS) + len(QUICK_PRESETS)} DDJ effect presets written")

    patch_effects_xml()
    if EFFECTS_ONLY:
        log("done (effects only). Start Mixxx; FX SELECT positions now load the DDJ Beat FX presets.")
        return
    patch_mixxx_cfg()
    patch_soundconfig()
    log("done. Start Mixxx; the DDJ-1000 lights up once the mapping loads.")


if __name__ == "__main__":
    main()
