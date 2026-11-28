---
".github": patch
---

changeset-version.yml drops pending changesets when every one is empty (e.g. the OpenWiki bot's openwiki-docs.md), so the release run publishes instead of stopping at "All changesets are empty".
