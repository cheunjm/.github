"""Tests for sync-secrets.py. Run: python3 -m unittest scripts/test_sync_secrets.py

Fake `op` and `gh` executables on PATH record their argv and stdin, so the
tests check exactly what would reach 1Password and GitHub.
"""

import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("sync-secrets.py")
SECRET_VALUE = "s3cr3t-value-do-not-leak"

FAKE_OP = f"""#!/usr/bin/env python3
import os, sys
ref = sys.argv[-1]
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write("op " + " ".join(sys.argv[1:]) + "\\n")
if "missing" in ref:
    sys.exit(1)
sys.stdout.write("{SECRET_VALUE}:" + ref)
"""

FAKE_GH = """#!/usr/bin/env python3
import os, sys
data = sys.stdin.read()
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write("gh " + " ".join(sys.argv[1:]) + "\\n")
    log.write("stdin " + data + "\\n")
"""


def write_exe(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class SyncSecretsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        write_exe(bin_dir / "op", FAKE_OP)
        write_exe(bin_dir / "gh", FAKE_GH)
        self.log = self.tmp / "log.txt"
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "FAKE_LOG": str(self.log),
        }

    def run_sync(self, manifest: str, *args: str) -> subprocess.CompletedProcess:
        path = self.tmp / "secrets.manifest.toml"
        path.write_text(textwrap.dedent(manifest))
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--manifest", str(path), *args],
            env=self.env,
            capture_output=True,
            text=True,
        )

    def log_lines(self) -> list[str]:
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_value_goes_to_stdin_never_argv(self) -> None:
        result = self.run_sync("""
            [repos.arami]
            [[secret]]
            name = "EXPO_TOKEN"
            ref = "op://Openclaw/expo/token"
            repos = ["arami"]
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        gh_calls = [line for line in self.log_lines() if line.startswith("gh ")]
        self.assertEqual(gh_calls, ["gh secret set EXPO_TOKEN --repo cheunjm/arami"])
        self.assertIn(
            f"stdin {SECRET_VALUE}:op://Openclaw/expo/token", self.log_lines()
        )
        for line in gh_calls:
            self.assertNotIn(SECRET_VALUE, line)
        self.assertNotIn(SECRET_VALUE, result.stdout + result.stderr)
        self.assertIn("EXPO_TOKEN arami set", result.stdout)

    def test_missing_ref_reported_and_exit_1(self) -> None:
        result = self.run_sync(
            """
            [repos.arami]
            [repos.ui]
            [[secret]]
            name = "GOOD"
            ref = "op://Openclaw/good/value"
            repos = "all"
            [[secret]]
            name = "BAD"
            ref = "op://Openclaw/missing/value"
            repos = ["ui"]
        """,
            "--dry-run",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("GOOD arami ok", result.stdout)
        self.assertIn("GOOD ui ok", result.stdout)
        self.assertIn("BAD ui missing", result.stdout)
        self.assertFalse(
            [line for line in self.log_lines() if line.startswith("gh ")],
            "dry run must not call gh",
        )
        self.assertNotIn(SECRET_VALUE, result.stdout + result.stderr)

    def test_env_and_variable_kinds(self) -> None:
        result = self.run_sync("""
            [repos.starlog]
            [[secret]]
            name = "DOPPLER_TOKEN"
            ref = "op://Openclaw/doppler.starlog/develop"
            repos = ["starlog"]
            env = "develop"
            [[secret]]
            name = "VERCEL_ORG_ID"
            ref = "op://Openclaw/vercel/org_id"
            repos = ["starlog"]
            kind = "variable"
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        gh_calls = [line for line in self.log_lines() if line.startswith("gh ")]
        self.assertEqual(
            gh_calls,
            [
                "gh secret set DOPPLER_TOKEN --repo cheunjm/starlog --env develop",
                "gh variable set VERCEL_ORG_ID --repo cheunjm/starlog",
            ],
        )
        self.assertIn("DOPPLER_TOKEN starlog develop set", result.stdout)

    def test_repo_and_name_filters(self) -> None:
        result = self.run_sync(
            """
            [repos.arami]
            [repos.ui]
            [[secret]]
            name = "A"
            ref = "op://Openclaw/a/v"
            repos = "all"
            [[secret]]
            name = "B"
            ref = "op://Openclaw/b/v"
            repos = "all"
        """,
            "--dry-run",
            "--repo",
            "ui",
            "--name",
            "B",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split("\n")[0], "B ui ok")
        self.assertNotIn("arami", result.stdout)

    def test_unknown_repo_in_secret_is_an_error(self) -> None:
        result = self.run_sync(
            """
            [repos.arami]
            [[secret]]
            name = "A"
            ref = "op://Openclaw/a/v"
            repos = ["nope"]
        """,
            "--dry-run",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("nope", result.stderr)


if __name__ == "__main__":
    unittest.main()
