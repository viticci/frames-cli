#!/usr/bin/env python3
"""Add Apple's iPad mini (A20 Pro) and Apple Watch Ultra 4 PNGs to a Frames 4 pack.

Requires Pillow, oxipng, and pngquant. Apple artwork stays outside the
repository. New frames get the same crop and optimization as the rest of the
pack; every file from the base pack is copied byte for byte. The destination
must not exist; the artwork and base pack are read-only.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import shutil
import sys
import tempfile

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_duo_assets import screen_mask, write_archive  # noqa: E402
from optimize_pack import optimize  # noqa: E402
from trim_pack import NOISE_ALPHA, trim_pack  # noqa: E402


SOURCES = {
    "ipad_specs": "https://www.apple.com/ipad-mini/specs/",
    "watch_specs": "https://www.apple.com/apple-watch-ultra-4/specs/",
    "ipad_artwork": "https://devimages-cdn.apple.com/design/resources/download/Bezel-iPad-mini-(A20-Pro).dmg",
    "watch_artwork": "https://devimages-cdn.apple.com/design/resources/download/Bezel-Apple-Watch-Ultra-4-2026.dmg",
}
MINI_COLORS = ("Midnight", "Starlight")
ULTRA_COLORS = (
    "Black + Alpine Loop Burgundy", "Black + Ocean Band Translucent Black", "Black + Trail Loop Burgundy",
    "Natural + Alpine Loop Desert", "Natural + Ocean Band Translucent Gray", "Natural + Trail Loop Sand",
)
# Screen sizes are Apple's published resolutions, which match the openings
# measured in the November 2026 PNGs. Neither device needs a mask: the bezel is
# fully opaque over every corner of the screenshot rectangle.
# iPad physicalHeight is Apple's 195.3 x 132.6 mm body. The Watch figure is the
# tallest band's 925 visible pixels at the screen's 326 ppi.
DEVICES = (
    {"name": "iPad mini A20 Pro Portrait", "folder": "mini", "colors": MINI_COLORS,
     "source": "iPad mini (A20 Pro) - {} - Portrait.png",
     "screen": (1512, 2316), "canvas": (1772, 2576), "opening": (130, 130, 1642, 2446), "physicalHeight": 195.3},
    {"name": "iPad mini A20 Pro Landscape", "folder": "mini", "colors": MINI_COLORS,
     "source": "iPad mini (A20 Pro) - {} - Landscape.png",
     "screen": (2316, 1512), "canvas": (2576, 1772), "opening": (130, 130, 2446, 1642), "physicalHeight": 132.6},
    # Ultra 3 and Ultra 4 share 422x514, so Ultra 4 is a variant of the Ultra 3 entry.
    {"name": "Watch Ultra 4", "folder": "ultra", "colors": ULTRA_COLORS, "variant_of": "Watch Ultra 3",
     "source": "AW Ultra 4 - {}.png",
     "screen": (422, 514), "canvas": (620, 940), "opening": (99, 213, 521, 727), "physicalHeight": 72.1},
)


def clear_screen_tint(image, opening):
    """Make the screen fully transparent.

    Apple's Ultra 4 PNGs tint the whole screen with 4/255 black, which would
    darken every screenshot by about 1.6%. Antialiased corners stay as drawn.
    """
    screen = image.crop(opening)
    tint = screen.getchannel("A").point(lambda value: 255 if value <= NOISE_ALPHA else 0)
    screen.paste((0, 0, 0, 0), mask=tint)
    image.paste(screen, opening)
    return image


def new_catalog():
    """Catalog entries for the new devices with uncropped offsets."""
    catalog = {"variants": {}}
    for device in DEVICES:
        x, y, right, bottom = device["opening"]
        if (right - x, bottom - y) != device["screen"]:
            raise ValueError("{} opening does not match its screen size".format(device["name"]))
        entry = {"name": device["name"], "colors": "yes", "x": str(x), "y": str(y),
                 "physicalHeight": device["physicalHeight"]}
        if "variant_of" in device:
            catalog["variants"][device["name"]] = entry
        else:
            catalog[str(device["screen"][0])] = entry
    return catalog


def merge_catalog(base, new):
    """Add new entries to the base catalog, refusing to replace anything."""
    for device in DEVICES:
        primary = device.get("variant_of")
        if primary and not any(value.get("name") == primary for value in base.values()):
            raise ValueError("Base has no {} entry".format(primary))
    for key, entry in new.items():
        if key == "variants":
            continue
        if key in base:
            raise ValueError("Base already defines width {}".format(key))
        base[key] = entry
    for name, entry in new["variants"].items():
        if name in base["variants"]:
            raise ValueError("Base already defines {}".format(name))
        base["variants"][name] = entry
    return base


def write_source_frames(folders, destination):
    """Save validated, tint-free copies of Apple's PNGs under pack filenames."""
    for device in DEVICES:
        first_mask = None
        for color in device["colors"]:
            path = folders[device["folder"]] / device["source"].format(color)
            with Image.open(path) as opened:
                rgba = opened.convert("RGBA")
            if rgba.size != device["canvas"]:
                raise ValueError("Unexpected canvas for {}: {}".format(path.name, rgba.size))
            mask = screen_mask(rgba, device["opening"])
            if mask.getbbox() != (0, 0) + device["screen"]:
                raise ValueError("Unexpected screen in {}".format(path.name))
            if first_mask is not None and mask.tobytes() != first_mask.tobytes():
                raise ValueError("Screens differ between finishes of {}".format(device["name"]))
            first_mask = mask
            clear_screen_tint(rgba, device["opening"]).save(
                destination / "{} {}.png".format(device["name"], color), "PNG")


