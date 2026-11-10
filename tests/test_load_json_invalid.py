import importlib.machinery
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path


FRAMES_PATH = Path(__file__).resolve().parents[1] / "frames"
loader = importlib.machinery.SourceFileLoader("frames_load_json", str(FRAMES_PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
frames = importlib.util.module_from_spec(spec)
loader.exec_module(frames)


class LoadJsonInvalidTests(unittest.TestCase):
    def _assets_with(self, root, content: bytes):
        assets = Path(root) / "assets"
        assets.mkdir()
        (assets / "NewFrames.json").write_bytes(content)
        (assets / "version.txt").write_text("4", encoding="utf-8")
        return assets

    def test_non_object_json_fails_cleanly(self):
        for content in (b"null", b"[]", b"123", b'"text"'):
            with self.subTest(content=content):
                with tempfile.TemporaryDirectory() as tmp:
                    assets = self._assets_with(tmp, content)
                    err = io.StringIO()
                    with redirect_stderr(err):
                        with self.assertRaises(SystemExit) as ctx:
                            frames.load_json(assets)
                    self.assertEqual(ctx.exception.code, 1)
                    self.assertIn("Invalid JSON", err.getvalue())
                    self.assertNotIn("Traceback", err.getvalue())

    def test_list_command_with_non_object_json_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            assets = self._assets_with(tmp, b"null")
            env = dict(os.environ, HOME=str(tmp))
            process = subprocess.run(
                [sys.executable, str(FRAMES_PATH), "--assets", str(assets), "list"],
                env=env, capture_output=True, text=True, check=False,
            )
            self.assertEqual(process.returncode, 1)
            self.assertIn("Invalid JSON", process.stderr)
            self.assertNotIn("Traceback", process.stderr)


if __name__ == "__main__":
    unittest.main()
