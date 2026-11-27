#!/usr/bin/env python3
"""The app step of cd.yml, per platform (INF-1983 D44, D45). Stdlib only.

  cd_app.py run --environment develop|master --message MSG --platforms android,ios
                [--app true] [--e2e false] [--e2e-platforms android,ios]
                [--store-submit false] [--firebase-groups ''] [--sideload-apk false]
                [--out DIR] [--eas-json eas.json] [--dry-run]
                [--fingerprint PLATFORM=HASH ...] [--builds-json PLATFORM=FILE ...]
  cd_app.py submit-key-path --environment master [--eas-json eas.json]

Per platform, in this order:
  1. fingerprint: `eas fingerprint:generate -p <p> -e <env> --json`;
  2. lookup: `eas build:list --fingerprint-hash <hash>` (finished builds of that platform);
  3. with --app: when a finished build of this fingerprint exists, publish the OTA first
     (`doppler run -- eas update --channel <env> --environment preview|production`), so
     existing installs update now; then always `eas build --local` (profile <env>) and
     `eas upload --fingerprint <hash>`; with --sideload-apk on Android also profile
     <env>-apk; then distribute: Firebase App Distribution (--firebase-groups) and, on
     master, `eas submit` (--store-submit);
  4. with --e2e: the test build for this fingerprint (profile e2e-<env>: an Android APK or
     an iOS simulator build) is downloaded when EAS has one, else built and uploaded. It
     lands in <out>/<p>/e2e/ for the workflow to upload as artifact e2e-app-<p>.
A failing platform fails the run only after the other platform finished.

--dry-run prints every command and runs none. The fingerprint and lookup are read-only:
they run when EXPO_TOKEN is set; otherwise --fingerprint and --builds-json supply them,
or a placeholder hash and an empty build list are used.

Environment: EXPO_TOKEN, FIREBASE_APP_ID_ANDROID (or FIREBASE_APP_ID), FIREBASE_APP_ID_IOS,
EXPO_ASC_API_KEY_PATH (set when an App Store Connect key is present: internal iOS builds
then refresh their ad hoc profile), GITHUB_STEP_SUMMARY.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

EAS_ENVIRONMENT = {"develop": "preview", "master": "production"}
FIREBASE_TOOLS = "firebase-tools@15.8.0"
PLATFORMS = ("android", "ios")


class AppError(Exception):
    pass


@dataclass
class Config:
    environment: str
    message: str
    platforms: list
    app: bool
    e2e: bool
    e2e_platforms: list
    store_submit: bool
    firebase_groups: str
    sideload_apk: bool
    out: str
    asc_key: bool
    firebase_app_ids: dict = field(default_factory=dict)


@dataclass
class Step:
    name: str
    argv: list | None = None
    note: str = ""
    capture_url: bool = False  # keep the Expo link `eas upload` prints
    notes_for: str = ""  # Firebase release notes get the Expo link of this upload step
    output: str = ""  # file the step writes; its directory is created first


# --- eas.json -------------------------------------------------------------------------


def resolve_profile(eas: dict, name: str, _seen: tuple = ()) -> dict:
    """The build profile with its `extends` chain merged (platform keys merged one level)."""
    if name in _seen:
        raise AppError(f"eas.json build profile {name} has an extends cycle")
    profiles = eas.get("build") or {}
    if name not in profiles:
        raise AppError(f"eas.json has no build profile {name}")
    own = dict(profiles[name])
    parent = own.pop("extends", None)
    if not parent:
        return own
    merged = resolve_profile(eas, parent, _seen + (name,))
    for key, value in own.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def artifact_ext(profile: dict, platform: str) -> str:
    if platform == "android":
        return (
            "apk" if (profile.get("android") or {}).get("buildType") == "apk" else "aab"
        )
    return "tar.gz" if (profile.get("ios") or {}).get("simulator") else "ipa"


def submit_key_path(eas: dict, environment: str) -> str:
    """The Play service account path the submit profile reads (eas submit takes no env var)."""
    return (
        ((eas.get("submit") or {}).get(environment) or {}).get("android") or {}
    ).get("serviceAccountKeyPath", "")


# --- lookups --------------------------------------------------------------------------


def fingerprint_hash(text: str) -> str:
    try:
        value = json.loads(text).get("hash")
    except (ValueError, AttributeError):
        value = None
    if not value:
        raise AppError("no hash in fingerprint:generate output")
    return value


def parse_builds(text: str) -> list:
    data = json.loads(text or "[]")
    if not isinstance(data, list):
        raise AppError("eas build:list --json did not return a list")
    return data


def _matching(builds: list, platform: str, hash_: str) -> list:
    out = []
    for b in builds:
        if str(b.get("platform", "")).lower() != platform:
            continue
        if str(b.get("status", "")).lower() != "finished":
            continue
        if ((b.get("fingerprint") or {}).get("hash")) != hash_:
            continue
        out.append(b)
    return sorted(out, key=lambda b: b.get("createdAt") or "", reverse=True)


def has_build(builds: list, platform: str, hash_: str) -> bool:
    """A finished build of this fingerprint exists, so an OTA reaches installs now."""
    return bool(_matching(builds, platform, hash_))


def e2e_build_url(builds: list, platform: str, hash_: str) -> str | None:
    """Newest installable test build of this fingerprint: an APK, or an iOS simulator build.
    Uploaded local builds carry no profile name, so the artifact type decides."""
    for b in _matching(builds, platform, hash_):
        url = (b.get("artifacts") or {}).get("buildUrl") or ""
        if platform == "android" and url.endswith(".apk"):
            return url
        if platform == "ios" and b.get("isForIosSimulator") and url:
            return url
    return None


def platform_order(platforms: list, e2e_platforms: list, e2e: bool) -> list:
    order = [p for p in platforms if p in PLATFORMS]
    if e2e:
        order += [p for p in e2e_platforms if p in PLATFORMS and p not in order]
    return order


# --- plan -----------------------------------------------------------------------------


def _build_and_upload(
    profile_name: str,
    profile: dict,
    platform: str,
    path: str,
    hash_: str,
    asc_key: bool,
) -> list:
    argv = [
        "doppler",
        "run",
        "--",
        "eas",
        "build",
        "--local",
        "--platform",
        platform,
        "--profile",
        profile_name,
        "--non-interactive",
        "--output",
        path,
    ]
    internal_device = profile.get("distribution") != "store" and not (
        profile.get("ios") or {}
    ).get("simulator")
    if platform == "ios" and asc_key and internal_device:
        # Devices added with `eas device:create` can install this build.
        argv.append("--refresh-ad-hoc-provisioning-profile")
    return [
        Step(f"build {profile_name}", argv, output=path),
        Step(
            f"upload {profile_name}",
            [
                "eas",
                "upload",
                "--platform",
                platform,
                "--build-path",
                path,
                "--fingerprint",
                hash_,
                "--non-interactive",
            ],
            capture_url=True,
        ),
    ]


def plan_platform(
    cfg: Config, eas: dict, platform: str, hash_: str, builds: list
) -> list:
    env = cfg.environment
    out = f"{cfg.out}/{platform}"
    steps: list = []
    release = cfg.app and platform in cfg.platforms
    want_e2e = cfg.e2e and platform in cfg.e2e_platforms
    e2e_profile = resolve_profile(eas, f"e2e-{env}") if want_e2e else None

    if release:
        profile = resolve_profile(eas, env)
        if has_build(builds, platform, hash_):
            steps.append(
                Step(
                    "ota",
                    [
                        "doppler",
                        "run",
                        "--",
                        "eas",
                        "update",
                        "--channel",
                        env,
                        "--environment",
                        EAS_ENVIRONMENT[env],
                        "--platform",
                        platform,
                        "--message",
                        cfg.message,
                        "--non-interactive",
                    ],
                )
            )
        ext = artifact_ext(profile, platform)
        main = f"{out}/{env}.{ext}"
        steps += _build_and_upload(env, profile, platform, main, hash_, cfg.asc_key)

        apk = ""
        if cfg.sideload_apk and platform == "android":
            apk_name = f"{env}-apk"
            apk = f"{out}/{apk_name}.apk"
            steps += _build_and_upload(
                apk_name,
                resolve_profile(eas, apk_name),
                platform,
                apk,
                hash_,
                cfg.asc_key,
            )

        if cfg.firebase_groups:
            target = ""
            if platform == "android":
                # One installable build per release: the main APK, else the sideload APK, else the AAB.
                target, target_name = (
                    (main, env) if ext == "apk" or not apk else (apk, f"{env}-apk")
                )
            elif profile.get("distribution") == "store":
                steps.append(
                    Step(
                        "note",
                        note=f"firebase: the {env} iOS build is store-signed and cannot "
                        "be installed from Firebase; it reaches testers through "
                        "TestFlight",
                    )
                )
            else:
                target, target_name = main, env
            if target:
                app_id = cfg.firebase_app_ids.get(platform, "")
                if not app_id:
                    steps.append(
                        Step(
                            "note",
                            note=f"firebase: no FIREBASE_APP_ID_{platform.upper()} "
                            f"variable in {env}; skipping",
                        )
                    )
                else:
                    steps.append(
                        Step(
                            f"firebase {target_name}",
                            [
                                "npx",
                                "--yes",
                                FIREBASE_TOOLS,
                                "appdistribution:distribute",
                                target,
                                "--app",
                                app_id,
                                "--groups",
                                cfg.firebase_groups,
                                "--release-notes",
                                cfg.message,
                            ],
                            notes_for=f"upload {target_name}",
                        )
                    )

        if cfg.store_submit:
            if env == "master":
                steps.append(
                    Step(
                        "submit",
                        [
                            "eas",
                            "submit",
                            "--platform",
                            platform,
                            "--profile",
                            env,
                            "--path",
                            main,
                            "--non-interactive",
                        ],
                    )
                )
            else:
                steps.append(
                    Step(
                        "note",
                        note="store_submit applies to master only; ignored on develop",
                    )
                )

    if want_e2e:
        name = f"e2e-{env}"
        path = f"{out}/e2e/app.{artifact_ext(e2e_profile, platform)}"
        url = e2e_build_url(builds, platform, hash_)
        if url:
            steps.append(
                Step(
                    f"download {name}",
                    ["curl", "-fsSL", "--retry", "3", "-o", path, url],
                    output=path,
                )
            )
        else:
            steps += _build_and_upload(
                name, e2e_profile, platform, path, hash_, cfg.asc_key
            )
    return steps


# --- run ------------------------------------------------------------------------------


def run_platforms(cfg: Config, eas: dict, platforms: list, lookup, runner, log) -> list:
    """Run every platform; a failure stops that platform only. Returns the failed ones."""
    failed = []
    for platform in platforms:
        log(f"::group::{platform}")
        try:
            hash_, builds = lookup(platform)
            if cfg.app and platform in cfg.platforms:
                if has_build(builds, platform, hash_):
                    log(
                        "decision: a finished build of this fingerprint exists: OTA, then build"
                    )
                else:
                    log("decision: no finished build of this fingerprint: build only")
            urls: dict = {}
            for step in plan_platform(cfg, eas, platform, hash_, builds):
                if step.argv is None:
                    log(f"::notice::{step.note}")
                    continue
                if step.notes_for and urls.get(step.notes_for):
                    step.argv[-1] = f"{step.argv[-1]} {urls[step.notes_for]}"
                code = runner(step)
                if isinstance(code, tuple):
                    code, url = code
                    if url:
                        urls[step.name] = url
                if code:
                    log(f"::error::{platform}: {step.name} failed (exit {code})")
                    failed.append(platform)
                    break
        except (AppError, subprocess.CalledProcessError, OSError, ValueError) as e:
            log(f"::error::{platform}: {e}")
            failed.append(platform)
        log("::endgroup::")
    return failed


def _summary(line: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a") as fh:
            fh.write(line + "\n")


def real_runner(step: Step):
    if step.output:
        Path(step.output).parent.mkdir(parents=True, exist_ok=True)
    print(f"$ {shlex.join(step.argv)}", flush=True)
    if not step.capture_url:
        return subprocess.run(step.argv).returncode
    url = ""
    with subprocess.Popen(
        step.argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    ) as proc:
        for line in proc.stdout:
            sys.stdout.write(line)
            m = re.search(r"https://expo\.dev/\S+", line)
            if m:
                url = m.group(0)
    if url:
        _summary(f"- **{step.name}:** {url}")
    return proc.returncode, url


def dry_runner(step: Step):
    print(f"[dry run] {shlex.join(step.argv)}", flush=True)
    return 0


def _pairs(values: list) -> dict:
    out = {}
    for v in values or []:
        key, _, val = v.partition("=")
        out[key] = val
    return out


def make_lookup(cfg: Config, dry_run: bool, fingerprints: dict, builds_files: dict):
    have_token = bool(os.environ.get("EXPO_TOKEN"))

    def capture(argv):
        print(f"$ {shlex.join(argv)}", flush=True)
        return subprocess.run(
            argv, check=True, stdout=subprocess.PIPE, text=True
        ).stdout

    def lookup(platform):
        if platform in fingerprints:
            hash_, source = fingerprints[platform], "given"
        elif dry_run and not have_token:
            hash_, source = f"<fingerprint-{platform}>", "not computed: no EXPO_TOKEN"
            print(
                f"[dry run] eas fingerprint:generate -p {platform} -e {cfg.environment} --json"
            )
        else:
            hash_ = fingerprint_hash(
                capture(
                    [
                        "eas",
                        "fingerprint:generate",
                        "-p",
                        platform,
                        "-e",
                        cfg.environment,
                        "--json",
                    ]
                )
            )
            source = "eas fingerprint:generate"
        print(f"fingerprint {hash_} ({source})")
        list_argv = [
            "eas",
            "build:list",
            "-p",
            platform,
            "--fingerprint-hash",
            hash_,
            "--status",
            "finished",
            "--limit",
            "50",
            "--json",
            "--non-interactive",
        ]
        if platform in builds_files:
            builds = parse_builds(Path(builds_files[platform]).read_text())
            print(f"builds: {len(builds)} from {builds_files[platform]} (given)")
        elif dry_run and not have_token:
            builds = []
            print(
                f"[dry run] {shlex.join(list_argv)}  (not run: no EXPO_TOKEN; assuming no build)"
            )
        else:
            builds = parse_builds(capture(list_argv))
            print(f"builds: {len(builds)} listed")
        _summary(
            f"- **{platform}:** fingerprint `{hash_}`, "
            f"{'a build exists' if has_build(builds, platform, hash_) else 'no build yet'}"
        )
        return hash_, builds

    return lookup


def _bool(value: str) -> bool:
    return str(value).lower() == "true"


def _csv(value: str) -> list:
    return [p.strip() for p in value.split(",") if p.strip()]


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="cd_app.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--environment", required=True, choices=["develop", "master"])
    r.add_argument("--message", required=True)
    r.add_argument("--platforms", default="android,ios")
    r.add_argument("--app", default="true")
    r.add_argument("--e2e", default="false")
    r.add_argument("--e2e-platforms", default="android,ios")
    r.add_argument("--store-submit", default="false")
    r.add_argument("--firebase-groups", default="")
    r.add_argument("--sideload-apk", default="false")
    r.add_argument("--out", default="build-out")
    r.add_argument("--eas-json", default="eas.json")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument(
        "--fingerprint",
        action="append",
        help="PLATFORM=HASH: skip fingerprint:generate",
    )
    r.add_argument(
        "--builds-json", action="append", help="PLATFORM=FILE: skip build:list"
    )
    k = sub.add_parser("submit-key-path")
    k.add_argument("--environment", required=True)
    k.add_argument("--eas-json", default="eas.json")
    args = ap.parse_args(argv)

    try:
        eas = json.loads(Path(args.eas_json).read_text())
    except (OSError, ValueError) as e:
        print(f"::error::cannot read {args.eas_json}: {e}")
        return 1

    if args.cmd == "submit-key-path":
        print(submit_key_path(eas, args.environment))
        return 0

    platforms = _csv(args.platforms)
    for p in platforms:
        if p not in PLATFORMS:
            print(f"::error::platforms takes android and ios, got {p!r}")
            return 1
    cfg = Config(
        environment=args.environment,
        message=args.message,
        platforms=platforms,
        app=_bool(args.app),
        e2e=_bool(args.e2e),
        e2e_platforms=_csv(args.e2e_platforms),
        store_submit=_bool(args.store_submit),
        firebase_groups=args.firebase_groups.strip(),
        sideload_apk=_bool(args.sideload_apk),
        out=args.out,
        asc_key=bool(os.environ.get("EXPO_ASC_API_KEY_PATH")),
        firebase_app_ids={
            "android": os.environ.get("FIREBASE_APP_ID_ANDROID")
            or os.environ.get("FIREBASE_APP_ID", ""),
            "ios": os.environ.get("FIREBASE_APP_ID_IOS", ""),
        },
    )
    order = platform_order(cfg.platforms, cfg.e2e_platforms, cfg.e2e)
    print(
        f"app step: environment {cfg.environment}, platforms {' '.join(order) or 'none'}, "
        f"app {cfg.app}, e2e {cfg.e2e}{', dry run' if args.dry_run else ''}"
    )
    lookup = make_lookup(
        cfg, args.dry_run, _pairs(args.fingerprint), _pairs(args.builds_json)
    )
    failed = run_platforms(
        cfg,
        eas,
        order,
        lookup,
        dry_runner if args.dry_run else real_runner,
        lambda line: print(line, flush=True),
    )
    if failed:
        print(f"::error::app step failed on: {' '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
