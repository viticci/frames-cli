import importlib.machinery
import importlib.util
from pathlib import Path
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


frames = load_module("frames_mini_ultra4", ROOT / "frames")
builder = load_module("build_mini_ultra4", ROOT / "scripts/build_mini_ultra4_assets.py")


def base_catalog():
    """The Ultra 3 entry and an older iPad mini, as pack 4.1.1 defines them."""
    return {
        "422": {"name": "Watch Ultra 3", "colors": "yes", "x": "55", "y": "206", "physicalHeight": 70.4},
        "1488": {"name": "iPad mini 2021 Portrait", "x": "121", "y": "125", "physicalHeight": 195.4},
        "variants": {},
    }


class MiniUltra4Tests(unittest.TestCase):
    def test_new_sizes_resolve_automatically(self):
        catalog = builder.merge_catalog(base_catalog(), builder.new_catalog())
        expected = {
            (1512, 2316): "iPad mini A20 Pro Portrait",
            (2316, 1512): "iPad mini A20 Pro Landscape",
            (422, 514): "Watch Ultra 4",
            (1488, 2266): "iPad mini 2021 Portrait",
        }
        for (width, height), name in expected.items():
            entry, _, _, _ = frames.resolve_device_entry(width, height, catalog)
            self.assertEqual(entry["name"], name)

    def test_ultra_3_stays_selectable_and_is_the_fallback_for_older_packs(self):
        catalog = builder.merge_catalog(base_catalog(), builder.new_catalog())
        entry, _, _, _ = frames.resolve_device_entry(422, 514, catalog, force_device="Watch Ultra 3")
        self.assertEqual(entry["name"], "Watch Ultra 3")
        entry, _, _, _ = frames.resolve_device_entry(422, 514, base_catalog())
        self.assertEqual(entry["name"], "Watch Ultra 3")

    def test_merge_refuses_to_replace_an_existing_entry(self):
        catalog = base_catalog()
        catalog["1512"] = {"name": "Something else", "x": "0", "y": "0"}
        with self.assertRaises(ValueError):
            builder.merge_catalog(catalog, builder.new_catalog())

    def test_screen_tint_is_cleared_without_touching_the_bezel(self):
        image = Image.new("RGBA", (6, 6), (9, 9, 9, 255))
        image.paste((0, 0, 0, 4), (1, 1, 5, 5))
        builder.clear_screen_tint(image, (1, 1, 5, 5))
        self.assertEqual(image.getpixel((2, 2)), (0, 0, 0, 0))
        self.assertEqual(image.getpixel((0, 0)), (9, 9, 9, 255))


if __name__ == "__main__":
    unittest.main()
