"""Tests for apply-rulesets.py. Run: python3 -m unittest scripts/test_apply_rulesets.py

A fake `gh` on PATH records argv and stdin and answers the ruleset listing
with FAKE_RULESETS (JSON).
"""

import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("apply-rulesets.py")

FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
data = sys.stdin.read() if not sys.stdin.isatty() else ""
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps({"argv": sys.argv[1:], "stdin": data}) + "\\n")
if sys.argv[1:3] == ["api", "repos/cheunjm/ui/rulesets"] and "-X" not in sys.argv:
    print(os.environ.get("FAKE_RULESETS", "[]"))
"""

MANIFEST = """
    [repos.ui]
    ruleset = true
    extra_checks = ["e2e / web"]

    [repos.arami]
    ruleset = false
"""


class ApplyRulesetsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        gh = bin_dir / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
        self.log = self.tmp / "log.jsonl"
        self.manifest = self.tmp / "secrets.manifest.toml"
        self.manifest.write_text(textwrap.dedent(MANIFEST))
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "FAKE_LOG": str(self.log),
        }

    def run_apply(
        self, *args: str, rulesets: str = "[]"
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--manifest", str(self.manifest), *args],
            env={**self.env, "FAKE_RULESETS": rulesets},
            capture_output=True,
            text=True,
        )

    def calls(self) -> list[dict]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_payload_has_gate_changeset_and_extras(self) -> None:
        result = self.run_apply("--repo", "ui", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        checks = payload["rules"][0]["parameters"]["required_status_checks"]
        self.assertEqual(
            [c["context"] for c in checks],
            ["ci / gate", "changeset / check", "e2e / web"],
        )
        self.assertTrue(all(c["integration_id"] == 15368 for c in checks))
        self.assertEqual(payload["name"], "default-branch")
        self.assertEqual(
            payload["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"]
        )
        self.assertEqual(
            payload["bypass_actors"],
            [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}],
        )
        self.assertEqual(self.calls(), [], "dry run must not call gh")

    def test_creates_with_post_when_missing(self) -> None:
        result = self.run_apply("--repo", "ui")
        self.assertEqual(result.returncode, 0, result.stderr)
        writes = [c for c in self.calls() if "-X" in c["argv"]]
        self.assertEqual(len(writes), 1)
        self.assertEqual(
            writes[0]["argv"][:4], ["api", "-X", "POST", "repos/cheunjm/ui/rulesets"]
        )
        self.assertEqual(json.loads(writes[0]["stdin"])["name"], "default-branch")

    def test_upsert_uses_put_when_named_ruleset_exists(self) -> None:
        existing = json.dumps(
            [{"id": 42, "name": "default-branch"}, {"id": 7, "name": "other"}]
        )
        result = self.run_apply("--repo", "ui", rulesets=existing)
        self.assertEqual(result.returncode, 0, result.stderr)
        writes = [c for c in self.calls() if "-X" in c["argv"]]
        self.assertEqual(
            [w["argv"][:4] for w in writes],
            [["api", "-X", "PUT", "repos/cheunjm/ui/rulesets/42"]],
        )

    def test_all_skips_repos_without_ruleset(self) -> None:
        result = self.run_apply("--all", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ui", result.stderr)
        self.assertNotIn("arami", result.stderr)


if __name__ == "__main__":
    unittest.main()
