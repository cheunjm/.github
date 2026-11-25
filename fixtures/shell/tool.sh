#!/usr/bin/env bash
# Fixture for the shared ci.yml shell preset (self.yml).
set -euo pipefail

echo "hello ${1:-world}"
