import importlib.machinery
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


frames = load_module("frames_duo_video", ROOT / "frames")
sys.path.insert(0, str(ROOT / "scripts"))
try:
    folded = load_module("build_duo_folded_video", ROOT / "scripts/build_duo_folded_assets.py")
finally:
    sys.path.remove(str(ROOT / "scripts"))

BOOK = "iPhone Duo Inner Partially Open Landscape"
LAPTOP = "iPhone Duo Inner Partially Open Portrait"
COLOR = "Star White"
HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def triangle(length, period):
    return bytes(round(255 * abs((i % period) / (period / 2) - 1)) for i in range(length))


def write_source(path, size):
    """Steep ramps, so a one-pixel shift shows while resampling kernels still agree."""
    width, height = size
    red = Image.frombytes("L", (width, 1), triangle(width, 48)).resize(size)
    green = Image.frombytes("L", (1, height), triangle(height, 40)).resize(size)
    Image.merge("RGB", (red, green, Image.new("L", size, 90))).save(path)


def write_pack(root, name, scale=1, laptop=False):
    """A small three-region pose shaped like the real ones, on a canvas with odd dimensions."""
    canvas = (321 * scale, 241 * scale)
    if laptop:
        source_size = (140, 200)
        before = [(0, 0), (1, 0), (0, 0.5), (1, 0.5), (0, 0.58), (1, 0.58), (0, 1), (1, 1)]
        after = [(60, 16), (260, 16), (60, 150), (260, 150), (52, 166), (268, 166), (24, 224), (296, 224)]
        quads = [(0, 1, 3, 2), (2, 3, 5, 4), (4, 5, 7, 6)]
        reflection = [0, 0, 0, 0, 0, 9, 14, 6, 2, 2]
    else:
        source_size = (200, 140)
        before = [(0, 0), (0.47, 0), (0.53, 0), (1, 0), (0, 1), (0.47, 1), (0.53, 1), (1, 1)]
        after = [(30, 18), (150, 40), (170, 40), (290, 18), (30, 222), (150, 200), (170, 200), (290, 222)]
        quads = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6)]
        reflection = [0, 0, 0, 0, 2, 6, 10, 12, 12, 12]
    after = [(x * scale + 0.37, y * scale - 0.21) for x, y in after]
    regions = []
    for quad in quads:
        polygon = [after[i] for i in quad]
        regions.append({"polygon": polygon,
                        "inverse": folded.inverse_perspective(polygon, [before[i] for i in quad], canvas)})
    warp = {"inputSizes": [list(source_size)], "regions": regions, "reflections": {COLOR: reflection}}
    if laptop:
        warp.update(blend="normal", reflectionAxis="y", maskByColor=True)
    entry = {"name": name, "x": "0", "y": "0", "mask": "yes", "colors": "yes", "warp": warp}

    body = (8 * scale, 6 * scale, canvas[0] - 8 * scale, canvas[1] - 6 * scale)
    shade = Image.linear_gradient("L").resize(canvas).point(lambda value: 20 + value // 3)
    frame = Image.merge("RGBA", (shade, shade, shade, Image.new("L", canvas)))
    alpha = Image.new("L", canvas)
    ImageDraw.Draw(alpha).rounded_rectangle(body, radius=20 * scale, fill=255)
    frame.putalpha(alpha.filter(ImageFilter.GaussianBlur(0.6)))
    frame.save(root / f"{name} {COLOR}.png")
    mask = Image.new("L", canvas)
    xs, ys = [x for x, _ in after], [y for _, y in after]
    ImageDraw.Draw(mask).rounded_rectangle(
        (min(xs) + 3 * scale, min(ys) + 3 * scale, max(xs) - 3 * scale, max(ys) - 3 * scale),
        radius=12 * scale, fill=255,
    )
    mask = mask.filter(ImageFilter.GaussianBlur(0.8))
    mask.save(root / (f"{name} {COLOR}_mask.png" if laptop else f"{name}_mask.png"))
    overlay = Image.new("RGBA", canvas)
    ImageDraw.Draw(overlay).ellipse((200 * scale, 60 * scale, 212 * scale, 72 * scale), fill=(4, 4, 6, 220))
    overlay.save(root / f"{name}_overlay.png")
    return {"variants": {name: entry}}, source_size, canvas


def video_args(**overrides):
    values = dict(spacing=4, no_scale=False, playback_offset=False, strip_audio=False, background=None,
                  alpha=False, codec="h264", preset="best", quality=None, rotate="none")
    values.update(overrides)
    return Namespace(**values)


class WarpedVideoMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def resolve(self, catalog, width, height, name=BOOK, **options):
        return frames.resolve_frame_metadata(width, height, self.root, catalog, color_arg=COLOR,
                                             force_device=name, **options)

    def test_recordings_with_the_display_shape_resolve(self):
        catalog, source_size, canvas = write_pack(self.root, BOOK)
        meta = self.resolve(catalog, *source_size, name="iPhone Duo Book Pose")
        self.assertEqual((meta["device"], meta["warp_size"], meta["frame_size"]), (BOOK, source_size, "321x241"))
        self.assertEqual((meta["x"], meta["y"], meta["has_mask"], meta["mask_missing"]), (0, 0, True, False))
        self.assertEqual(Path(meta["mask_path"]).name, f"{BOOK}_mask.png")
        self.assertEqual(Path(meta["overlay_path"]).name, f"{BOOK}_overlay.png")
        # Encoders round recordings to even sizes, and other scales keep the shape.
        self.assertEqual(self.resolve(catalog, 400, 280)["warp_size"], (400, 280))
        self.assertEqual(self.resolve(catalog, 200, 139)["warp_size"], (200, 139))

    def test_other_shapes_are_rejected_before_rendering(self):
        catalog, source_size, _ = write_pack(self.root, BOOK)
        for width, height in ((140, 200), (200, 100)):
            with self.assertRaisesRegex(ValueError, f"inner display recording \\(200x140.*this video is {width}x{height}"):
                self.resolve(catalog, width, height)

    def test_rotation_metadata_decides_the_delivered_shape(self):
        catalog, _, _ = write_pack(self.root, BOOK)
        sideways = {"width": 140, "height": 200, "display_rotation": -90}
        self.assertEqual(frames._video_display_size(sideways), (200, 140))
        self.assertEqual(frames._video_display_size({"width": 140, "height": 200, "display_rotation": 180}), (140, 200))
        self.assertEqual(frames._video_display_size({"width": 140, "height": 200}), (140, 200))
        meta = self.resolve(catalog, 140, 200, display_size=frames._video_display_size(sideways))
        self.assertEqual(meta["warp_size"], (200, 140))

    def test_mask_by_color_and_missing_layers(self):
        catalog, source_size, _ = write_pack(self.root, LAPTOP, laptop=True)
        meta = self.resolve(catalog, *source_size, name="iPhone Duo Laptop Pose")
        self.assertEqual(Path(meta["mask_path"]).name, f"{LAPTOP} {COLOR}_mask.png")
        (self.root / f"{LAPTOP}_overlay.png").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "Overlay missing"):
            self.resolve(catalog, *source_size, name=LAPTOP)
        (self.root / f"{LAPTOP} {COLOR}_mask.png").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "Display mask missing"):
            self.resolve(catalog, *source_size, name=LAPTOP)

    def test_layers_follow_a_rescaled_catalog(self):
        plans = []
        for scale in (1, 2):
            root = self.root / str(scale)
            root.mkdir()
            catalog, source_size, _ = write_pack(root, BOOK, scale=scale)
            meta = frames.resolve_frame_metadata(*source_size, root, catalog, color_arg=COLOR, force_device=BOOK)
            with frames._warp_video_assets([meta]):
                layers = meta["warp_layers"]
                for region in layers["regions"]:
                    with Image.open(region["opacity_path"]) as opacity:
                        self.assertEqual(opacity.size, region["box"][2:])
                    with Image.open(region["reflection_path"]) as reflection:
                        self.assertEqual(reflection.size, region["box"][2:])
                work_dir = Path(layers["regions"][0]["opacity_path"]).parent
            self.assertFalse(work_dir.exists())
            self.assertNotIn("warp_layers", meta)
            plans.append(layers)
        small, large = plans
        self.assertEqual(len(small["regions"]), 3)
        self.assertEqual(small["overlay_box"], (200, 60, 13, 13))
        self.assertEqual(large["overlay_box"], (400, 120, 25, 25))
        for one, two in zip(small["regions"], large["regions"]):
            # The same part of the recording, give or take the pixel of slack around each
            # polygon, lands on a canvas region twice the size.
            for a, b in zip(one["source"], two["source"]):
                self.assertLessEqual(abs(a - b), 2)
            for a, b in zip(one["box"], two["box"]):
                self.assertLessEqual(abs(2 * a - b), 3)
            self.assertGreaterEqual(two["work_size"], two["box"][2:])


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe required")
class WarpedVideoRenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def pose(self, name, laptop=False):
        catalog, source_size, canvas = write_pack(self.root, name, laptop=laptop)
        source = self.root / "source.png"
        write_source(source, source_size)
        still, _ = frames.frame_screenshot(source, self.root, catalog, force_device=name, color_arg=COLOR)
        meta = frames.resolve_frame_metadata(*source_size, self.root, catalog, color_arg=COLOR, force_device=name)
        return source, still, meta, canvas

    def clip(self, source, name="clip.mp4"):
        clip = self.root / name
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-framerate", "10",
                        "-i", str(source), "-t", "0.3", "-c:v", "libx264", "-pix_fmt", "yuv444p", "-crf", "4",
                        str(clip)], check=True, capture_output=True)
        return clip, {"duration": 0.3, "fps_rate": "10/1", "audio": False}

    def video_frame(self, source, meta):
        """First frame of the framed stream, before any encoder."""
        output = self.root / "frame.png"
        args = video_args(alpha=True)
        with frames._warp_video_assets([meta]):
            inputs, filters, label, next_index = frames._framed_video_filters(
                source, meta, {"duration": 1, "fps_rate": "1/1", "audio": False}, args, pad_output=False,
            )
            self.assertEqual(next_index, len(inputs) // 2)
            filters.append(f"[{label}]format=rgba[png]")
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs,
                            "-filter_complex", ";".join(filters), "-map", "[png]", "-frames:v", "1", str(output)],
                           check=True, capture_output=True)
        with Image.open(output) as image:
            return image.convert("RGBA")

    def decode(self, video):
        result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video),
                                 "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
                                check=True, capture_output=True)
        meta = frames.probe_video(video)
        return Image.frombytes("RGBA", (meta["width"], meta["height"]), result.stdout)

    def assert_matches_still(self, still, frame):
        self.assertEqual(frame.size, still.size)
        # The hardware's alpha is the output's alpha.
        self.assertLessEqual(ImageChops.difference(still.getchannel("A"), frame.getchannel("A")).getextrema()[1], 1)
        visible = still.getchannel("A").point(lambda value: 255 if value == 255 else 0)
        difference = ImageChops.difference(still.convert("RGB"), frame.convert("RGB"))
        worst = max(ImageChops.multiply(band, visible).getextrema()[1] for band in difference.split())
        # A one-pixel shift of the test ramps would differ by about ten levels.
        self.assertLessEqual(worst, 6)

    def test_book_pose_frame_matches_the_still(self):
        source, still, meta, _ = self.pose(BOOK)
        frame = self.video_frame(source, meta)
        self.assert_matches_still(still, frame)
        # The display is lit, the camera overlay is on top, and the hardware is untouched.
        self.assertGreater(max(frame.getpixel((90, 120))[:3]), 120)
        self.assertLess(max(frame.getpixel((206, 66))[:3]), 60)
        self.assertEqual(frame.getpixel((14, 120)), still.getpixel((14, 120)))
        self.assertEqual(frame.getpixel((0, 0))[3], 0)

    def test_laptop_pose_frame_matches_the_still(self):
        source, still, meta, _ = self.pose(LAPTOP, laptop=True)
        self.assert_matches_still(still, self.video_frame(source, meta))

    def test_export_pads_to_even_dimensions_and_keeps_the_display(self):
        source, still, meta, canvas = self.pose(BOOK)
        clip, video_meta = self.clip(source)
        output = self.root / "framed.mp4"
        frames.render_framed_video(clip, output, meta, video_meta, video_args())
        self.assertNotIn("warp_layers", meta)
        with self.decode(output) as image:
            self.assertEqual(image.size, (canvas[0] + 1, canvas[1] + 1))
            for point in ((90, 120), (160, 120), (240, 110), (14, 120)):
                for got, expected in zip(image.getpixel(point)[:3], still.getpixel(point)[:3]):
                    self.assertLessEqual(abs(got - expected), 24)
            self.assertGreater(min(image.getpixel((2, 2))[:3]), 235)

    def test_alpha_export_and_merge_keep_transparency(self):
        source, still, meta, canvas = self.pose(BOOK)
        clip, video_meta = self.clip(source)
        output = self.root / "framed.mov"
        frames.render_framed_video(clip, output, meta, video_meta, video_args(alpha=True))
        with self.decode(output) as image:
            self.assertEqual(image.size, canvas)
            self.assertEqual(image.getpixel((1, 1))[3], 0)
            self.assertEqual(image.getpixel((90, 120))[3], 255)
            for got, expected in zip(image.getpixel((90, 120))[:3], still.getpixel((90, 120))[:3]):
                self.assertLessEqual(abs(got - expected), 6)
        items = [{"src": clip, "video_meta": dict(video_meta), "frame_meta": dict(meta), "info": {}} for _ in range(2)]
        merged = self.root / "merged.mov"
        result = frames.render_merged_video(items, merged, video_args(alpha=True))
        self.assertEqual((result["width"], result["height"]), (2 * canvas[0] + 4, canvas[1]))
        with self.decode(merged) as image:
            self.assertEqual(image.getpixel((canvas[0] + 2, 120))[3], 0)
            for left in (0, canvas[0] + 4):
                self.assertEqual(image.getpixel((left + 90, 120))[3], 255)
                for got, expected in zip(image.getpixel((left + 90, 120))[:3], still.getpixel((90, 120))[:3]):
                    self.assertLessEqual(abs(got - expected), 6)


if __name__ == "__main__":
    unittest.main()
