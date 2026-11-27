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
import copy
import json
import os
import subprocess
import sys
import urllib.parse

CI_CHECK = "ci / gate"
E2E_CONTEXT = "cd/e2e-develop"
CI_APP_ID = 15368
E2E_CREATOR = "github-actions[bot]"
MISSING = object()
VERSION_FILES = {
    "package.json": [("version",)],
    "package-lock.json": [("version",), ("packages", "", "version")],
    "app.json": [("expo", "version")],
}


def gh_api(path):
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def git(cwd, *args, check=True):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, check=check)


def on_main(cwd, sha):
    base = "origin/main" if git(cwd, "rev-parse", "--verify", "-q", "origin/main", check=False).returncode == 0 else "main"
    return git(cwd, "merge-base", "--is-ancestor", sha, base, check=False).returncode == 0


def latest_prerelease(api, repo, version):
    """Newest GitHub prerelease (by created_at) whose tag starts with vX.Y.Z-."""
    releases = api(f"repos/{repo}/releases?per_page=100")
    prefix = f"v{version}-"
    pre = [r for r in releases if r.get("prerelease") and str(r.get("tag_name", "")).startswith(prefix)]
    if not pre:
        return None
    return max(pre, key=lambda r: r.get("created_at", ""))["tag_name"]


def show_json(cwd, rev, path):
    return json.loads(git(cwd, "show", f"{rev}:{path}").stdout)


def strip_version(doc, paths):
    """Return (doc without the version fields, {path: value or MISSING})."""
    doc = copy.deepcopy(doc)
    values = {}
    for path in paths:
        node = doc
        for key in path[:-1]:
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, dict) and path[-1] in node:
            values[path] = node.pop(path[-1])
        else:
            values[path] = MISSING
    return doc, values


def version_only(cwd, rc, sha, path, version):
    try:
        old = show_json(cwd, rc, path)
        new = show_json(cwd, sha, path)
        old_doc, old_vals = strip_version(old, VERSION_FILES[path])
        new_doc, new_vals = strip_version(new, VERSION_FILES[path])
    except (ValueError, subprocess.CalledProcessError, AttributeError):
        return False
    if old_doc != new_doc:
        return False
    for key, val in new_vals.items():
        if (val is MISSING) != (old_vals[key] is MISSING):
            return False
        if val is not MISSING and val != version:
            return False
    return True


def code_differs(cwd, rc, sha, version):
    out = git(
        cwd, "diff", "--no-renames", "--name-status", "-z", "--no-ext-diff", "--no-textconv",
        "--no-color", rc, sha,
    ).stdout
    parts = out.split("\0")
    for status, path in zip(parts[0::2], parts[1::2]):
        if path == "CHANGELOG.md" or path.startswith(".changeset/"):
            continue
        if path in VERSION_FILES and status == "M" and version_only(cwd, rc, sha, path, version):
            continue
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
    runs = [r for r in runs if r.get("name") == CI_CHECK and (r.get("app") or {}).get("id") == CI_APP_ID]
    latest = max(runs, key=lambda r: r.get("id", 0), default=None)
    if not latest or latest.get("conclusion") != "success":
        return fail(f"`{CI_CHECK}` is not green on {sha}: cut a new rc first")

    rc = latest_prerelease(api, repo, version)
    if not rc or "-rc." not in rc:
        return fail(f"latest prerelease of {version} is not an rc: cut a new rc first")
    rc_sha = git(cwd, "rev-list", "-n", "1", rc, check=False).stdout.strip()
    if not rc_sha:
        return fail(f"{rc} not found locally: cut a new rc first")

    if code_differs(cwd, rc, sha, version):
        return fail(f"code differs from {rc}: cut a new rc first")

    if require_e2e:
        statuses = api(f"repos/{repo}/commits/{rc_sha}/statuses?per_page=100")
        statuses = [
            s for s in statuses
            if s.get("context") == E2E_CONTEXT and (s.get("creator") or {}).get("login") == E2E_CREATOR
        ]
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
