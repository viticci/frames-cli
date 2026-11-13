import contextlib
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from argparse import Namespace
from unittest import mock

from PIL import Image, ImageDraw, PngImagePlugin


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


frames = load_module("frames_duo", ROOT / "frames")
builder = load_module("build_duo", ROOT / "scripts/build_duo_assets.py")
sys.path.insert(0, str(ROOT / "scripts"))  # the folded builder imports its sibling
folded = load_module("build_duo_folded", ROOT / "scripts/build_duo_folded_assets.py")

BOOK = "iPhone Duo Inner Partially Open Landscape"
LAPTOP = "iPhone Duo Inner Partially Open Portrait"
# Maps each pixel of a 24x12 canvas to the same place in the screenshot.
IDENTITY_24x12 = [1 / 24, 0, 0, 0, 1 / 12, 0, 0, 0]


def warped_pack(root, name, frame, mask, warp, camera=None):
    """Write a one-frame pack for a warped pose and return its catalog."""
    frame.save(root / f"{name} Star White.png")
    mask.save(root / f"{name}_mask.png")
    if camera:
        camera.save(root / f"{name}_camera.png")
    return {"variants": {name: {"name": name, "x": "0", "y": "0", "mask": "yes", "colors": "yes", "warp": warp}}}

POSES = {"iPhone Duo Book Pose": "iPhone Duo Inner Partially Open Landscape",
         "iPhone Duo Laptop Pose": "iPhone Duo Inner Partially Open Portrait"}


