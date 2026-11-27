"""Tests for the migration contract guard. Run: python3 -m unittest scripts/test_contract_check.py

Pure functions are tested on diff text; the CLI is tested against temp git repos.
"""

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "contract_check.py"
spec = importlib.util.spec_from_file_location("contract_check", SCRIPT)
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)


def diff_for(path, lines, start=1):
    body = "".join("+%s\n" % line for line in lines)
    return "diff --git a/%s b/%s\n--- /dev/null\n+++ b/%s\n@@ -0,0 +%d,%d @@\n%s" % (
        path, path, path, start, len(lines), body)


def ERR(loc):
    return '%s is a contract change: add "-- contract: safe after vX.Y.Z" and a minor changeset' % loc


class ScanTest(unittest.TestCase):
    def test_additive_passes(self):
        d = diff_for("m/1.sql", ["create table a (id int);", "alter table a add column b text;"])
        self.assertEqual(cc.scan(d), [])

    def test_each_destructive_statement_is_flagged_with_line(self):
        cases = [
            "ALTER TABLE a DROP COLUMN b;",
            "DROP TABLE a;",
            "ALTER TABLE x RENAME TO y;",
            "ALTER TABLE a RENAME COLUMN b TO c;",
            "ALTER TABLE a ALTER COLUMN c TYPE bigint;",
            "ALTER TABLE a ALTER COLUMN c SET DATA TYPE bigint;",
        ]
        for sql in cases:
            with self.subTest(sql=sql):
                d = diff_for("m/2.sql", ["select 1;", sql], start=10)
                self.assertEqual(cc.scan(d), [("m/2.sql", 11, sql)])

    def test_lowercase_flagged(self):
        d = diff_for("m/3.sql", ["alter table a drop column b;"])
        self.assertEqual(len(cc.scan(d)), 1)

    def test_comment_text_not_flagged(self):
        d = diff_for("m/4.sql", ["-- drop column b later", "select 1; -- drop table a"])
        self.assertEqual(cc.scan(d), [])

    def test_column_named_type_not_flagged(self):
        d = diff_for("m/5.sql", ["alter table a alter column type set not null;"])
        self.assertEqual(cc.scan(d), [])

    def test_multiple_files_and_hunks(self):
        d = (diff_for("a.sql", ["drop table a;"]) +
             "diff --git a/b.sql b/b.sql\n--- a/b.sql\n+++ b/b.sql\n@@ -3,0 +4,1 @@\n+drop table b;\n"
             "@@ -9,0 +11,2 @@\n+select 1;\n+drop table c;\n")
        self.assertEqual([(f, n) for f, n, _ in cc.scan(d)], [("a.sql", 1), ("b.sql", 4), ("b.sql", 12)])


class MarkerTest(unittest.TestCase):
    def test_marker_line(self):
        self.assertTrue(cc.has_marker("select 1;\n-- contract: safe after v1.2.3\n"))
        self.assertTrue(cc.has_marker("  -- contract: safe after v10.0.0-rc.1  \n"))

    def test_bad_markers(self):
        for text in ["-- contract: safe after v1.x", "-- contract: safe after 1.2.3",
                     "-- contract: safe after v1.2", "select 1; -- contract: safe after v1.2.3"]:
            with self.subTest(text=text):
                self.assertFalse(cc.has_marker(text))


class GitCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = self._tmp.name
        self.git("init", "-q", "-b", "main")
        self.write("package.json", '{"name": "app", "version": "1.0.0"}\n')
        self.write(".changeset/config.json", "{}\n")
        self.write(".changeset/README.md", "readme\n")
        self.commit("base")
        self.base = self.git("rev-parse", "HEAD")

    def git(self, *args):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                   GIT_COMMITTER_EMAIL="t@t")
        r = subprocess.run(["git", "-C", self.repo, *args], capture_output=True, text=True, check=True, env=env)
        return r.stdout.strip()

    def write(self, rel, text):
        p = Path(self.repo, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)

    def run_cli(self, *args):
        r = subprocess.run(["python3", str(SCRIPT), *args], cwd=self.repo, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr


class ScanCliTest(GitCase):
    def scan(self):
        return self.run_cli("scan", "--base", self.base, "--head", "HEAD", "--paths", "supabase/migrations/**")

    def test_additive_passes(self):
        self.write("supabase/migrations/1.sql", "create table a (id int);\n")
        self.commit("m")
        self.assertEqual(self.scan()[0], 0)

    def test_destructive_fails_with_message(self):
        self.write("supabase/migrations/1.sql", "create table a (id int);\nalter table a drop column b;\n")
        self.commit("m")
        code, out = self.scan()
        self.assertEqual(code, 1)
        self.assertIn(ERR("supabase/migrations/1.sql:2"), out)

    def test_marker_passes(self):
        self.write("supabase/migrations/1.sql", "-- contract: safe after v1.1.0\nalter table a drop column b;\n")
        self.commit("m")
        self.assertEqual(self.scan()[0], 0)

    def test_bad_marker_fails(self):
        self.write("supabase/migrations/1.sql", "-- contract: safe after v1.x\ndrop table a;\n")
        self.commit("m")
        self.assertEqual(self.scan()[0], 1)

    def test_paths_scope(self):
        self.write("elsewhere/1.sql", "drop table a;\n")
        self.commit("m")
        self.assertEqual(self.scan()[0], 0)


class ChangesetCliTest(GitCase):
    def check(self):
        return self.run_cli("changeset", "--base", self.base, "--head", "HEAD", "--paths", "supabase/migrations/**")

    def contract(self):
        self.write("supabase/migrations/1.sql", "-- contract: safe after v1.1.0\ndrop table a;\n")

    def changeset(self, level, name="app"):
        self.write(".changeset/x.md", '---\n"%s": %s\n---\n\nChange.\n' % (name, level))

    def test_no_contract_migration_needs_nothing(self):
        self.write("supabase/migrations/1.sql", "create table a (id int);\n")
        self.changeset("patch")
        self.commit("m")
        self.assertEqual(self.check()[0], 0)

    def test_patch_fails(self):
        self.contract()
        self.changeset("patch")
        self.commit("m")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("a contract migration needs a minor changeset", out)

    def test_minor_passes(self):
        self.contract()
        self.changeset("minor")
        self.commit("m")
        self.assertEqual(self.check()[0], 0)

    def test_major_fails(self):
        self.contract()
        self.changeset("major")
        self.commit("m")
        self.assertEqual(self.check()[0], 1)

    def test_minor_for_other_package_fails(self):
        self.contract()
        self.changeset("minor", name="other")
        self.commit("m")
        self.assertEqual(self.check()[0], 1)

    def test_no_changeset_fails(self):
        self.contract()
        self.commit("m")
        self.assertEqual(self.check()[0], 1)


if __name__ == "__main__":
    unittest.main()
