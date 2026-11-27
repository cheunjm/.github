"""Tests for cd_plan. Run: python3 -m unittest scripts/test_cd_plan.py"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cd_plan  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "cd_plan.py"
SHA = "0123456789abcdef0123456789abcdef01234567"


def changeset(*lines):
    return "---\n" + "\n".join(lines) + "\n---\n\nSummary.\n"


class NextVersionTest(unittest.TestCase):
    def test_no_changesets_is_next_patch(self):
        self.assertEqual(cd_plan.next_version("app", "1.3.0", []), "1.3.1")

    def test_highest_bump_for_the_package_wins(self):
        sets = [
            changeset('"app": patch'),
            changeset("app: minor"),
            changeset('"other": major'),
        ]
        self.assertEqual(cd_plan.next_version("app", "1.3.2", sets), "1.4.0")

    def test_major(self):
        self.assertEqual(
            cd_plan.next_version("app", "1.3.2", [changeset("'app': major")]), "2.0.0"
        )

    def test_empty_changeset_and_none_count_as_patch(self):
        self.assertEqual(
            cd_plan.next_version(
                "app", "1.3.2", ["---\n---\n", changeset('"app": none')]
            ),
            "1.3.3",
        )

    def test_from_a_prerelease_lands_on_the_release_it_was_heading_for(self):
        self.assertEqual(cd_plan.next_version("app", "1.4.0-next.3", []), "1.4.0")
        self.assertEqual(
            cd_plan.next_version("app", "1.4.0-rc.0", [changeset('"app": minor')]),
            "1.4.0",
        )
        self.assertEqual(
            cd_plan.next_version("app", "2.0.0-rc.0", [changeset('"app": major')]),
            "2.0.0",
        )
        self.assertEqual(
            cd_plan.next_version("app", "1.4.1-rc.0", [changeset('"app": minor')]),
            "1.5.0",
        )


class ValidateTest(unittest.TestCase):
    def test_empty_environment_deploys_nothing(self):
        self.assertEqual(
            cd_plan.validate("", "", "", SHA),
            {"environment": "", "tag": "", "checkout": ""},
        )

    def test_unknown_environment_fails(self):
        with self.assertRaisesRegex(
            cd_plan.PlanError, "environment must be develop or master"
        ):
            cd_plan.validate("staging", "", "", SHA)

    def test_master_needs_a_release_tag(self):
        for tag in ["", "1.4.0", "v1.4", "v1.4.0-rc.0", "v1.4.0 ; x"]:
            with (
                self.subTest(tag=tag),
                self.assertRaisesRegex(cd_plan.PlanError, "master needs tag vX.Y.Z"),
            ):
                cd_plan.validate("master", tag, "", SHA)

    def test_master_takes_no_ref(self):
        with self.assertRaisesRegex(
            cd_plan.PlanError, "master deploys a tag; ref must be empty"
        ):
            cd_plan.validate("master", "v1.4.0", SHA, SHA)

    def test_master_checks_out_the_tag(self):
        self.assertEqual(
            cd_plan.validate("master", "v1.4.0", "", SHA),
            {"environment": "master", "tag": "v1.4.0", "checkout": "refs/tags/v1.4.0"},
        )

    def test_develop_takes_no_tag(self):
        with self.assertRaisesRegex(
            cd_plan.PlanError, "develop deploys a ref; tag must be empty"
        ):
            cd_plan.validate("develop", "v1.4.0", SHA, SHA)

    def test_develop_checks_out_ref_or_falls_back_to_the_run_sha(self):
        other = "f" * 40
        self.assertEqual(cd_plan.validate("develop", "", other, SHA)["checkout"], other)
        self.assertEqual(cd_plan.validate("develop", "", "", SHA)["checkout"], SHA)

    def test_develop_ref_must_be_a_sha(self):
        for ref in ["main", "abc", "zz" * 20, "abc1234; rm"]:
            with (
                self.subTest(ref=ref),
                self.assertRaisesRegex(cd_plan.PlanError, "ref must be a commit SHA"),
            ):
                cd_plan.validate("develop", "", ref, SHA)


class VersionTest(unittest.TestCase):
    def test_master_version_is_the_tag_and_must_match_package_json(self):
        self.assertEqual(
            cd_plan.release_version("master", "v1.4.0", SHA, "app", "1.4.0", []),
            {"version": "1.4.0", "message": "v1.4.0"},
        )
        with self.assertRaisesRegex(
            cd_plan.PlanError, "tag v1.4.0 does not match package.json version 1.3.0"
        ):
            cd_plan.release_version("master", "v1.4.0", SHA, "app", "1.3.0", [])

    def test_develop_version_is_the_pending_bump_and_message_carries_the_sha(self):
        self.assertEqual(
            cd_plan.release_version(
                "develop", "", SHA, "app", "1.3.0", [changeset('"app": minor')]
            ),
            {"version": "1.4.0", "message": "1.4.0+0123456"},
        )


MIGRATION_LIST = """
  Local          | Remote         | Time (UTC)
  ----------------|----------------|---------------------
  `20240101000000` | `20240101000000` | `2024-01-01 00:00:00`
  `20240202000000` | ` `            | `2024-02-02 00:00:00`
   20240303000000 |                | 2024-03-03 00:00:00
                 | 20240404000000 | 2024-04-04 00:00:00
