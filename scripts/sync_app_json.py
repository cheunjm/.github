#!/usr/bin/env python3
"""Set app.json `expo.version` to package.json `version` (INF-1983 D44). Stdlib only.

  sync_app_json.py APP_JSON [PACKAGE_JSON]   (PACKAGE_JSON defaults to package.json)

Rewrites the file as 2-space JSON with a trailing newline. Fails when
`expo.version` is missing, so a wrong path or a differently shaped file is
never silently skipped.
"""

import json
import sys


def main(argv):
    if not argv:
        print("usage: sync_app_json.py APP_JSON [PACKAGE_JSON]", file=sys.stderr)
        return 2
    app_path = argv[0]
    pkg_path = argv[1] if len(argv) > 1 else "package.json"
    with open(pkg_path) as fh:
        version = json.load(fh)["version"]
    with open(app_path) as fh:
        app = json.load(fh)
    expo = app.get("expo") if isinstance(app, dict) else None
    if not isinstance(expo, dict) or "version" not in expo:
        print("::error::%s has no expo.version to set" % app_path)
        return 1
    expo["version"] = version
    with open(app_path, "w") as fh:
        json.dump(app, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("%s expo.version = %s" % (app_path, version))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
