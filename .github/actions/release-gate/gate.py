#!/usr/bin/env python3
"""Master release gate (INF-1983 D45, D46).

  gate.py --sha SHA --version X.Y.Z [--require-e2e]   (--tag is accepted and ignored)

Needs GH_TOKEN (gh) and a full-history checkout. Fails in this order: not on main;
`ci / gate` not green on the SHA; no `cd/develop` success (from github-actions[bot])
in the SHA's first-parent history, 100 commits back at most; code differs from the
newest such commit (the tested commit) beyond version fields, CHANGELOG.md and
.changeset/; (--require-e2e) the tested commit has no green `cd/e2e-develop` status.
Every failure message ends in `press the release button first`.
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
DEVELOP_CONTEXT = "cd/develop"
STATUS_CREATOR = "github-actions[bot]"
SEARCH_DEPTH = 100
HINT = "press the release button first"
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


def green_status(api, repo, sha, context):
    """True when the newest `context` status on sha from github-actions[bot] is success."""
    statuses = api(f"repos/{repo}/commits/{sha}/statuses?per_page=100")
    mine = [
        s for s in statuses
        if s.get("context") == context and (s.get("creator") or {}).get("login") == STATUS_CREATOR
    ]
    newest = max(mine, key=lambda s: s.get("created_at", ""), default=None)
    return bool(newest) and newest.get("state") == "success"


def tested_commit(api, repo, cwd, sha):
    """Newest commit in sha's first-parent history (sha included) deployed to develop."""
    commits = git(cwd, "rev-list", "--first-parent", "-n", str(SEARCH_DEPTH), sha).stdout.split()
    for c in commits:
        if green_status(api, repo, c, DEVELOP_CONTEXT):
            return c
    return None


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


def strict_eq(a, b):
    """Equality that requires the same JSON type (Python treats 1 == 1.0 == True)."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(strict_eq(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(strict_eq(x, y) for x, y in zip(a, b))
    return a == b


def version_only(cwd, rc, sha, path, version):
    try:
        old = show_json(cwd, rc, path)
        new = show_json(cwd, sha, path)
        old_doc, old_vals = strip_version(old, VERSION_FILES[path])
        new_doc, new_vals = strip_version(new, VERSION_FILES[path])
    except (ValueError, subprocess.CalledProcessError, AttributeError):
        return False
    if not strict_eq(old_doc, new_doc):
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


def check(sha, version, require_e2e, api=gh_api, cwd=".", repo=None):
    repo = repo or os.environ.get("GITHUB_REPOSITORY", "")
    if not on_main(cwd, sha):
        return fail(f"{sha} is not on main: {HINT}")

    q = urllib.parse.urlencode({"check_name": CI_CHECK})
    runs = api(f"repos/{repo}/commits/{sha}/check-runs?{q}").get("check_runs", [])
    runs = [r for r in runs if r.get("name") == CI_CHECK and (r.get("app") or {}).get("id") == CI_APP_ID]
    latest = max(runs, key=lambda r: r.get("id", 0), default=None)
    if not latest or latest.get("conclusion") != "success":
        return fail(f"`{CI_CHECK}` is not green on {sha}: {HINT}")

    tested = tested_commit(api, repo, cwd, sha)
    if not tested:
        return fail(f"no develop deploy before {sha[:7]}: {HINT}")

    if code_differs(cwd, tested, sha, version):
        return fail(f"code differs from the last develop deploy {tested[:7]}: {HINT}")

    if require_e2e and not green_status(api, repo, tested, E2E_CONTEXT):
        return fail(f"{tested[:7]} has no green develop e2e: {HINT}")

    print(f"gate ok: {sha} matches the develop deploy {tested[:7]}")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sha", required=True)
    p.add_argument("--tag", default="", help="accepted and ignored")
    p.add_argument("--version", required=True)
    p.add_argument("--require-e2e", action="store_true")
    a = p.parse_args()
    return check(a.sha, a.version, a.require_e2e)


if __name__ == "__main__":
    sys.exit(main())
