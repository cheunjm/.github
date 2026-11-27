#!/usr/bin/env bash
# The Version PR's version-script when `app-json` is set (INF-1983 D44): run
# `changeset version`, then set expo.version in $APP_JSON to the new package.json version.
set -euo pipefail
if [ -z "${APP_JSON:-}" ]; then
  echo "::error::APP_JSON is empty: the workflow exports it from the app-json input"
  exit 1
fi
npx changeset version
python3 "$(dirname "$0")/sync_app_json.py" "$APP_JSON"
