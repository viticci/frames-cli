#!/usr/bin/env python3
"""Add Apple HomeView frames, built from Apple Store product images, to a Frames 4 pack.

Apple publishes no HomeView bezels, so this uses the transparent product
renders from the Apple Store. Download them once into an empty folder:

    for name in select-silver select-starlight select-rosepink select-spacegray \\
                wallmount-select-silver wallmount-select-spacegray; do
      curl -o "homeview-$name-202610.png" \\
        "https://store.storeimages.cdn-apple.com/1/as-images.apple.com/is/homeview-$name-202610?wid=4000&hei=4000&fmt=png-alpha"
    done

Each render shows a different picture on the screen. The builder finds the
display opening, removes the picture, and scales the render so the opening is
exactly 1088 x 1088, HomeView's native resolution. The destination must not
exist; the renders and the base pack are read-only. Requires Pillow.
"""

import argparse
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile

from PIL import Image, ImageChops, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_duo_assets import optimize_png, sha256, write_archive  # noqa: E402


SOURCES = {
    "specs": "https://www.apple.com/apple-homeview/specs/",
    "store": "https://www.apple.com/shop/buy-home/apple-homeview",
    "renders": "https://store.storeimages.cdn-apple.com/1/as-images.apple.com/is/homeview-select-silver-202610?wid=4000&hei=4000&fmt=png-alpha",
}
SCREEN = 1088
SOURCE_SIZE = (4000, 4000)
# QuickTime mirrors HomeView at 1080 x 1080; those captures scale up to the opening.
QUICKTIME = 1080
# Apple renders the bezel pure black. A pixel whose brightest channel stays
# below this in every finish is bezel; dark purple wallpaper is not.
BEZEL_LEVEL = 8
# The display body is 145.5 mm square (Apple's specs). physicalHeight is the
# visible body height in the front view: the wall-mounted model is the square,
# and the tabletop render is 1.1853 times taller than wide, or 172.5 mm, within
# Apple's 173.2 mm maximum height for the tilting stand.
VIEWS = (
    {"name": "HomeView", "source": "select",
     "colors": ("Silver", "Starlight", "Rose Pink", "Space Gray"),
     "canvas": (1260, 1494), "opening": (86, 86), "physicalHeight": 172.5},
    {"name": "HomeView Wall Mounted", "source": "wallmount-select",
     "colors": ("Silver", "Space Gray"),
     "canvas": (1260, 1260), "opening": (86, 86), "physicalHeight": 145.5, "manual": True},
)


def source_name(view, color):
    return "homeview-{}-{}-202610.png".format(view["source"], color.lower().replace(" ", ""))


