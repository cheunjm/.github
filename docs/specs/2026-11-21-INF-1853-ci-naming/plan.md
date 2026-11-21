# Unified CI check naming and reusable CI workflows

Linear: https://linear.app/jaemincheun/issue/INF-1853/ci-unify-check-naming-as-area-action-across-all-repos-with-reusable

## Background and constraints
Check names across `cheunjm` repos are inconsistent. Workflow names mix styles (`CI`, `changeset`, `Agent Review`, `Notify on Merge`, `Auto-update PR branches`, `Agents CI`, `sync-dotfiles`). Checks from reusable workflows stutter or do not describe themselves (`notify / notify`, `update / update`, `decision-log / decision-log`, `review / Review (openclaw)`). Each repo also writes its own lint/test/typecheck/build jobs.

Constraints found while reading the repos:
- A check from a reusable workflow is named `<caller job> / <called job>`. The first half lives in each repo's caller, the second half in the shared file.
- Mergify's required-check lists have already drifted from the real names (stock-tracker requires `check-types` but the job is `typecheck`; ui requires `check`, `e2e-web`, `lint-type-build`, `unit-test` but runs `lint`, `typecheck`, `test`, `e2e`).
- `ci-autofix.yml` is triggered by a `workflow_run` of the workflows named `CI` and `changeset`, so renaming those workflows silently stops autofix until the trigger list is updated.
- Each repo has one `mac-studio` runner that runs one job at a time, so a parallel CI would serialize there.
- Some checks come from outside apps (Mergify, Codecov, Chromatic) and cannot be renamed by us.

## Scope
**In scope**
- Every check produced by our own workflows in every `cheunjm` repo, named `<area> / <action>`, lowercase.
- A reusable `ci-node.yml` (lint, typecheck, test, build, format, audit, gate) used by the six Node repos: stock-tracker, ui, arami, starlog, crosscheck, dotclaw.
- Renaming shared-workflow jobs in this repo, with `ci-autofix.yml` accepting old and new workflow names during the transition.
- Per-repo caller renames and Mergify rules that require only `ci / gate` and `changeset / check`.
- Shell, Python and no-CI repos (claude-statusline, clipsync, dotfiles, engineering-log, conventions) rename their local jobs to the pattern.
- A convention doc in `cheunjm/conventions`.

**Out of scope** (will not do)
- Renaming checks created by apps: `Mergify Merge Queue`, `Summary`, `codecov/*`, `chromatic`, `UI Tests`.
- `ci-shell.yml` and `ci-python.yml` (listed under Later).
- Changing what any check does. This work renames and regroups only.
- Moving CI onto the Mac Studio.

## Stage goals
1. **Spec and convention**: this folder plus the convention PR in `cheunjm/conventions`. Done when both are merged.
2. **Shared renames**: shared workflow jobs renamed per the vocabulary, and `ci-autofix.yml` triggers on both the old and new workflow names. Done when a test PR in a caller repo shows the new names and autofix still fires.
3. **`ci-node.yml`**: reusable workflow with boolean-toggled jobs, command overrides, `runner` input defaulting to `ubuntu-latest`, and a `ci / gate` job that fails on any failed or cancelled need and passes on skipped. Done when one Node repo runs it end to end.
4. **Node repos**: each of stock-tracker, ui, arami, starlog, crosscheck, dotclaw switches to `ci-node.yml`, renames its caller jobs and workflow names, and replaces its Mergify required checks with `ci / gate` and `changeset / check`. Done when each repo's PR checks list shows only `<area> / <action>` names (plus app checks) and Mergify gates on the new names.
5. **Other repos**: claude-statusline, clipsync, dotfiles, engineering-log and conventions rename local jobs. Done when each shows only the pattern plus app checks.
6. **Cleanup**: remove the old workflow names from `ci-autofix.yml`. Done when no repo has a required check name that no workflow produces.

## Verification
- Per repo: open a PR and read `gh pr checks <n>`; every non-app check matches `^[a-z0-9-]+ / [a-z0-9-]+$`.
- Per repo: `.mergify.yml` required checks all exist in the latest PR's check list.
- Autofix: a PR with a deliberate format error in a caller repo still gets an autofix commit.
- `ci / gate`: a PR with one job failing blocks the gate; a PR with a path-filtered skip passes it.
- `actionlint` on every changed workflow (the custom `mac-studio` label is a known false positive).

## Assumptions
- Mergify matches required checks by exact check name.
- The `<caller job> / <called job>` naming rule holds for every reusable workflow call.
- All callers are private repos and callers use `secrets: inherit`.
- Free-plan private repos cannot block merges on required checks, so the gate is advisory there.

## Terms
- **area**: what a check is about, taken from the shared workflow's purpose (`ci`, `changeset`, `review`, `notify`, `labels`, `decisions`, `branches`, `migrations`, `autofix`, `wiki`, `release`, `db`, `docker`, `schema`, `e2e`).
- **action**: the verb or short noun for what the job does (`lint`, `check`, `openclaw`, `slack`).
- **gate**: the aggregate job `ci / gate` that depends on every other `ci` job.

## Later
- `ci-shell.yml` and `ci-python.yml`.
- Wrapping Chromatic and Codecov so they show as `visual / chromatic` and `coverage / codecov` (not planned; app-created statuses cannot all be wrapped).
- Reconsidering a `CI_RUNNER` fallback for CI once Studio CI times are measured.
