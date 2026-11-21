# Decisions: Unified CI check naming and reusable CI workflows

Numbers are never reused, renumbered or deleted. Reverse a decision by adding a new entry that supersedes it.

## D1: Scope covers every check from our own workflows
- **Problem:** Rename only the shared workflows' checks, or every check in every repo.
- **Options:** A: shared workflows and their callers only; B: everything, including repo-local jobs.
- **Choice:** B.
- **Rationale:** The user wants one naming everywhere and as many reusable workflows as possible.
- **Proposed by:** ai (proposed A)
- **Chosen by:** human
- **Impact:** high

## D2: Every check is `<area> / <action>`, lowercase
- **Problem:** Which pattern, and does it apply to repo-local jobs.
- **Options:** A: `<area> / <action>` for shared checks, plain words for local jobs; B: `<area> / <action>` for all; C: flat names without a slash.
- **Choice:** B. Repo-local jobs become `ci / lint`, `ci / test` and so on.
- **Rationale:** GitHub adds the slash for any reusable workflow, so a flat style cannot be uniform. One pattern for all also lets repo-local jobs move into reusable workflows without another rename.
- **Proposed by:** human (changed the AI's A)
- **Chosen by:** human
- **Impact:** high

## D3: One reusable CI workflow per stack
- **Problem:** How repo-local CI becomes reusable.
- **Options:** A: one workflow per stack with boolean-toggled jobs and overridable commands; B: one workflow per job; C: leave repo-specific jobs local.
- **Choice:** A for the shared jobs, plus C for repo-specific logic (prisma, docker, schema, e2e), which stays local but follows the naming. Accepted via "continue".
- **Rationale:** One shared setup (Node, cache, registry auth) instead of repeating it per job; repos switch jobs on or off with inputs.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** high

## D4: One required gate per repo, `ci / gate`
- **Problem:** What Mergify and branch protection require.
- **Options:** A: one aggregate job; B: list every job.
- **Choice:** A. Mergify requires `ci / gate` and `changeset / check`.
- **Rationale:** Mergify lists have already drifted from real names in stock-tracker and ui. An aggregate means adding or removing a job never edits Mergify. Skipped needs count as success so path-filtered repos pass.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** high

## D5: Area and action vocabulary
- **Problem:** The words used for areas and actions.
- **Options:** Accept the proposed table or edit words.
- **Choice:** Accepted as proposed:

  | Today | New check name |
  |---|---|
  | lint, typecheck, test, build, format, audit, aggregate CI | `ci / lint`, `ci / typecheck`, `ci / test`, `ci / build`, `ci / format`, `ci / audit`, `ci / gate` |
  | `changeset / check` | unchanged |
  | Version Packages job | `changeset / version` |
  | prerelease job | `changeset / prerelease` |
  | `review / Review (openclaw)` | `review / openclaw` |
  | `notify / notify` | `notify / slack` |
  | `decision-log / decision-log`, `dispatch` | `labels / decision-log`, `decisions / dispatch` |
  | `update / update` | `branches / update` |
  | `migration` | `migrations / scan` |
  | ci-autofix jobs | `autofix / <step>` (for example `autofix / format`, `autofix / changeset`, `autofix / agent`) |
  | openwiki update | `wiki / update` |
  | Release | `release / publish` |
  | repo-specific | `db / prisma`, `docker / build`, `schema / check`, `e2e / web`, `ci / shellcheck`, `ci / lint-python`, `ci / paths` |
- **Rationale:** Area is the file's purpose and action is the verb; support jobs such as `paths-filter` stay in their area with a plain name.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** med
- **Labels:** revisit (exact `autofix / <step>` words not yet checked against ci-autofix's internal jobs)

## D6: Title Case workflow names, with a dual-name transition
- **Problem:** Workflow `name:` style, and how to rename safely given `ci-autofix` triggers on the names `CI` and `changeset`.
- **Options:** A: Title Case area words, shared renames first with `ci-autofix` accepting old and new names, then per-repo PRs, then remove old names; B: one coordinated sweep.
- **Choice:** A.
- **Rationale:** A repo that lags in a sweep would lose autofix and its merge gate until it catches up.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** high

## D7: App-created checks are excluded
- **Problem:** Mergify, Codecov and Chromatic checks have names we do not control.
- **Options:** A: exclude them; B: wrap them in our own workflows.
- **Choice:** A. The convention applies to our own workflows only.
- **Rationale:** `UI Tests` and similar statuses are created by the app and cannot all be wrapped; wrapping would move apps onto tokens for little gain.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** low

## D8: First cut is `ci-node.yml` only
- **Problem:** Which stacks get a shared workflow first.
- **Options:** A: `ci-node.yml` first for six Node repos; shell and Python repos rename local jobs only; B: all three stacks at once.
- **Choice:** A.
- **Rationale:** Prove the design on Node before designing the shell and Python variants.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** med

## D9: `ci-node.yml` defaults to `ubuntu-latest`
- **Problem:** Where CI runs by default, given one job at a time per Studio runner.
- **Options:** A: `runner` input, then `CI_RUNNER` variable, then `ubuntu-latest`; B: Studio by default; C: always hosted.
- **Choice:** `ubuntu-latest` by default, with a `runner` input to override. The `CI_RUNNER` variable is not consulted for CI.
- **Rationale:** CI is the heaviest workload and the Studio would serialize its parallel jobs; hosted keeps PR feedback fast.
- **Proposed by:** ai (proposed A)
- **Chosen by:** human
- **Impact:** med
- **Labels:** revisit (measure real Studio CI times first)

## D10: Delivery order and tracking
- **Problem:** How to ship a change that spans every repo.
- **Options:** A: spec, then convention PR, then stacked code PRs in `.github`, then one PR per repo, tracked by one Linear parent with a child per step; B: code straight away.
- **Choice:** A. Accepted via "continue".
- **Rationale:** The decisions otherwise live only in one conversation and a fresh session could not resume a step.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** low

## D11: Action words for autofix, wiki and release, and local job names
- **Problem:** D5 left the `autofix / <step>` words open (marked revisit), and reading the shared files showed `wiki / update` and `release / publish` do not match how those workflows are built.
- **Options:** A: keep D5's words; B: derive them from the real jobs.
- **Choice:** B.
  - ci-autofix jobs: `autofix / resolve-pr`, `autofix / format-lint`, `autofix / agent-gather`, `autofix / agent-patch`, `autofix / agent-verify`, `autofix / agent-push`, `autofix / changeset`. The script-fix job fixes both format and lint, so `format-lint` replaces `format`.
  - openwiki has two jobs, so it is `wiki / generate` and `wiki / publish` (there is no single `wiki / update`).
  - The Release workflow only calls `changeset-version.yml`, which publishes inside the same job via `changesets/action`. Its check is `changeset / version` (caller job id `changeset`), so there is no `release / publish`.
  - A repo-local job, which GitHub does not prefix, sets `name: "<area> / <action>"` itself (for example `ci / actionlint`, `decisions / dispatch`).
  - This repo's own `ci.yml` job stays `Validate workflow YAML` for now: branch protection on `cheunjm/.github` requires that exact name (plus `changeset / check`), so it is renamed to `ci / actionlint` only in the same step that updates the protection rule.
  - `ci-autofix` accepts the workflow names `changeset` and `Changeset`. The agent-fix gather step matches failed job names with `grep -i test|typecheck|build`, which still matches `ci / test`, `ci / typecheck` and `ci / build`.
- **Rationale:** Names should describe the job that exists. Keeping a name that does not match its workflow would break the rule that the action says what the job does.
- **Proposed by:** ai
- **Chosen by:** ai
- **Impact:** low
- **Labels:** revisit
- **Supersedes:** part of D5 (the autofix, wiki and release rows)
