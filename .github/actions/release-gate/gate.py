#!/usr/bin/env python3
"""Master release gate (INF-1983 D26, D27, D45).

  gate.py --sha SHA --tag TAG --version X.Y.Z [--require-e2e]

Needs GH_TOKEN (gh) and a full-history checkout with tags. Fails in this order:
not on main; `ci / gate` not green on the SHA; latest prerelease of X.Y.Z is not an
rc; code differs from that rc beyond version fields, CHANGELOG.md and .changeset/;
(--require-e2e) the rc's commit has no green `cd/e2e-develop` status.
Every failure message ends in `cut a new rc first`.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse

CI_CHECK = "ci / gate"
E2E_CONTEXT = "cd/e2e-develop"
VERSION_FILES = ("package.json", "package-lock.json", "app.json")
VERSION_LINE = re.compile(r'^\s*"version": ')


def gh_api(path):
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def git(cwd, *args, check=True):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, check=check)


def on_main(cwd, sha):
    base = "origin/main" if git(cwd, "rev-parse", "--verify", "-q", "origin/main", check=False).returncode == 0 else "main"
    return git(cwd, "merge-base", "--is-ancestor", sha, base, check=False).returncode == 0


def latest_prerelease(cwd, version):
    pat = re.compile(r"^v?" + re.escape(version) + r"-([A-Za-z]+)\.(\d+)$")
    best = None
    for tag in git(cwd, "tag", "--list").stdout.split():
        m = pat.match(tag)
        if not m:
            continue
        n = int(m.group(2))
        is_rc = m.group(1) == "rc"
        # on a tie across channels, a non-rc wins so the gate fails closed
        key = (n, not is_rc)
        if best is None or key > best[0]:
            best = (key, tag, is_rc)
    return (best[1], best[2]) if best else (None, False)


def code_differs(cwd, rc, sha):
    files = git(cwd, "diff", "--name-only", rc, sha).stdout.split("\n")
    changed = [
        f for f in files
        if f and f != "CHANGELOG.md" and not f.startswith(".changeset/")
    ]
    if any(f not in VERSION_FILES for f in changed):
        return True
    if not changed:
        return False
    diff = git(cwd, "diff", "-U0", rc, sha, "--", *changed).stdout
    for line in diff.split("\n"):
        if line.startswith(("+++", "---")) or not line or line[0] not in "+-":
            continue
        if not VERSION_LINE.match(line[1:]):
            return True
    return False


def fail(msg):
    print(msg, file=sys.stderr)
    return 1


def check(sha, tag, version, require_e2e, api=gh_api, cwd=".", repo=None):
    repo = repo or os.environ.get("GITHUB_REPOSITORY", "")
    if not on_main(cwd, sha):
        return fail(f"{sha} is not on main: cut a new rc first")

    q = urllib.parse.urlencode({"check_name": CI_CHECK})
    runs = api(f"repos/{repo}/commits/{sha}/check-runs?{q}").get("check_runs", [])
    runs = [r for r in runs if r.get("name", CI_CHECK) == CI_CHECK]
    latest = max(runs, key=lambda r: r.get("id", 0), default=None)
    if not latest or latest.get("conclusion") != "success":
        return fail(f"`{CI_CHECK}` is not green on {sha}: cut a new rc first")

    rc, is_rc = latest_prerelease(cwd, version)
    if not rc or not is_rc:
        return fail(f"latest prerelease of {version} is not an rc: cut a new rc first")

    if code_differs(cwd, rc, sha):
        return fail(f"code differs from {rc}: cut a new rc first")

    if require_e2e:
        rc_sha = git(cwd, "rev-list", "-n", "1", rc).stdout.strip()
        statuses = [s for s in api(f"repos/{repo}/commits/{rc_sha}/statuses") if s.get("context") == E2E_CONTEXT]
        newest = max(statuses, key=lambda s: s.get("created_at", ""), default=None)
        if not newest or newest.get("state") != "success":
            return fail(f"{rc} has no green develop e2e: cut a new rc first")

    print(f"gate ok: {sha} matches {rc}")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sha", required=True)
    p.add_argument("--tag", default="")
    p.add_argument("--version", required=True)
    p.add_argument("--require-e2e", action="store_true")
    a = p.parse_args()
    return check(a.sha, a.tag, a.version, a.require_e2e)


if __name__ == "__main__":
    sys.exit(main())
