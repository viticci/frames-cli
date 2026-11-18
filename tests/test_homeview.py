import importlib.machinery
import importlib.util
from pathlib import Path
import unittest

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


frames = load_module("frames_homeview", ROOT / "frames")
builder = load_module("build_homeview", ROOT / "scripts/build_homeview_assets.py")


def render(screen_color):
    """A HomeView-shaped render at output scale: aluminum, black bezel, picture.

    The picture's bottom is a dark purple that is darker than the old luminance
    cutoff in every finish, as in Apple's wall-mounted renders."""
    image = Image.new("RGBA", (1260, 1260))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, 1259, 1259), 220, fill=(200, 200, 205, 255))
    draw.rounded_rectangle((16, 16, 1243, 1243), 200, fill=(0, 0, 0, 255))
    draw.rounded_rectangle((86, 86, 1173, 1173), 130, fill=screen_color)
    draw.rectangle((300, 1100, 960, 1173), fill=(30, 5, 45, 255))
    return image


class HomeViewTests(unittest.TestCase):
    def test_capture_sizes_resolve_to_the_tabletop_frame(self):
        catalog = builder.catalog_entries({"variants": {}})
        entry, name, _, _ = frames.resolve_device_entry(1088, 1088, catalog)
        self.assertEqual((name, frames.resize_target(entry, 1088, 1088)), ("HomeView", None))
        # QuickTime mirrors at 1080 x 1080; it fills the same opening.
        entry, name, _, _ = frames.resolve_device_entry(1080, 1080, catalog)
        self.assertEqual((name, frames.resize_target(entry, 1080, 1080)), ("HomeView", (1088, 1088)))
        # Wall Mounted is only chosen by name, and QuickTime captures still fill it.
        for size, target in ((1088, None), (1080, (1088, 1088))):
            entry, name, _, _ = frames.resolve_device_entry(size, size, catalog, force_device="HomeView Wall Mounted")
            self.assertEqual((name, frames.resize_target(entry, size, size)), ("HomeView Wall Mounted", target))
        with self.assertRaises(ValueError):
            frames.resolve_device_entry(1080, 1920, catalog)
        for view in builder.VIEWS:
            self.assertEqual(frames.FRAME_COLORS[view["name"]], list(view["colors"]))

    def test_dark_wallpaper_at_the_edge_is_cut_out_with_the_screen(self):
        view = {"name": "Test", "canvas": (1260, 1260), "opening": (86, 86)}
        built, mask = builder.build_frames([render((40, 60, 200, 255)), render((200, 60, 140, 255))], view)
        self.assertEqual(mask.size, (1088, 1088))
        self.assertEqual(mask.getpixel((544, 1080)), 255)
        self.assertEqual(mask.getpixel((0, 0)), 0)
        for frame in built:
            # The purple strip is gone with the rest of the picture; the bezel stays.
            self.assertEqual(frame.getpixel((630, 1150))[3], 0)
            self.assertEqual(frame.getpixel((630, 50)), (0, 0, 0, 255))


if __name__ == "__main__":
    unittest.main()
