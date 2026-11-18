# Changesets

Every PR adds one changeset file here: run `npx changeset` (or `npx changeset add --empty` for docs/CI-only changes) and commit the generated file. The `changeset` check fails PRs without one. A "Version Packages" PR consumes them into `CHANGELOG.md` and a version bump.

The root `package.json` is metadata only (this repo is not a Node package). Shared workflows live in `cheunjm/.github`.
