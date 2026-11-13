#!/usr/bin/env python3
"""Add the partially open Duo poses to a Frames 4 asset pack.

Requires Pillow. Apple's Photoshop templates are read directly, so the display
mask, the camera layers, and their Blend If ranges come from the files rather
than from a rendered preview. Each pose is scaled down until a native
screenshot is never magnified anywhere on the display.
"""

import argparse
import json
import math
from pathlib import Path
import re
import shutil
from statistics import median
import struct
import tempfile

from PIL import Image

from build_duo_assets import COLORS, sha256, write_archive


# Orientation, then the native capture size followed by the announced size.
VIEWS = (
    ("Landscape", [[2853, 2007], [2670, 1878]]),
    ("Portrait", [[2007, 2853], [1878, 2670]]),
)
# The "Camera" group, bottom layer first. Photoshop shows each one over a
# different brightness range of the pixels below it (Blend If, Underlying Layer).
CAMERA_LAYERS = ("black", "dark", "light")


def read_channel(source, size):
    """Decode one raw or PackBits channel at the current offset."""
    width, height = size
    compression = struct.unpack(">H", source.read(2))[0]
    if compression == 0:
        return Image.frombytes("L", size, source.read(width * height))
    if compression != 1:
        raise ValueError(f"Unsupported PSD channel compression {compression}")
    rows = struct.unpack(f">{height}H", source.read(2 * height))
    return Image.frombytes("L", size, source.read(sum(rows)), "packbits", "L")


def read_psd(path):
    """Read a template's canvas size, layers, and merged preview.

    Each layer has its pixels and canvas offset, its user mask on the full
    canvas, its Blend If range for the underlying layers (black start, black
    end, white start, white end), and its Smart Object descriptor.
    """
    with path.open("rb") as source:
        signature, version = struct.unpack(">4sH6x", source.read(12))
        channels, height, width, depth, mode = struct.unpack(">HIIHH", source.read(14))
        if (signature, version, depth, mode) != (b"8BPS", 1, 8, 3):
            raise ValueError(f"Expected an 8-bit RGB PSD: {path.name}")
        for _ in range(2):  # color mode data, image resources
            source.seek(struct.unpack(">I", source.read(4))[0], 1)
        preview_offset = struct.unpack(">I", source.read(4))[0] + source.tell()
        source.read(4)
        records = []
        for _ in range(abs(struct.unpack(">h", source.read(2))[0])):
            top, left, bottom, right = struct.unpack(">4i", source.read(16))
            sizes = [struct.unpack(">hI", source.read(6))
                     for _ in range(struct.unpack(">H", source.read(2))[0])]
            source.read(12)
            end = struct.unpack(">I", source.read(4))[0] + source.tell()
            mask = source.read(struct.unpack(">I", source.read(4))[0])
            ranges = source.read(struct.unpack(">I", source.read(4))[0])
            name_length = source.read(1)[0]
            name = source.read(name_length).decode("macroman").strip().lower()
            source.seek(-(name_length + 1) % 4, 1)
            descriptor = None
            while source.tell() < end:
                marker, key, length = struct.unpack(">4s4sI", source.read(12))
                if marker != b"8BIM":
                    raise ValueError(f"Unexpected layer data in {path.name}")
                data = source.read(length + length % 2)
                if key == b"SoLd":
                    descriptor = data
            records.append((name, (left, top, right, bottom), sizes, mask, descriptor,
                            tuple(ranges[4:8])))
        layers = {}
        for name, box, sizes, mask, descriptor, blend_if in records:
            size = (box[2] - box[0], box[3] - box[1])
            planes = {}
            for channel, length in sizes:
                end = source.tell() + length
                if channel == -2:
                    top, left, bottom, right = struct.unpack(">4i", mask[:16])
                    planes[channel] = Image.new("L", (width, height), mask[16])
                    planes[channel].paste(read_channel(source, (right - left, bottom - top)), (left, top))
                elif size[0] and size[1]:
                    planes[channel] = read_channel(source, size)
                source.seek(end)
            image = Image.merge("RGBA", [planes[index] for index in (0, 1, 2, -1)]) if 0 in planes else None
            layers[name] = {"image": image, "offset": box[:2], "mask": planes.get(-2),
                            "blendIf": blend_if, "descriptor": descriptor}
        source.seek(preview_offset)
        if struct.unpack(">H", source.read(2))[0] != 1:
            raise ValueError(f"Expected a PackBits preview in {path.name}")
        rows = struct.unpack(f">{height * channels}H", source.read(2 * height * channels))
        preview = Image.merge("RGB", [
            Image.frombytes("L", (width, height), source.read(sum(rows[index * height:(index + 1) * height])),
                            "packbits", "L")
            for index in range(3)
        ])
    return (width, height), layers, preview


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


def warp_quads(descriptor):
    """Extract the three Perspective Warp quads from the Smart Object descriptor.

    Each quad pairs its canvas polygon with the matching screenshot corners,
    normalized to the range 0 to 1.
    """
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
    return [([after[i] for i in indices], [normalized[i] for i in indices])
            for indices in (struct.unpack(">4I", b"".join(quad)) for quad in quads)]


