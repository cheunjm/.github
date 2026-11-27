---
".github": patch
---

The release gate now proves develop deploys from the release-button run jobs (develop-status, e2e-status) instead of commit statuses, so a forged status cannot unlock production.
