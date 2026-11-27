#!/usr/bin/env python3
"""Master release gate (INF-1983 D45, D46).

  gate.py --sha SHA --version X.Y.Z [--require-e2e]   (--tag is accepted and ignored)

Needs GH_TOKEN (gh, `actions: read`) and a full-history checkout. Fails in this order: not
on main; `ci / gate` not green on the SHA; no develop deploy in the SHA's first-parent
history, 100 commits back at most (a deploy is a workflow_dispatch run of
release-candidate.yml on the default branch at that commit with a successful
`develop-status` job; commit statuses are never read); code differs from the newest such
commit (the tested commit) beyond version fields, CHANGELOG.md and .changeset/;
(--require-e2e) the tested commit has no run with a successful `e2e-status` job.
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
DEVELOP_JOB = "develop-status"
E2E_JOB = "e2e-status"
CI_APP_ID = 15368
RELEASE_WORKFLOW_FILE = "release-candidate.yml"
RELEASE_WORKFLOW = ".github/workflows/" + RELEASE_WORKFLOW_FILE
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


class UnverifiedDeploys(Exception):
    pass


class Deploys:
    """Develop deploys proven by the jobs of release-button runs, never by commit statuses.

    A commit status can be posted by any job token, so it proves nothing. A run of the
    repo's release-candidate.yml, dispatched on the default branch at the commit, whose
    cd.yml `develop-status` (or `e2e-status`) job succeeded, does. The run's own conclusion
    is not checked: a failing Storybook leaves the deploy standing.
    """

    def __init__(self, api, repo):
        self.api = api
        self.repo = repo
        self.branch = None
        self._jobs = {}

    def _get(self, path):
        try:
            return self.api(path)
        except Exception as e:
            raise UnverifiedDeploys() from e

    def default_branch(self):
        if self.branch is None:
            self.branch = self._get(f"repos/{self.repo}").get("default_branch")
        return self.branch

    def jobs(self, run_id):
        if run_id not in self._jobs:
            out = self._get(f"repos/{self.repo}/actions/runs/{run_id}/jobs?filter=latest&per_page=100")
            self._jobs[run_id] = out.get("jobs", [])
        return self._jobs[run_id]

    def runs(self, sha):
        branch = self.default_branch()
        q = urllib.parse.urlencode(
            {"head_sha": sha, "event": "workflow_dispatch", "branch": branch, "per_page": 100}
        )
        out = self._get(f"repos/{self.repo}/actions/workflows/{RELEASE_WORKFLOW_FILE}/runs?{q}")
        runs = [
            r for r in out.get("workflow_runs", [])
            if r.get("event") == "workflow_dispatch"
            and (r.get("path") or "").startswith(RELEASE_WORKFLOW)
            and r.get("head_sha") == sha
            and r.get("head_branch") == branch
        ]
        return sorted(runs, key=lambda r: r.get("created_at", ""), reverse=True)

    def succeeded(self, sha, job_suffix):
        """True when a qualifying run on sha has a successful job named `... / <job_suffix>`."""
        for run in self.runs(sha):
            for job in self.jobs(run.get("id")):
                if (job.get("name") or "").endswith(f"/ {job_suffix}") and job.get("conclusion") == "success":
                    return True
        return False


def tested_commit(deploys, cwd, sha):
    """Newest commit in sha's first-parent history (sha included) deployed to develop."""
    commits = git(cwd, "rev-list", "--first-parent", "-n", str(SEARCH_DEPTH), sha).stdout.split()
    for c in commits:
        try:
            if deploys.succeeded(c, DEVELOP_JOB):
                return c
        except UnverifiedDeploys as e:
            raise UnverifiedDeploys(f"could not verify develop deploys on {c[:7]}") from e
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


def version_only(cwd, tested, sha, path, version):
    try:
        old = show_json(cwd, tested, path)
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


def code_differs(cwd, tested, sha, version):
    out = git(
        cwd, "diff", "--no-renames", "--name-status", "-z", "--no-ext-diff", "--no-textconv",
        "--no-color", tested, sha,
    ).stdout
    parts = out.split("\0")
    for status, path in zip(parts[0::2], parts[1::2]):
        if path == "CHANGELOG.md" or path.startswith(".changeset/"):
            continue
        if path in VERSION_FILES and status == "M" and version_only(cwd, tested, sha, path, version):
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

    deploys = Deploys(api, repo)
    try:
        tested = tested_commit(deploys, cwd, sha)
    except UnverifiedDeploys as e:
        return fail(f"{e}: {HINT}")
    if not tested:
        return fail(f"no develop deploy before {sha[:7]}: {HINT}")

    if code_differs(cwd, tested, sha, version):
        return fail(f"code differs from the last develop deploy {tested[:7]}: {HINT}")

    if require_e2e:
        try:
            e2e_ok = deploys.succeeded(tested, E2E_JOB)
        except UnverifiedDeploys:
            return fail(f"could not verify develop deploys on {tested[:7]}: {HINT}")
        if not e2e_ok:
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
