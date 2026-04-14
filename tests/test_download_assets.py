import importlib.machinery
import importlib.util
import shutil
import ssl
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest import mock


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


if __name__ == "__main__":
    unittest.main()
