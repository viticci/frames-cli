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
sys.path.insert(0, str(ROOT / "scripts"))  # the folded builder imports its sibling
try:
    folded = load_module("build_duo_folded_video", ROOT / "scripts/build_duo_folded_assets.py")
finally:
    sys.path.remove(str(ROOT / "scripts"))

BOOK = "iPhone Duo Inner Partially Open Landscape"
LAPTOP = "iPhone Duo Inner Partially Open Portrait"
COLOR = "Star White"
RANGES = [[0, 0, 10, 30], [10, 30, 60, 90], [60, 90, 255, 255]]
CAMERA_COLORS = ((6, 6, 8), (52, 44, 40), (214, 222, 236))
HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def triangle(length, period):
    return bytes(round(255 * abs((i % period) / (period / 2) - 1)) for i in range(length))


def write_source(path, size, level=None):
    """Steep ramps, so a one-pixel shift shows while resampling kernels still agree; or one gray level."""
    if level is not None:
        Image.new("RGB", size, (level, level, level)).save(path)
        return
    width, height = size
    red = Image.frombytes("L", (width, 1), triangle(width, 96)).resize(size)
    green = Image.frombytes("L", (1, height), triangle(height, 80)).resize(size)
    Image.merge("RGB", (red, green, Image.new("L", size, 90))).save(path)


