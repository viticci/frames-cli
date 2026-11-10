#!/usr/bin/env python3
"""Add the partially open Duo landscape pose to a Frames 4 asset pack."""

import argparse
import io
import json
from pathlib import Path
import re
import shutil
from statistics import median
import struct
import subprocess
import tempfile

from PIL import Image

from build_duo_assets import COLORS, write_archive


NAME = "iPhone Duo Inner Partially Open Landscape"
CANVAS = (5600, 4500)


def descriptor_points(descriptor, key):
    """Read the pixel-coordinate points in a Perspective Warp vertex list."""
    start = descriptor.index(key + b"VlLs") + len(key) + 4
    count = struct.unpack_from(">I", descriptor, start)[0]
    # Each entry is a descriptor for a point with two unit doubles.
    pattern = rb"HrznUntF#Pxl(.{8})\x00{4}VrtcUntF#Pxl(.{8})"
    return [struct.unpack(">2d", x + y)
            for x, y in re.findall(pattern, descriptor[start:], re.DOTALL)[:count]]


def inverse_perspective(destination, source):
    """Solve the eight coefficients Pillow uses to sample a projective transform."""
    rows = []
    for (x, y), (u, v) in zip(destination, source):
        x, y = x / CANVAS[0], y / CANVAS[1]
        rows.extend(([x, y, 1, 0, 0, 0, -u * x, -u * y, u],
                     [0, 0, 0, x, y, 1, -v * x, -v * y, v]))
    for index in range(8):
        pivot = max(range(index, 8), key=lambda i: abs(rows[i][index]))
        rows[index], rows[pivot] = rows[pivot], rows[index]
        divisor = rows[index][index]
        rows[index] = [value / divisor for value in rows[index]]
        for i, row in enumerate(rows):
            if i != index:
                rows[i] = [value - row[index] * basis
                           for value, basis in zip(row, rows[index])]
    a, b, c, d, e, f, g, h = (row[-1] for row in rows)
    width, height = CANVAS
    return [a / width, b / height, c, d / width, e / height, f, g / width, h / height]


def warp_regions(path):
    """Extract the Smart Object placement and its three Perspective Warp regions."""
    # The descriptors precede the pixel data in these templates.
    with path.open("rb") as source:
        header = source.read(1024 * 1024)
    start = header.index(b"8BIMSoLd") + 8
    length = struct.unpack_from(">I", header, start)[0]
    descriptor = header[start + 4:start + 4 + length]
    transform = descriptor.index(b"nonAffineTransformVlLs") + len(b"nonAffineTransformVlLs") + 4
    placement = [struct.unpack(">d", value)[0] for value in
                 re.findall(rb"doub(.{8})", descriptor[transform:transform + 96], re.DOTALL)]
    left, top, right, top_right, bottom_right, bottom, bottom_left, bottom_y = placement
    if (left, top, right, bottom) != (bottom_left, top_right, bottom_right, bottom_y):
        raise ValueError("Expected an axis-aligned landscape Smart Object")
    before = descriptor_points(descriptor, b"vertices")
    after = descriptor_points(descriptor, b"warpedVertices")
    quads = re.findall(
        rb"indicesVlLs\x00\x00\x00\x04long(.{4})long(.{4})long(.{4})long(.{4})",
        descriptor, re.DOTALL,
    )
    if len(before) != 8 or len(after) != 8 or len(quads) != 3:
        raise ValueError("Unexpected Perspective Warp geometry")
    normalized = [((x - left) / (right - left), (y - top) / (bottom - top))
                  for x, y in before]
    regions = []
    for quad in quads:
        indices = struct.unpack(">4I", b"".join(quad))
        polygon = [after[i] for i in indices]
        regions.append({"polygon": polygon, "inverse": inverse_perspective(
            polygon, [normalized[i] for i in indices],
        )})
    return regions


