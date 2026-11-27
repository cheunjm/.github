"""Tests for sync_app_json. Run: python3 -m unittest scripts/test_sync_app_json.py"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "sync_app_json.py"


class SyncAppJsonTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        (self.dir / "package.json").write_text('{\n  "name": "app",\n  "version": "1.4.0"\n}\n')

    def run_script(self, app_text):
        (self.dir / "app.json").write_text(app_text)
        r = subprocess.run(["python3", str(SCRIPT), "app.json"], cwd=self.dir, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_writes_version_keeps_format(self):
        code, _ = self.run_script('{\n  "expo": {\n    "name": "a",\n    "version": "1.3.0",\n    "slug": "a"\n  }\n}\n')
        self.assertEqual(code, 0)
        self.assertEqual((self.dir / "app.json").read_text(),
                         '{\n  "expo": {\n    "name": "a",\n    "version": "1.4.0",\n    "slug": "a"\n  }\n}\n')

    def test_missing_expo_version_fails(self):
        for text in ['{"expo": {"name": "a"}}\n', '{"name": "a"}\n']:
            with self.subTest(text=text):
                code, out = self.run_script(text)
                self.assertEqual(code, 1)
                self.assertIn("app.json has no expo.version", out)
                self.assertEqual((self.dir / "app.json").read_text(), text)

    def test_non_ascii_kept(self):
        self.run_script('{\n  "expo": {\n    "name": "ü",\n    "version": "0.0.1"\n  }\n}\n')
        self.assertIn("ü", (self.dir / "app.json").read_text())


if __name__ == "__main__":
    unittest.main()
