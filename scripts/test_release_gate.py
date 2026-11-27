"""Tests for the release-gate action. Run: python3 -m unittest scripts/test_release_gate.py

Each test builds a temp git repo with a `main` branch; the GitHub API is a fake
function passed to gate.check, so nothing touches the network.
"""

import contextlib
import importlib.util
import io
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

GATE = Path(__file__).resolve().parent.parent / ".github" / "actions" / "release-gate" / "gate.py"
spec = importlib.util.spec_from_file_location("gate", GATE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

PKG = '{\n  "name": "x",\n  "version": "%s",\n  "retries": 1,\n  "dependencies": {"a": "%s"}\n}\n'
LOCK = (
    '{\n  "name": "x",\n  "version": "%s",\n  "packages": {\n    "": {\n      "version": "%s"\n    },\n'
    '    "node_modules/a": {\n      "version": "%s"\n    }\n  }\n}\n'
)
APP = '{\n  "expo": {\n    "version": "%s",\n    "supportsTablet": true\n  }\n}\n'
BOT = {"login": "github-actions[bot]"}


class ReleaseGateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = self._tmp.name
        self.paths = []
        self.check_runs = [{"id": 1, "name": "ci / gate", "conclusion": "success", "app": {"id": 15368}}]
        self.statuses = {}
        self.git("init", "-q", "-b", "main")
        self.write_versions("1.2.2", "1.0.0", "1.0.0")
        self.write("src.js", "one\n")
        self.write("critical.js", "critical\n")
        self.write("CHANGELOG.md", "# log\n")
        self.commit("base")
        self.dev_sha = self.sha()
        self.deploy(self.dev_sha)

    def write_versions(self, version, dep, lockdep):
        self.write("package.json", PKG % (version, dep))
        self.write("package-lock.json", LOCK % (version, version, lockdep))
        self.write("app.json", APP % version)

    def bump(self, version="1.2.3"):
        self.write_versions(version, "1.0.0", "1.0.0")
        self.commit("bump")

    def deploy(self, sha, state="success", creator=BOT, created_at="2026-01-01T00:00:00Z", context="cd/develop"):
        self.statuses.setdefault(sha, []).append(
            {"context": context, "state": state, "created_at": created_at, "creator": creator}
        )

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
        self.paths.append(path)
        if "check-runs" in path:
            return {"check_runs": self.check_runs}
        m = re.search(r"commits/([0-9a-f]{40})/statuses", path)
        if m:
            return self.statuses.get(m.group(1), [])
        raise AssertionError(path)

    def run_gate(self, require_e2e=False, sha=None):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = gate.check(
                sha or self.sha(), "1.2.3", require_e2e, self.api, cwd=self.repo, repo="o/r",
            )
        return code, err.getvalue()

    def e2e(self, state="success", creator=BOT, created_at="2026-01-02T00:00:00Z", sha=None):
        self.deploy(sha or self.dev_sha, state, creator, created_at, context="cd/e2e-develop")

    def test_version_only_diff_passes(self):
        self.bump()
        code, err = self.run_gate()
        self.assertEqual(code, 0, err)

    def test_dependency_change_fails(self):
        self.write("package.json", PKG % ("1.2.3", "2.0.0"))
        self.commit("dep")
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn(f"code differs from the last develop deploy {self.dev_sha[:7]}: press the release button first", err)

    def test_lockfile_dependency_version_bump_fails(self):
        self.write_versions("1.2.3", "1.0.0", "9.9.9")
        self.commit("lock dep")
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn(f"code differs from the last develop deploy {self.dev_sha[:7]}: press the release button first", err)

    def test_version_other_than_release_fails(self):
        self.bump("1.2.4")
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn(f"code differs from the last develop deploy {self.dev_sha[:7]}: press the release button first", err)

    def test_bool_to_int_change_fails(self):
        self.bump()
        self.write("app.json", (APP % "1.2.3").replace("true", "1"))
        self.commit("tablet")
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn(f"code differs from the last develop deploy {self.dev_sha[:7]}: press the release button first", err)

    def test_int_to_float_change_fails(self):
        self.bump()
        self.write("package.json", (PKG % ("1.2.3", "1.0.0")).replace('"retries": 1', '"retries": 1.0'))
        self.commit("retries")
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn(f"code differs from the last develop deploy {self.dev_sha[:7]}: press the release button first", err)

    def test_source_change_fails(self):
        self.write("src.js", "two\n")
        self.commit("code")
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn(f"code differs from the last develop deploy {self.dev_sha[:7]}: press the release button first", err)

    def test_rename_into_changeset_fails(self):
        os.makedirs(os.path.join(self.repo, ".changeset"))
        self.git("mv", "critical.js", ".changeset/x.md")
        self.commit("hide")
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn(f"code differs from the last develop deploy {self.dev_sha[:7]}: press the release button first", err)





    def test_changelog_and_changeset_ignored(self):
        self.write("CHANGELOG.md", "# log\nmore\n")
        self.write(".changeset/a.md", "---\n---\n")
        self.commit("docs")
        code, err = self.run_gate()
        self.assertEqual(code, 0, err)





    def test_not_on_main_fails(self):
        self.git("checkout", "-q", "-b", "side")
        self.write("src.js", "side\n")
        self.commit("side")
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("not on main: press the release button first", err)

    def test_ci_gate_not_success_fails(self):
        self.check_runs[0]["conclusion"] = "failure"
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("ci / gate", err)

    def test_ci_gate_from_other_app_fails(self):
        self.check_runs[0]["app"] = {"id": 1}
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("ci / gate", err)

    def test_no_develop_deploy_fails(self):
        self.statuses.clear()
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn(f"no develop deploy before {self.sha()[:7]}: press the release button first", err)

    def test_develop_deploy_beyond_100_commits_fails(self):
        for i in range(100):
            self.write("src.js", f"n{i}\n")
            self.commit(f"c{i}")
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("no develop deploy before", err)

    def test_newest_develop_deploy_is_used(self):
        self.write("src.js", "two\n")
        self.commit("code")
        second = self.sha()
        self.deploy(second)
        self.bump()
        code, err = self.run_gate()
        self.assertEqual(code, 0, err)
        self.write("src.js", "three\n")
        self.commit("more code")
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn(f"code differs from the last develop deploy {second[:7]}: press the release button first", err)

    def test_code_after_develop_deploy_fails(self):
        self.write("src.js", "two\n")
        self.commit("code")
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn(f"code differs from the last develop deploy {self.dev_sha[:7]}: press the release button first", err)

    def test_version_only_after_develop_deploy_passes(self):
        self.bump()
        self.write("CHANGELOG.md", "# log\n1.2.3\n")
        self.write(".changeset/a.md", "---\n---\n")
        self.commit("version")
        code, err = self.run_gate()
        self.assertEqual(code, 0, err)

    def test_develop_status_from_other_creator_ignored(self):
        self.statuses[self.dev_sha][0]["creator"] = {"login": "someone"}
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("no develop deploy before", err)

    def test_failed_develop_status_ignored(self):
        self.statuses[self.dev_sha][0]["state"] = "failure"
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("no develop deploy before", err)

    def test_missing_e2e_on_tested_commit_fails(self):
        self.bump()
        code, err = self.run_gate(require_e2e=True)
        self.assertEqual(code, 1)
        self.assertIn(f"{self.dev_sha[:7]} has no green develop e2e: press the release button first", err)

    def test_e2e_on_tested_commit_passes(self):
        self.bump()
        self.e2e()
        self.e2e("failure", created_at="2026-01-01T00:00:00Z")
        code, err = self.run_gate(require_e2e=True)
        self.assertEqual(code, 0, err)

    def test_e2e_only_on_other_commit_fails(self):
        self.write("src.js", "two\n")
        self.commit("code")
        second = self.sha()
        self.deploy(second)
        self.e2e(sha=self.dev_sha)
        code, err = self.run_gate(require_e2e=True)
        self.assertEqual(code, 1)
        self.assertIn(f"{second[:7]} has no green develop e2e", err)

    def test_newest_e2e_failing_fails(self):
        self.bump()
        self.e2e("failure", created_at="2026-01-03T00:00:00Z")
        self.e2e("success", created_at="2026-01-02T00:00:00Z")
        code, err = self.run_gate(require_e2e=True)
        self.assertEqual(code, 1)

    def test_e2e_status_from_other_creator_fails(self):
        self.bump()
        self.e2e(creator={"login": "someone"})
        code, err = self.run_gate(require_e2e=True)
        self.assertEqual(code, 1)
        self.assertIn("has no green develop e2e: press the release button first", err)


if __name__ == "__main__":
    unittest.main()
