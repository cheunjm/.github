#!/usr/bin/env python3
"""Set app.json `expo.version` to package.json `version` (INF-1983 D44). Stdlib only.

  sync_app_json.py APP_JSON [PACKAGE_JSON]   (PACKAGE_JSON defaults to package.json)

Replaces only the `expo.version` string in the text, so every other byte (inline
arrays, key order, indentation, trailing newline) is untouched. Fails when
`expo.version` is missing or ambiguous, so a wrong path or a differently shaped file is
never silently skipped.
"""

import json
import sys


def skip_ws(t, i):
    while i < len(t) and t[i] in " \t\r\n":
        i += 1
    return i


def parse(t, i):
    """Parse the JSON value at t[i]. Return (end, members): members maps each object key to
    (start, end, members) and is None for non-objects."""
    c = t[i]
    if c == '"':
        j = i + 1
        while t[j] != '"':
            j += 2 if t[j] == "\\" else 1
        return j + 1, None
    if c == "{":
        members = {}
        i = skip_ws(t, i + 1)
        while t[i] != "}":
            ke, _ = parse(t, i)
            key = json.loads(t[i:ke])
            i = skip_ws(t, ke)
            i = skip_ws(t, i + 1)
            ve, sub = parse(t, i)
            if key in members:
                raise ValueError("ambiguous: duplicate key %r" % key)
            members[key] = (i, ve, sub)
            i = skip_ws(t, ve)
            if t[i] == ",":
                i = skip_ws(t, i + 1)
        return i + 1, members
    if c == "[":
        i = skip_ws(t, i + 1)
        while t[i] != "]":
            i, _ = parse(t, i)
            i = skip_ws(t, i)
            if t[i] == ",":
                i = skip_ws(t, i + 1)
        return i + 1, None
    j = i
    while t[j] not in ",}] \t\r\n":
        j += 1
    return j, None


def main(argv):
    if not argv:
        print("usage: sync_app_json.py APP_JSON [PACKAGE_JSON]", file=sys.stderr)
        return 2
    app_path = argv[0]
    pkg_path = argv[1] if len(argv) > 1 else "package.json"
    with open(pkg_path) as fh:
        version = json.load(fh)["version"]
    with open(app_path) as fh:
        text = fh.read()
    json.loads(text)
    try:
        _, top = parse(text, skip_ws(text, 0))
    except ValueError as e:
        print("::error::%s is %s" % (app_path, e))
        return 1
    expo = (top or {}).get("expo")
    entry = (expo[2] or {}).get("version") if expo else None
    if not entry or not text.startswith('"', entry[0]):
        print("::error::%s has no expo.version to set" % app_path)
        return 1
    new = text[:entry[0]] + json.dumps(version) + text[entry[1]:]
    with open(app_path, "w") as fh:
        fh.write(new)
    print("%s expo.version = %s" % (app_path, version))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
