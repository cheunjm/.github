---
".github": patch
---

`openwiki-update.yml`: the publish job bases the docs PR on the latest default branch instead of the triggering commit, so a queued run no longer opens a PR that conflicts with the docs the previous run merged.
