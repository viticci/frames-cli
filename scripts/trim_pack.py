#!/usr/bin/env python3
"""Crop every frame in a Frames pack to its visible device.

Requires Pillow and oxipng. The Apple Frames shortcut scales merged devices by
canvas height and bottom-aligns canvases, so empty borders of different sizes
skew merges. Cropping makes each canvas match its device. All colors of a
device share one crop box because they share one x/y offset, and every catalog
entry for that device shifts by the crop. Outside the box the crop drops only
invisible specks (alpha at or below NOISE_ALPHA) and lone stray pixels; the
report counts them. Everything kept is pixel-identical. Masks are screenshot-sized and stay as they are. The source
pack is read-only and the destination must not exist.
"""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image, ImageChops, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_duo_assets import write_archive  # noqa: E402

# Highest alpha (0-255) treated as noise when finding a device's edges.
NOISE_ALPHA = 8


def catalog_entries(catalog):
    """Yield every device entry: flat, height overlaps, and variants."""
    for key, value in catalog.items():
        if key == "variants":
            yield from value.values()
        else:
            yield from value.get("overlap", {}).values() or [value]


def is_sideways(name, size):
    """Same rule as the CLI: landscape frames stored in portrait are turned 90° counterclockwise."""
    return name.endswith(" Landscape") and size[1] > size[0]


def frame_files(folder, names):
    """Map each device name to its PNGs ('Name.png' and 'Name Color.png'), longest name first."""
    files = {name: [] for name in names}
    for path in sorted(folder.glob("*.png")):
        if path.stem.endswith("_mask"):
            continue
        matches = [n for n in names if path.stem == n or path.stem.startswith(n + " ")]
        if matches:
            files[max(matches, key=len)].append(path)
    return files


def visible(alpha):
    """Mask of device pixels: above NOISE_ALPHA and touching another such pixel.

    Some of Apple's frames carry a lone pixel at the corner, which would
    otherwise pin the crop to the full canvas."""
    mask = alpha.point(lambda v: 255 if v > NOISE_ALPHA else 0)
    padded = Image.new("L", (mask.width + 2, mask.height + 2), 0)
    padded.paste(mask, (1, 1))
    neighbors = padded.filter(ImageFilter.Kernel((3, 3), [1, 1, 1, 1, 0, 1, 1, 1, 1], scale=1))
    return ImageChops.multiply(mask, neighbors.crop((1, 1, mask.width + 1, mask.height + 1)))


def display_alpha(path, name):
    with Image.open(path) as image:
        alpha = image.convert("RGBA").getchannel("A")
    return alpha.transpose(Image.ROTATE_90) if is_sideways(name, alpha.size) else alpha


def trim_pack(source, destination, version, archive=None):
    """Write a trimmed copy of source; return a report of what changed."""
    if destination.exists():
        raise ValueError("Destination must not exist: {}".format(destination))
    catalog = json.loads((source / "NewFrames.json").read_text(encoding="utf-8"))
    entries = list(catalog_entries(catalog))
    names = sorted({entry["name"] for entry in entries})
    # Warped frames, masks, and camera layers use absolute canvas coordinates.
    warped = {entry["name"] for entry in entries if entry.get("warp")}
    files = {name: paths for name, paths in frame_files(source, names).items() if name not in warped}
    destination.mkdir(parents=True)
    report = {"devices": {}, "untouched": []}
    claimed = {path for paths in files.values() for path in paths}
    for path in sorted(source.iterdir()):
        if path.name.startswith("."):
            continue
        if path not in claimed:
            shutil.copyfile(path, destination / path.name)
            if path.suffix == ".png" and not path.stem.endswith("_mask"):
                report["untouched"].append(path.name)

    for name, paths in files.items():
        if not paths:
            continue
        with Image.open(paths[0]) as first:
            sideways = is_sideways(name, first.size)
            stored_width = first.width
        alphas = [display_alpha(path, name) for path in paths]
        size = alphas[0].size
        if any(alpha.size != size for alpha in alphas):
            raise ValueError("{} colors have different canvas sizes".format(name))
        boxes = [visible(alpha).getbbox() for alpha in alphas]
        box = (min(b[0] for b in boxes), min(b[1] for b in boxes),
               max(b[2] for b in boxes), max(b[3] for b in boxes))
        dropped = max(max_outside(alpha, box) for alpha in alphas)
        # Stray pixels above the noise level that the crop removes.
        above = lambda image: image.point(lambda v: 255 if v > NOISE_ALPHA else 0).histogram()[255]
        lone = sum(above(alpha) - above(alpha.crop(box)) for alpha in alphas)
        # Crop box in the stored orientation (inverse of a 90° counterclockwise turn).
        stored = (stored_width - box[3], box[0], stored_width - box[1], box[2]) if sideways else box
        for path in paths:
            with Image.open(path) as image:
                image.load()
                cropped = image.crop(stored)
                if image.mode == "P" and "transparency" in image.info:
                    cropped.save(destination / path.name, "PNG", transparency=image.info["transparency"])
                else:
                    cropped.save(destination / path.name, "PNG")
            subprocess.run(["oxipng", "-q", "-o", "4", "--strip", "safe", str(destination / path.name)], check=True)
        report["devices"][name] = {"files": len(paths), "canvas": size, "box": box,
                                   "dropped_alpha": dropped, "dropped_lone": lone, "shift": (box[0], box[1])}

    for entry in catalog_entries(catalog):
        info = report["devices"].get(entry["name"])
        if info:
            x, y = int(entry["x"]) - info["shift"][0], int(entry["y"]) - info["shift"][1]
            if x < 0 or y < 0:
                raise ValueError("Crop cuts into the screen of {}".format(entry["name"]))
            entry["x"], entry["y"] = str(x), str(y)
    (destination / "NewFrames.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    # No trailing newline: the Apple Frames shortcut compares this text exactly.
    (destination / "version.txt").write_text(version, encoding="utf-8")
    if archive:
        write_archive(destination, archive)
    return report


def max_outside(alpha, box):
    """Strongest alpha outside box, i.e. the most visible pixel the crop drops."""
    hole = Image.new("L", alpha.size, 0)
    hole.paste(alpha, (0, 0))
    hole.paste(0, box)
    return hole.getextrema()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Existing Frames pack folder")
    parser.add_argument("destination", type=Path, help="New folder for the trimmed pack")
    parser.add_argument("--version", required=True, help="version.txt for the new pack")
    parser.add_argument("--archive", type=Path, help="New ZIP file for distribution")
    parser.add_argument("--report", type=Path, help="Write the per-device report as JSON")
    args = parser.parse_args()
    try:
        report = trim_pack(args.source, args.destination, args.version, args.archive)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, "Error: {}\n".format(error))
    if args.report:
        args.report.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    devices = report["devices"]
    print("Trimmed {} devices ({} PNGs); strongest dropped alpha {}; {} frames untouched".format(
        len(devices), sum(d["files"] for d in devices.values()),
        max(d["dropped_alpha"] for d in devices.values()), len(report["untouched"])))


if __name__ == "__main__":
    main()
