"""Tests for the studio-lock action. Run: python3 -m unittest scripts/test_studio_lock.py"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LOCK = Path(__file__).resolve().parent.parent / ".github" / "actions" / "studio-lock" / "lock.py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(LOCK), *args], capture_output=True, text=True)


def acquire(lock_dir: str, owner_id: str, pid: int | None = None, timeout: str = "0") -> subprocess.CompletedProcess:
    owner = {"id": owner_id, "repo": "cheunjm/x", "run_url": "https://example.test/run"}
    if pid is not None:
        owner["pid"] = pid
    return run(
        "acquire", "--dir", lock_dir, "--slots", "2", "--timeout-minutes", timeout,
        "--poll-seconds", "0", "--owner", json.dumps(owner),
    )


class StudioLockTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = os.path.join(self._tmp.name, "lock")

    def test_two_owners_get_different_slots(self):
        a = acquire(self.dir, "1-a", pid=os.getpid())
        b = acquire(self.dir, "1-b", pid=os.getpid())
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertEqual(b.returncode, 0, b.stderr)
        self.assertNotEqual(a.stdout.strip(), b.stdout.strip())
        self.assertRegex(a.stdout.strip(), r"^slot=[01]$")

    def test_third_owner_times_out(self):
        acquire(self.dir, "1-a", pid=os.getpid())
        acquire(self.dir, "1-b", pid=os.getpid())
        c = acquire(self.dir, "1-c", pid=os.getpid(), timeout="0")
        self.assertEqual(c.returncode, 1)
        self.assertIn("no Studio slot in 0 min", c.stderr + c.stdout)

    def test_dead_owner_slot_is_reused(self):
        acquire(self.dir, "1-a", pid=os.getpid())
        dead = acquire(self.dir, "1-dead", pid=999999)
        self.assertEqual(dead.returncode, 0, dead.stderr)
        c = acquire(self.dir, "1-c", pid=os.getpid())
        self.assertEqual(c.returncode, 0, c.stderr)
        self.assertEqual(c.stdout.strip(), dead.stdout.strip())

    def test_release_ignores_foreign_owner(self):
        a = acquire(self.dir, "1-a", pid=os.getpid())
        slot = a.stdout.strip().split("=")[1]
        r = run("release", "--dir", self.dir, "--slot", slot, "--owner-id", "9-other")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isdir(os.path.join(self.dir, f"slot-{slot}")))

    def test_release_frees_slot(self):
        a = acquire(self.dir, "1-a", pid=os.getpid())
        slot = a.stdout.strip().split("=")[1]
        r = run("release", "--dir", self.dir, "--slot", slot, "--owner-id", "1-a")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.dir, f"slot-{slot}")))


if __name__ == "__main__":
    unittest.main()
