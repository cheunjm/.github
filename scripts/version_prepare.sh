#!/usr/bin/env bash
# Export what the Version PR's version-script needs when `app-json` is set (INF-1983 D44):
# APP_JSON (validated) and VERSION_SCRIPT, appended to $GITHUB_ENV. Reads APP_JSON_INPUT.
set -euo pipefail
value="${APP_JSON_INPUT:-}"
if [[ ! "$value" =~ ^[A-Za-z0-9._/-]+$ || "$value" == /* || "/$value/" == *"/../"* ]]; then
  echo "::error::app-json must be a relative path of letters, digits, . _ - / without '..' segments (got: $value)"
  exit 1
fi
dir="$(cd "$(dirname "$0")" && pwd)"
{
  echo "APP_JSON=$value"
  echo "VERSION_SCRIPT=$dir/version_with_app_json.sh"
} >> "$GITHUB_ENV"
