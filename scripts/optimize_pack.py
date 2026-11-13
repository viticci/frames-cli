#!/usr/bin/env python3
"""Shrink every PNG in a Frames pack without visible changes.

Requires Pillow, oxipng, and pngquant. Each frame is quantized with pngquant
and kept only if it passes a strict visual check; otherwise the frame is
recompressed losslessly with oxipng. Masks and camera layers are data, not
pictures, and are always lossless. The source
pack is read-only and the destination must not exist.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import math
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image, ImageChops, ImageStat

# A quantized frame must stay this close to the original, measured after
# compositing on both white and black so transparent edges count too.
MIN_PSNR = 50.0
# Worst mean error (0-255) of any 32x32 block. Catches local color shifts,
# such as dark camera lenses, that a whole-image average hides.
MAX_BLOCK_ERROR = 2


def visual_error(original, candidate):
    """Return (lowest PSNR, worst 32px block error) across white and black."""
    a = Image.open(original).convert("RGBA")
    b = Image.open(candidate).convert("RGBA")
    if a.size != b.size:
        return 0.0, 255
    psnrs, worst = [], 0
    for background in ((255, 255, 255, 255), (0, 0, 0, 255)):
        base = Image.new("RGBA", a.size, background)
        diff = ImageChops.difference(Image.alpha_composite(base, a).convert("RGB"),
                                     Image.alpha_composite(base, b).convert("RGB"))
        mse = sum(value * value for value in ImageStat.Stat(diff).rms) / 3
        psnrs.append(99.0 if mse == 0 else 10 * math.log10(255 ** 2 / mse))
        blocks = diff.convert("L").resize((max(1, a.width // 32), max(1, a.height // 32)), Image.BOX)
        worst = max(worst, blocks.getextrema()[1])
    return min(psnrs), worst


def oxipng(path):
    subprocess.run(["oxipng", "-q", "-o", "4", "--strip", "safe", str(path)], check=True)


def optimize(job):
    """Write the smallest acceptable version of one PNG; return a report row."""
    source, destination = job
    with tempfile.TemporaryDirectory() as temporary:
        lossless = Path(temporary) / "lossless.png"
        shutil.copyfile(source, lossless)
        oxipng(lossless)
        if Image.open(source).convert("RGBA").tobytes() != Image.open(lossless).convert("RGBA").tobytes():
            raise ValueError("oxipng changed pixels in {}".format(source.name))
        best, kind, error = lossless, "lossless", None
        if not source.stem.endswith(("_mask", "_camera")):
            quantized = Path(temporary) / "quantized.png"
            result = subprocess.run(["pngquant", "--speed", "1", "--strip", "--force",
                                     "--output", str(quantized), str(source)], capture_output=True)
            if result.returncode == 0:
                oxipng(quantized)
                error = visual_error(source, quantized)
                if (error[0] >= MIN_PSNR and error[1] <= MAX_BLOCK_ERROR
                        and quantized.stat().st_size < lossless.stat().st_size):
                    best, kind = quantized, "quantized"
        shutil.copyfile(best, destination)
    return source.name, kind, source.stat().st_size, destination.stat().st_size, error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Existing Frames pack folder")
    parser.add_argument("destination", type=Path, help="New folder for the optimized pack")
    args = parser.parse_args()
    if args.destination.exists():
        parser.exit(1, "Error: destination must not exist: {}\n".format(args.destination))
    args.destination.mkdir(parents=True)
    jobs = []
    for path in sorted(args.source.iterdir()):
        if path.name.startswith("."):
            continue
        if path.suffix == ".png":
            jobs.append((path, args.destination / path.name))
        else:
            shutil.copyfile(path, args.destination / path.name)
    rows = list(ProcessPoolExecutor().map(optimize, jobs))
    before = sum(row[2] for row in rows)
    after = sum(row[3] for row in rows)
    quantized = [row for row in rows if row[1] == "quantized"]
    print("{} PNGs: {:,} -> {:,} bytes ({:.1%} smaller); {} quantized, {} lossless".format(
        len(rows), before, after, 1 - after / before, len(quantized), len(rows) - len(quantized)))


if __name__ == "__main__":
    main()
