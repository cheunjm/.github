#!/usr/bin/env python3
"""Expand/contract guard for SQL migrations (INF-1983 D42, D43). Stdlib only.

  contract_check.py scan      --base B --head H --paths 'glob\\nglob'
  contract_check.py changeset --base B --head H --paths 'glob\\nglob'

`scan` fails when an added migration line drops a table or column, renames a
table or column, or changes a column type, unless the same file carries a line
`-- contract: safe after vX.Y.Z`. `changeset` fails when the PR adds or changes
a migration with a `-- contract:` line but no changeset added by the PR gives
this repo's package.json name `minor`.

Matching is per statement and case-insensitive, on added lines only: comments
(`--` to end of line, also inside a string literal, and `/* */`) are stripped, the
lines are joined and split on `;`, and the patterns are searched anywhere in a
statement (so a DO $$ ... $$ body is caught). Allowed: DROP FUNCTION/POLICY/TRIGGER/INDEX and ALTER TABLE
DROP CONSTRAINT/DEFAULT/NOT NULL/IDENTITY/EXPRESSION.
"""

import argparse
import json
import re
import subprocess
import sys

DROP_OBJECT = re.compile(r"\bDROP\s+(TABLE|VIEW|MATERIALIZED\s+VIEW)\b", re.IGNORECASE)
ALTER_TABLE = re.compile(r"\bALTER\s+TABLE\b", re.IGNORECASE)
BLOCK_COMMENT = re.compile(r"/\*.*?(\*/|\Z)", re.DOTALL)
# Inside ALTER TABLE: DROP COLUMN (with or without the COLUMN keyword) but not the
# DROP CONSTRAINT / DEFAULT / NOT NULL / IDENTITY / EXPRESSION sub-commands.
ALTER_DROP = re.compile(r"\bDROP\s+(?!CONSTRAINT\b|DEFAULT\b|NOT\s+NULL\b|IDENTITY\b|EXPRESSION\b)\S", re.IGNORECASE)
ALTER_RENAME = re.compile(r"\bRENAME\s+(TO\b|(COLUMN\s+)?\S+\s+TO\b)", re.IGNORECASE)
ALTER_TYPE = re.compile(r"\bALTER\s+(?:COLUMN\s+)?(?!COLUMN\b|TABLE\b)\S+\s+(?:SET\s+DATA\s+)?TYPE\b",
                        re.IGNORECASE)
MARKER = re.compile(r"^\s*--\s*contract:\s*safe after v\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?\s*$",
                    re.MULTILINE)
ANY_CONTRACT_LINE = re.compile(r"^\s*--\s*contract:", re.MULTILINE)
HUNK = re.compile(r"^@@ -\S+ \+(\d+)")
CHANGESET_ENTRY = re.compile(r"""^\s*["']?(.+?)["']?\s*:\s*(major|minor|patch)\s*$""")


def is_contract(statement):
    """Patterns are searched anywhere in the statement, so DO $$ ... $$ bodies count."""
    if DROP_OBJECT.search(statement):
        return True
    m = ALTER_TABLE.search(statement)
    if m:
        rest = statement[m.start():]
        return bool(ALTER_DROP.search(rest) or ALTER_RENAME.search(rest) or ALTER_TYPE.search(rest))
    return False


def statements(lines):
    """Split (lineno, text) pairs into (start_line, statement) on `;`.

    Comments (`--` to end of line, `/* */` across lines) are blanked first. Lines are joined
    per run of consecutive line numbers, so separate hunks never merge.
    """
    groups = []
    for no, text in lines:
        if groups and groups[-1][-1][0] + 1 == no:
            groups[-1].append((no, text))
        else:
            groups.append([(no, text)])
    out = []
    for group in groups:
        text = "\n".join(t.split("--", 1)[0] for _, t in group)
        text = BLOCK_COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
        offset = 0
        for seg in text.split(";"):
            stripped = seg.lstrip()
            if stripped.strip():
                first = offset + len(seg) - len(stripped)
                out.append((group[0][0] + text.count("\n", 0, first), " ".join(stripped.split())))
            offset += len(seg) + 1
    return out


def scan(diff_text):
    """Return (file, line, statement) for each added SQL statement that is a contract change."""
    added = {}
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
            added.setdefault(path, []).append((line, raw[1:]))
            line += 1
    found = []
    for path, lines in added.items():
        for start, stmt in statements(lines):
            if is_contract(stmt):
                found.append((path, start, stmt))
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
    diff = git("diff", "-U0", "--no-renames", "--diff-filter=AM", a.base, a.head, "--", *specs)
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
    changed = git("diff", "--name-only", "--no-renames", "--diff-filter=AM", a.base, a.head, "--", *specs).split("\n")
    contract = [f for f in changed if f and ANY_CONTRACT_LINE.search(head_text(a.head, f))]
    if not contract:
        print("No contract migration in this PR.")
        return 0
    with open("package.json") as fh:
        package = json.load(fh)["name"]
    added = [f for f in git("diff", "--name-only", "--no-renames", "--diff-filter=A", a.base, a.head, "--", ".changeset/*.md").split("\n")
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
