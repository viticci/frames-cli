#!/usr/bin/env python3
"""Add Apple's iPhone Duo PNGs to a standard Frames 4 pack.

Requires Pillow. Apple artwork stays outside the repository. The destination
must not exist; the original artwork, base pack, and user config are read-only.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import tempfile
import zipfile

from PIL import Image, ImageDraw


COLORS = ("Night Sky", "Star White")
SOURCES = {
    "specs": "https://www.apple.com/iphone-duo/specs/",
    "announcement": "https://www.apple.com/newsroom/2026/09/apple-unveils-iphone-duo/",
    "artwork": "https://devimages-cdn.apple.com/design/resources/download/Bezel-iPhone-Duo.dmg",
}
# Screen sizes are the Xcode 27.1 simulator's captures, which match the openings
# measured in the September 9, 2026 PNGs. Exact checks stop a changed download
# using stale geometry. Inner mockups at the announced 1878x2670 still scale in.
VIEWS = (
    {"name": "iPhone Duo Outer Portrait", "source": "Outer Closed Portrait",
     "screen": (1398, 2034), "canvas": (1574, 2194), "opening": (88, 80, 1486, 2114), "physicalHeight": 117.8},
    {"name": "iPhone Duo Outer Landscape", "source": "Outer Closed Landscape",
     "screen": (2034, 1398), "canvas": (2194, 1574), "opening": (80, 88, 2114, 1486), "physicalHeight": 84.1},
    {"name": "iPhone Duo Inner Portrait", "source": "Inner Open Portrait", "announced": (1878, 2670),
     "screen": (2007, 2853), "canvas": (2247, 3093), "opening": (120, 120, 2127, 2973), "physicalHeight": 164.6},
    {"name": "iPhone Duo Inner Landscape", "source": "Inner Open Landscape", "announced": (2670, 1878),
     "screen": (2853, 2007), "canvas": (3093, 2247), "opening": (120, 120, 2973, 2127), "physicalHeight": 117.8},
    {"name": "iPhone Duo Outer Open", "source": "Outer Open",
     "screen": (1398, 2034), "canvas": (3056, 2194), "opening": (1570, 80, 2968, 2114), "physicalHeight": 117.8,
     "manual": True},
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def catalog_entries():
    """Use exact width and height matching; keep the rear view manual."""
    entries = {"variants": {}}
    for view in VIEWS:
        x, y, right, bottom = view["opening"]
        if (right - x, bottom - y) != view["screen"]:
            raise ValueError("{} opening does not match its screen size".format(view["name"]))
        entry = {
            "name": view["name"], "x": str(x), "y": str(y),
            "mask": "yes", "colors": "yes", "physicalHeight": view["physicalHeight"],
        }
        if view.get("manual"):
            entries["variants"][view["name"]] = entry
            continue
        sizes = [view["screen"]]
        if "announced" in view:
            # Scale announced-size mockups, including with --device, to the opening.
            entry.update(resizeWidth=str(right - x), resizeHeight=str(bottom - y))
            sizes.append(view["announced"])
        for width, height in sizes:
            entries.setdefault(str(width), {"overlap": {}})["overlap"][str(height)] = entry
    return entries


def screen_mask(image, opening):
    """Fill the enclosed screen up to fully opaque bezel pixels.

    A binary mask beneath the bezel preserves Apple's own antialiasing without
    applying its transparency twice. The opaque camera remains in the frame.
    """
    x, y, right, bottom = opening
    mask = image.getchannel("A").point(lambda value: 255 if value < 255 else 0)
    seed = ((x + right) // 2, (y + bottom) // 2)
    ImageDraw.floodfill(mask, seed, 128)
    mask = mask.point(lambda value: 255 if value == 128 else 0)
    if mask.getbbox() != opening:
        raise ValueError("Apple's screen opening changed: expected {}, got {}".format(opening, mask.getbbox()))
    return mask.crop(opening)


def optimize_png(data, rgba):
    """Remove descriptive metadata and choose the smaller lossless encoding."""
    stripped = bytearray(data[:8])
    offset = 8
    chunks = []
    while offset < len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        chunk = data[offset:offset + 12 + length]
        chunks.append(kind)
        if kind not in (b"iTXt", b"tEXt", b"zTXt", b"eXIf", b"pHYs", b"tIME"):
            stripped.extend(chunk)
        offset += 12 + length
    candidates = [bytes(stripped)]
    # Preserve color management chunks verbatim if Apple adds them later.
    if not set(chunks).intersection((b"iCCP", b"sRGB", b"gAMA", b"cHRM", b"cICP")):
        clean = Image.frombytes("RGBA", rgba.size, rgba.tobytes())
        output = io.BytesIO()
        clean.save(output, "PNG", optimize=True)
        candidates.append(output.getvalue())
    result = min(candidates, key=len)
    with Image.open(io.BytesIO(result)) as check:
        if check.convert("RGBA").tobytes() != rgba.tobytes():
            raise ValueError("Lossless optimization changed image pixels")
    return result


def write_archive(folder, archive):
    """Write a deterministic ZIP without Finder files or absolute paths."""
    if archive.exists():
        raise ValueError("Archive already exists: {}".format(archive))
    with zipfile.ZipFile(str(archive), "x", zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.name.startswith("."):
                raise ValueError("Unexpected item in built pack: {}".format(path))
            member = zipfile.ZipInfo("Frames/" + path.name, (2026, 9, 30, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = 0o100644 << 16
            output.writestr(member, path.read_bytes())


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
    additions = catalog_entries()
    for key, entry in additions.items():
        if key == "variants":
            for name, variant in entry.items():
                if name in catalog["variants"]:
                    raise ValueError("Base already defines {}".format(name))
                catalog["variants"][name] = variant
        else:
            if key in catalog:
                raise ValueError("Base already defines width {}".format(key))
            catalog[key] = entry

    destination.parent.mkdir(parents=True, exist_ok=True)
    # Build report for the caller; the pack itself ships only frames and catalog.
    manifest = {"sources": SOURCES,
                "base_catalog_sha256": sha256((base / "NewFrames.json").read_bytes()),
                "frames": [], "masks": [], "base_files": {}}
    with tempfile.TemporaryDirectory(prefix="duo-build-", dir=str(destination.parent)) as temporary:
        stage = Path(temporary) / "pack"
        stage.mkdir()
        for path in sorted(base.glob("*.png")):
            data = path.read_bytes()
            (stage / path.name).write_bytes(data)
            manifest["base_files"][path.name] = sha256(data)
        if not manifest["base_files"]:
            raise ValueError("Base pack contains no frame PNGs")
        for view in VIEWS:
            first_mask = None
            for color in COLORS:
                name = "iPhone Duo - {} - {}.png".format(color, view["source"])
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
                manifest["frames"].append({
                    "file": filename, "source_file": name, "source_sha256": sha256(data),
                    "sha256": sha256(optimized), "rgba_sha256": sha256(rgba.tobytes()),
                    "source_bytes": len(data), "bytes": len(optimized),
                    "canvas": view["canvas"], "screen": view["screen"], "opening": view["opening"],
                    "rgba_identical": True,
                })
            mask_name = view["name"] + "_mask.png"
            first_mask.save(stage / mask_name, "PNG", optimize=True)
            manifest["masks"].append({"file": mask_name, "size": first_mask.size,
                                      "sha256": sha256((stage / mask_name).read_bytes())})
            print("Prepared {}".format(view["name"]), flush=True)
        (stage / "NewFrames.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
        # No trailing newline: the Apple Frames shortcut compares this text exactly.
        (stage / "version.txt").write_text(version, encoding="utf-8")
        license_path = source.parent / "Apple Design Resources License.rtf"
        if not license_path.is_file():
            raise ValueError("Keep Apple Design Resources License.rtf beside the source PNG folder")
        shutil.copyfile(license_path, stage / license_path.name)
        stage.rename(destination)
    if archive:
        write_archive(destination, archive)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="PNG folder from Apple's iPhone Duo download")
    parser.add_argument("--base-assets", type=Path, required=True, help="Existing Apple Frames 4 assets")
    parser.add_argument("--output", type=Path, required=True, help="New assets directory")
    parser.add_argument("--archive", type=Path, help="New ZIP file for distribution")
    args = parser.parse_args()
    try:
        manifest = build_pack(args.source, args.base_assets, args.output, args.archive)
    except (ValueError, OSError) as error:
        parser.exit(1, "Error: {}\n".format(error))
    before = sum(item["source_bytes"] for item in manifest["frames"])
    after = sum(item["bytes"] for item in manifest["frames"])
    print("Duo PNGs: {:,} -> {:,} bytes ({:.1%} smaller)".format(before, after, 1 - after / before))
    print("Built {}".format(args.output))


if __name__ == "__main__":
    main()