def write_pack(root, name, scale=1, laptop=False):
    """A small three-region pose built like the real ones: minified, with extents, a
    reflection span, and three camera layers, on a canvas with odd dimensions."""
    canvas = (321 * scale, 241 * scale)
    if laptop:
        source_size = (280, 400)
        before = [(0, 0), (1, 0), (0, 0.5), (1, 0.5), (0, 0.58), (1, 0.58), (0, 1), (1, 1)]
        after = [(60, 16), (260, 16), (60, 150), (260, 150), (52, 166), (268, 166), (24, 224), (296, 224)]
        quads = [(0, 1, 3, 2), (2, 3, 5, 4), (4, 5, 7, 6)]
        reflection, span = [0, 0, 0, 0, 0, 9, 14, 6, 2, 2], [0.5, 9.5]
    else:
        source_size = (400, 280)
        before = [(0, 0), (0.47, 0), (0.53, 0), (1, 0), (0, 1), (0.47, 1), (0.53, 1), (1, 1)]
        after = [(30, 18), (150, 40), (170, 40), (290, 18), (30, 222), (150, 200), (170, 200), (290, 222)]
        quads = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6)]
        reflection, span = [0, 0, 0, 0, 2, 6, 10, 12, 12, 12], [1.25, 9]
    after = [(x * scale + 0.37, y * scale - 0.21) for x, y in after]
    regions = []
    for quad in quads:
        polygon = [after[i] for i in quad]
        region = {"polygon": polygon,
                  "inverse": folded.inverse_perspective(polygon, [before[i] for i in quad], canvas)}
        scales = folded.region_scales(region, source_size)
        region["extent"] = [round(scales[2] * source_size[0], 2), round(scales[3] * source_size[1], 2)]
        regions.append(region)
    warp = {"inputSizes": [list(source_size)], "regions": regions, "reflections": {COLOR: reflection},
            "reflectionSpan": span, "camera": {"x": 200 * scale, "y": 60 * scale, "blendIf": RANGES}}
    if laptop:
        warp.update(blend="normal", reflectionAxis="y")
    entry = {"name": name, "x": "0", "y": "0", "mask": "yes", "colors": "yes", "warp": warp}

    body = (8 * scale, 6 * scale, canvas[0] - 8 * scale, canvas[1] - 6 * scale)
    shade = Image.linear_gradient("L").resize(canvas).point(lambda value: 20 + value // 3)
    frame = Image.merge("RGBA", (shade, shade, shade, Image.new("L", canvas)))
    alpha = Image.new("L", canvas)
    ImageDraw.Draw(alpha).rounded_rectangle(body, radius=20 * scale, fill=255)
    frame.putalpha(alpha.filter(ImageFilter.GaussianBlur(0.6)))
    frame.save(root / f"{name} {COLOR}.png")
    # The mask reaches past the slanted polygon edges, as the real ones do.
    mask = Image.new("L", canvas)
    xs, ys = [x for x, _ in after], [y for _, y in after]
    ImageDraw.Draw(mask).rounded_rectangle(
        (min(xs) + 3 * scale, min(ys) + 3 * scale, max(xs) - 3 * scale, max(ys) - 3 * scale),
        radius=12 * scale, fill=255,
    )
    mask.filter(ImageFilter.GaussianBlur(0.8)).save(root / f"{name}_mask.png")
    side = 12 * scale
    strip = Image.new("RGBA", (side * len(RANGES), side))
    for index, color in enumerate(CAMERA_COLORS):
        ImageDraw.Draw(strip).ellipse((index * side + 1, 1, (index + 1) * side - 2, side - 2), fill=(*color, 230))
    strip.save(root / f"{name}_camera.png")
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
        catalog, source_size, _ = write_pack(self.root, BOOK)
        meta = self.resolve(catalog, *source_size, name="iPhone Duo Book Pose")
        self.assertEqual((meta["device"], meta["warp_size"], meta["frame_size"]), (BOOK, source_size, "321x241"))
        self.assertEqual((meta["x"], meta["y"], meta["has_mask"], meta["mask_missing"]), (0, 0, True, False))
        self.assertEqual(Path(meta["mask_path"]).name, f"{BOOK}_mask.png")
        self.assertEqual(Path(meta["camera_path"]).name, f"{BOOK}_camera.png")
        # Encoders round recordings to even sizes, and other scales keep the shape.
        self.assertEqual(self.resolve(catalog, 200, 140)["warp_size"], (200, 140))
        self.assertEqual(self.resolve(catalog, 400, 278)["warp_size"], (400, 278))

    def test_other_shapes_are_rejected_before_rendering(self):
        catalog, _, _ = write_pack(self.root, BOOK)
        for width, height in ((280, 400), (400, 200)):
            with self.assertRaisesRegex(ValueError, f"inner display recording \\(400x280.*this video is {width}x{height}"):
                self.resolve(catalog, width, height)

    def test_rotation_metadata_decides_the_delivered_shape(self):
        catalog, _, _ = write_pack(self.root, BOOK)
        sideways = {"width": 280, "height": 400, "display_rotation": -90}
        self.assertEqual(frames._video_display_size(sideways), (400, 280))
        self.assertEqual(frames._video_display_size({"width": 280, "height": 400, "display_rotation": 180}), (280, 400))
        self.assertEqual(frames._video_display_size({"width": 280, "height": 400}), (280, 400))
        meta = self.resolve(catalog, 280, 400, display_size=frames._video_display_size(sideways))
        self.assertEqual(meta["warp_size"], (400, 280))

    def test_missing_layers_and_incomplete_entries_are_reported(self):
        catalog, source_size, _ = write_pack(self.root, LAPTOP, laptop=True)
        meta = self.resolve(catalog, *source_size, name="iPhone Duo Laptop Pose")
        warp = catalog["variants"][LAPTOP]["warp"]
        regions = warp.pop("regions")
        with self.assertRaisesRegex(ValueError, "incomplete warp entry"):
            with frames._warp_video_assets([meta]):
                pass
        warp["regions"] = regions
        reflections, warp["reflections"] = warp["reflections"], None
        with self.assertRaisesRegex(ValueError, "incomplete warp entry"):
            with frames._warp_video_assets([meta]):
                pass
        warp["reflections"] = reflections
        sizes, warp["inputSizes"] = warp["inputSizes"], [[0, 400]]
        with self.assertRaisesRegex(ValueError, "incomplete warp entry"):
            self.resolve(catalog, *source_size, name=LAPTOP)
        warp["inputSizes"] = sizes
        (self.root / f"{LAPTOP}_camera.png").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "Camera layers missing"):
            self.resolve(catalog, *source_size, name=LAPTOP)
        (self.root / f"{LAPTOP}_mask.png").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "Display mask missing"):
            self.resolve(catalog, *source_size, name=LAPTOP)
        del warp["inputSizes"]
        with self.assertRaisesRegex(ValueError, "incomplete warp entry"):
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
                tile = layers["tile"]
                for key in ("opacity_path", "reflection_path"):
                    with Image.open(layers[key]) as layer:
                        self.assertEqual(layer.size, tile[2:])
                self.assertEqual(layers["draft_size"], (2 * tile[2], 2 * tile[3]))
                with Image.open(layers["coverage_path"]) as layer:
                    self.assertEqual(layer.size, layers["draft_size"])
                for region in layers["regions"]:
                    with Image.open(region["clip_path"]) as clip:
                        self.assertEqual(clip.size, region["box"][2:])
                    self.assertGreaterEqual(region["work_size"], region["box"][2:])
                work_dir = Path(layers["opacity_path"]).parent
            self.assertFalse(work_dir.exists())
            self.assertNotIn("warp_layers", meta)
            plans.append(layers)
        small, large = plans
        self.assertEqual(len(small["regions"]), 3)
        self.assertEqual(small["camera"]["box"], (200, 60, 12, 12))
        self.assertEqual(large["camera"]["box"], (400, 120, 24, 24))
        self.assertEqual(large["camera"]["ranges"], [tuple(levels) for levels in RANGES])
        # The same display lands on a canvas twice the size; the filter's apron and the
        # mask's soft edge keep their width.
        for a, b in zip(small["tile"], large["tile"]):
            self.assertLessEqual(abs(2 * a - b), 16)
        for one, two in zip(small["regions"], large["regions"]):
            for a, b in zip(one["box"], two["box"]):
                self.assertLessEqual(abs(2 * a - b), 32)
            # A larger canvas shows more of the recording's detail, up to all of it.
            self.assertLess(one["detail"][0], two["detail"][0])
            self.assertLessEqual(two["detail"], (400, 280))


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe required")
class WarpedVideoRenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def pose(self, name, laptop=False, level=None):
        catalog, source_size, canvas = write_pack(self.root, name, laptop=laptop)
        source = self.root / "source.png"
        write_source(source, source_size, level)
        still, _ = frames.frame_screenshot(source, self.root, catalog, force_device=name, color_arg=COLOR)
        meta = frames.resolve_frame_metadata(*source_size, self.root, catalog, color_arg=COLOR, force_device=name)
        return source, still, meta, canvas

    def clip(self, source, name="clip.mp4"):
        clip = self.root / name
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-framerate", "10",
                        "-i", str(source), "-t", "0.3", "-c:v", "libx264", "-pix_fmt", "yuv444p", "-crf", "4",
                        str(clip)], check=True, capture_output=True)
        return clip, {"duration": 0.3, "fps_rate": "10/1", "audio": False}

    def video_frame(self, source, meta, **options):
        """First frame of the framed stream, before any encoder."""
        output = self.root / "frame.png"
        args = video_args(**(options or {"alpha": True}))
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

    def assert_matches_still(self, still, frame, limit=12):
        self.assertEqual(frame.size, still.size)
        # The hardware's alpha is the output's alpha.
        self.assertLessEqual(ImageChops.difference(still.getchannel("A"), frame.getchannel("A")).getextrema()[1], 1)
        visible = still.getchannel("A").point(lambda value: 255 if value == 255 else 0)
        difference = ImageChops.difference(still.convert("RGB"), frame.convert("RGB"))
        worst = ImageChops.multiply(
            ImageChops.lighter(ImageChops.lighter(*difference.split()[:2]), difference.split()[2]), visible)
        self.assertLessEqual(worst.getextrema()[1], limit)
        # Resampling differs by a few levels on a few edge pixels. A one-pixel shift of the
        # test ramps would put most of the display's 40,000 pixels over this.
        self.assertLessEqual(sum(worst.histogram()[5:]), 80)

    def test_book_pose_frame_matches_the_still(self):
        source, still, meta, _ = self.pose(BOOK)
        frame = self.video_frame(source, meta)
        self.assert_matches_still(still, frame)
        # The display is lit, the hardware is untouched, and the canvas corner is clear.
        self.assertGreater(max(frame.getpixel((90, 120))[:3]), 100)
        self.assertEqual(frame.getpixel((14, 120)), still.getpixel((14, 120)))
        self.assertEqual(frame.getpixel((0, 0))[3], 0)

    def test_laptop_pose_frame_matches_the_still(self):
        source, still, meta, _ = self.pose(LAPTOP, laptop=True)
        self.assert_matches_still(still, self.video_frame(source, meta))

    def test_opaque_background_matches_the_flattened_still(self):
        source, still, meta, _ = self.pose(BOOK)
        # ProRes keeps full chroma, so the comparison is not blurred by 4:2:0 subsampling.
        frame = self.video_frame(source, meta, background="#204060", alpha=True)
        flat = Image.alpha_composite(Image.new("RGBA", still.size, "#204060"), still)
        for got, expected in zip(frame.getpixel((0, 0)), (0x20, 0x40, 0x60, 255)):
            self.assertLessEqual(abs(got - expected), 1)
        self.assert_matches_still(flat, frame)

    def test_camera_layers_follow_the_brightness_below(self):
        seen = []
        for level in (0, 20, 45, 75, 255):
            source, still, meta, _ = self.pose(BOOK, level=level)
            frame = self.video_frame(source, meta)
            self.assert_matches_still(still, frame, limit=6)
            seen.append(frame.getpixel((206, 66))[:3])
        # Black, dark, and light content each bring out their own layer, with blends between.
        self.assertEqual(len(set(seen)), len(seen))
        self.assertGreater(min(seen[4]), 200)

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
