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

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


frames = load_module("frames_iphone_18_pro", ROOT / "frames")
builder = load_module("build_iphone_18_pro", ROOT / "scripts/build_iphone_18_pro_assets.py")


class IPhone18ProTests(unittest.TestCase):
    def test_colors_and_shared_resolution_default(self):
        catalog = {
            "1206": {"name": "iPhone 17 Portrait", "x": "72", "y": "69"},
            "2622": {"name": "iPhone 17 Landscape", "x": "69", "y": "72"},
            "variants": builder.catalog_entries()["variants"],
        }
        for size, expected in (((1206, 2622), "iPhone 18 Pro Portrait"),
                               ((2622, 1206), "iPhone 18 Pro Landscape")):
            with self.subTest(expected=expected):
                entry, name, primary, is_variant = frames.resolve_device_entry(*size, catalog)
                self.assertEqual(name, expected)
                self.assertEqual(primary, "iPhone 17 " + expected.rsplit(" ", 1)[1])
                self.assertTrue(is_variant)
                self.assertEqual(frames.get_color(name, None), "Black")
                self.assertEqual(frames.get_color(name, "burgundy", strict=True), "Burgundy")
                self.assertEqual((entry["x"], entry["y"]),
                                 ("72", "69") if size[0] == 1206 else ("69", "72"))

    def test_explicit_iphone_17_pro_still_resolves(self):
        old = {"name": "iPhone 17 Pro Portrait", "x": "72", "y": "69"}
        catalog = {"variants": dict(builder.catalog_entries()["variants"], **{old["name"]: old})}
        entry, name, primary, is_variant = frames.resolve_device_entry(
            1206, 2622, catalog, force_device="iPhone 17 Pro Portrait"
        )
        self.assertIs(entry, old)
        self.assertEqual((name, primary, is_variant), (old["name"], old["name"], False))

    def test_older_pack_falls_back_to_iphone_17_pro(self):
        old = {"name": "iPhone 17 Pro Portrait", "x": "72", "y": "69"}
        catalog = {
            "1206": {"name": "iPhone 17 Portrait", "x": "72", "y": "69"},
            "variants": {old["name"]: old},
        }
        entry, name, primary, is_variant = frames.resolve_device_entry(1206, 2622, catalog)
        self.assertIs(entry, old)
        self.assertEqual(name, old["name"])
        self.assertEqual(primary, "iPhone 17 Portrait")
        self.assertTrue(is_variant)

    def test_list_and_catalog_include_both_orientations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = {
                "1206": {"name": "iPhone 17 Portrait", "x": "72", "y": "69"},
                "2622": {"name": "iPhone 17 Landscape", "x": "69", "y": "72"},
                "variants": builder.catalog_entries()["variants"],
            }
            (root / "NewFrames.json").write_text(json.dumps(catalog), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                frames.cmd_list(Namespace(assets=str(root)))
            listing = output.getvalue()
            self.assertIn("iPhone 18 Pro Portrait", listing)
            self.assertIn("iPhone 18 Pro Landscape", listing)

    def test_mask_validates_opening_and_keeps_camera_cutout(self):
        image = Image.new("RGBA", (16, 12), (20, 20, 20, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((3, 2, 12, 9), fill=(0, 0, 0, 0))
        image.putpixel((8, 3), (0, 0, 0, 255))
        mask = builder.screen_mask(image, (3, 2, 13, 10))
        self.assertEqual(mask.size, (10, 8))
        self.assertEqual(mask.getpixel((5, 1)), 0)
        with self.assertRaisesRegex(ValueError, "opening changed"):
            builder.screen_mask(image, (2, 2, 13, 10))

    def test_builder_creates_complete_non_destructive_pack(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            base = root / "base"
            output = root / "output"
            source.mkdir()
            base.mkdir()
            (base / "NewFrames.json").write_text('{"variants": {}}', encoding="utf-8")
            (base / "Frames.json").write_text("{}", encoding="utf-8")
            (base / "version.txt").write_text("4\n", encoding="utf-8")
            Image.new("RGBA", (2, 2), "black").save(base / "Existing.png")

            views = (
                {"name": "iPhone 18 Pro Portrait", "screen": (8, 12), "canvas": (12, 16),
                 "opening": (2, 2, 10, 14), "physicalHeight": 149.6},
                {"name": "iPhone 18 Pro Landscape", "screen": (12, 8), "canvas": (16, 12),
                 "opening": (2, 2, 14, 10), "physicalHeight": 71.5},
            )
            with mock.patch.object(builder, "VIEWS", views):
                for view in views:
                    image = Image.new("RGBA", view["canvas"], (20, 20, 20, 255))
                    x, y, right, bottom = view["opening"]
                    ImageDraw.Draw(image).rectangle((x, y, right - 1, bottom - 1), fill=(0, 0, 0, 0))
                    image.putpixel(((x + right) // 2, y + 1), (0, 0, 0, 255))
                    for color in builder.COLORS:
                        image.save(source / ("{} {}.png".format(view["name"], color)))

                manifest = builder.build_pack(source, base, output)
                self.assertEqual(len(manifest["frames"]), 8)
                self.assertTrue((output / "Existing.png").is_file())
                catalog = json.loads((output / "NewFrames.json").read_text(encoding="utf-8"))
                for view in views:
                    name = view["name"]
                    self.assertIn(name, catalog["variants"])
                    self.assertEqual((output / (name + ".png")).read_bytes(),
                                     (output / (name + " Black.png")).read_bytes())
                    with Image.open(output / (name + "_mask.png")) as mask:
                        self.assertEqual(mask.size, view["screen"])
                with self.assertRaisesRegex(ValueError, "must not exist"):
                    builder.build_pack(source, base, output)


if __name__ == "__main__":
    unittest.main()