"""


class MigrationListTest(unittest.TestCase):
    def test_parses_rows(self):
        rows = cd_plan.parse_migration_list(MIGRATION_LIST)
        self.assertEqual(
            rows,
            [
                ("20240101000000", "20240101000000"),
                ("20240202000000", ""),
                ("20240303000000", ""),
                ("", "20240404000000"),
            ],
        )

    def test_pending_and_remote_only(self):
        rows = cd_plan.parse_migration_list(MIGRATION_LIST)
        self.assertEqual(cd_plan.local_only(rows), ["20240202000000", "20240303000000"])
        self.assertEqual(cd_plan.remote_only(rows), ["20240404000000"])

    def test_empty_history(self):
        self.assertEqual(
            cd_plan.parse_migration_list(
                "  Local | Remote | Time (UTC)\n  ---|---|---\n"
            ),
            [],
        )

    def test_cli_fails_on_pending_unless_warn_only(self):
        def run(*args):
            return subprocess.run(
                [sys.executable, str(SCRIPT), "migrations", *args],
                input=MIGRATION_LIST,
                capture_output=True,
                text=True,
            )

        r = run("--fail-on", "local-only", "--hint", "tick backend")
        self.assertEqual(r.returncode, 1)
        self.assertIn(
            "2 local migrations are not on the remote database: 20240202000000 20240303000000",
            r.stdout,
        )
        self.assertIn("tick backend", r.stdout)
        r = run("--fail-on", "remote-only")
        self.assertEqual(r.returncode, 1)
        self.assertIn("1 remote migration has no local file: 20240404000000", r.stdout)
        r = run("--fail-on", "remote-only", "--warn-only")
        self.assertEqual(r.returncode, 0)
        self.assertIn("::warning::", r.stdout)


class ChecklistTest(unittest.TestCase):
    def test_table_lists_every_target_in_order(self):
        table = cd_plan.checklist_table(
            {
                "backend": "false",
                "app": "true",
                "web": "true",
                "storybook": "false",
                "e2e": "true",
            },
            dry_run=True,
        )
        lines = table.splitlines()
        self.assertEqual(lines[0], "| Step | Runs |")
        self.assertEqual(
            [line.split("|")[1].strip() for line in lines[2:]],
            ["backend", "app", "web", "storybook", "e2e"],
        )
        self.assertIn("| app | yes (dry run) |", table)
        self.assertIn("| backend | no |", table)


class CliTest(unittest.TestCase):
    def test_resolve_writes_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "package.json").write_text(
                json.dumps({"name": "app", "version": "1.3.0"})
            )
            (root / ".changeset").mkdir()
            (root / ".changeset" / "a.md").write_text(changeset('"app": minor'))
            (root / ".changeset" / "README.md").write_text("# not a changeset\n")
            out = root / "out.txt"
            r = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "version",
                    "--environment",
                    "develop",
                    "--sha",
                    SHA,
                ],
                cwd=root,
                capture_output=True,
                text=True,
                env={"GITHUB_OUTPUT": str(out), "PATH": "/usr/bin:/bin"},
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(out.read_text(), "version=1.4.0\nmessage=1.4.0+0123456\n")

    def test_validate_error_is_an_annotation(self):
        r = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "validate",
                "--environment",
                "prod",
                "--fallback-sha",
                SHA,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 1)
        self.assertIn(
            "::error::environment must be develop or master, got 'prod'", r.stdout
        )


MIGRATION_LIST_V3 = """
  LOCAL          │ REMOTE         │ TIME (UTC)
 ────────────────┼────────────────┼─────────────────────
  20240101000000 │ 20240101000000 │ 2024-01-01 00:00:00
  20240202000000 │                │ 2024-02-02 00:00:00
                 │ 20240404000000 │ 2024-04-04 00:00:00