def read_layers(psd):
    """Read cached PSD layer pixels with ImageMagick, retaining canvas offsets."""
    command = ["magick", "identify", "-format", "%s|%l|%X|%Y|%w|%h\n", str(psd)]
    layers = [line.split("|") for line in subprocess.check_output(command, text=True).splitlines()]
    if [layer[1].strip() for layer in layers] != ["", "Hardware", "Screen Content", "Black", "Dark", "Light"]:
        raise ValueError(f"Unexpected layer layout in {psd.name}")
    if tuple(map(int, layers[0][4:])) != CANVAS:
        raise ValueError(f"Unexpected canvas dimensions in {psd.name}")
    pixels = {}
    for index, name, x, y, _, _ in layers[1:]:
        png = subprocess.check_output(["magick", f"{psd}[{index}]", "+repage", "PNG32:-"])
        with Image.open(io.BytesIO(png)) as image:
            pixels[name.strip()] = (image.convert("RGBA"), (int(x), int(y)))
    return pixels


def reflection_profile(psd):
    """Sample the neutral reflection in Apple's merged preview, away from text and edges."""
    png = subprocess.check_output([
        "magick", f"{psd}[0]", "-resize", "1400x1125!", "PNG24:-",
    ])
    with Image.open(io.BytesIO(png)) as preview:
        samples = preview.convert("L").resize((100, 1125), Image.BOX)
    columns = [round(median(samples.getpixel((x, y)) for y in (200, 275, 850, 930)))
               for x in range(25, 75)]
    # Continue the outer values to the sides. The display mask supplies the perimeter.
    levels = [columns[0]] * 25 + columns + [columns[-1]] * 25
    return [max(0, level - columns[0]) for level in levels]


def build_pack(source, base, output):
    if output.exists():
        raise ValueError(f"Destination must not exist: {output}")
    catalog = json.loads((base / "NewFrames.json").read_text(encoding="utf-8"))
    if NAME in catalog["variants"]:
        raise ValueError(f"Base already defines {NAME}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="duo-folded-", dir=output.parent) as temporary:
        stage = Path(temporary) / "pack"
        shutil.copytree(base, stage, ignore=shutil.ignore_patterns(".*"))
        shared = None
        reflections = {}
        for color in COLORS:
            psd = source / f"iPhone Duo - {color} - Inner Partially Open Landscape.psd"
            regions = warp_regions(psd)
            reflections[color] = reflection_profile(psd)
            layers = read_layers(psd)
            frame = Image.new("RGBA", CANVAS)
            frame.alpha_composite(*layers["Hardware"])
            frame.save(stage / f"{NAME} {color}.png")
            mask = Image.new("L", CANVAS)
            content, offset = layers["Screen Content"]
            mask.paste(content.getchannel("A"), offset)
            overlay = Image.new("RGBA", CANVAS)
            for layer in ("Light", "Dark", "Black"):
                overlay.alpha_composite(*layers[layer])
            signature = (regions, mask.tobytes(), overlay.tobytes())
            if shared is None:
                shared = signature
                mask.save(stage / f"{NAME}_mask.png")
                overlay.save(stage / f"{NAME}_overlay.png")
            elif signature != shared:
                raise ValueError("Landscape finishes disagree on the geometry, display mask, or camera")
        catalog["variants"][NAME] = {
            "name": NAME, "x": "0", "y": "0", "mask": "yes", "colors": "yes",
            "physicalHeight": 117.8,
            "warp": {"inputSizes": [[2853, 2007], [2670, 1878]], "regions": regions,
                     "reflections": reflections},
        }
        (stage / "NewFrames.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
        shutil.copyfile(source.parent / "Apple Design Resources License.rtf",
                        stage / "Apple Design Resources License.rtf")
        stage.rename(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Photoshop folder from the iPhone Duo download")
    parser.add_argument("--base-assets", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    try:
        if args.archive and args.archive.exists():
            raise ValueError(f"Archive already exists: {args.archive}")
        build_pack(args.source, args.base_assets, args.output)
        if args.archive:
            write_archive(args.output, args.archive)
    except (KeyError, ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
