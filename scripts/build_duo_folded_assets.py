#!/usr/bin/env python3
"""Add the partially open Duo poses to a Frames 4 asset pack."""

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

from PIL import Image, ImageChops

from build_duo_assets import COLORS, sha256, write_archive


VIEWS = (
    ("Landscape", (5600, 4500), [[2853, 2007], [2670, 1878]]),
    ("Portrait", (6600, 5000), [[2007, 2853], [1878, 2670]]),
)


def descriptor_points(descriptor, key):
    """Read the pixel-coordinate points in a Perspective Warp vertex list."""
    start = descriptor.index(key + b"VlLs") + len(key) + 4
    count = struct.unpack_from(">I", descriptor, start)[0]
    # Each entry is a descriptor for a point with two unit doubles.
    pattern = rb"HrznUntF#Pxl(.{8})\x00{4}VrtcUntF#Pxl(.{8})"
    # The finishes can differ in the last bits of the same vertex coordinate.
    return [tuple(round(value, 9) for value in struct.unpack(">2d", x + y))
            for x, y in re.findall(pattern, descriptor[start:], re.DOTALL)[:count]]


def inverse_perspective(destination, source, canvas):
    """Solve the eight coefficients Pillow uses to sample a projective transform."""
    rows = []
    for (x, y), (u, v) in zip(destination, source):
        x, y = x / canvas[0], y / canvas[1]
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
    width, height = canvas
    return [a / width, b / height, c, d / width, e / height, f, g / width, h / height]


def warp_regions(path, canvas):
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
    # The laptop template turns its landscape Smart Object by 90 degrees.
    # Its placed rectangle is already upright in portrait screenshot coordinates.
    xs, ys = placement[::2], placement[1::2]
    left, right, top, bottom = min(xs), max(xs), min(ys), max(ys)
    if any(min(abs(x - left), abs(x - right)) > 0.01 for x in xs) or any(
        min(abs(y - top), abs(y - bottom)) > 0.01 for y in ys
    ):
        raise ValueError("Expected an axis-aligned placed Smart Object")
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
            polygon, [normalized[i] for i in indices], canvas,
        )})
    return regions


def read_layers(psd, canvas):
    """Read cached PSD layer pixels with ImageMagick, retaining canvas offsets."""
    command = ["magick", "identify", "-format", "%s|%l|%X|%Y|%w|%h\n", str(psd)]
    layers = [line.split("|") for line in subprocess.check_output(command, text=True).splitlines()]
    names = [layer[1].strip().lower() for layer in layers]
    if names != ["", "hardware", "screen content", "black", "dark", "light"]:
        raise ValueError(f"Unexpected layer layout in {psd.name}")
    if tuple(map(int, layers[0][4:])) != canvas:
        raise ValueError(f"Unexpected canvas dimensions in {psd.name}")
    pixels = {}
    for index, name, x, y, _, _ in layers[1:]:
        png = subprocess.check_output(["magick", f"{psd}[{index}]", "+repage", "PNG32:-"])
        with Image.open(io.BytesIO(png)) as image:
            pixels[name.strip().lower()] = (image.convert("RGBA"), (int(x), int(y)))
    return pixels


def read_preview(psd, full_size):
    command = ["magick", f"{psd}[0]"]
    if not full_size:
        command.extend(["-resize", "1400x1125!"])
    png = subprocess.check_output([*command, "PNG24:-"])
    with Image.open(io.BytesIO(png)) as preview:
        return preview.convert("L")


def reflection_profile(preview, vertical):
    """Sample the neutral reflection in Apple's merged preview, away from text and edges."""
    gray = preview.resize((1400, 1125), Image.BOX)
    if vertical:
        # Take side samples so the placeholder label and camera stay out of the profile.
        samples = gray.resize((1400, 375), Image.BOX)
        rows = [round(median(samples.getpixel((x, y)) for x in (240, 300, 1100, 1160)))
                for y in range(40, 335)]
        levels = [rows[0]] * 40 + rows + [rows[-1]] * 40
        return [max(0, level - rows[0]) for level in levels]
    samples = gray.resize((100, 1125), Image.BOX)
    columns = [round(median(samples.getpixel((x, y)) for y in (200, 275, 850, 930)))
               for x in range(25, 75)]
    # Continue the outer values to the sides. The display mask supplies the perimeter.
    levels = [columns[0]] * 25 + columns + [columns[-1]] * 25
    return [max(0, level - columns[0]) for level in levels]


def laptop_display_mask(preview, frame, overlay):
    """Recover the opening from Apple's composite because the cached screen layer is cropped."""
    # The neutral placeholder raises the hardware's display gray from 14 to 30.
    difference = ImageChops.subtract(preview, frame.convert("L"))
    mask = difference.point(lambda value: min(255, round(value * 255 / 16)))
    mask = ImageChops.lighter(mask, overlay.getchannel("A"))
    return ImageChops.multiply(mask, frame.getchannel("A"))


def build_view(source, stage, orientation, canvas, input_sizes):
    name = f"iPhone Duo Inner Partially Open {orientation}"
    vertical = orientation == "Portrait"
    shared = None
    reflections = {}
    for color in COLORS:
        psd = source / f"iPhone Duo - {color} - Inner Partially Open {orientation}.psd"
        regions = warp_regions(psd, canvas)
        preview = read_preview(psd, full_size=vertical)
        reflections[color] = reflection_profile(preview, vertical)
        layers = read_layers(psd, canvas)
        frame = Image.new("RGBA", canvas)
        frame.alpha_composite(*layers["hardware"])
        frame.save(stage / f"{name} {color}.png")
        overlay = Image.new("RGBA", canvas)
        for layer in ("light", "dark", "black"):
            overlay.alpha_composite(*layers[layer])
        if vertical:
            mask = laptop_display_mask(preview, frame, overlay)
            mask.save(stage / f"{name} {color}_mask.png")
            mask_signature = None
        else:
            mask = Image.new("L", canvas)
            content, offset = layers["screen content"]
            mask.paste(content.getchannel("A"), offset)
            mask_signature = sha256(mask.tobytes())
        signature = (regions, mask_signature, sha256(overlay.tobytes()))
        if shared is None:
            shared = signature
            if not vertical:
                mask.save(stage / f"{name}_mask.png")
            overlay.save(stage / f"{name}_overlay.png")
        elif signature != shared:
            raise ValueError(f"{orientation} finishes disagree on the geometry, display mask, or camera")
    entry = {
        "name": name, "x": "0", "y": "0", "mask": "yes", "colors": "yes",
        "warp": {"inputSizes": input_sizes, "regions": regions, "reflections": reflections},
    }
    if vertical:
        entry["warp"].update(blend="normal", reflectionAxis="y", maskByColor=True)
    else:
        entry["physicalHeight"] = 117.8
    return entry


def build_pack(source, base, output):
    if output.exists():
        raise ValueError(f"Destination must not exist: {output}")
    catalog = json.loads((base / "NewFrames.json").read_text(encoding="utf-8"))
    for orientation, _, _ in VIEWS:
        name = f"iPhone Duo Inner Partially Open {orientation}"
        if name in catalog["variants"]:
            raise ValueError(f"Base already defines {name}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="duo-folded-", dir=output.parent) as temporary:
        stage = Path(temporary) / "pack"
        shutil.copytree(base, stage, ignore=shutil.ignore_patterns(".*"))
        for view in VIEWS:
            entry = build_view(source, stage, *view)
            catalog["variants"][entry["name"]] = entry
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