class DuoTests(unittest.TestCase):
    def test_warped_screenshot_stays_inside_its_region_the_mask_and_the_frame(self):
        size = (24, 12)
        # The transform covers the whole canvas; only the slanted polygon keeps it to the left.
        regions = [{"polygon": [(0, 0), (12, 0), (6, 12), (0, 12)], "inverse": IDENTITY_24x12}]
        warp = {"inputSizes": [[24, 12]], "regions": regions, "blend": "normal",
                "camera": {"x": 2, "y": 8, "blendIf": [[0, 0, 255, 255]]}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frame = Image.new("RGBA", size, (80, 80, 80, 255))
            frame.paste((0, 0, 0, 0), (23, 0, 24, 12))
            mask = Image.new("L", size, 255)
            mask.putpixel((1, 4), 0)
            catalog = warped_pack(root, BOOK, frame, mask, warp, camera=Image.new("RGBA", (2, 2), "blue"))
            Image.new("RGB", size, "red").save(root / "input.png")
            Image.new("RGB", (12, 24), "red").save(root / "sideways.png")

            result, info = frames.frame_screenshot(
                root / "input.png", root, catalog, force_device="iPhone Duo Book Pose", color_arg="Star White",
            )
            self.assertEqual(info["device"], BOOK)
            self.assertTrue(info["masked"])
            self.assertEqual(result.getpixel((5, 4)), (255, 0, 0, 255))
            self.assertEqual(result.getpixel((10, 10)), (80, 80, 80, 255))  # outside the polygon
            self.assertEqual(result.getpixel((18, 4)), (80, 80, 80, 255))
            self.assertEqual(result.getpixel((1, 4)), (80, 80, 80, 255))   # outside the mask
            self.assertEqual(result.getpixel((23, 4))[3], 0)               # outside the hardware
            self.assertEqual(result.getpixel((2, 8)), (0, 0, 255, 255))    # the camera, on top
            with self.assertRaisesRegex(ValueError, r"requires an iPhone Duo inner screenshot \(24x12\)"):
                frames.frame_screenshot(root / "sideways.png", root, catalog, force_device=BOOK, color_arg="Star White")
            metadata = frames.resolve_frame_metadata(
                *size, root, catalog, color_arg="Star White", force_device="iPhone Duo Book Pose",
            )
            self.assertEqual((metadata["device"], metadata["warp_size"]), (BOOK, size))
            self.assertNotIn("iPhone Duo Book Pose", frames.build_device_name_index({"variants": {}}))
            # A hand-edited catalog reports an error the CLI can print, not a traceback.
            del warp["inputSizes"]
            with self.assertRaisesRegex(ValueError, "incomplete warp entry"):
                frames.frame_screenshot(root / "input.png", root, catalog, force_device=BOOK, color_arg="Star White")

    def test_book_pose_screens_the_screenshot_and_adds_the_reflection_across(self):
        size = (24, 12)
        warp = {"regions": [{"polygon": [(0, 0), (24, 0), (24, 12), (0, 12)], "inverse": IDENTITY_24x12}],
                "reflections": {"Star White": [0, 12]}}
        result = frames.composite_warped(
            Image.new("RGBA", size, (100, 100, 100, 255)), Image.new("RGBA", size, (80, 80, 80, 255)),
            Image.new("RGBA", size, "white"), None, warp, "Star White",
        )
        # Screen: 255 - (255 - 80) * (255 - 100) / 255. Normal blending would give 100.
        self.assertEqual(result.getpixel((3, 6)), (149, 149, 149, 255))
        self.assertEqual(result.getpixel((20, 6)), (161, 161, 161, 255))
        # A frame cropped to the right half of the canvas covers only the profile's second entry.
        warp["reflectionSpan"] = [1, 2]
        result = frames.composite_warped(
            Image.new("RGBA", size, (100, 100, 100, 255)), Image.new("RGBA", size, (80, 80, 80, 255)),
            Image.new("RGBA", size, "white"), None, warp, "Star White",
        )
        self.assertEqual(result.getpixel((0, 6)), (155, 155, 155, 255))
        self.assertEqual(result.getpixel((20, 6)), (161, 161, 161, 255))

    def test_laptop_pose_uses_normal_blending_and_vertical_reflection(self):
        size = (12, 24)
        warp = {
            "regions": [{"polygon": [(0, 0), (12, 0), (12, 24), (0, 24)],
                         "inverse": [1 / 12, 0, 0, 0, 1 / 24, 0, 0, 0]}],
            "blend": "normal", "reflectionAxis": "y", "reflections": {"Star White": [0, 12]},
        }
        catalog = {"variants": {LAPTOP: {"name": LAPTOP, "warp": warp}}}
        entry, _, _, _ = frames.resolve_device_entry(*size, catalog, force_device="iPhone Duo Laptop Pose")
        result = frames.composite_warped(
            Image.new("RGBA", size, (30, 30, 30, 255)), Image.new("RGBA", size, (80, 80, 80, 255)),
            Image.new("RGBA", size, "white"), None, entry["warp"], "Star White",
        )
        self.assertEqual(result.getpixel((5, 2)), (30, 30, 30, 255))
        self.assertEqual(result.getpixel((5, 21)), (42, 42, 42, 255))

    def test_translucent_screenshot_is_even_across_the_hinge(self):
        size = (24, 12)
        # Two regions meet on a slanted line, and both polygons fill the pixels along it.
        warp = {"blend": "normal", "regions": [
            {"polygon": [(0, 0), (10, 0), (14, 12), (0, 12)], "inverse": IDENTITY_24x12},
            {"polygon": [(10, 0), (24, 0), (24, 12), (14, 12)], "inverse": IDENTITY_24x12},
        ]}
        frame, mask = Image.new("RGBA", size, "black"), Image.new("RGBA", size, "white")
        for alpha in (128, 255):
            result = frames.composite_warped(Image.new("RGBA", size, (255, 255, 255, alpha)),
                                             frame, mask, None, warp, "Star White")
            # No doubled hinge, and no gap.
            self.assertEqual(result.getchannel("R").getextrema(), (alpha, alpha))

    def test_projection_interpolates_and_filters(self):
        frame, mask = Image.new("RGBA", (24, 4), "black"), Image.new("RGBA", (24, 4), "white")
        warp = {"blend": "normal", "regions": [{"polygon": [(0, 0), (24, 0), (24, 4), (0, 4)],
                                                "inverse": [1 / 24, 0, 0, 0, 1 / 4, 0, 0, 0]}]}
        # Enlarged twelve times, two pixels blend into each other instead of meeting at a hard step.
        pair = Image.new("RGBA", (2, 1), "black")
        pair.putpixel((1, 0), (255, 255, 255, 255))
        result = frames.composite_warped(pair, frame, mask, None, warp, "Star White")
        self.assertEqual(result.getpixel((3, 2))[0], 0)
        self.assertTrue(20 < result.getpixel((8, 2))[0] < 70)
        # Squeezed to an eighth, one dark row in four averages to light gray. Sampling
        # single rows instead would return all white or all black, the source of moire.
        lines = Image.new("RGBA", (24, 32), "white")
        for y in range(0, 32, 4):
            lines.paste((0, 0, 0, 255), (0, y, 24, y + 1))
        warp["regions"][0]["extent"] = [24, 4]
        result = frames.composite_warped(lines, frame, mask, None, warp, "Star White")
        for x, y in ((2, 0), (12, 1), (20, 2), (7, 3)):
            self.assertAlmostEqual(result.getpixel((x, y))[0], 191, delta=12)

    def test_camera_layers_follow_the_brightness_below(self):
        # Three 2x1 layers in one strip, bottom first, with Apple's ranges.
        strip = Image.new("RGBA", (6, 1))
        colors = ((5, 5, 5, 255), (50, 40, 40, 255), (200, 220, 240, 255))
        for index, layer in enumerate(colors):
            strip.paste(layer, (index * 2, 0, index * 2 + 2, 1))
        camera = {"x": 1, "y": 1, "blendIf": [[0, 0, 10, 30], [10, 30, 60, 90], [60, 90, 255, 255]]}
        for below, expected in ((0, colors[0]), (45, colors[1]), (255, colors[2])):
            image = Image.new("RGBA", (4, 3), (below, below, below, 255))
            frames.composite_camera(image, strip, camera)
            self.assertEqual(image.getpixel((1, 1)), expected)
            self.assertEqual(image.getpixel((2, 1)), expected)
            self.assertEqual(image.getpixel((3, 1)), (below, below, below, 255))
        # Halfway through a range's fade the layer is half visible.
        image = Image.new("RGBA", (4, 3), (20, 20, 20, 255))
        frames.composite_camera(image, strip.crop((0, 0, 2, 1)), dict(camera, blendIf=[[0, 0, 10, 30]]))
        self.assertIn(image.getpixel((1, 1))[0], (12, 13))

    def test_list_shows_installed_duo_views_and_manual_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = root / "NewFrames.json"
            catalog_path.write_text(json.dumps(builder.catalog_entries()), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                frames.cmd_list(Namespace(assets=str(root)))
            listing = output.getvalue()
            for name in (view["name"] for view in builder.VIEWS):
                self.assertIn(name, listing)
            self.assertIn("Manual frames", listing)
            self.assertIn("select with --device", listing)
            catalog_path.write_text('{"variants": {}}', encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                frames.cmd_list(Namespace(assets=str(root)))
            self.assertNotIn("iPhone Duo", output.getvalue())

    def test_native_resolutions_require_both_dimensions(self):
        catalog = builder.catalog_entries()
        expected = {
            (1398, 2034): "iPhone Duo Outer Portrait",
            (2034, 1398): "iPhone Duo Outer Landscape",
            (2007, 2853): "iPhone Duo Inner Portrait",
            (2853, 2007): "iPhone Duo Inner Landscape",
            (1878, 2670): "iPhone Duo Inner Portrait",
            (2670, 1878): "iPhone Duo Inner Landscape",
        }
        for (width, height), name in expected.items():
            with self.subTest(name=name, size=(width, height)):
                _, detected = frames.detect_device_size(width, height, catalog)
                self.assertEqual(detected, name)
                self.assertEqual(frames.detect_device_size(width, height + 1, catalog), (None, None))
                self.assertEqual(frames.get_color(name, "star white", strict=True), "Star White")
                self.assertEqual(frames.get_color(name, None), "Night Sky")
        manual = frames.resolve_device_entry(1398, 2034, catalog, force_device="iPhone Duo Outer Open")
        self.assertEqual((manual[0]["x"], manual[0]["y"]), ("1570", "80"))
        self.assertEqual(frames.get_color(manual[1], "2", strict=True), "Star White")

    def test_explicit_inner_resize_matches_image_and_video_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            name = "iPhone Duo Inner Landscape"
            Image.new("RGBA", (15, 11)).save(root / (name + " Night Sky.png"))
            Image.new("L", (11, 7), 255).save(root / (name + "_mask.png"))
            source = root / "native.png"
            Image.new("RGB", (8, 6), "red").save(source)
            entry = {"name": name, "x": "2", "y": "2", "colors": "yes", "mask": "yes",
                     "resizeWidth": "11", "resizeHeight": "7"}
            catalog = {"8": {"overlap": {"6": entry}}}
            image, info = frames.frame_screenshot(source, root, catalog)
            self.assertEqual(image.getchannel("A").getbbox(), (2, 2, 13, 9))
            self.assertEqual(image.getpixel((12, 8)), (255, 0, 0, 255))
            self.assertTrue(info["resized"])
            metadata = frames.resolve_frame_metadata(8, 6, root, catalog)
            self.assertEqual((metadata["resize_width"], metadata["resize_height"]), (11, 7))
            entry.pop("resizeHeight")
            legacy = frames.resolve_frame_metadata(8, 6, root, catalog)
            self.assertEqual(legacy["resize_height"], 8)

    def test_simulator_inner_captures_frame_without_scaling(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = builder.catalog_entries()
            captures = {
                (2007, 2853): ("iPhone Duo Inner Portrait", (1878, 2670)),
                (2853, 2007): ("iPhone Duo Inner Landscape", (2670, 1878)),
            }
            for (width, height), (name, announced) in captures.items():
                with self.subTest(name=name):
                    entry, detected = frames.detect_device_size(width, height, catalog)
                    self.assertEqual(detected, name)
                    self.assertIsNone(frames.resize_target(entry, width, height))
                    forced = frames.resolve_device_entry(*announced, catalog, force_device=name)[0]
                    self.assertEqual(frames.resize_target(forced, *announced), (width, height))

            name = "iPhone Duo Inner Landscape"
            Image.new("RGBA", (15, 11)).save(root / (name + " Night Sky.png"))
            Image.new("L", (11, 7), 255).save(root / (name + "_mask.png"))
            source = root / "capture.png"
            Image.new("RGB", (11, 7), "red").save(source)
            entry = {"name": name, "x": "2", "y": "2", "colors": "yes", "mask": "yes",
                     "resizeWidth": "11", "resizeHeight": "7"}
            image, info = frames.frame_screenshot(source, root, {"11": {"overlap": {"7": entry}}})
            self.assertFalse(info["resized"])
            self.assertEqual(image.getchannel("A").getbbox(), (2, 2, 13, 9))

    def test_doctor_asks_to_update_packs_without_duo(self):
        for include_duo in (True, False):
            with self.subTest(include_duo=include_duo), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                catalog = builder.catalog_entries() if include_duo else {"variants": {}}
                catalog["variants"]["iPhone 18 Pro Portrait"] = {"name": "iPhone 18 Pro Portrait", "x": "0", "y": "0"}
                (root / "NewFrames.json").write_text(json.dumps(catalog), encoding="utf-8")
                (root / "version.txt").write_text("4", encoding="utf-8")
                output = io.StringIO()
                with mock.patch.object(frames, "CONFIG_FILE", root / "missing.json"), \
                        contextlib.redirect_stdout(output):
                    frames.cmd_doctor(Namespace(assets=str(root), json=True))
                notes = " ".join(json.loads(output.getvalue())["notes"])
                self.assertEqual("predates iPhone Duo" in notes, not include_duo)

    def pose_catalog(self, include_poses=True):
        """The Duo catalog, with the partially open poses of pack 4.2.2 when asked."""
        catalog = builder.catalog_entries()
        if include_poses:
            catalog["variants"].update({name: {"name": name, "x": "0", "y": "0", "colors": "yes", "warp": {}}
                                        for name in POSES.values()})
        return catalog

    def test_flat_inner_screenshots_keep_flat_frames_when_poses_are_installed(self):
        sizes = {(2853, 2007): "Landscape", (2670, 1878): "Landscape", (2007, 2853): "Portrait", (1878, 2670): "Portrait"}
        with tempfile.TemporaryDirectory() as directory:
            for (width, height), orientation in sizes.items():
                flat = f"iPhone Duo Inner {orientation}"
                pose = f"iPhone Duo Inner Partially Open {orientation}"
                capture = Path(directory) / f"{width}.png"
                Image.new("RGB", (width, height)).save(capture)
                for include_poses in (True, False):
                    with self.subTest(size=(width, height), include_poses=include_poses):
                        catalog = self.pose_catalog(include_poses)
                        entry, name, primary, is_variant = frames.resolve_device_entry(width, height, catalog)
                        self.assertEqual((name, primary, is_variant), (flat, flat, False))
                        self.assertNotIn("warp", entry)
                        # info offers the pose as a choice, and reports no choice without it.
                        info = frames._info_for_image(capture, catalog)
                        self.assertEqual((info["device"], info["is_variant"]), (flat, False))
                        self.assertEqual(info["variants"], [flat, pose] if include_poses else [])

    def test_poses_follow_the_inner_display_default_color(self):
        for pose in POSES.values():
            self.assertEqual(frames.get_color(pose, None, {"iPhone Duo Inner": "Star White"}), "Star White")
            self.assertEqual(frames.get_color(pose, None, {"iPhone Duo Inner": "Star White",
                                                           "iPhone Duo Inner Partially Open": "Night Sky"}), "Night Sky")
            self.assertEqual(frames.get_color(pose, "Night Sky", {"iPhone Duo Inner": "Star White"}), "Night Sky")
            self.assertEqual(frames.get_color(pose, None, {"iPhone Duo Outer": "Star White"}), "Night Sky")
        self.assertEqual(frames.get_color("iPhone Duo Inner Portrait", None,
                                          {"iPhone Duo Inner Partially Open": "Star White"}), "Night Sky")

    @mock.patch.object(frames.C, "enabled", False)
    def test_list_colors_and_doctor_present_the_poses_a_pack_provides(self):
        for include_poses in (True, False):
            with self.subTest(include_poses=include_poses), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                catalog = self.pose_catalog(include_poses)
                (root / "NewFrames.json").write_text(json.dumps(catalog), encoding="utf-8")
                (root / "version.txt").write_text("4.2.2" if include_poses else "4.2.1", encoding="utf-8")
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    frames.cmd_list(Namespace(assets=str(root)))
                manual = output.getvalue().split("Manual frames")[1].split("Default Variants")[0]
                self.assertIn("iPhone Duo Outer Open", manual)
                for alias, name in POSES.items():
                    self.assertEqual(f"{alias} ({name})" in manual, include_poses)
                self.assertEqual("Pose" in output.getvalue(), include_poses)
                self.assertNotIn("Partially Open", output.getvalue().split("Default Variants")[1])

                # The color picker gives the poses a row only when the pack can render them.
                devices = dict(frames._build_device_list(root))
                self.assertEqual("iPhone Duo Inner Partially Open" in devices, include_poses)
                self.assertEqual(devices["iPhone Duo Inner"], ["Night Sky", "Star White"])

                output = io.StringIO()
                with mock.patch.object(frames, "CONFIG_FILE", root / "missing.json"), \
                        contextlib.redirect_stdout(output):
                    frames.cmd_doctor(Namespace(assets=str(root), json=True))
                notes = " ".join(json.loads(output.getvalue())["notes"])
                self.assertEqual("the iPhone Duo Book and Laptop poses. Run `frames setup`" in notes, not include_poses)
                self.assertNotIn("predates iPhone Duo", notes)

                # Asking for a pose an older pack lacks says how to get it.
                for name in (*POSES, *POSES.values()):
                    if include_poses:
                        self.assertEqual(frames.resolve_device_entry(1, 1, catalog, force_device=name)[1], POSES.get(name, name))
                    else:
                        with self.assertRaisesRegex(ValueError, "predates the iPhone Duo Book and Laptop poses. Run `frames setup`"):
                            frames.resolve_device_entry(1, 1, catalog, force_device=name)
                with self.assertRaisesRegex(ValueError, "'iPhone Duo Sideways' not found in dictionary"):
                    frames.resolve_device_entry(1, 1, catalog, force_device="iPhone Duo Sideways")

        # Colors come from the CLI's own table, so short names work with any pack.
        for query in ("laptop pose", "iPhone Duo Laptop Pose"):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                frames.cmd_list_colors(Namespace(device_name=query))
            self.assertEqual(output.getvalue().split(), "iPhone Duo Inner Partially Open Portrait (iPhone Duo Laptop Pose) "
                             "1. Night Sky (default) 2. Star White".split())

    def test_mask_uses_enclosed_opening_and_preserves_partial_bezel_alpha(self):
        image = Image.new("RGBA", (16, 12))
        draw = ImageDraw.Draw(image)
        draw.rectangle((2, 2, 13, 9), fill=(30, 40, 50, 255))
        draw.rectangle((4, 4, 11, 7), fill=(0, 0, 0, 0))
        image.putpixel((4, 4), (30, 40, 50, 128))
        image.putpixel((8, 4), (0, 0, 0, 255))  # Opaque camera.
        mask = builder.screen_mask(image, (4, 4, 12, 8))
        screen = frames.apply_mask(Image.new("RGBA", (8, 4), "white"), mask.convert("RGBA"))
        result = frames.composite(screen, image, 4, 4)
        self.assertEqual(result.getpixel((4, 4))[3], 255)
        self.assertEqual(result.getpixel((8, 4)), (0, 0, 0, 255))
        self.assertEqual(result.getpixel((0, 0))[3], 0)
        with self.assertRaisesRegex(ValueError, "opening changed"):
            builder.screen_mask(image, (3, 4, 12, 8))

    def test_optimization_strips_metadata_without_changing_rgba(self):
        image = Image.new("RGBA", (20, 20), (10, 70, 90, 128))
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("Comment", "unused metadata " * 1000)
        source = io.BytesIO()
        image.save(source, "PNG", pnginfo=metadata, dpi=(300, 300))
        optimized = builder.optimize_png(source.getvalue(), image)
        self.assertLess(len(optimized), len(source.getvalue()))
        with Image.open(io.BytesIO(optimized)) as decoded:
            self.assertEqual(decoded.tobytes(), image.tobytes())
            self.assertNotIn("Comment", decoded.info)
            self.assertNotIn("dpi", decoded.info)


def packed_plane(image):
    """PackBits one channel, a literal run per row: the row byte counts, then the rows."""
    rows = [bytes([image.width - 1]) + image.crop((0, y, image.width, y + 1)).tobytes()
            for y in range(image.height)]
    return struct.pack(f">{len(rows)}H", *map(len, rows)), b"".join(rows)


def psd_layer(name, box, color, blend_if=(0, 0, 255, 255), mask=None, descriptor=None):
    """One layer record and its channel data. A mask is (box, default, image)."""
    left, top, right, bottom = box
    planes = Image.new("RGBA", (right - left, bottom - top), color).split()
    data = {channel: struct.pack(">H", 1) + b"".join(packed_plane(planes[index]))
            for channel, index in ((-1, 3), (0, 0), (1, 1), (2, 2))}
    block = b""
    if mask:
        (mask_left, mask_top, mask_right, mask_bottom), default, image = mask
        data[-2] = struct.pack(">H", 0) + image.tobytes()  # stored raw
        block = struct.pack(">4iBBH", mask_top, mask_left, mask_bottom, mask_right, default, 0, 0)
    ranges = bytes((0, 0, 255, 255)) + bytes(blend_if) + bytes((0, 0, 255, 255)) * 8
    label = bytes([len(name)]) + name.encode()
    label += bytes(-len(label) % 4)
    blocks = b"8BIMluni" + struct.pack(">I", 3) + b"abc\0"  # an odd-length block the reader skips
    if descriptor:
        blocks += b"8BIMSoLd" + struct.pack(">I", len(descriptor)) + descriptor + bytes(len(descriptor) % 2)
    extra = (struct.pack(">I", len(block)) + block + struct.pack(">I", len(ranges)) + ranges
             + label + blocks)
    record = (struct.pack(">4iH", top, left, bottom, right, len(data))
              + b"".join(struct.pack(">hI", channel, len(value)) for channel, value in data.items())
              + b"8BIMnorm" + bytes((255, 0, 8, 0)) + struct.pack(">I", len(extra)) + extra)
    return record, b"".join(data.values())


def warp_descriptor(placement, before, after, quads):
    """The parts of a Smart Object descriptor the builder reads: placement and Perspective Warp."""
    def points(key, values):
        return key + b"VlLs" + struct.pack(">I", len(values)) + b"".join(
            b"HrznUntF#Pxl" + struct.pack(">d", x) + bytes(4) + b"VrtcUntF#Pxl" + struct.pack(">d", y)
            for x, y in values)
    return (b"nonAffineTransformVlLs" + struct.pack(">I", 8)
            + b"".join(b"doub" + struct.pack(">d", value) for value in placement)
            + points(b"vertices", before) + points(b"warpedVertices", after)
            + b"".join(b"indicesVlLs" + struct.pack(">I", 4)
                       + b"".join(b"long" + struct.pack(">I", index) for index in quad) for quad in quads))


def write_psd(path, size, layers, preview):
    """Write the smallest 8-bit RGB PSD that Apple's templates resemble."""
    records, pixels = zip(*layers)
    info = struct.pack(">h", -len(layers)) + b"".join(records) + b"".join(pixels)
    section = struct.pack(">I", len(info)) + info
    counts, rows = zip(*(packed_plane(plane) for plane in Image.new("RGBA", size, preview).split()))
    path.write_bytes(b"8BPS" + struct.pack(">H6xHIIHH", 1, 4, size[1], size[0], 8, 3)
                     + struct.pack(">II", 0, 0) + struct.pack(">I", len(section)) + section
                     + struct.pack(">H", 1) + b"".join(counts) + b"".join(rows))


class FoldedBuilderTests(unittest.TestCase):
    UNIT = [(0, 0), (1, 0), (1, 1), (0, 1)]

    def test_inverse_perspective_returns_canvas_corners_to_screenshot_corners(self):
        polygon = [(10, 5), (90, 15), (80, 45), (20, 40)]
        a, b, c, d, e, f, g, h = folded.inverse_perspective(polygon, self.UNIT, (100, 50))
        for (x, y), (u, v) in zip(polygon, self.UNIT):
            w = g * x + h * y + 1
            self.assertAlmostEqual((a * x + b * y + c) / w, u)
            self.assertAlmostEqual((d * x + e * y + f) / w, v)
        # Pillow reads the coefficients the same way: each corner color lands in its corner.
        corners = Image.new("RGB", (2, 2))
        colors = ("red", "green", "blue", "white")
        for (u, v), color in zip(self.UNIT, colors):
            corners.putpixel((u, v), Image.new("RGB", (1, 1), color).getpixel((0, 0)))
        warped = corners.transform((100, 50), Image.PERSPECTIVE,
                                   [a * 2, b * 2, c * 2, d * 2, e * 2, f * 2, g, h], Image.NEAREST)
        for (x, y), (u, v) in zip(((16, 10), (84, 18), (76, 41), (24, 37)), self.UNIT):
            self.assertEqual(warped.getpixel((x, y)), corners.getpixel((u, v)))

    def test_region_scales_measure_canvas_pixels_per_screenshot_pixel(self):
        box = [(0, 0), (200, 0), (200, 25), (0, 25)]
        region = folded.place_regions([(box, self.UNIT)], (200, 25), (200, 25), (0, 0, 200, 25))[0]
        # A 100x50 screenshot on 200x25 pixels: doubled across, halved down.
        peak, low, across, down = folded.region_scales(region, (100, 50))
        self.assertEqual([round(value, 6) for value in (peak, low, across, down)], [2, 0.5, 2, 0.5])

    def test_fit_regions_shrinks_the_canvas_until_nothing_is_magnified(self):
        # A panel tilted toward the viewer: the scale grows toward its wide bottom edge.
        quads = [([(100, 0), (300, 0), (400, 200), (0, 200)], self.UNIT)]
        canvas, native = (400, 200), (100, 100)
        with self.assertRaisesRegex(ValueError, "would be magnified"):
            folded.fit_regions(quads, canvas, canvas, (0, 0, *canvas), native)
        size = folded.fitted_size(quads, canvas, native)
        self.assertLess(size[0], 400)
        region = folded.fit_regions(quads, canvas, size, (0, 0, *size), native)[0]
        peak, low, across, down = folded.region_scales(region, native)
        self.assertLessEqual(peak, 1)
        self.assertGreater(peak, 0.95)  # as large as a whole-pixel canvas allows
        self.assertLess(low, peak / 2)
        self.assertEqual(region["polygon"][2], (size[0], size[1]))
        self.assertEqual(region["extent"], [round(across * 100, 2), round(down * 100, 2)])

        # Cropping moves the polygon and leaves every scale as it was.
        cropped = folded.fit_regions(quads, canvas, size, (3, 2, size[0], size[1]), native)[0]
        self.assertEqual(cropped["polygon"][2], (size[0] - 3, size[1] - 2))
        self.assertEqual(cropped["extent"], region["extent"])
        for before, after in zip(folded.region_scales(region, native), folded.region_scales(cropped, native)):
            self.assertAlmostEqual(before, after)
        # The solved transform still returns the moved corners to the screenshot's corners.
        a, b, c, d, e, f, g, h = cropped["inverse"]
        for (x, y), (u, v) in zip(cropped["polygon"], self.UNIT):
            w = g * x + h * y + 1
            self.assertAlmostEqual((a * x + b * y + c) / w, u)
            self.assertAlmostEqual((d * x + e * y + f) / w, v)

    def test_device_box_is_shared_and_ignores_invisible_specks(self):
        dark = Image.new("RGBA", (40, 30))
        dark.paste((20, 20, 20, 255), (6, 5, 34, 26))
        dark.paste((20, 20, 20, 8), (4, 5, 6, 26))        # at the noise level: invisible
        light = Image.new("RGBA", (40, 30))
        light.paste((200, 200, 200, 255), (5, 6, 33, 25))
        light.putpixel((0, 0), (255, 255, 255, 255))      # a lone stray pixel
        self.assertEqual(folded.device_box([dark, light]), ((5, 5, 34, 26), 255))
        self.assertEqual(folded.device_box([dark]), ((6, 5, 34, 26), 8))

    def test_built_pose_is_cropped_to_the_device_with_its_geometry(self):
        # A 100x80 template: a device with a 20 and 16 pixel border around it, and a
        # 40x36 display that three side-by-side quads fill without distortion.
        display = (30, 22, 70, 58)
        columns = (0, 16, 24, 40)
        before = [(x, y) for y in (0, 36) for x in columns]
        after = [(x + display[0], y + display[1]) for x, y in before]
        descriptor = warp_descriptor((0, 0, 40, 0, 40, 36, 0, 36), before, after,
                                     [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6)])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for color, shade, body in (("Night Sky", 20, (20, 16, 90, 70)), ("Star White", 200, (20, 17, 89, 70))):
                write_psd(root / f"iPhone Duo - {color} - Inner Partially Open Portrait.psd", (100, 80), [
                    psd_layer("Hardware", body, (shade, shade, shade, 255)),
                    psd_layer("Screen Content ", display, (1, 2, 3, 255), descriptor=descriptor,
                              mask=(display, 0, Image.new("L", (40, 36), 255))),
                    psd_layer("black", (40, 30, 44, 34), (9, 9, 9, 40), blend_if=(0, 0, 10, 30)),
                    psd_layer("dark", (40, 30, 44, 34), (8, 8, 8, 50), blend_if=(10, 30, 60, 90)),
                    psd_layer("light", (40, 30, 44, 34), (7, 7, 7, 60), blend_if=(60, 90, 255, 255)),
                ], (42, 43, 44, 255))
            with contextlib.redirect_stdout(io.StringIO()):
                entry = folded.build_view(root, root, "Portrait", [[22, 17]])
            warp = entry["warp"]
            images = {}
            for color in ("Night Sky", "Star White"):
                with Image.open(root / f"{LAPTOP} {color}.png") as image:
                    images[color] = image.convert("RGBA")
            with Image.open(root / f"{LAPTOP}_mask.png") as image:
                mask = image.convert("L")
            with Image.open(root / f"{LAPTOP}_camera.png") as image:
                camera_size = (image.width // 3, image.height)

            # The scaled template was 47x37, with a border of about 9 and 7 pixels.
            # None of it is left around the device.
            size = images["Night Sky"].size
            self.assertEqual(images["Star White"].size, size)
            self.assertEqual(mask.size, size)
            self.assertTrue(size[0] < 40 and size[1] < 32)
            self.assertEqual(folded.device_box(images.values())[0], (0, 0, *size))
            # The mask, the regions, and the camera moved together with the crop.
            left, top, right, bottom = mask.point(lambda value: 255 if value > 127 else 0).getbbox()
            corners = [point for region in warp["regions"] for point in region["polygon"]]
            self.assertAlmostEqual(min(x for x, _ in corners), left, delta=1)
            self.assertAlmostEqual(min(y for _, y in corners), top, delta=1)
            self.assertAlmostEqual(max(x for x, _ in corners), right, delta=1)
            self.assertAlmostEqual(max(y for _, y in corners), bottom, delta=1)
            # The camera's center is 12 and 10 template pixels into the display.
            self.assertAlmostEqual(warp["camera"]["x"] + camera_size[0] / 2, left + 12 * 47 / 100, delta=1)
            self.assertAlmostEqual(warp["camera"]["y"] + camera_size[1] / 2, top + 10 * 37 / 80, delta=1)
            self.assertTrue(0 < warp["reflectionSpan"][0] < warp["reflectionSpan"][1] < len(warp["reflections"]["Night Sky"]))
            folded.check_not_magnified(warp["regions"], (22, 17))

            # Through the CLI, a screenshot fills the display and nothing else.
            Image.new("RGB", (22, 17), "red").save(root / "input.png")
            result, _ = frames.frame_screenshot(root / "input.png", root, {"variants": {LAPTOP: entry}},
                                                force_device=LAPTOP, color_arg="Night Sky")
            self.assertEqual(result.size, size)
            away_from_camera = (right - 4, bottom - 4)
            self.assertEqual(result.getpixel(away_from_camera), (255, 0, 0, 255))
            self.assertEqual(result.getpixel((left + 3, top + 3)), (255, 0, 0, 255))
            self.assertEqual(result.getpixel((left - 3, (top + bottom) // 2))[:3], (20, 20, 20))
            self.assertEqual(result.getpixel((right + 2, (top + bottom) // 2))[:3], (20, 20, 20))
            self.assertNotEqual(result.getpixel((warp["camera"]["x"] + camera_size[0] // 2,
                                                 warp["camera"]["y"] + camera_size[1] // 2)), (255, 0, 0, 255))

    def test_reads_layers_masks_blend_ranges_and_preview_from_a_psd(self):
        mask = Image.new("L", (5, 4), 255)
        mask.putpixel((4, 3), 128)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "template.psd"
            write_psd(path, (8, 6), [
                psd_layer("Hardware", (0, 0, 8, 6), (10, 20, 30, 255)),
                psd_layer("Screen Content ", (1, 1, 5, 4), (1, 2, 3, 200),
                          mask=((2, 1, 7, 5), 0, mask), descriptor=b"descriptor"),
                psd_layer("Black", (2, 2, 4, 3), (9, 9, 9, 40), blend_if=(0, 0, 10, 30)),
                psd_layer("Dark", (1, 2, 4, 4), (8, 8, 8, 50), blend_if=(10, 30, 60, 90)),
                psd_layer("Light", (2, 1, 3, 3), (7, 7, 7, 60), blend_if=(60, 90, 255, 255)),
            ], (42, 43, 44, 255))
            canvas, layers, preview = folded.read_psd(path)
        self.assertEqual(canvas, (8, 6))
        self.assertEqual(preview.getpixel((7, 5)), (42, 43, 44))
        self.assertEqual(layers["hardware"]["image"].getpixel((7, 5)), (10, 20, 30, 255))
        content = layers["screen content"]
        self.assertEqual((content["image"].size, content["offset"]), ((4, 3), (1, 1)))
        self.assertEqual(content["image"].getpixel((0, 0)), (1, 2, 3, 200))
        self.assertEqual(content["descriptor"], b"descriptor")
        # The mask covers the whole canvas: its default outside its box, its pixels inside.
        self.assertEqual(content["mask"].size, (8, 6))
        self.assertEqual([content["mask"].getpixel(point) for point in ((1, 1), (2, 1), (6, 4), (7, 4))],
                         [0, 255, 128, 0])
        self.assertEqual(layers["dark"]["blendIf"], (10, 30, 60, 90))

        strip, camera = folded.camera_strip(layers, canvas, canvas)
        self.assertEqual(camera, {"x": 1, "y": 1, "blendIf": [[0, 0, 10, 30], [10, 30, 60, 90], [60, 90, 255, 255]]})
        self.assertEqual(strip.size, (9, 3))
        # Each layer keeps its place inside its own cell: black, then dark, then light.
        self.assertEqual(strip.getpixel((1, 1)), (9, 9, 9, 40))
        self.assertEqual(strip.getpixel((3, 1)), (8, 8, 8, 50))
        self.assertEqual(strip.getpixel((7, 0)), (7, 7, 7, 60))
        self.assertEqual(strip.getpixel((0, 0))[3], 0)


if __name__ == "__main__":
    unittest.main()
