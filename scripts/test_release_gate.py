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
import urllib.parse
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


class ReleaseGateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = self._tmp.name
        self.paths = []
        self.check_runs = [{"id": 1, "name": "ci / gate", "conclusion": "success", "app": {"id": 15368}}]
        self.runs = []
        self.jobs = {}
        self.api_error = False
        self.loose_runs = False
        self.status_reads = []
        self.default_branch = "main"
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

    def deploy(self, sha, state="success", created_at="2026-01-01T00:00:00Z", job="develop-status", **run):
        """A release-button run on sha whose cd job `job` ended `state` (latest attempt)."""
        rid = 1000 + len(self.runs)
        self.runs.append({
            "id": rid, "event": "workflow_dispatch", "head_branch": self.default_branch,
            "path": ".github/workflows/release-candidate.yml", "head_sha": sha,
            "conclusion": "success", "created_at": created_at, **run,
        })
        self.jobs[rid] = [{"name": f"cd / {job}", "conclusion": state}]
        return rid

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
        if self.api_error and "/actions/" in path:
            raise RuntimeError("HTTP 500")
        if "check-runs" in path:
            return {"check_runs": self.check_runs}
        if "/statuses" in path:
            self.status_reads.append(path)
            return []
        m = re.fullmatch(r"repos/o/r/actions/workflows/release-candidate\.yml/runs\?(.*)", path)
        if m:
            q = urllib.parse.parse_qs(m.group(1))
            sha = q["head_sha"][0]
            assert q["event"] == ["workflow_dispatch"] and q["branch"] == [self.default_branch], q
            return {"workflow_runs": [r for r in self.runs if r["head_sha"] == sha or self.loose_runs]}
        m = re.fullmatch(r"repos/o/r/actions/runs/([0-9]+)/jobs\?(.*)", path)
        if m:
            assert "filter=latest" in m.group(2), path
            return {"jobs": self.jobs[int(m.group(1))]}
        if path == "repos/o/r":
            return {"default_branch": self.default_branch}
        raise AssertionError(path)

    def run_gate(self, require_e2e=False, sha=None):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = gate.check(
                sha or self.sha(), "1.2.3", require_e2e, self.api, cwd=self.repo, repo="o/r",
            )
        return code, err.getvalue()

    def e2e(self, state="success", created_at="2026-01-02T00:00:00Z", sha=None):
        self.deploy(sha or self.dev_sha, state, created_at, job="e2e-status")

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
        self.runs.clear()
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



    def test_missing_e2e_on_tested_commit_fails(self):
        self.bump()
        code, err = self.run_gate(require_e2e=True)
        self.assertEqual(code, 1)
        self.assertIn(f"{self.dev_sha[:7]} has no green develop e2e: press the release button first", err)


    def test_second_parent_develop_status_ignored(self):
        self.runs.clear()
        self.git("checkout", "-q", "-b", "side")
        self.write("side.js", "side\n")
        self.commit("side")
        self.deploy(self.sha())
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "-m", "merge", "side")
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn(f"no develop deploy before {self.sha()[:7]}", err)

    def test_e2e_only_on_other_commit_fails(self):
        self.write("src.js", "two\n")
        self.commit("code")
        second = self.sha()
        self.deploy(second)
        self.e2e(sha=self.dev_sha)
        code, err = self.run_gate(require_e2e=True)
        self.assertEqual(code, 1)
        self.assertIn(f"{second[:7]} has no green develop e2e", err)



    def assert_no_develop_deploy(self):
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("no develop deploy before", err)










    def test_e2e_job_on_tested_commit_passes(self):
        self.bump()
        self.e2e()
        code, err = self.run_gate(require_e2e=True)
        self.assertEqual(code, 0, err)

    def test_e2e_job_failed_fails(self):
        self.bump()
        self.e2e("failure")
        code, err = self.run_gate(require_e2e=True)
        self.assertEqual(code, 1)
        self.assertIn(f"{self.dev_sha[:7]} has no green develop e2e: press the release button first", err)

    def test_e2e_job_not_required_without_flag(self):
        self.bump()
        code, err = self.run_gate()
        self.assertEqual(code, 0, err)

    def test_non_dispatch_runs_ignored(self):
        for event in ("pull_request", "push", "schedule"):
            self.runs.clear()
            self.deploy(self.dev_sha, event=event)
            self.assert_no_develop_deploy()

    def test_other_workflow_path_ignored(self):
        self.runs.clear()
        self.deploy(self.dev_sha, path=".github/workflows/other.yml")
        self.assert_no_develop_deploy()

    def test_path_with_ref_suffix_counts(self):
        self.runs.clear()
        self.deploy(self.dev_sha, path=".github/workflows/release-candidate.yml@refs/heads/main")
        code, err = self.run_gate()
        self.assertEqual(code, 0, err)

    def test_run_on_other_branch_ignored(self):
        self.runs.clear()
        self.deploy(self.dev_sha, head_branch="feature")
        self.assert_no_develop_deploy()

    def test_run_head_sha_mismatch_ignored(self):
        self.runs.clear()
        self.deploy(self.dev_sha, head_sha="f" * 40)
        self.loose_runs = True
        self.assert_no_develop_deploy()

    def test_develop_job_failed_or_missing_not_tested(self):
        for state in ("failure", "skipped", None):
            self.runs.clear()
            self.deploy(self.dev_sha, state)
            self.assert_no_develop_deploy()
        self.runs.clear()
        self.deploy(self.dev_sha, job="plan")
        self.assert_no_develop_deploy()

    def test_failed_run_with_green_develop_job_counts(self):
        self.runs.clear()
        self.deploy(self.dev_sha, conclusion="failure")
        self.bump()
        code, err = self.run_gate()
        self.assertEqual(code, 0, err)

    def test_rerun_uses_latest_attempt(self):
        self.runs.clear()
        rid = self.deploy(self.dev_sha, "failure")
        self.assert_no_develop_deploy()
        self.jobs[rid] = [{"name": "cd / develop-status", "conclusion": "success"}]
        self.bump()
        code, err = self.run_gate()
        self.assertEqual(code, 0, err)
        self.assertTrue(any("filter=latest" in p for p in self.paths), self.paths)

    def test_default_branch_other_than_main_honoured(self):
        self.default_branch = "trunk"
        self.runs[0]["head_branch"] = "main"
        self.assert_no_develop_deploy()
        self.runs[0]["head_branch"] = "trunk"
        self.bump()
        code, err = self.run_gate()
        self.assertEqual(code, 0, err)

    def test_api_error_fails_closed(self):
        self.api_error = True
        code, err = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn(f"could not verify develop deploys on {self.sha()[:7]}: press the release button first", err)

    def test_forged_status_has_no_effect(self):
        self.runs.clear()
        self.assert_no_develop_deploy()
        self.assertEqual(self.status_reads, [])


if __name__ == "__main__":
    unittest.main()
