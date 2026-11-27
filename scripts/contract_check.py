#!/usr/bin/env python3
"""Expand/contract guard for SQL migrations (INF-1983 D42, D43). Stdlib only.

  contract_check.py scan      --base B --head H --paths 'glob\\nglob'
  contract_check.py changeset --base B --head H --paths 'glob\\nglob'

`scan` fails when an added migration line drops a table or column, renames a
table or column, or changes a column type, unless the same file carries a line
`-- contract: safe after vX.Y.Z`. `changeset` fails when the PR adds or changes
a migration with a `-- contract:` line but no changeset added by the PR gives
this repo's package.json name `minor`.

Matching is line-based and case-insensitive, on added lines only, after
stripping `--` comments (a `--` inside a string literal also ends the line).
"""

import argparse
import json
import re
import subprocess
import sys

CONTRACT = re.compile(
    r"\bDROP\s+(TABLE|COLUMN)\b"
    r"|\bRENAME\s+(TO|COLUMN)\b"
    r"|\bALTER\s+COLUMN\s+\S+\s+(SET\s+DATA\s+)?TYPE\b",
    re.IGNORECASE,
)
MARKER = re.compile(r"^\s*--\s*contract:\s*safe after v\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?\s*$",
                    re.MULTILINE)
ANY_CONTRACT_LINE = re.compile(r"^\s*--\s*contract:", re.MULTILINE)
HUNK = re.compile(r"^@@ -\S+ \+(\d+)")
CHANGESET_ENTRY = re.compile(r"""^\s*["']?(.+?)["']?\s*:\s*(major|minor|patch)\s*$""")


def scan(diff_text):
    """Return (file, line, text) for each added line that is a contract change."""
    found = []
    path = None
    line = 0
    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            target = raw[4:]
            path = target[2:] if target.startswith("b/") else None
            continue
        if raw.startswith("--- ") or raw.startswith("diff "):
            continue
        m = HUNK.match(raw)
        if m:
            line = int(m.group(1))
            continue
        if raw.startswith("+") and path:
            text = raw[1:]
            if CONTRACT.search(text.split("--", 1)[0]):
                found.append((path, line, text))
            line += 1
    return found


def has_marker(text):
    return bool(MARKER.search(text))


def error_text(loc):
    return '%s is a contract change: add "-- contract: safe after vX.Y.Z" and a minor changeset' % loc


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def pathspecs(paths):
    return [":(glob)%s" % p.strip() for p in paths.splitlines() if p.strip()]


def head_text(head, path):
    return git("show", "%s:%s" % (head, path))


def cmd_scan(a):
    specs = pathspecs(a.paths)
    if not specs:
        print("::error::migration paths are empty")
        return 1
    diff = git("diff", "-U0", "--diff-filter=AM", a.base, a.head, "--", *specs)
    bad = []
    markers = {}
    for path, line, _ in scan(diff):
        if path not in markers:
            markers[path] = has_marker(head_text(a.head, path))
        if not markers[path]:
            bad.append((path, line))
    for path, line in bad:
        print("::error file=%s,line=%d::%s" % (path, line, error_text("%s:%d" % (path, line))))
    if not bad:
        print("No unmarked contract changes.")
    return 1 if bad else 0


def changeset_levels(text, package):
    """Levels the changeset frontmatter gives `package`."""
    parts = text.split("---")
    if len(parts) < 3:
        return []
    levels = []
    for entry in parts[1].splitlines():
        m = CHANGESET_ENTRY.match(entry)
        if m and m.group(1) == package:
            levels.append(m.group(2))
    return levels


def cmd_changeset(a):
    specs = pathspecs(a.paths)
    if not specs:
        return 0
    changed = git("diff", "--name-only", "--diff-filter=AM", a.base, a.head, "--", *specs).split("\n")
    contract = [f for f in changed if f and ANY_CONTRACT_LINE.search(head_text(a.head, f))]
    if not contract:
        print("No contract migration in this PR.")
        return 0
    with open("package.json") as fh:
        package = json.load(fh)["name"]
    added = [f for f in git("diff", "--name-only", "--diff-filter=A", a.base, a.head, "--", ".changeset/*.md").split("\n")
             if f and f != ".changeset/README.md"]
    for f in added:
        if "minor" in changeset_levels(head_text(a.head, f), package):
            print("Contract migration %s covered by minor changeset %s." % (", ".join(contract), f))
            return 0
    print("::error::a contract migration needs a minor changeset (%s): add one giving \"%s\" minor" %
          (", ".join(contract), package))
    return 1


def main(argv):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("scan", cmd_scan), ("changeset", cmd_changeset)):
        s = sub.add_parser(name)
        s.add_argument("--base", required=True)
        s.add_argument("--head", default="HEAD")
        s.add_argument("--paths", required=True)
        s.set_defaults(fn=fn)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
