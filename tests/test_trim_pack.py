import importlib.machinery
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import trim_pack  # noqa: E402


def load_frames():
    loader = importlib.machinery.SourceFileLoader("frames_trim", str(ROOT / "frames"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


frames = load_frames()


def device(size, body, hole):
    """A frame canvas with an opaque body and a transparent screen hole."""
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    image.paste((40, 40, 40, 255), body)
    image.paste((0, 0, 0, 0), hole)
    return image


@unittest.skipUnless(shutil.which("oxipng"), "oxipng is required")
class TrimPackTests(unittest.TestCase):
    def test_colors_share_one_crop_and_offsets_follow(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "pack", Path(directory) / "out"
            source.mkdir()
            # Two colors with different margins; a lone corner pixel must not pin the crop.
            red = device((100, 140), (10, 20, 90, 130), (20, 30, 80, 120))
            red.putpixel((0, 0), (255, 255, 255, 255))
            red.save(source / "Phone Portrait Red.png")
            device((100, 140), (12, 18, 88, 132), (20, 30, 80, 120)).save(source / "Phone Portrait Blue.png")
            # Landscape stored sideways (portrait canvas), as the CLI rotates it.
            device((60, 120), (5, 10, 50, 115), (15, 20, 40, 105)).save(source / "Phone Landscape.png")
            catalog = {
                "60": {"name": "Phone Portrait", "x": "20", "y": "30", "colors": "yes"},
                "85": {"name": "Phone Landscape", "x": "20", "y": "20"},
                "variants": {"Phone Portrait": {"name": "Phone Portrait", "x": "20", "y": "30"}},
            }
            (source / "NewFrames.json").write_text(json.dumps(catalog))
            (source / "version.txt").write_text("4.1.0")

            trim_pack.trim_pack(source, output, "4.1.1")

            new = json.loads((output / "NewFrames.json").read_text())
            self.assertEqual(Image.open(output / "Phone Portrait Red.png").size, (80, 114))
            self.assertEqual(Image.open(output / "Phone Portrait Blue.png").size, (80, 114))
            self.assertEqual((new["60"]["x"], new["60"]["y"]), ("10", "12"))
            self.assertEqual(new["variants"]["Phone Portrait"], {**catalog["variants"]["Phone Portrait"], "x": "10", "y": "12"})
            self.assertEqual((output / "version.txt").read_text(), "4.1.1")

            # The sideways frame still frames a landscape screenshot exactly as before.
            shot = Image.new("RGBA", (85, 25), (200, 0, 0, 255))
            old = Image.open(source / "Phone Landscape.png").convert("RGBA").transpose(Image.ROTATE_90)
            trimmed = Image.open(output / "Phone Landscape.png").convert("RGBA")
            self.assertTrue(frames.asset_is_sideways("Phone Landscape", trimmed.size))
            trimmed = trimmed.transpose(Image.ROTATE_90)
            before = frames.composite(shot, old, 20, 20)
            after = frames.composite(shot, trimmed, int(new["85"]["x"]), int(new["85"]["y"]))
            self.assertEqual(before.getchannel("A").getbbox(), (10, 10, 115, 55))
            self.assertEqual(before.crop((10, 10, 115, 55)).tobytes(), after.tobytes())


if __name__ == "__main__":
    unittest.main()