def build_pack(folders, base, destination, version, archive=None):
    """Build and validate a complete pack without replacing any existing path."""
    if destination.exists():
        raise ValueError("Destination must not exist: {}".format(destination))
    if archive and archive.exists():
        raise ValueError("Archive already exists: {}".format(archive))
    catalog = json.loads((base / "NewFrames.json").read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or "variants" not in catalog:
        raise ValueError("Base must be an Apple Frames 4 pack")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mini-ultra-build-", dir=str(destination.parent)) as temporary:
        temporary = Path(temporary)
        raw, trimmed, stage = temporary / "raw", temporary / "trimmed", temporary / "pack"
        raw.mkdir()
        write_source_frames(folders, raw)
        (raw / "NewFrames.json").write_text(json.dumps(new_catalog()), encoding="utf-8")
        report = trim_pack(raw, trimmed, version)
        stage.mkdir()
        for path in sorted(base.iterdir()):
            if not path.name.startswith("."):
                shutil.copyfile(path, stage / path.name)
        frames = sorted(trimmed.glob("*.png"))
        rows = list(ProcessPoolExecutor().map(optimize, [(path, stage / path.name) for path in frames]))
        new = json.loads((trimmed / "NewFrames.json").read_text(encoding="utf-8"))
        merged = merge_catalog(catalog, new)
        (stage / "NewFrames.json").write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        # No trailing newline: the Apple Frames shortcut compares this text exactly.
        (stage / "version.txt").write_text(version, encoding="utf-8")
        stage.rename(destination)
    if archive:
        write_archive(destination, archive)
    return {"sources": SOURCES, "devices": report["devices"], "entries": new,
            "frames": [{"file": row[0], "kind": row[1], "bytes": row[3]} for row in rows]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mini", type=Path, required=True, help="PNG folder from Apple's iPad mini (A20 Pro) download")
    parser.add_argument("--ultra", type=Path, required=True, help="PNG folder from Apple's Apple Watch Ultra 4 download")
    parser.add_argument("--base-assets", type=Path, required=True, help="Existing cropped Frames pack")
    parser.add_argument("--output", type=Path, required=True, help="New assets directory")
    parser.add_argument("--version", required=True, help="version.txt for the new pack")
    parser.add_argument("--archive", type=Path, help="New ZIP file for distribution")
    parser.add_argument("--report", type=Path, help="Write the build report as JSON")
    args = parser.parse_args()
    try:
        report = build_pack({"mini": args.mini, "ultra": args.ultra}, args.base_assets,
                            args.output, args.version, args.archive)
    except (ValueError, OSError) as error:
        parser.exit(1, "Error: {}\n".format(error))
    if args.report:
        args.report.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print("Added {} frames ({:,} bytes); built {}".format(
        len(report["frames"]), sum(row["bytes"] for row in report["frames"]), args.output))


if __name__ == "__main__":
    main()
