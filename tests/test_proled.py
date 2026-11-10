import importlib.machinery
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


frames = load_module("frames_proled", ROOT / "frames")
builder = load_module("build_proled", ROOT / "scripts/build_proled_assets.py")


def base_catalog():
    """The two MacBook Pro widths as the published v4 pack defines them."""
    return {
        "3024": {"name": "MacBook Pro M5 14", "colors": "yes", "x": "418", "y": "288", "physicalHeight": 254.1},
        "3456": {"name": "MacBook Pro M5 16", "colors": "yes", "x": "402", "y": "303", "physicalHeight": 284.0},
        "variants": {},
    }


class PROLEDTests(unittest.TestCase):
    def test_shared_14_inch_width_splits_by_height(self):
        catalog = builder.add_catalog_entries(builder.split_shared_width(base_catalog(), 3024, 1964))
        expected = {
            (3024, 1964): "MacBook Pro M5 14",
            (3024, 1986): "MacBook Pro PROLED 14",
            (3472, 2266): "MacBook Pro PROLED 16",
            (3456, 2234): "MacBook Pro M5 16",
        }
        for (width, height), name in expected.items():
            entry, _, _, _ = frames.resolve_device_entry(width, height, catalog)
            self.assertEqual(entry["name"], name)
        with self.assertRaises(ValueError):
            frames.resolve_device_entry(3024, 1890, catalog)

    def test_unsplit_shared_width_is_refused(self):
        with self.assertRaises(ValueError):
            builder.add_catalog_entries(base_catalog())

    def test_scaled_captures_fit_native_opening_and_reject_other_heights(self):
        catalog = builder.add_scaled_entries(builder.add_catalog_entries(
            builder.split_shared_width(base_catalog(), 3024, 1964)))
        for width, height in builder.SCALED_16_SIZES:
            entry, name, _, _ = frames.resolve_device_entry(width, height, catalog)
            self.assertEqual(name, "MacBook Pro PROLED 16")
            self.assertEqual(frames.resize_target(entry, width, height), (3472, 2266))
            with self.assertRaises(ValueError):
                frames.resolve_device_entry(width, height + 1, catalog)


if __name__ == "__main__":
    unittest.main()
