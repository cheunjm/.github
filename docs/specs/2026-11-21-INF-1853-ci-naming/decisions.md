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

## D12: ci-node.yml covers four Node repos, not six
- **Problem:** D8 and the plan counted crosscheck and dotclaw as Node repos. Reading their CI for INF-1859 showed otherwise.
- **Options:** A: keep six and stretch ci-node.yml to run ruff, mypy, unittest and shellcheck; B: correct the list.
- **Choice:** B. `ci-node.yml` covers stock-tracker, ui, arami and starlog. crosscheck (ruff, mypy, unittest) and dotclaw (shellcheck, ruff) rename their local jobs to the pattern now and move to `ci-python.yml` and `ci-shell.yml` later, like the other non-Node repos.
- **Rationale:** `ci-node.yml` runs `npm ci` and npm scripts. Forcing Python and shell commands into it would turn the command overrides into a second, worse shell runner.
- **Proposed by:** ai
- **Chosen by:** ai
- **Impact:** low
- **Supersedes:** part of D8 (the list of six repos)

## D13: ci-node.yml interface
- **Problem:** What the shared Node CI exposes (Q11 and Q12 in the grilling session).
- **Options:** Filtering and extras inside the shared workflow, or callers pass booleans and overrides.
- **Choice:** Callers keep their own `paths-filter` job (named `ci / paths`) and pass `run_*` booleans. Inputs: `runner` (`ubuntu-latest`), `node_version` (`20`), `registry_scope`, `run_lint|typecheck|test|format|audit` (true), `run_build` (false), a `*_command` override per job, and `test_reports`. Secrets `PKG_READ_TOKEN` and `CODECOV_TOKEN` are optional. The `gate` job treats skipped needs as passes.
- **Rationale:** Filter groups differ a lot by repo (seven in stock-tracker), so they stay where the paths are; one `test_reports` flag keeps stock-tracker's JUnit and Codecov steps on the shared path.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** med

## D14: Codecov is its own input, separate from test_reports
- **Problem:** D13 bundled JUnit upload, test report and Codecov under one `test_reports` flag. ui's CI sends coverage to Codecov from a `coverage` folder and has no JUnit step, while stock-tracker has both, so one flag could not serve both.
- **Options:** A: keep one flag and make ui drop Codecov or keep its own test job; B: split into `test_reports` (JUnit upload and report) and `codecov` (plus `codecov_directory`, `codecov_flags`).
- **Choice:** B. `codecov_directory`, when set, also uploads that directory as the `coverage` artifact, which ui does today.
- **Rationale:** Dropping Codecov from ui would lose its `codecov/*` PR statuses, and a local test job would defeat the shared workflow. No repo used `test_reports` yet, so the split breaks nothing.
- **Proposed by:** ai
- **Chosen by:** ai
- **Impact:** low
- **Supersedes:** part of D13 (the `test_reports` definition)

## D15: ui's gate covers only the shared jobs
- **Problem:** `ci / gate` inside `ci-node.yml` cannot wait on a caller's other jobs, and ui has `contrast`, `chromatic` and `e2e` beyond the shared six.
- **Options:** A: `ci / gate` covers only the shared jobs and the extras stay informational; B: add a ui-only aggregate that waits on everything.
- **Choice:** A. Mergify in ui requires `ci / gate` and `changeset / check`.
- **Rationale:** ui's current Mergify rules require names no job produces (`lint-type-build`, `unit-test`, `e2e-web`, `check`), so nothing blocks on e2e or Chromatic today; the e2e job has a history of Chrome failures; Chromatic visual review is a human approval anyway.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** med
- **Labels:** revisit

## D16: ci-node.yml supports the Turborepo remote cache
- **Problem:** stock-tracker's scripts run through `turbo run ...` and its CI sets `TURBO_TOKEN` and `TURBO_TEAM` at workflow level. A caller's workflow-level `env` does not reach a reusable workflow, so migrating would silently drop the remote cache and slow builds.
- **Options:** A: add an optional `turbo_team` input and `TURBO_TOKEN` secret that `ci-node.yml` sets as `env` only on the lint, typecheck, test and build command steps (not on `npm ci` or third-party action steps), and only when `turbo_team` is non-empty; B: stock-tracker keeps its own CI jobs.
- **Choice:** A. Both are optional and empty by default, so other callers are unaffected.
- **Rationale:** B would leave the repo with the most CI on the old path, which is the problem this work removes.
- **Proposed by:** ai
- **Chosen by:** ai
- **Impact:** low
- **Not done:** PR runs can still write to the remote cache, as in stock-tracker's CI today. Making PR runs read-only is a possible follow-up once the exact Turborepo setting is verified.

## D17: INF-1918 repos use the shared callers, including `auto-update-branches`
- **Problem:** six repos were missed by the plan. maps-organizer, star-organizer and portfolio carried an inline `auto-update-branches` that rebases every open PR, which differs from the shared workflow (merges `main` into open non-draft same-repo PRs, never rebases).
- **Options:** A: keep the inline copy and only rename it; B: replace it with the shared caller, as dotfiles already did in INF-1866.
- **Choice:** B. maps-organizer, portfolio and graph-engine also call `ci-node.yml` (format and audit off, as before); mem0 and star-organizer keep local Python jobs with a new `ci / gate`.
- **Rationale:** The goal is as many reusable workflows as possible, and a second behavior for the same name would confuse the `branches / update` check. The repos are private and solo, so the rebase-versus-merge difference is low risk.
- **Proposed by:** ai
- **Chosen by:** ai
- **Impact:** low

## D18: Drop the lowercase `changeset` name and rename this repo's actionlint job
- **Problem:** D-earlier decisions kept `changeset` accepted in `ci-autofix.yml` and left `Validate workflow YAML` unrenamed until every repo was migrated and branch protection could change in the same step.
- **Options:** A: keep both names forever; B: after every repo uses `Changeset`, accept only `Changeset`, rename the job to `ci / actionlint`, and change branch protection in two steps (require only `changeset / check`, merge, then add `ci / actionlint`).
- **Choice:** B. A scan of every non-archived `cheunjm` repo found no workflow named `changeset`. The same step moves this repo's direct `auto-label.yml` trigger into a `labels.yml` caller, so its check reads `labels / decision-log` instead of the bare `decision-log`.
- **Rationale:** Required checks match by exact name, so a rename in one PR would block that PR. Two steps avoid a window where nothing is required on the wrong name.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** med
- **Supersedes:** the "stays `Validate workflow YAML` for now" note under the earlier ci.yml decision

## D19: Decision-log dispatch becomes a shared workflow (INF-1878)
- **Problem:** 14 repos each carried an inline `dispatch-decision-log.yml` (10 distinct versions) that spliced the PR title and body into a script with `${{ }}`. actionlint flags it as script injection, and fixing it meant 14 separate edits.
- **Options:** A: one shared `decision-dispatch.yml` and a thin caller per repo; B: patch every copy in place.
- **Choice:** A. The check stays `decisions / dispatch` (caller job id `decisions`, shared job `dispatch`).
- **Rationale:** One fix instead of 14, and the copies cannot drift again. The shared job passes every PR field through `env:` and builds the payload with `jq --arg`.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** med
