---
".github": patch
---

fix(workflows): [INF-1983] push major and prerelease tags with git instead of the refs API, which answers 403 for the App on commits that carry workflow files
