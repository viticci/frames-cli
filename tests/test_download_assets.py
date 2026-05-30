import importlib.machinery
import importlib.util
import shutil
import ssl
import tempfile
import unittest
import urllib.error
import zipfile
from argparse import Namespace
from pathlib import Path
from unittest import mock

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
FRAMES_PATH = ROOT / "frames"


def load_frames_module():
    loader = importlib.machinery.SourceFileLoader("frames_module", str(FRAMES_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


frames = load_frames_module()


class DownloadAssetsTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.workdir = Path(self.tempdir.name)
        self.zip_path = self.workdir / "assets.zip"
        self.dest_dir = self.workdir / "dest"
        self._make_assets_zip(self.zip_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def _make_assets_zip(self, zip_path):
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("Frames/NewFrames.json", '{"version": 4}')
            zf.writestr("Frames/version.txt", "4")
            zf.writestr("Frames/iPhone 16 Pro.png", "png-data")

    def _copy_zip_for_urllib(self, url, filename, reporthook=None):
        shutil.copy2(self.zip_path, filename)
        if reporthook is not None:
            reporthook(1, 1, 1)
        return filename, {}

    def _copy_zip_for_curl(self, filename, curl_path=None):
        shutil.copy2(self.zip_path, filename)

    def test_download_assets_uses_urllib_when_available(self):
        with mock.patch("urllib.request.urlretrieve", side_effect=self._copy_zip_for_urllib) as urlretrieve:
            ok = frames.download_assets(self.dest_dir)

        self.assertTrue(ok)
        urlretrieve.assert_called_once()
        self.assertTrue((self.dest_dir / "NewFrames.json").exists())
        self.assertTrue((self.dest_dir / "iPhone 16 Pro.png").exists())

    def test_download_assets_falls_back_to_curl_on_ssl_error(self):
        ssl_error = urllib.error.URLError(
            ssl.SSLCertVerificationError("certificate verify failed")
        )

        with (
            mock.patch("urllib.request.urlretrieve", side_effect=ssl_error),
            mock.patch.object(frames.shutil, "which", return_value="/usr/bin/curl"),
            mock.patch.object(frames, "_download_with_curl", side_effect=self._copy_zip_for_curl) as curl_download,
        ):
            ok = frames.download_assets(self.dest_dir)

        self.assertTrue(ok)
        curl_download.assert_called_once()
        self.assertTrue((self.dest_dir / "NewFrames.json").exists())

    def test_download_assets_does_not_fallback_for_non_ssl_errors(self):
        network_error = urllib.error.URLError("temporary failure in name resolution")

        with (
            mock.patch("urllib.request.urlretrieve", side_effect=network_error),
            mock.patch.object(frames, "_download_with_curl") as curl_download,
        ):
            ok = frames.download_assets(self.dest_dir)

        self.assertFalse(ok)
        curl_download.assert_not_called()


class ColorArgumentTests(unittest.TestCase):
    def test_parse_per_input_colors_requires_matching_count(self):
        self.assertEqual(
            frames.parse_per_input_colors("Silver, random,default", 3),
            ["Silver", "random", "default"],
        )
        with self.assertRaises(ValueError):
            frames.parse_per_input_colors("Silver,random", 3)

    def test_color_and_colors_are_mutually_exclusive(self):
        frames.validate_color_args(Namespace(color="Silver", colors=None))
        with self.assertRaises(ValueError):
            frames.validate_color_args(Namespace(color="Silver", colors="random"))

    def test_random_color_resolves_per_call(self):
        with mock.patch.object(frames.random, "choice", side_effect=["Silver", "Space Black"]):
            first = frames.get_color("MacBook Pro M5 14", "random")
            second = frames.get_color("MacBook Pro M5 14", "random")
        self.assertEqual(first, "Silver")
        self.assertEqual(second, "Space Black")

    def test_strict_invalid_color_fails(self):
        with self.assertRaises(ValueError):
            frames.get_color("MacBook Pro M5 14", "Cosmic Orange", strict=True)


class VideoHelperTests(unittest.TestCase):
    def _version_process(self, tool, version):
        return frames.subprocess.CompletedProcess(
            [tool, "-version"],
            0,
            stdout=f"{tool} version {version} Copyright\n",
            stderr="",
        )

    def test_require_ffmpeg_tools_reports_missing_tools(self):
        def fake_which(tool):
            return None if tool == "ffmpeg" else f"/usr/bin/{tool}"

        with mock.patch.object(frames.shutil, "which", side_effect=fake_which):
            with self.assertRaises(RuntimeError) as cm:
                frames.require_ffmpeg_tools()

        self.assertIn("Missing required video tool(s): ffmpeg", str(cm.exception))
        self.assertIn("on PATH", str(cm.exception))

    def test_require_ffmpeg_tools_rejects_old_ffmpeg_version(self):
        def fake_run(cmd, text, capture_output, check):
            tool = cmd[0]
            version = "4.4" if tool == "ffmpeg" else "8.1"
            return self._version_process(tool, version)

        with (
            mock.patch.object(frames.shutil, "which", return_value="/usr/bin/tool"),
            mock.patch.object(frames.subprocess, "run", side_effect=fake_run),
        ):
            with self.assertRaises(RuntimeError) as cm:
                frames.require_ffmpeg_tools()

        self.assertIn("ffmpeg 5.1+ is required", str(cm.exception))
        self.assertIn("found 4.4", str(cm.exception))

    def test_require_ffmpeg_tools_rejects_old_ffprobe_version(self):
        def fake_run(cmd, text, capture_output, check):
            tool = cmd[0]
            version = "8.1" if tool == "ffmpeg" else "4.4"
            return self._version_process(tool, version)

        with (
            mock.patch.object(frames.shutil, "which", return_value="/usr/bin/tool"),
            mock.patch.object(frames.subprocess, "run", side_effect=fake_run),
        ):
            with self.assertRaises(RuntimeError) as cm:
                frames.require_ffmpeg_tools()

        self.assertIn("ffprobe 5.1+ is required", str(cm.exception))
        self.assertIn("found 4.4", str(cm.exception))

    def test_ffmpeg_progress_cmd_enables_machine_progress(self):
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", "in.mp4", "out.mp4"]
        progress_cmd = frames._ffmpeg_progress_cmd(cmd)

        self.assertEqual(progress_cmd[:4], ["ffmpeg", "-progress", "pipe:1", "-nostats"])
        self.assertIn("-hide_banner", progress_cmd)

    def test_progress_time_formats_short_and_long_durations(self):
        self.assertEqual(frames._format_progress_time(0.5), "0.5s")
        self.assertEqual(frames._format_progress_time(75), "01:15")
        self.assertEqual(frames._format_progress_time(3661), "1:01:01")

    def test_run_ffmpeg_non_tty_uses_single_captured_run(self):
        completed = frames.subprocess.CompletedProcess(["ffmpeg"], 0, stdout="", stderr="")
        with (
            mock.patch.object(frames.sys.stdout, "isatty", return_value=False),
            mock.patch.object(frames.subprocess, "run", return_value=completed) as run,
        ):
            result = frames._run_ffmpeg(["ffmpeg", "-version"], progress_label="Framing demo.mp4", progress_total=10)

        self.assertEqual(result.returncode, 0)
        run.assert_called_once()

    def test_video_tools_install_hint_uses_homebrew_on_macos(self):
        with mock.patch.object(frames.sys, "platform", "darwin"):
            self.assertEqual(frames._video_tools_install_hint("Missing required video tool(s): ffmpeg."), "brew install ffmpeg")
            self.assertEqual(frames._video_tools_install_hint("ffmpeg 5.1+ is required for video framing; found 4.4."), "brew upgrade ffmpeg")

    def test_probe_video_parses_first_video_and_audio_stream(self):
        payload = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 3024,
                    "height": 1964,
                    "avg_frame_rate": "1404/25",
                    "duration": "14.5",
                },
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {"duration": "14.583333"},
        }
        with mock.patch.object(frames, "_run_json_command", return_value=payload):
            info = frames.probe_video(Path("sample.mp4"))

        self.assertEqual(info["width"], 3024)
        self.assertEqual(info["height"], 1964)
        self.assertAlmostEqual(info["fps"], 56.16)
        self.assertTrue(info["audio"])
        self.assertEqual(info["audio_codec"], "aac")

    def test_probe_video_rejects_invalid_duration(self):
        payload = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 3024,
                    "height": 1964,
                    "avg_frame_rate": "30/1",
                }
            ],
            "format": {"duration": "nan"},
        }
        with mock.patch.object(frames, "_run_json_command", return_value=payload):
            with self.assertRaises(ValueError):
                frames.probe_video(Path("sample.mp4"))

    def test_probe_video_rejects_invalid_dimensions(self):
        payload = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 0,
                    "height": 1964,
                    "avg_frame_rate": "30/1",
                    "duration": "3",
                }
            ],
            "format": {"duration": "3"},
        }
        with mock.patch.object(frames, "_run_json_command", return_value=payload):
            with self.assertRaises(ValueError):
                frames.probe_video(Path("sample.mp4"))

    def test_probe_video_normalizes_invalid_frame_rate(self):
        payload = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 3024,
                    "height": 1964,
                    "avg_frame_rate": "0/0",
                    "duration": "3",
                }
            ],
            "format": {"duration": "3"},
        }
        with mock.patch.object(frames, "_run_json_command", return_value=payload):
            info = frames.probe_video(Path("sample.mp4"))

        self.assertEqual(info["fps"], 30.0)
        self.assertEqual(info["fps_rate"], "30/1")

    def test_video_info_returns_probe_and_frame_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp)
            Image.new("RGBA", (1350, 2760)).save(assets / "iPhone 17 Pro Portrait Silver.png")
            device_dict = {
                "1206": {
                    "name": "iPhone 17 Portrait",
                    "overlap": {
                        "2622": {
                            "name": "iPhone 17 Portrait",
                            "x": "72",
                            "y": "69",
                            "colors": "yes",
                            "mask": "yes",
                            "physicalHeight": 149.6,
                        }
                    },
                },
                "variants": {
                    "iPhone 17 Pro Portrait": {
                        "name": "iPhone 17 Pro Portrait",
                        "x": "72",
                        "y": "69",
                        "colors": "yes",
                        "mask": "yes",
                        "physicalHeight": 149.6,
                    }
                },
            }
            video_meta = {
                "width": 1206,
                "height": 2622,
                "duration": 5.5,
                "fps": 60.0,
                "fps_rate": "60/1",
                "codec": "hevc",
                "audio": True,
                "audio_codec": "aac",
            }

            with mock.patch.object(frames, "probe_video", return_value=video_meta):
                info = frames._video_info_for_path(
                    Path("demo.mp4"),
                    assets,
                    device_dict,
                    color_arg="Silver",
                    strict_color=True,
                )

        self.assertEqual(info["device"], "iPhone 17 Pro Portrait")
        self.assertEqual(info["primary_match"], "iPhone 17 Portrait")
        self.assertEqual(info["dimensions"], "1206x2622")
        self.assertEqual(info["duration"], 5.5)
        self.assertEqual(info["codec"], "hevc")
        self.assertEqual(info["audio_codec"], "aac")
        self.assertEqual(info["color"], "Silver")
        self.assertEqual(info["frame_size"], "1350x2760")

    def test_background_color_rejects_invalid_hex(self):
        self.assertEqual(frames._background_color("#f5f5f5"), "0xf5f5f5")
        with self.assertRaises(ValueError):
            frames._background_color("#zzzzzz")

    def test_parser_recognizes_video_info_command(self):
        parser = frames.build_parser()
        args = parser.parse_args(["video-info", "--colors", "Silver,random", "a.mp4", "b.mp4"])
        self.assertEqual(args.cmd, "video-info")
        self.assertEqual(args.colors, "Silver,random")
        self.assertEqual(args.files, ["a.mp4", "b.mp4"])

    def test_video_path_gathering_is_top_level_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.mp4").write_text("")
            (root / "b.mov").write_text("")
            (root / "c.png").write_text("")
            nested = root / "nested"
            nested.mkdir()
            (nested / "d.mp4").write_text("")

            gathered = frames._gather_video_paths([root])

        self.assertEqual([p.name for p in gathered], ["a.mp4", "b.mov"])

    def test_merge_layout_uses_physical_scaling_and_bottom_alignment(self):
        items = [
            {"frame_meta": {"frame_width": 3860, "frame_height": 2540, "physicalHeight": 254.1}},
            {"frame_meta": {"frame_width": 3000, "frame_height": 2300, "physicalHeight": 215.5}},
        ]
        width, height, layout = frames.compute_video_merge_layout(items, spacing=60, no_scale=False)

        self.assertEqual(height, 2540)
        self.assertEqual(layout[0]["scale_factor"], 1.0)
        self.assertLess(layout[1]["scale_factor"], 1.0)
        self.assertEqual(layout[1]["y"], height - layout[1]["height"])
        self.assertEqual(width, layout[0]["width"] + 60 + layout[1]["width"])

    def test_video_output_path_accepts_single_explicit_file(self):
        args = Namespace(output="/tmp/out/custom.mov", alpha=True, codec="h264", background="white")
        out = frames._video_output_path(Path("/tmp/in/demo.mp4"), args, multiple=False)
        self.assertEqual(out, Path("/tmp/out/custom.mov"))


class FrameMetadataTests(unittest.TestCase):
    def test_resolve_frame_metadata_returns_frame_and_resize_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp)
            Image.new("RGBA", (3000, 2300)).save(assets / "iPad Pro 2024 13 Landscape.png")
            device_dict = {
                "3200": {
                    "name": "iPad Pro 2024 13 Landscape",
                    "resizeWidth": 2752,
                    "x": "124",
                    "y": "118",
                    "physicalHeight": 215.5,
                }
            }

            meta = frames.resolve_frame_metadata(
                3200,
                2400,
                assets,
                device_dict,
            )

        self.assertEqual(meta["device"], "iPad Pro 2024 13 Landscape")
        self.assertEqual(meta["frame_size"], "3000x2300")
        self.assertEqual(meta["resize_width"], 2752)
        self.assertEqual(meta["resize_height"], 2064)
        self.assertIsNone(meta["color"])


if __name__ == "__main__":
    unittest.main()
