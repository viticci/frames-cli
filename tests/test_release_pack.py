import contextlib
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


frames = load_module("frames_release_pack", ROOT / "frames")
release = load_module("release_pack", ROOT / "scripts/release_pack.py")

POSE = "iPhone Duo Inner Partially Open Landscape"


class ReleasePackTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.base = self.make_pack("base", {"100": {"name": "Phone", "x": "1", "y": "1"}, "variants": {}}, "4.2.1")
        catalog = json.loads((self.base / "NewFrames.json").read_text(encoding="utf-8"))
        catalog["variants"][POSE] = {"name": POSE, "x": "0", "y": "0", "warp": {"regions": [[0.5, 1e-05]]}}
        # Builders copy the base pack, so a built pack still carries the old version.
        self.built = self.make_pack("built", catalog, "4.2.1")
        for suffix in (" Night Sky.png", "_mask.png", "_overlay.png"):
            Image.new("RGBA", (4, 4), "black").save(self.built / (POSE + suffix))

    def make_pack(self, name, catalog, version):
        folder = self.root / name
        folder.mkdir()
        (folder / "NewFrames.json").write_bytes(release.dump_catalog(catalog))
        (folder / "version.txt").write_text(version, encoding="utf-8")
        (folder / "Apple Design Resources License.rtf").write_text("license", encoding="utf-8")
        Image.new("RGBA", (4, 4), "red").save(folder / "Phone.png")
        return folder

    def run_release(self, tag="out"):
        return release.release_pack(self.built, self.base, "4.2.2", [POSE],
                                    self.root / tag, self.root / (tag + ".zip"))

    def test_release_zip_is_reproducible_and_installs_through_frames_setup(self):
        summary = self.run_release()
        self.assertEqual((summary["pngs"], summary["unchanged_files"], len(summary["new_files"])), (4, 2, 3))
        self.assertEqual((self.built / "version.txt").read_text(encoding="utf-8"), "4.2.1")
        self.assertEqual(self.run_release("again")["sha256"], summary["sha256"])
        # The published ZIP of the previous pack works as the base too.
        release.write_archive(self.base, self.root / "base.zip")
        self.base = self.root / "base.zip"
        self.assertEqual(self.run_release("from-zip")["sha256"], summary["sha256"])

        # Guided setup downloads the ZIP, extracts it, and saves the folder typed at its prompt.
        installed, config = self.root / "installed", self.root / "config" / "config.json"
        with mock.patch.object(frames, "ASSETS_URL", Path(summary["archive"]).as_uri()), \
                mock.patch.object(frames, "CONFIG_DIR", config.parent), \
                mock.patch.object(frames, "CONFIG_FILE", config), \
                mock.patch.object(frames, "offer_video_tools_setup"), \
                mock.patch("builtins.input", return_value=str(installed)), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(frames.guided_setup())
        self.assertEqual(json.loads(config.read_text(encoding="utf-8")), {"assets_path": str(installed.resolve())})
        self.assertEqual(frames.check_assets_version(installed), (True, 4))
        self.assertEqual((installed / "version.txt").read_bytes(), b"4.2.2")
        self.assertEqual(release.read_pack(installed), release.read_pack(self.root / "out"))
        self.assertIn("iPhone Duo Book Pose", frames.build_device_name_index(frames.load_json(installed)))

    def test_release_stops_when_the_pack_changes_what_already_shipped(self):
        def recolor():
            Image.new("RGBA", (4, 4), "blue").save(self.built / "Phone.png")

        def edit_catalog(change):
            def apply():
                catalog = json.loads((self.built / "NewFrames.json").read_text(encoding="utf-8"))
                change(catalog)
                (self.built / "NewFrames.json").write_bytes(release.dump_catalog(catalog))
            return apply

        cases = {
            "Changed since": recolor,
            "Missing from": lambda: (self.built / "Phone.png").unlink(),
            "changes more than": edit_catalog(lambda catalog: catalog["100"].update(x="2")),
            "Expected added variants": edit_catalog(lambda catalog: catalog["variants"].update(Extra={"name": "Extra"})),
            "not valid JSON": edit_catalog(lambda catalog: catalog["variants"][POSE]["warp"].update(bad=float("nan"))),
            "does not belong": lambda: (self.built / "notes.png").write_bytes(b""),
        }
        for message, damage in cases.items():
            with self.subTest(message=message):
                originals = {path: path.read_bytes() for path in self.built.iterdir()}
                damage()
                with self.assertRaisesRegex(ValueError, message):
                    self.run_release(message)
                self.assertFalse((self.root / message).exists())
                for path in self.built.iterdir():
                    path.unlink()
                for path, data in originals.items():
                    path.write_bytes(data)


if __name__ == "__main__":
    unittest.main()
