---
".github": patch
---

`openwiki-update.yml`: when the OpenWiki planner exits without a plan (a model flake), the run retries once from a clean `openwiki/` instead of failing.
