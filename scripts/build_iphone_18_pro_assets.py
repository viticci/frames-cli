#!/usr/bin/env python3
"""Build an iPhone 18 Pro pack from supplied PNGs and a Frames 4 pack.

Requires Pillow. Apple artwork stays outside the repository. The destination
must not exist; the source artwork, base pack, and user config are read-only.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

from PIL import Image, ImageDraw


COLORS = ("Black", "Silver", "Glacier", "Burgundy")
SOURCES = {
    "specs": "https://www.apple.com/iphone-18-pro/specs/",
    "announcement": "https://www.apple.com/newsroom/2026/09/apple-debuts-iphone-18-pro-and-iphone-18-pro-max/",
}
VIEWS = (
    {
        "name": "iPhone 18 Pro Portrait",
        "screen": (1206, 2622),
        "canvas": (1350, 2760),
        "opening": (72, 69, 1278, 2691),
        "physicalHeight": 149.6,
    },
    {
        "name": "iPhone 18 Pro Landscape",
        "screen": (2622, 1206),
        "canvas": (2760, 1350),
        "opening": (69, 72, 2691, 1278),
        "physicalHeight": 71.5,
    },
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def catalog_entries():
    """Return variants for the resolution shared with iPhone 17."""
    variants = {}
    for view in VIEWS:
        x, y, _, _ = view["opening"]
        variants[view["name"]] = {
            "name": view["name"],
            "mask": "yes",
            "colors": "yes",
            "x": str(x),
            "y": str(y),
            "physicalHeight": view["physicalHeight"],
        }
    return {"variants": variants}


def screen_mask(image, opening):
    """Create a binary mask for the transparent opening beneath the bezel."""
    x, y, right, bottom = opening
    mask = image.getchannel("A").point(lambda value: 255 if value < 255 else 0)
    seed = ((x + right) // 2, (y + bottom) // 2)
    ImageDraw.floodfill(mask, seed, 128)
    mask = mask.point(lambda value: 255 if value == 128 else 0)
    if mask.getbbox() != opening:
        raise ValueError("Screen opening changed: expected {}, got {}".format(opening, mask.getbbox()))
    return mask.crop(opening)


def write_archive(folder, archive):
    """Write a deterministic ZIP without Finder files or absolute paths."""
    if archive.exists():
        raise ValueError("Archive already exists: {}".format(archive))
    with zipfile.ZipFile(str(archive), "x", zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.name.startswith("."):
                raise ValueError("Unexpected item in built pack: {}".format(path))
            member = zipfile.ZipInfo("Frames-iPhone-18-Pro/" + path.name, (2026, 9, 19, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = 0o100644 << 16
            output.writestr(member, path.read_bytes())


def build_pack(source, base, destination, archive=None):
    """Build and validate a complete pack without replacing existing paths."""
    if destination.exists():
        raise ValueError("Destination must not exist: {}".format(destination))
    if archive and archive.exists():
        raise ValueError("Archive already exists: {}".format(archive))

    catalog_path = base / "NewFrames.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or "variants" not in catalog:
        raise ValueError("Base must be an Apple Frames 4 pack")
    version = (base / "version.txt").read_text(encoding="utf-8").strip()
    if int(version.split(".")[0]) < 4:
        raise ValueError("Base asset version must be at least 4")

    for name, entry in catalog_entries()["variants"].items():
        if name in catalog["variants"]:
            raise ValueError("Base already defines {}".format(name))
        catalog["variants"][name] = entry

    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "pack": "iPhone 18 Pro 1",
        "sources": SOURCES,
        "base_catalog_sha256": sha256(catalog_path.read_bytes()),
        "frames": [],
        "masks": [],
    }
    with tempfile.TemporaryDirectory(prefix="iphone-18-pro-build-", dir=str(destination.parent)) as temporary:
        stage = Path(temporary) / "pack"
        shutil.copytree(base, stage)
        for view in VIEWS:
            first_mask = None
            for color in COLORS:
                filename = "{} {}.png".format(view["name"], color)
                data = (source / filename).read_bytes()
                with Image.open(io.BytesIO(data)) as opened:
                    rgba = opened.convert("RGBA")
                if rgba.size != view["canvas"]:
                    raise ValueError("Unexpected canvas for {}: {}".format(filename, rgba.size))
                mask = screen_mask(rgba, view["opening"])
                if first_mask is not None and mask.tobytes() != first_mask.tobytes():
                    raise ValueError("Screen masks differ between finishes: {}".format(view["name"]))
                first_mask = mask
                shutil.copyfile(source / filename, stage / filename)
                if color == COLORS[0]:
                    shutil.copyfile(source / filename, stage / (view["name"] + ".png"))
                manifest["frames"].append({
                    "file": filename,
                    "source_sha256": sha256(data),
                    "bytes": len(data),
                    "canvas": view["canvas"],
                    "screen": view["screen"],
                    "opening": view["opening"],
                })
            mask_name = view["name"] + "_mask.png"
            first_mask.save(stage / mask_name, "PNG", optimize=True)
            manifest["masks"].append({
                "file": mask_name,
                "size": first_mask.size,
                "sha256": sha256((stage / mask_name).read_bytes()),
            })
        (stage / "NewFrames.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
        (stage / "iPhone-18-Pro.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        stage.rename(destination)

    if archive:
        write_archive(destination, archive)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Folder containing the eight named bezel PNGs")
    parser.add_argument("--base-assets", type=Path, required=True, help="Existing Apple Frames 4 assets")
    parser.add_argument("--output", type=Path, required=True, help="New complete assets directory")
    parser.add_argument("--archive", type=Path, help="Optional new ZIP file")
    args = parser.parse_args()
    try:
        manifest = build_pack(args.source, args.base_assets, args.output, args.archive)
    except (ValueError, OSError) as error:
        parser.exit(1, "Error: {}\n".format(error))
    print("Prepared {} iPhone 18 Pro frames".format(len(manifest["frames"])))
    print("Built {}".format(args.output))


if __name__ == "__main__":
    main()
