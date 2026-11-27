"""Tests for cd_app. Run: python3 -m unittest scripts/test_cd_app.py"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cd_app  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "cd_app.py"
H = "819ad65ea892500f3dc7cd7d7f070313acff70e6"

EAS = {
    "cli": {"appVersionSource": "remote"},
    "build": {
        "develop": {
            "distribution": "internal",
            "channel": "develop",
            "autoIncrement": True,
            "android": {"buildType": "apk"},
        },
        "develop-apk": {"extends": "develop"},
        "e2e-develop": {
            "extends": "develop",
            "android": {"buildType": "apk"},
            "ios": {"simulator": True},
        },
        "master": {"distribution": "store", "channel": "master", "autoIncrement": True},
        "master-apk": {
            "extends": "master",
            "autoIncrement": False,
            "android": {"buildType": "apk"},
        },
        "e2e-master": {
            "extends": "master",
            "distribution": "internal",
            "android": {"buildType": "apk"},
            "ios": {"simulator": True},
        },
    },
    "submit": {
        "master": {"android": {"serviceAccountKeyPath": "./play-service-account.json"}}
    },
}


def build(
    platform="ANDROID",
    status="FINISHED",
    hash_=H,
    url="https://expo.dev/a/b.apk",
    sim=False,
    created="2026-11-01",
):
    return {
        "id": url,
        "platform": platform,
        "status": status,
        "fingerprint": {"hash": hash_},
        "artifacts": {"buildUrl": url},
        "isForIosSimulator": sim,
        "buildProfile": None,
        "createdAt": created,
    }


def cfg(**kw):
    base = dict(
        environment="develop",
        message="1.4.0+0123456",
        platforms=["android", "ios"],
        app=True,
        e2e=False,
        e2e_platforms=["android", "ios"],
        store_submit=False,
        firebase_groups="",
        sideload_apk=False,
        out="/out",
        asc_key=False,
        firebase_app_ids={"android": "1:111:android:aa", "ios": "1:111:ios:bb"},
    )
    base.update(kw)
    return cd_app.Config(**base)


def names(steps):
    return [s.name for s in steps]


class ProfileTest(unittest.TestCase):
    def test_extends_merges_platform_keys(self):
        p = cd_app.resolve_profile(EAS, "e2e-master")
        self.assertEqual(p["channel"], "master")
        self.assertEqual(p["distribution"], "internal")
        self.assertEqual(p["android"], {"buildType": "apk"})
        self.assertNotIn("extends", p)

    def test_missing_profile_fails(self):
        with self.assertRaisesRegex(
            cd_app.AppError, "eas.json has no build profile e2e-staging"
        ):
            cd_app.resolve_profile(EAS, "e2e-staging")

    def test_extends_cycle_fails(self):
        with self.assertRaisesRegex(cd_app.AppError, "extends cycle"):
            cd_app.resolve_profile(
                {"build": {"a": {"extends": "b"}, "b": {"extends": "a"}}}, "a"
            )

    def test_artifact_ext(self):
        self.assertEqual(
            cd_app.artifact_ext(cd_app.resolve_profile(EAS, "develop"), "android"),
            "apk",
        )
        self.assertEqual(
            cd_app.artifact_ext(cd_app.resolve_profile(EAS, "master"), "android"), "aab"
        )
        self.assertEqual(
            cd_app.artifact_ext(cd_app.resolve_profile(EAS, "master"), "ios"), "ipa"
        )
        self.assertEqual(
            cd_app.artifact_ext(cd_app.resolve_profile(EAS, "e2e-develop"), "ios"),
            "tar.gz",
        )

    def test_submit_key_path(self):
        self.assertEqual(
            cd_app.submit_key_path(EAS, "master"), "./play-service-account.json"
        )
        self.assertEqual(cd_app.submit_key_path(EAS, "develop"), "")


class LookupTest(unittest.TestCase):
    def test_fingerprint_hash_from_json(self):
        self.assertEqual(
            cd_app.fingerprint_hash(json.dumps({"hash": H, "sources": []})), H
        )
        with self.assertRaisesRegex(
            cd_app.AppError, "no hash in fingerprint:generate output"
        ):
            cd_app.fingerprint_hash("{}")

    def test_has_build_needs_a_finished_build_of_this_platform_and_hash(self):
        self.assertTrue(cd_app.has_build([build()], "android", H))
        self.assertFalse(cd_app.has_build([build(status="ERRORED")], "android", H))
        self.assertFalse(cd_app.has_build([build(platform="IOS")], "android", H))
        self.assertFalse(cd_app.has_build([build(hash_="other")], "android", H))
        self.assertFalse(cd_app.has_build([], "android", H))

    def test_e2e_build_is_an_apk_or_a_simulator_build(self):
        aab = build(url="https://expo.dev/a/store.aab")
        apk_old = build(url="https://expo.dev/a/old.apk", created="2026-10-01")
        apk_new = build(url="https://expo.dev/a/new.apk", created="2026-11-02")
        self.assertEqual(
            cd_app.e2e_build_url([aab, apk_old, apk_new], "android", H),
            "https://expo.dev/a/new.apk",
        )
        self.assertIsNone(cd_app.e2e_build_url([aab], "android", H))
        ipa = build(platform="IOS", url="https://expo.dev/a/app.ipa")
        sim = build(platform="IOS", url="https://expo.dev/a/app.tar.gz", sim=True)
        self.assertIsNone(cd_app.e2e_build_url([ipa], "ios", H))
        self.assertEqual(
            cd_app.e2e_build_url([ipa, sim], "ios", H), "https://expo.dev/a/app.tar.gz"
        )

    def test_platform_order(self):
        self.assertEqual(
            cd_app.platform_order(["ios", "android"], ["android"], True),
            ["ios", "android"],
        )
        self.assertEqual(
            cd_app.platform_order(["android"], ["android", "ios", "web"], True),
            ["android", "ios"],
        )
        self.assertEqual(
            cd_app.platform_order(["android"], ["ios"], False), ["android"]
        )


class PlanTest(unittest.TestCase):
    def test_develop_with_a_build_publishes_the_ota_first(self):
        steps = cd_app.plan_platform(cfg(), EAS, "android", H, [build()])
        self.assertEqual(names(steps), ["ota", "build develop", "upload develop"])
        self.assertEqual(
            steps[0].argv,
            [
                "doppler",
                "run",
                "--",
                "eas",
                "update",
                "--channel",
                "develop",
                "--environment",
                "preview",
                "--platform",
                "android",
                "--message",
                "1.4.0+0123456",
                "--non-interactive",
            ],
        )
        self.assertEqual(
            steps[1].argv,
            [
                "doppler",
                "run",
                "--",
                "eas",
                "build",
                "--local",
                "--platform",
                "android",
                "--profile",
                "develop",
                "--non-interactive",
                "--output",
                "/out/android/develop.apk",
            ],
        )
        self.assertEqual(
            steps[2].argv,
            [
                "eas",
                "upload",
                "--platform",
                "android",
                "--build-path",
                "/out/android/develop.apk",
                "--fingerprint",
                H,
                "--non-interactive",
            ],
        )
        self.assertTrue(steps[2].capture_url)

    def test_without_a_build_it_only_builds(self):
        steps = cd_app.plan_platform(cfg(), EAS, "android", H, [build(hash_="old")])
        self.assertEqual(names(steps), ["build develop", "upload develop"])

    def test_develop_distributes_to_firebase(self):
        steps = cd_app.plan_platform(cfg(firebase_groups="testers"), EAS, "ios", H, [])
        self.assertEqual(
            names(steps), ["build develop", "upload develop", "firebase develop"]
        )
        fb = steps[2]
        self.assertEqual(
            fb.argv[:6],
            [
                "npx",
                "--yes",
                "firebase-tools@15.8.0",
                "appdistribution:distribute",
                "/out/ios/develop.ipa",
                "--app",
            ],
        )
        self.assertEqual(
            fb.argv[6:10], ["1:111:ios:bb", "--groups", "testers", "--release-notes"]
        )
        self.assertEqual(fb.notes_for, "upload develop")

    def test_ios_internal_build_refreshes_ad_hoc_profile_with_an_asc_key(self):
        steps = cd_app.plan_platform(cfg(asc_key=True), EAS, "ios", H, [])
        self.assertIn("--refresh-ad-hoc-provisioning-profile", steps[0].argv)
        steps = cd_app.plan_platform(
            cfg(asc_key=True, environment="master"), EAS, "ios", H, []
        )
        self.assertNotIn("--refresh-ad-hoc-provisioning-profile", steps[0].argv)

    def test_sideload_apk_builds_the_apk_profile(self):
        steps = cd_app.plan_platform(cfg(sideload_apk=True), EAS, "android", H, [])
        self.assertEqual(
            names(steps),
            [
                "build develop",
                "upload develop",
                "build develop-apk",
                "upload develop-apk",
            ],
        )
        self.assertEqual(steps[2].argv[-1], "/out/android/develop-apk.apk")
        steps = cd_app.plan_platform(cfg(sideload_apk=True), EAS, "ios", H, [])
        self.assertEqual(names(steps), ["build develop", "upload develop"])

    def test_master_submits_both_stores_and_sends_installable_builds_to_firebase(self):
        c = cfg(
            environment="master",
            message="v1.4.0",
            store_submit=True,
            firebase_groups="qa",
            sideload_apk=True,
        )
        steps = cd_app.plan_platform(c, EAS, "android", H, [build()])
        self.assertEqual(
            names(steps),
            [
                "ota",
                "build master",
                "upload master",
                "build master-apk",
                "upload master-apk",
                "firebase master-apk",
                "submit",
            ],
        )
        self.assertEqual(
            steps[0].argv[5:9], ["--channel", "master", "--environment", "production"]
        )
        self.assertEqual(
            steps[-1].argv,
            [
                "eas",
                "submit",
                "--platform",
                "android",
                "--profile",
                "master",
                "--path",
                "/out/android/master.aab",
                "--non-interactive",
            ],
        )
        steps = cd_app.plan_platform(c, EAS, "ios", H, [])
        self.assertEqual(
            names(steps), ["build master", "upload master", "note", "submit"]
        )
        self.assertIn("store-signed", steps[2].note)

    def test_master_android_without_apk_sends_the_aab(self):
        c = cfg(environment="master", message="v1.4.0", firebase_groups="qa")
        steps = cd_app.plan_platform(c, EAS, "android", H, [])
        self.assertEqual(
            names(steps), ["build master", "upload master", "firebase master"]
        )
        self.assertEqual(steps[2].argv[4], "/out/android/master.aab")

    def test_store_submit_on_develop_is_ignored(self):
        steps = cd_app.plan_platform(cfg(store_submit=True), EAS, "android", H, [])
        self.assertEqual(names(steps), ["build develop", "upload develop", "note"])
        self.assertIn("store_submit applies to master only", steps[-1].note)

    def test_firebase_without_app_id_is_a_note(self):
        c = cfg(firebase_groups="testers", firebase_app_ids={"android": "", "ios": ""})
        steps = cd_app.plan_platform(c, EAS, "android", H, [])
        self.assertEqual(names(steps), ["build develop", "upload develop", "note"])
        self.assertIn("FIREBASE_APP_ID_ANDROID", steps[-1].note)

    def test_e2e_reuses_an_existing_test_build(self):
        builds = [build(platform="IOS", url="https://expo.dev/a/app.tar.gz", sim=True)]
        steps = cd_app.plan_platform(cfg(e2e=True), EAS, "ios", H, builds)
        self.assertEqual(
            names(steps),
            ["ota", "build develop", "upload develop", "download e2e-develop"],
        )
        self.assertEqual(
            steps[-1].argv,
            [
                "curl",
                "-fsSL",
                "--retry",
                "3",
                "-o",
                "/out/ios/e2e/app.tar.gz",
                "https://expo.dev/a/app.tar.gz",
            ],
        )

    def test_e2e_builds_and_uploads_a_missing_test_build(self):
        steps = cd_app.plan_platform(
            cfg(e2e=True, environment="master", message="v1.4.0"), EAS, "android", H, []
        )
        self.assertEqual(
            names(steps),
            ["build master", "upload master", "build e2e-master", "upload e2e-master"],
        )
        self.assertEqual(
            steps[2].argv[-5:],
            [
                "--profile",
                "e2e-master",
                "--non-interactive",
                "--output",
                "/out/android/e2e/app.apk",
            ],
        )

    def test_e2e_only_skips_the_release(self):
        steps = cd_app.plan_platform(
            cfg(app=False, e2e=True), EAS, "android", H, [build()]
        )
        self.assertEqual(names(steps), ["download e2e-develop"])

    def test_platform_only_in_e2e_gets_only_the_test_build(self):
        steps = cd_app.plan_platform(
            cfg(platforms=["android"], e2e=True), EAS, "ios", H, []
        )
        self.assertEqual(names(steps), ["build e2e-develop", "upload e2e-develop"])

    def test_missing_e2e_profile_fails(self):
        eas = {"build": {"develop": {}}}
        with self.assertRaisesRegex(
            cd_app.AppError, "eas.json has no build profile e2e-develop"
        ):
            cd_app.plan_platform(cfg(e2e=True), eas, "android", H, [])


class DryRunTest(unittest.TestCase):
    """The CLI in --dry-run with fixture lookups prints the plan and runs nothing."""

    def run_cli(self, builds):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "eas.json").write_text(json.dumps(EAS))
            (root / "builds.json").write_text(json.dumps(builds))
            r = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "run",
                    "--dry-run",
                    "--environment",
                    "develop",
                    "--message",
                    "1.4.0+0123456",
                    "--platforms",
                    "android",
                    "--e2e",
                    "true",
                    "--e2e-platforms",
                    "android",
                    "--firebase-groups",
                    "testers",
                    "--out",
                    str(root / "out"),
                    "--fingerprint",
                    "android=" + H,
                    "--builds-json",
                    "android=" + str(root / "builds.json"),
                ],
                cwd=root,
                capture_output=True,
                text=True,
                env={
                    "PATH": "/nonexistent",
                    "FIREBASE_APP_ID_ANDROID": "1:111:android:aa",
                },
            )
            self.assertFalse(
                (root / "out").exists() and any((root / "out").rglob("*.apk"))
            )
            return r

    def test_build_exists(self):
        r = self.run_cli([build()])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("fingerprint " + H + " (given)", r.stdout)
        self.assertIn(
            "decision: a finished build of this fingerprint exists: OTA, then build",
            r.stdout,
        )
        self.assertIn("[dry run] doppler run -- eas update --channel develop", r.stdout)
        self.assertIn("[dry run] curl -fsSL", r.stdout)

    def test_no_build(self):
        r = self.run_cli([])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(
            "decision: no finished build of this fingerprint: build only", r.stdout
        )
        self.assertNotIn("eas update", r.stdout)
        self.assertIn(
            "[dry run] doppler run -- eas build --local --platform android --profile e2e-develop",
            r.stdout,
        )


class FailureTest(unittest.TestCase):
    def test_a_failing_platform_fails_after_the_other_finishes(self):
        calls = []

        def runner(step):
            calls.append(step.name)
            return 1 if step.name == "build develop" and len(calls) == 1 else 0

        c = cfg()
        failed = cd_app.run_platforms(
            c,
            EAS,
            ["android", "ios"],
            lookup=lambda p: (H, []),
            runner=runner,
            log=lambda *_: None,
        )
        self.assertEqual(failed, ["android"])
        self.assertEqual(calls, ["build develop", "build develop", "upload develop"])


if __name__ == "__main__":
    unittest.main()
