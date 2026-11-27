---
".github": patch
---

The release gate now verifies the release-button run behind cd/develop and cd/e2e-develop statuses, so a forged github-actions[bot] status no longer unlocks production.
