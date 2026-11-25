---
".github": patch
---

fix(workflows): [INF-1983] major-tag.yml looks up the major tag exactly (git/ref) and resolves the release commit, so the first v1 is created; add a workflow_dispatch to point a major tag at an existing release
