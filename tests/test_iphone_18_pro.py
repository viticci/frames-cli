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


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


frames = load_module("frames_iphone_18_pro", ROOT / "frames")

# Native size -> (primary NewFrames.json match, iPhone 17 Pro default, iPhone 18 Pro default)
SHARED_SIZES = {
    (1206, 2622): ("iPhone 17 Portrait", "iPhone 17 Pro Portrait", "iPhone 18 Pro Portrait"),
    (2622, 1206): ("iPhone 17 Landscape", "iPhone 17 Pro Landscape", "iPhone 18 Pro Landscape"),
    (1320, 2868): ("iPhone 17 Pro Max Portrait", "iPhone 17 Pro Max Portrait", "iPhone 18 Pro Max Portrait"),
    (2868, 1320): ("iPhone 17 Pro Max Landscape", "iPhone 17 Pro Max Landscape", "iPhone 18 Pro Max Landscape"),
}


def catalog(include_18=True):
    """A minimal Frames 4 catalog shaped like the published packs."""
    data = {"variants": {}}
    for (width, _), (primary, pro17, pro18) in SHARED_SIZES.items():
        data[str(width)] = {"name": primary, "x": "1", "y": "1"}
        data["variants"][pro17] = {"name": pro17, "x": "2", "y": "2"}
        if include_18:
            data["variants"][pro18] = {"name": pro18, "x": "3", "y": "3"}
    return data


class IPhone18ProTests(unittest.TestCase):
    def test_shared_sizes_prefer_18_pro_and_fall_back_to_17_pro(self):
        for size, (primary, pro17, pro18) in SHARED_SIZES.items():
            with self.subTest(size=size):
                entry, name, matched, _ = frames.resolve_device_entry(*size, catalog())
                self.assertEqual((name, matched, entry["x"]), (pro18, primary, "3"))
                self.assertEqual(frames.get_color(name, None), "Burgundy")
                self.assertEqual(frames.get_color(name, "glacier", strict=True), "Glacier")
                self.assertIn(pro17, frames.installed_variants(primary, catalog()))

                # Packs published before iPhone 18 Pro keep the previous default.
                entry, name, _, _ = frames.resolve_device_entry(*size, catalog(include_18=False))
                self.assertEqual(name, pro17)
                self.assertNotIn(pro18, frames.installed_variants(primary, catalog(include_18=False)))

                entry, name, _, is_variant = frames.resolve_device_entry(*size, catalog(), force_device=pro17)
                self.assertEqual((name, entry["x"], is_variant), (pro17, "2", False))

    @mock.patch.object(frames.C, "enabled", False)
    def test_list_and_doctor_describe_the_installed_pack(self):
        for include_18, default, stale in ((True, "iPhone 18 Pro Portrait", False),
                                           (False, "iPhone 17 Pro Portrait", True)):
            with self.subTest(include_18=include_18), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "NewFrames.json").write_text(json.dumps(catalog(include_18)), encoding="utf-8")
                (root / "version.txt").write_text("4", encoding="utf-8")
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    frames.cmd_list(Namespace(assets=str(root)))
                self.assertIn("iPhone 17 Portrait → " + default, output.getvalue())
                # A frame is manual only while a newer default takes its sizes.
                manual = output.getvalue().split("Default Variants")[0].partition("Manual frames")[2]
                self.assertEqual("iPhone 17 Pro Portrait" in manual, include_18)
                self.assertEqual("iPhone 17 Pro Max Landscape" in manual, include_18)
                self.assertNotIn("iPhone 18 Pro", manual)

                output = io.StringIO()
                with mock.patch.object(frames, "CONFIG_FILE", root / "missing.json"), \
                        contextlib.redirect_stdout(output):
                    frames.cmd_doctor(Namespace(assets=str(root), json=True))
                notes = " ".join(json.loads(output.getvalue())["notes"])
                self.assertEqual("predates iPhone 18 Pro" in notes, stale)


if __name__ == "__main__":
    unittest.main()
