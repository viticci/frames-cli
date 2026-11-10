import contextlib
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
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


class DuoTests(unittest.TestCase):
    def test_warped_regions_stay_clipped_to_the_display(self):
        name = "iPhone Duo Inner Partially Open Landscape"
        size = (24, 12)
        regions = [
            {"polygon": [(0, 0), (11, 0), (11, 12), (0, 12)],
             "inverse": [1 / 24, 0, 0.5, 0, 1 / 12, 0, 0, 0]},
            {"polygon": [(12, 0), (24, 0), (24, 12), (12, 12)],
             "inverse": [1 / 24, 0, -0.5, 0, 1 / 12, 0, 0, 0]},
        ]
        entry = {
            "name": name, "x": "0", "y": "0", "mask": "yes", "colors": "yes",
            "warp": {"inputSizes": [[24, 12]], "regions": regions,
                     "reflections": {"Star White": [0, 12]}},
        }
        catalog = {"variants": {name: entry}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = Image.new("RGB", size, "red")
            source.paste("blue", (12, 0, 24, 12))
            source.save(root / "input.png")
            Image.new("RGBA", size, "black").save(root / f"{name} Star White.png")
            mask = Image.new("L", size, 255)
            mask.putpixel((1, 4), 0)
            mask.save(root / f"{name}_mask.png")
            overlay = Image.new("RGBA", size)
            overlay.putpixel((18, 4), (255, 255, 255, 255))
            overlay.save(root / f"{name}_overlay.png")

            result, info = frames.frame_screenshot(
                root / "input.png", root, catalog, force_device="iPhone Duo Book Pose", color_arg="Star White",
            )
            self.assertEqual(info["device"], name)
            self.assertTrue(info["masked"])
            self.assertEqual(result.getpixel((5, 4)), (0, 0, 255, 255))
            self.assertEqual(result.getpixel((20, 4)), (255, 12, 12, 255))
            self.assertEqual(result.getpixel((1, 4)), (0, 0, 0, 255))
            self.assertEqual(result.getpixel((18, 4)), (255, 255, 255, 255))
            with self.assertRaisesRegex(ValueError, "screenshots only"):
                frames.resolve_frame_metadata(*size, root, catalog, force_device="iPhone Duo Book Pose")
            self.assertNotIn("iPhone Duo Book Pose", frames.build_device_name_index({"variants": {}}))

    def test_laptop_pose_uses_normal_blending_and_vertical_reflection(self):
        name = "iPhone Duo Inner Partially Open Portrait"
        size = (12, 24)
        warp = {
            "regions": [{"polygon": [(0, 0), (12, 0), (12, 24), (0, 24)],
                         "inverse": [1 / 12, 0, 0, 0, 1 / 24, 0, 0, 0]}],
            "blend": "normal", "reflectionAxis": "y", "reflections": {"Star White": [0, 12]},
        }
        catalog = {"variants": {name: {"name": name, "warp": warp}}}
        entry, _, _, _ = frames.resolve_device_entry(*size, catalog, force_device="iPhone Duo Laptop Pose")
        result = frames.composite_warped(
            Image.new("RGBA", size, (30, 30, 30, 255)),
            Image.new("RGBA", size, (80, 80, 80, 255)),
            Image.new("RGBA", size, "white"),
            Image.new("RGBA", size),
            entry["warp"], "Star White",
        )
        self.assertEqual(result.getpixel((5, 2)), (30, 30, 30, 255))
        self.assertEqual(result.getpixel((5, 21)), (42, 42, 42, 255))

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


if __name__ == "__main__":
    unittest.main()
