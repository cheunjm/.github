#!/usr/bin/env python3
"""Plan helpers for cd.yml (INF-1983 D40, D44, D46). Stdlib only.

cd_plan.py validate --environment E [--tag T] [--ref R] --fallback-sha S
    Checks the button's inputs and writes `environment`, `tag` and `checkout`
    (the ref to check out) to $GITHUB_OUTPUT. An empty environment deploys nothing.
cd_plan.py version --environment E [--tag T] --sha S
    Run in the checkout. Writes `version` and `message` (the OTA message):
    master: the tag's X.Y.Z, which must equal package.json; message = the tag.
    develop: package.json bumped by the pending changesets (as the release
    button computes it); message = X.Y.Z+<sha7>.
cd_plan.py migrations --fail-on local-only|remote-only [--warn-only] [--require-rows] [--hint TEXT]
    Reads `supabase migration list --output-format json` (or its text table) from
    stdin. local-only: migrations not yet on the remote (the pending-migrations
    guard). remote-only: remote history with no local file (D23). Exits 1 when any
    are found, unless --warn-only. --require-rows (local migration files exist):
    zero parsed rows exits 1, even with --warn-only.
cd_plan.py checklist --dry-run true|false backend=true app=false ...
    Prints the checklist table (also to $GITHUB_STEP_SUMMARY).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

TARGETS = ["backend", "app", "web", "storybook", "e2e"]
RANK = {"none": 0, "patch": 1, "minor": 2, "major": 3}


class PlanError(Exception):
    pass


def next_version(name: str, version: str, changesets: list[str]) -> str:
    """package.json version bumped by the highest pending changeset for `name` (at least a
    patch), like semver.inc: from a prerelease, a bump first lands on the release it was
    heading for. Same result as release-candidate.yml."""
    bump = 1
    for text in changesets:
        m = re.match(r"^---\r?\n([\s\S]*?)\r?\n?---", text)
        if not m:
            continue
        for line in m.group(1).splitlines():
            r = re.match(
                r"""^\s*["']?([^"':]+)["']?\s*:\s*(major|minor|patch|none)\s*$""", line
            )
            if r and r.group(1).strip() == name:
                bump = max(bump, RANK[r.group(2)])
    core, _, pre = version.partition("-")
    major, minor, patch = (int(x) for x in core.split("."))
    if bump == 3:
        return (
            f"{major}.0.0" if pre and minor == 0 and patch == 0 else f"{major + 1}.0.0"
        )
    if bump == 2:
        return f"{major}.{minor}.0" if pre and patch == 0 else f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch}" if pre else f"{major}.{minor}.{patch + 1}"


def validate(environment: str, tag: str, ref: str, fallback_sha: str) -> dict:
    if environment == "":
        return {"environment": "", "tag": "", "checkout": ""}
    if environment not in ("develop", "master"):
        raise PlanError(f"environment must be develop or master, got {environment!r}")
    if environment == "master":
        if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
            raise PlanError(
                f"master needs tag vX.Y.Z (the Version PR's release tag), got {tag!r}"
            )
        if ref:
            raise PlanError("master deploys a tag; ref must be empty")
        return {"environment": "master", "tag": tag, "checkout": f"refs/tags/{tag}"}
    if tag:
        raise PlanError("develop deploys a ref; tag must be empty")
    sha = ref or fallback_sha
    if not re.fullmatch(r"[0-9a-f]{7,40}", sha):
        raise PlanError(
            f"ref must be a commit SHA (the release button's ref output), got {sha!r}"
        )
    return {"environment": "develop", "tag": "", "checkout": sha}


def release_version(
    environment: str,
    tag: str,
    sha: str,
    name: str,
    pkg_version: str,
    changesets: list[str],
) -> dict:
    if environment == "master":
        version = tag[1:]
        if version != pkg_version:
            raise PlanError(
                f"tag {tag} does not match package.json version {pkg_version}"
            )
        return {"version": version, "message": tag}
    version = next_version(name, pkg_version, changesets)
    return {"version": version, "message": f"{version}+{sha[:7]}"}


def parse_migration_list(text: str) -> list[tuple[str, str]]:
    """(local, remote) per row of `supabase migration list`; either side is '' when absent.

    Reads the JSON of `--output-format json` (CLI 3: one object with `migrations`, each
    {local, remote, time}) when stdout carries it, else the text table: CLI 2 separates
    cells with `|`, CLI 3 with `│` and draws its rule with `─┼─`."""
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict) and isinstance(data.get("migrations"), list):
            return [(str(m.get("local") or ""), str(m.get("remote") or ""))
                    for m in data["migrations"] if isinstance(m, dict) and (m.get("local") or m.get("remote"))]
    rows = []
    for line in text.splitlines():
        cells = [c.strip().strip("`").strip() for c in re.split(r"[|│]", line)]
        if len(cells) < 3:
            continue
        local, remote = cells[0], cells[1]
        if local.lower() == "local":
            continue
        if not (re.fullmatch(r"\d+", local or "0") and re.fullmatch(r"\d+", remote or "0")):
            continue  # rule rows (---|--- or ───┼───) and anything else that is not a version
        if local or remote:
            rows.append((local, remote))
    return rows


def local_only(rows):
    return [local for local, remote in rows if local and not remote]


def remote_only(rows):
    return [remote for local, remote in rows if remote and not local]


def checklist_table(targets: dict, dry_run: bool) -> str:
    lines = ["| Step | Runs |", "|---|---|"]
    for t in TARGETS:
        on = targets.get(t) == "true"
        lines.append(
            f"| {t} | {('yes (dry run)' if dry_run else 'yes') if on else 'no'} |"
        )
    return "\n".join(lines)


def write_outputs(values: dict) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    text = "".join(f"{k}={v}\n" for k, v in values.items())
    if path:
        with open(path, "a") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)


def read_changesets(root: Path) -> list[str]:
    d = root / ".changeset"
    if not d.is_dir():
        return []
    return [p.read_text() for p in sorted(d.glob("*.md")) if p.name != "README.md"]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="cd_plan.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("--environment", default="")
    v.add_argument("--tag", default="")
    v.add_argument("--ref", default="")
    v.add_argument("--fallback-sha", required=True)
    ver = sub.add_parser("version")
    ver.add_argument("--environment", required=True)
    ver.add_argument("--tag", default="")
    ver.add_argument("--sha", required=True)
    m = sub.add_parser("migrations")
    m.add_argument("--fail-on", choices=["local-only", "remote-only"], required=True)
    m.add_argument("--warn-only", action="store_true")
    m.add_argument("--hint", default="")
    m.add_argument("--require-rows", action="store_true",
                   help="local migration files exist: zero parsed rows is an error, never a pass")
    c = sub.add_parser("checklist")
    c.add_argument("--dry-run", default="false")
    c.add_argument("targets", nargs="*")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "validate":
            out = validate(args.environment, args.tag, args.ref, args.fallback_sha)
            if not out["environment"]:
                print("::notice::environment is empty: nothing deploys")
            write_outputs(out)
        elif args.cmd == "version":
            pkg = json.loads(Path("package.json").read_text())
            out = release_version(
                args.environment,
                args.tag,
                args.sha,
                pkg.get("name", ""),
                pkg["version"],
                read_changesets(Path(".")),
            )
            write_outputs(out)
        elif args.cmd == "migrations":
            rows = parse_migration_list(sys.stdin.read())
            if args.require_rows and not rows:
                # Fail closed: an output format this parser does not know must not pass the guard.
                print("::error::could not parse supabase migration list")
                return 1
            if args.fail_on == "local-only":
                found = local_only(rows)
                what = "local migration{s} {are} not on the remote database"
            else:
                found = remote_only(rows)
                what = "remote migration{s} {has} no local file"
            print(
                f"{len(rows)} migrations listed; {len(local_only(rows))} pending, "
                f"{len(remote_only(rows))} remote-only"
            )
            if found:
                n = len(found)
                what = what.format(
                    s="s" if n > 1 else "",
                    are="are" if n > 1 else "is",
                    has="have" if n > 1 else "has",
                )
                level = "warning" if args.warn_only else "error"
                hint = f" {args.hint}" if args.hint else ""
                print(f"::{level}::{n} {what}: {' '.join(found)}.{hint}")
                return 0 if args.warn_only else 1
        elif args.cmd == "checklist":
            targets = dict(t.split("=", 1) for t in args.targets)
            table = checklist_table(targets, args.dry_run == "true")
            print(table)
            summary = os.environ.get("GITHUB_STEP_SUMMARY")
            if summary:
                with open(summary, "a") as fh:
                    fh.write(table + "\n")
    except PlanError as e:
        print(f"::error::{e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
