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

    def test_only_version_value_changes(self):
        text = ('{\n  "name": "top",\n  "version": "9.9.9",\n  "expo": {\n    "version": "1.3.0",\n'
                '    "platforms": ["ios", "android"],\n    "extra": {"version": "x", "a": [1, 2]},\n'
                '    "name": "a"\n  }\n}\n')
        code, _ = self.run_script(text)
        self.assertEqual(code, 0)
        self.assertEqual((self.dir / "app.json").read_text(), text.replace('"1.3.0"', '"1.4.0"'))

    def test_four_space_and_no_trailing_newline_untouched(self):
        text = '{"expo":{"version":"0.1.0","x":[ 1,2 ]}}'
        self.run_script(text)
        self.assertEqual((self.dir / "app.json").read_text(), text.replace("0.1.0", "1.4.0"))

    def test_duplicate_expo_version_fails(self):
        code, out = self.run_script('{"expo": {"version": "1.0.0", "version": "1.1.0"}}\n')
        self.assertEqual(code, 1)
        self.assertIn("ambiguous", out)

    def test_non_ascii_kept(self):
        self.run_script('{\n  "expo": {\n    "name": "ü",\n    "version": "0.0.1"\n  }\n}\n')
        self.assertIn("ü", (self.dir / "app.json").read_text())


SCRIPTS = Path(__file__).resolve().parent


class VersionScriptTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def prepare(self, value):
        env_file = self.dir / "github_env"
        env_file.write_text("")
        env = {"PATH": "/usr/bin:/bin", "APP_JSON_INPUT": value, "GITHUB_ENV": str(env_file)}
        r = subprocess.run(["bash", str(SCRIPTS / "version_prepare.sh")], env=env, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr, env_file.read_text()

    def test_prepare_exports_app_json_and_script(self):
        code, _, env = self.prepare("apps/mobile/app.json")
        self.assertEqual(code, 0)
        self.assertIn("APP_JSON=apps/mobile/app.json\n", env)
        self.assertIn("VERSION_SCRIPT=%s/version_with_app_json.sh\n" % SCRIPTS, env)

    def test_prepare_rejects_bad_paths(self):
        for bad in ["", "../app.json", "a/../b.json", "/etc/app.json", "a b.json", "a;b.json", "$(x).json"]:
            with self.subTest(bad=bad):
                code, out, env = self.prepare(bad)
                self.assertEqual(code, 1)
                self.assertIn("app-json must be", out)
                self.assertEqual(env, "")

    def test_version_script_fails_without_app_json(self):
        r = subprocess.run(["bash", str(SCRIPTS / "version_with_app_json.sh")], env={"PATH": "/usr/bin:/bin"},
                           capture_output=True, text=True, cwd=self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("APP_JSON is empty", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
