---
".github": minor
---

feat(workflows): [INF-1983] ci.yml runs its slots in one job by default (`layout: single`, about 2 billed minutes per run; `matrix` keeps a check per slot) and ignores `openwiki/**`; openwiki-update opens wiki PRs with the arami-bot App and an empty changeset so they pass rulesets
