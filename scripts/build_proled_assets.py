#!/usr/bin/env python3
"""Add Apple's MacBook Pro with PROLED XDR Display PNGs to a Frames 4 pack.

Requires Pillow. Apple artwork stays outside the repository. The destination
must not exist; the original artwork, base pack, and user config are read-only.
Run it on a pack that already has iPhone Duo (see build_duo_assets.py).
"""

import argparse
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_duo_assets import optimize_png, screen_mask, sha256, write_archive  # noqa: E402


COLORS = ("Silver", "Space Black")
SOURCES = {
    "specs": "https://www.apple.com/macbook-pro/proled-xdr-display/specs/",
    "announcement": "https://www.apple.com/newsroom/2026/10/apple-unveils-groundbreaking-macbook-pro-with-proled-xdr-display/",
    "artwork": "https://devimages-cdn.apple.com/design/resources/download/Bezel-MacBook-Pro-PROLED-XDR-Display.dmg",
}
# Screen sizes are Apple's published native resolutions, which match the
# openings measured in the October 2026 PNGs. The Dynamic Island is opaque
# artwork inside the opening, so the frame draws it over the screenshot.
# physicalHeight uses the same mm-per-body-pixel ratio as the M5 MacBook Pro
# frames (254.1 / 2296 px and 284.0 / 2578 px), so merges stay proportional.
VIEWS = (
    {"name": "MacBook Pro PROLED 14", "source": "14-inch",
     "screen": (3024, 1986), "canvas": (3860, 2540), "opening": (418, 277, 3442, 2263), "physicalHeight": 248.5},
    {"name": "MacBook Pro PROLED 16", "source": "16-inch",
     "screen": (3472, 2266), "canvas": (4260, 2840), "opening": (394, 287, 3866, 2553), "physicalHeight": 279.5},
)


def add_catalog_entries(catalog):
    """Add PROLED entries; split widths already used by another Mac by height.

    The 14-inch shares its 3024 width with the M5 MacBook Pro (3024x1964), so
    that width becomes an exact-height overlap that keeps the existing frame.
    """
    for view in VIEWS:
        x, y, right, bottom = view["opening"]
        width, height = view["screen"]
        if (right - x, bottom - y) != (width, height):
            raise ValueError("{} opening does not match its screen size".format(view["name"]))
        entry = {"name": view["name"], "x": str(x), "y": str(y),
                 "mask": "yes", "colors": "yes", "physicalHeight": view["physicalHeight"]}
        existing = catalog.get(str(width))
        if existing is None:
            catalog[str(width)] = entry
            continue
        if "overlap" not in existing:
            raise ValueError("Width {} has no height split; add {}'s height to the builder".format(
                width, existing.get("name")))
        if str(height) in existing["overlap"]:
            raise ValueError("Base already defines {}x{}".format(width, height))
        existing["overlap"][str(height)] = entry
    return catalog


def split_shared_width(catalog, width, height):
    """Turn a flat width entry into an overlap keyed by its known height."""
    entry = catalog.get(str(width))
    if entry is not None and "overlap" not in entry:
        catalog[str(width)] = {"overlap": {str(height): entry}}
    return catalog


def build_pack(source, base, destination, archive=None):
    """Build and validate a complete pack without replacing any existing path."""
    if destination.exists():
        raise ValueError("Destination must not exist: {}".format(destination))
    if archive and archive.exists():
        raise ValueError("Archive already exists: {}".format(archive))
    catalog = json.loads((base / "NewFrames.json").read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or "variants" not in catalog:
        raise ValueError("Base must be an Apple Frames 4 pack")
    version = (base / "version.txt").read_text(encoding="utf-8").strip()
    if int(version.split(".")[0]) < 4:
        raise ValueError("Base asset version must be at least 4")
    if catalog.get("3024", {}).get("name") not in (None, "MacBook Pro M5 14"):
        raise ValueError("Unexpected 3024-wide entry in base: {}".format(catalog["3024"]))
    add_catalog_entries(split_shared_width(catalog, 3024, 1964))

    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"sources": SOURCES, "frames": [], "masks": []}
    with tempfile.TemporaryDirectory(prefix="proled-build-", dir=str(destination.parent)) as temporary:
        stage = Path(temporary) / "pack"
        stage.mkdir()
        for path in sorted(base.glob("*.png")):
            shutil.copyfile(path, stage / path.name)
        license_path = source.parent / "Apple Design Resources License.rtf"
        if not license_path.is_file():
            raise ValueError("Keep Apple Design Resources License.rtf beside the source PNG folder")
        shutil.copyfile(license_path, stage / license_path.name)
        for view in VIEWS:
            first_mask = None
            for color in COLORS:
                name = "MacBook Pro with PROLED XDR Display {} {}.png".format(view["source"], color)
                data = (source / name).read_bytes()
                with Image.open(io.BytesIO(data)) as opened:
                    rgba = opened.convert("RGBA")
                if rgba.size != view["canvas"]:
                    raise ValueError("Unexpected canvas for {}: {}".format(name, rgba.size))
                mask = screen_mask(rgba, view["opening"])
                if first_mask is not None and mask.tobytes() != first_mask.tobytes():
                    raise ValueError("Screen masks differ between finishes: {}".format(view["name"]))
                first_mask = mask
                optimized = optimize_png(data, rgba)
                filename = "{} {}.png".format(view["name"], color)
                (stage / filename).write_bytes(optimized)
                manifest["frames"].append({"file": filename, "source_sha256": sha256(data),
                                           "source_bytes": len(data), "bytes": len(optimized)})
            mask_name = view["name"] + "_mask.png"
            first_mask.save(stage / mask_name, "PNG", optimize=True)
            manifest["masks"].append({"file": mask_name, "size": first_mask.size})
            print("Prepared {}".format(view["name"]), flush=True)
        (stage / "NewFrames.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
        (stage / "version.txt").write_text(version + "\n", encoding="utf-8")
        stage.rename(destination)
    if archive:
        write_archive(destination, archive)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="PNG folder from Apple's PROLED download")
    parser.add_argument("--base-assets", type=Path, required=True, help="Existing Apple Frames 4 assets with iPhone Duo")
    parser.add_argument("--output", type=Path, required=True, help="New assets directory")
    parser.add_argument("--archive", type=Path, help="New ZIP file for distribution")
    args = parser.parse_args()
    try:
        manifest = build_pack(args.source, args.base_assets, args.output, args.archive)
    except (ValueError, OSError) as error:
        parser.exit(1, "Error: {}\n".format(error))
    before = sum(item["source_bytes"] for item in manifest["frames"])
    after = sum(item["bytes"] for item in manifest["frames"])
    print("PROLED PNGs: {:,} -> {:,} bytes ({:.1%} smaller)".format(before, after, 1 - after / before))
    print("Built {}".format(args.output))


if __name__ == "__main__":
    main()