def region_scales(region, size, steps=32):
    """Sample a region's local scale, in canvas pixels per screenshot pixel.

    The scale changes across a perspective region, so this walks its corners
    and edges. Returns the largest and smallest scale in any direction, then
    the largest along the screenshot's x axis and along its y axis.
    """
    a, b, c, d, e, f, g, h = region["inverse"]
    width, height = size
    polygon = region["polygon"]
    samples = []
    for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1]):
        for step in range(steps):
            x, y = x0 + (x1 - x0) * step / steps, y0 + (y1 - y0) * step / steps
            w = g * x + h * y + 1
            u, v = (a * x + b * y + c) / w, (d * x + e * y + f) / w
            # Jacobian of the canvas-to-screenshot map, then its inverse.
            ux, uy = (a - u * g) / w * width, (b - u * h) / w * width
            vx, vy = (d - v * g) / w * height, (e - v * h) / w * height
            determinant = ux * vy - uy * vx
            xu, xv, yu, yv = vy / determinant, -uy / determinant, -vx / determinant, ux / determinant
            half = (xu * xu + xv * xv + yu * yu + yv * yv) / 2
            spread = math.sqrt(max(0, half * half - (xu * yv - xv * yu) ** 2))
            samples.append((math.sqrt(half + spread), math.sqrt(max(0, half - spread)),
                            math.hypot(xu, yu), math.hypot(xv, yv)))
    return (max(sample[0] for sample in samples), min(sample[1] for sample in samples),
            max(sample[2] for sample in samples), max(sample[3] for sample in samples))


def scaled_regions(quads, canvas, size):
    """Place Apple's quads on a canvas scaled to size and solve each inverse transform."""
    regions = []
    for polygon, source in quads:
        polygon = [(x * size[0] / canvas[0], y * size[1] / canvas[1]) for x, y in polygon]
        regions.append({"polygon": polygon, "inverse": inverse_perspective(polygon, source, size)})
    return regions


def fit_regions(quads, canvas, native):
    """Shrink Apple's canvas until a native screenshot is never magnified.

    Returns the new canvas size and its regions. Each region records its
    extent: the most canvas pixels the screenshot's full width and height
    span there, which is all the detail the region can show.
    """
    peak = max(region_scales(region, native)[0] for region in scaled_regions(quads, canvas, canvas))
    size = tuple(math.floor(side / peak) for side in canvas)
    regions = scaled_regions(quads, canvas, size)
    for region in regions:
        scales = region_scales(region, native)
        region["extent"] = [round(scales[2] * native[0], 2), round(scales[3] * native[1], 2)]
    check_not_magnified(regions, native)
    return size, regions


def check_not_magnified(regions, native):
    """Fail the build if any region shows a native screenshot above its own resolution."""
    peak = max(region_scales(region, native)[0] for region in regions)
    if peak > 1:
        raise ValueError("A {}x{} screenshot would be magnified {:.4f}x".format(*native, peak))


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


def camera_strip(layers, canvas, size):
    """Scale the camera layers and lay them side by side, bottom layer first.

    Returns the strip and the catalog entry that places it and gives each
    layer's Blend If range.
    """
    scaled = []
    for name in CAMERA_LAYERS:
        full = Image.new("RGBA", canvas)
        full.alpha_composite(layers[name]["image"], layers[name]["offset"])
        scaled.append(full.resize(size, Image.LANCZOS))
    boxes = [image.getchannel("A").getbbox() for image in scaled]
    box = (min(b[0] for b in boxes), min(b[1] for b in boxes),
           max(b[2] for b in boxes), max(b[3] for b in boxes))
    width = box[2] - box[0]
    strip = Image.new("RGBA", (width * len(scaled), box[3] - box[1]))
    for index, image in enumerate(scaled):
        strip.paste(image.crop(box), (index * width, 0))
    return strip, {"x": box[0], "y": box[1],
                   "blendIf": [list(layers[name]["blendIf"]) for name in CAMERA_LAYERS]}


def build_view(source, stage, orientation, input_sizes):
    name = f"iPhone Duo Inner Partially Open {orientation}"
    vertical = orientation == "Portrait"
    native = tuple(input_sizes[0])
    shared = None
    reflections = {}
    for color in COLORS:
        psd = source / f"iPhone Duo - {color} - Inner Partially Open {orientation}.psd"
        canvas, layers, preview = read_psd(psd)
        content = layers["screen content"]
        size, regions = fit_regions(warp_quads(content["descriptor"]), canvas, native)
        reflections[color] = reflection_profile(preview.convert("L"), vertical)
        frame = Image.new("RGBA", canvas)
        frame.alpha_composite(layers["hardware"]["image"], layers["hardware"]["offset"])
        frame.resize(size, Image.LANCZOS).save(stage / f"{name} {color}.png")
        # The layer mask is the display opening. Averaging keeps its interior solid.
        mask = content["mask"].resize(size, Image.BOX)
        strip, camera = camera_strip(layers, canvas, size)
        signature = (size, regions, camera, sha256(mask.tobytes()), sha256(strip.tobytes()))
        if shared is None:
            shared = signature
            mask.save(stage / f"{name}_mask.png")
            strip.save(stage / f"{name}_camera.png")
        elif signature != shared:
            raise ValueError(f"{orientation} finishes disagree on the geometry, display mask, or camera")
    print("{}: {}x{} -> {}x{} ({:.4f})".format(name, *canvas, *size, size[0] / canvas[0]))
    for index, region in enumerate(regions):
        print("  region {}: scale {:.4f} to {:.4f}".format(index, *region_scales(region, native)[1::-1]))
    entry = {
        "name": name, "x": "0", "y": "0", "mask": "yes", "colors": "yes",
        "warp": {"inputSizes": input_sizes, "regions": regions, "reflections": reflections,
                 "camera": camera},
    }
    if vertical:
        # The laptop template's screen layer blends normally; the book's screens.
        entry["warp"].update(blend="normal", reflectionAxis="y")
    else:
        entry["physicalHeight"] = 117.8
    return entry


def build_pack(source, base, output):
    if output.exists():
        raise ValueError(f"Destination must not exist: {output}")
    catalog = json.loads((base / "NewFrames.json").read_text(encoding="utf-8"))
    for orientation, _ in VIEWS:
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
    except (KeyError, ValueError, OSError, struct.error) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
