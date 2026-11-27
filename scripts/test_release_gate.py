"""Tests for the release-gate action. Run: python3 -m unittest scripts/test_release_gate.py

Each test builds a temp git repo with a `main` branch; the GitHub API is a fake
function passed to gate.check, so nothing touches the network.
"""

import contextlib
import importlib.util
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

GATE = Path(__file__).resolve().parent.parent / ".github" / "actions" / "release-gate" / "gate.py"
spec = importlib.util.spec_from_file_location("gate", GATE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

PKG = '{\n  "name": "x",\n  "version": "%s",\n  "dependencies": {"a": "%s"}\n}\n'


class ReleaseGateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = self._tmp.name
        self.ci_conclusion = "success"
        self.statuses = []
        self.git("init", "-q", "-b", "main")
        self.write("package.json", PKG % ("1.2.3", "1.0.0"))
        self.write("package-lock.json", '{\n  "version": "1.2.3"\n}\n')
        self.write("app.json", '{\n  "expo": {\n    "version": "1.2.3"\n  }\n}\n')
        self.write("src.js", "one\n")
        self.write("CHANGELOG.md", "# log\n")
        self.commit("base")
        self.rc_sha = self.sha()
        self.git("tag", "v1.2.3-rc.1")

    def git(self, *args):
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", self.repo, *args],
            check=True, capture_output=True, text=True,
        ).stdout.strip()

    def write(self, name, text):
        p = Path(self.repo, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)

    def sha(self):
        return self.git("rev-parse", "HEAD")

    def api(self, path):
        if "check-runs" in path:
            return {"check_runs": [{"id": 1, "conclusion": self.ci_conclusion}]}
        if "statuses" in path:
            return self.statuses
        raise AssertionError(path)

    def run_gate(self, require_e2e=False, sha=None):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = gate.check(
                sha or self.sha(), "", "1.2.3", require_e2e, self.api, cwd=self.repo, repo="o/r",
            )
        return code, err.getvalue()

    def test_version_only_diff_passes(self):
        self.write("package.json", PKG % ("1.2.4", "1.0.0"))
        self.write("package-lock.json", '{\n  "version": "1.2.4"\n}\n')
        self.write("app.json", '{\n  "expo": {\n    "version": "1.2.4"\n  }\n}\n')
        self.commit("bump")
        code, err = self.run_gate()
        self.assertEqual(code, 0, err)

    def test_dependency_change_fails(self):
        self.write("package.json", PKG % ("1.2.3", "2.0.0"))
        self.commit("dep")
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("code differs from v1.2.3-rc.1: cut a new rc first", err)

    def test_source_change_fails(self):
        self.write("src.js", "two\n")
        self.commit("code")
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("code differs from v1.2.3-rc.1: cut a new rc first", err)

    def test_next_latest_fails(self):
        self.write("CHANGELOG.md", "# log\nmore\n")
        self.commit("next")
        self.git("tag", "v1.2.3-next.2")
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("latest prerelease of 1.2.3 is not an rc: cut a new rc first", err)

    def test_no_prerelease_fails(self):
        self.git("tag", "-d", "v1.2.3-rc.1")
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("cut a new rc first", err)

    def test_changelog_and_changeset_ignored(self):
        self.write("CHANGELOG.md", "# log\nmore\n")
        self.write(".changeset/a.md", "---\n---\n")
        self.commit("docs")
        code, err = self.run_gate()
        self.assertEqual(code, 0, err)

    def test_missing_e2e_status_fails(self):
        code, err = self.run_gate(require_e2e=True)
        self.assertEqual(code, 1)
        self.assertIn("v1.2.3-rc.1 has no green develop e2e: cut a new rc first", err)

    def test_green_e2e_status_passes(self):
        self.statuses = [
            {"context": "cd/e2e-develop", "state": "success", "created_at": "2026-01-02T00:00:00Z"},
            {"context": "cd/e2e-develop", "state": "failure", "created_at": "2026-01-01T00:00:00Z"},
        ]
        code, err = self.run_gate(require_e2e=True)
        self.assertEqual(code, 0, err)

    def test_newest_e2e_status_failing_fails(self):
        self.statuses = [
            {"context": "cd/e2e-develop", "state": "failure", "created_at": "2026-01-02T00:00:00Z"},
            {"context": "cd/e2e-develop", "state": "success", "created_at": "2026-01-01T00:00:00Z"},
        ]
        code, err = self.run_gate(require_e2e=True)
        self.assertEqual(code, 1)

    def test_not_on_main_fails(self):
        self.git("checkout", "-q", "-b", "side")
        self.write("src.js", "side\n")
        self.commit("side")
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("not on main: cut a new rc first", err)

    def test_ci_gate_not_success_fails(self):
        self.ci_conclusion = "failure"
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("ci / gate", err)


if __name__ == "__main__":
    unittest.main()