"""

MIGRATION_LIST_JSON = (
    json.dumps(
        {
            "migrations": [
                {
                    "local": "20240101000000",
                    "remote": "20240101000000",
                    "time": "2024-01-01 00:00:00",
                },
                {
                    "local": "20240202000000",
                    "remote": "",
                    "time": "2024-02-02 00:00:00",
                },
                {
                    "local": "",
                    "remote": "20240404000000",
                    "time": "2024-04-04 00:00:00",
                },
            ],
            "message": "Migrations listed",
            "target": {"kind": "linked"},
        }
    )
    + "\n"
)

EXPECTED_ROWS = [
    ("20240101000000", "20240101000000"),
    ("20240202000000", ""),
    ("", "20240404000000"),
]


class MigrationListV3Test(unittest.TestCase):
    def test_box_drawing_table(self):
        self.assertEqual(cd_plan.parse_migration_list(MIGRATION_LIST_V3), EXPECTED_ROWS)

    def test_json_output(self):
        self.assertEqual(
            cd_plan.parse_migration_list(MIGRATION_LIST_JSON), EXPECTED_ROWS
        )

    def test_json_with_stray_lines(self):
        self.assertEqual(
            cd_plan.parse_migration_list("Connecting...\n" + MIGRATION_LIST_JSON),
            EXPECTED_ROWS,
        )

    def run_cli(self, text, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "migrations", *args],
            input=text,
            capture_output=True,
            text=True,
        )

    def test_v3_and_json_trip_the_guards(self):
        for text in (MIGRATION_LIST_V3, MIGRATION_LIST_JSON):
            with self.subTest(text=text[:20]):
                r = self.run_cli(text, "--fail-on", "local-only", "--require-rows")
                self.assertEqual(r.returncode, 1)
                self.assertIn(
                    "1 local migration is not on the remote database: 20240202000000",
                    r.stdout,
                )
                r = self.run_cli(text, "--fail-on", "remote-only", "--require-rows")
                self.assertEqual(r.returncode, 1)
                self.assertIn(
                    "1 remote migration has no local file: 20240404000000", r.stdout
                )

    def test_zero_rows_fails_closed_when_rows_are_required(self):
        for text in [
            "",
            "something else entirely\n",
            "LOCAL │ REMOTE │ TIME (UTC)\n───┼───┼───\n",
            '{"migrations": []}\n',
        ]:
            with self.subTest(text=text):
                r = self.run_cli(text, "--fail-on", "local-only", "--require-rows")
                self.assertEqual(r.returncode, 1)
                self.assertIn(
                    "::error::could not parse supabase migration list", r.stdout
                )
                r = self.run_cli(
                    text, "--fail-on", "local-only", "--require-rows", "--warn-only"
                )
                self.assertEqual(r.returncode, 1)
        r = self.run_cli("", "--fail-on", "remote-only")
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