def find_opening(renders):
    """Return the display opening as a binary mask over the source renders.

    Every finish shows a different picture, so a pixel that is dark in all of
    them is bezel. The opening is everything the bezel ring encloses, including
    any dark parts of the pictures that do not touch the ring.
    """
    alpha = renders[0].getchannel("A")
    # Finishes differ only in the antialiasing of their outline.
    if len({render.getchannel("A").getbbox() for render in renders}) != 1:
        raise ValueError("Finishes have different outlines")
    brightest = Image.new("L", alpha.size)
    for render in renders:
        for band in render.convert("RGB").split():
            brightest = ImageChops.lighter(brightest, band)
    opaque = alpha.point(lambda value: 255 if value == 255 else 0)
    dark = ImageChops.multiply(brightest.point(lambda value: 255 if value < BEZEL_LEVEL else 0), opaque)

    left, top, right, bottom = alpha.getbbox()
    # Seed the ring in the first wide black run across the middle of the
    # screen, past any stray black pixels in the aluminum edge.
    y = top + (right - left) // 2
    row = [dark.getpixel((x, y)) for x in range(left, right)]
    start = next(x for x in range(len(row) - 40) if all(row[x:x + 40]))
    ImageDraw.floodfill(dark, (left + start + 20, y), 128)
    ring = dark.point(lambda value: 255 if value == 128 else 0)
    center = ((left + right) // 2, top + (right - left) // 2)
    if ring.getpixel(center):
        raise ValueError("The bezel reaches the middle of the screen")
    ImageDraw.floodfill(ring, center, 64)
    opening = ring.point(lambda value: 255 if value == 64 else 0)
    box = opening.getbbox()
    width, height = box[2] - box[0], box[3] - box[1]
    if abs(width - height) > 2 or not 0.84 < width / (right - left) < 0.89:
        raise ValueError("Unexpected screen opening {} in body {}".format(box, (left, top, right, bottom)))
    return opening


def build_frames(renders, view):
    """Scale each finish so its opening is SCREEN pixels; return frames and the mask."""
    opening = find_opening(renders)
    left, top, right, bottom = opening.getbbox()
    scale_x, scale_y = (right - left) / SCREEN, (bottom - top) / SCREEN
    ox, oy = view["opening"]
    width, height = view["canvas"]
    box = (left - ox * scale_x, top - oy * scale_y, left + (width - ox) * scale_x, top + (height - oy) * scale_y)
    if box[0] < 0 or box[1] < 0 or box[2] > opening.width or box[3] > opening.height:
        raise ValueError("{} canvas reaches past the render: {}".format(view["name"], box))

    # Exact area coverage of the opening in each output pixel.
    coverage = opening.resize((width, height), Image.BOX, box=box)
    inside = coverage.point(lambda value: 255 if value else 0)
    screen = (ox, oy, ox + SCREEN, oy + SCREEN)
    if inside.getbbox() != screen:
        raise ValueError("{} opening landed at {}, not {}".format(view["name"], inside.getbbox(), screen))
    # The bezel stays opaque up to the opening's edge, where coverage fades it out.
    edge_alpha = coverage.point(lambda value: 255 - value)
    black = Image.new("RGB", (width, height))
    frames = []
    for render in renders:
        cut = render.copy()
        cut.paste((0, 0, 0, 0), mask=opening)
        # Resample premultiplied so transparent pixels add no color.
        scaled = cut.convert("RGBa").resize((width, height), Image.LANCZOS, box=box).convert("RGBA")
        bbox = scaled.getchannel("A").getbbox()
        if bbox is None or bbox[0] > 1 or bbox[1] > 1 or bbox[2] < width - 1 or bbox[3] < height - 1:
            raise ValueError("{} body does not fill its canvas: {}".format(view["name"], bbox))
        rgb = Image.composite(black, scaled.convert("RGB"), inside)
        rgb.putalpha(Image.composite(edge_alpha, scaled.getchannel("A"), inside))
        frames.append(rgb)
    # A binary mask under the bezel keeps the frame's own antialiased edge.
    return frames, inside.crop(screen)


def catalog_entries(catalog):
    """Detect 1088 x 1088 and QuickTime's 1080 x 1080; keep the wall mount manual."""
    for view in VIEWS:
        ox, oy = view["opening"]
        entry = {"name": view["name"], "x": str(ox), "y": str(oy),
                 "mask": "yes", "colors": "yes", "physicalHeight": view["physicalHeight"]}
        if view.get("manual"):
            if view["name"] in catalog["variants"]:
                raise ValueError("Base already defines {}".format(view["name"]))
            catalog["variants"][view["name"]] = entry
            continue
        scaled = dict(entry, resizeWidth=str(SCREEN), resizeHeight=str(SCREEN))
        for size, item in ((SCREEN, entry), (QUICKTIME, scaled)):
            if str(size) in catalog:
                raise ValueError("Base already defines width {}".format(size))
            catalog[str(size)] = {"overlap": {str(size): item}}
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
    catalog_entries(catalog)

    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"sources": SOURCES, "frames": [], "masks": []}
    with tempfile.TemporaryDirectory(prefix="homeview-build-", dir=str(destination.parent)) as temporary:
        stage = Path(temporary) / "pack"
        stage.mkdir()
        for path in sorted(base.iterdir()):
            if path.is_file() and not path.name.startswith(".") and path.name not in ("NewFrames.json", "version.txt"):
                shutil.copyfile(path, stage / path.name)
        for view in VIEWS:
            sources, renders = [], []
            for color in view["colors"]:
                data = (source / source_name(view, color)).read_bytes()
                with Image.open(io.BytesIO(data)) as opened:
                    rgba = opened.convert("RGBA")
                if rgba.size != SOURCE_SIZE:
                    raise ValueError("Download {} at 4000 x 4000, not {}".format(source_name(view, color), rgba.size))
                sources.append(data)
                renders.append(rgba)
            frames, mask = build_frames(renders, view)
            for color, data, frame in zip(view["colors"], sources, frames):
                filename = "{} {}.png".format(view["name"], color)
                output = io.BytesIO()
                frame.save(output, "PNG", optimize=True)
                optimized = optimize_png(output.getvalue(), frame)
                (stage / filename).write_bytes(optimized)
                manifest["frames"].append({"file": filename, "source_sha256": sha256(data), "bytes": len(optimized)})
            mask_name = view["name"] + "_mask.png"
            mask.save(stage / mask_name, "PNG", optimize=True)
            manifest["masks"].append({"file": mask_name, "size": mask.size})
            print("Prepared {}".format(view["name"]), flush=True)
        (stage / "NewFrames.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
        # No trailing newline: the Apple Frames shortcut compares this text exactly.
        (stage / "version.txt").write_text(version, encoding="utf-8")
        stage.rename(destination)
    if archive:
        write_archive(destination, archive)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, required=True, help="Folder with the six Apple Store renders")
    parser.add_argument("--base-assets", type=Path, required=True, help="Existing Apple Frames 4 assets")
    parser.add_argument("--output", type=Path, required=True, help="New assets directory")
    parser.add_argument("--archive", type=Path, help="New ZIP file for distribution")
    args = parser.parse_args()
    try:
        manifest = build_pack(args.source, args.base_assets, args.output, args.archive)
    except (ValueError, OSError, StopIteration) as error:
        parser.exit(1, "Error: {}\n".format(error))
    for item in manifest["frames"] + manifest["masks"]:
        print("  {}".format(item["file"]))
    print("Built {}".format(args.output))


if __name__ == "__main__":
    main()
