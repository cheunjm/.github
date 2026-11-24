# .github

Default GitHub templates and reusable workflows for all `cheunjm` repos.

## What belongs here

- Issue templates (bug, feature, chore)
- PR template
- Reusable GitHub Actions workflows (Claude Code, code review, changelog, etc.)
- GitHub-specific configs (FUNDING.yml, CODEOWNERS, etc.)
- Tools registry (TOOLS.md)

## What does NOT belong here

- Coding conventions, standards, or style guides → `cheunjm/conventions`
- Repo-specific workflows or configs → the repo itself
- Secrets, credentials, or environment values → 1Password

## When to update this repo

When working on any `cheunjm` repo and you notice:
- A GitHub workflow being duplicated across repos — extract it here as a reusable workflow
- An issue or PR template improvement that should apply everywhere
- A new GitHub App or tool installed — update TOOLS.md

Ask Jace before adding or changing defaults — these affect all repos.

## Verification

After implementing changes, always run the test/verification steps from the plan before committing or opening a PR. After merging, verify the changes work on the default branch when possible. This includes running workflows locally (e.g. `act`), validating YAML syntax, and testing that calling repos can reference updated workflows. Do not treat verification as optional or skip it.

## Reusable Workflows

Other repos call these via `uses: cheunjm/.github/.github/workflows/{name}.yml@main`. Available:

| Workflow | Trigger |
|----------|---------|
| `db-migration-check.yml` | PR with migration file changes (deterministic SQL risk scan, no LLM) |
| `auto-update-branches.yml` | Push to default branch (merges it into open non-draft same-repo PRs that target it; never rebases) |
| `notify-merge.yml` | Push to default branch (parameterized: `slack_channel`, `repo_label`) |
| `changeset-check.yml` | Pull request (caller workflow is named `Changeset` with job id `changeset`): fails unless the PR adds a new `.changeset/*.md` (empty allowed), diffed against the PR's own base so each stack layer needs its own; validates with the pinned changesets CLI; `changeset-release/*` and `dependabot/*` are exempt. Job name is `check`, so the required context is `changeset / check` |
| `changeset-version.yml` | Push to default branch + `workflow_dispatch`: keeps one "Version Packages" PR per repo using the `arami-bot` token; optional `publish`, `install-command`, `registry-url`, `scope` inputs and `PKG_READ_TOKEN` secret. Pins `@changesets/cli` and `changelog-github` and installs them ephemerally (`--no-save`), so repos carry no changesets dependency. Repos that already declare both packages and install them (monorepos, private registries) pass `install-tooling: false` and use their own versions. Runs `changesets/action` v2, which refuses to run on Changesets CLI v2: keep the CLI on 3.x (Node 22+) here and in any repo that declares its own. Its v1 inputs were renamed (`version-script`, `publish-script`, `pr-title`, `commit-message`), and it needs the token via `github-token` |
| `changeset-prerelease.yml` | `workflow_dispatch` via caller (`phase`: `enter-dev` / `enter-rc` / `release-stable`): opens a PR that enters or exits changesets pre mode instead of pushing to the default branch |
| `ci-node.yml` | `workflow_call` for npm projects: jobs `lint`, `typecheck`, `test`, `format`, `audit`, `build` and one `gate`. With caller job id `ci` the checks are `ci / lint` and so on, and `ci / gate` is the only CI check a repo requires (failed or cancelled needs fail it, skipped needs pass). Each job runs only when its `run_*` input is true, so a caller that path-filters passes `run_lint: ${{ needs.paths.outputs.code == 'true' }}`. `*_command` inputs override the npm script (default `npm run lint`, `npm run typecheck`, `npm run test`, `npm run format:check`, `npm audit --audit-level=critical --omit=dev`, `npm run build`). `registry_scope` (e.g. `@cheunjm`) plus the `PKG_READ_TOKEN` secret reads private packages; `test_reports` adds a JUnit upload and test report (caller grants `checks: write`); `codecov` sends coverage to Codecov (`codecov_directory`, `codecov_flags`, `CODECOV_TOKEN` secret; a set directory is also uploaded as the `coverage` artifact); `turbo_team` plus the `TURBO_TOKEN` secret turn on the Turborepo remote cache for the lint, typecheck, test and build steps (a caller's workflow-level `env` does not reach a reusable workflow). `runner` defaults to `ubuntu-latest` and ignores `CI_RUNNER`. The file sets no `permissions:`; callers grant `contents: read` |
| `e2e-maestro.yml` | `workflow_call` for Maestro UI e2e: `platforms` (`android`, `ios`, `web`, comma-separated) fans out to jobs `android`, `ios`, `web` (with caller job id `e2e` the checks are `e2e / android` and so on). The workflow boots the device (Android emulator with KVM and a cached AVD, a throwaway iOS simulator that it deletes afterwards, headless Chrome) and passes it to the caller's `test-command` as `E2E_DEVICE` (emulator serial, simulator UDID, web URL) with `E2E_PLATFORM`; an empty `test-command` runs `maestro test <flows-path>` with a JUnit report. The caller supplies `install-command` (default `npm ci`), `setup-command`, `build-command`, `teardown-command` (always runs; use it to stop a local backend on self-hosted runners) and for web `serve-command` plus `web-url`. Maestro is pinned (`maestro-version`, default 2.12.1). `supabase-cli: true` installs the Supabase CLI at `supabase-version` (pinned, default 3.2.0; `latest` hits GitHub API rate limits). Runners: `android-runner` and `web-runner` default `ubuntu-latest`, `ios-runner` defaults to `mac-studio` (needs Xcode and, for a local Supabase stack, Docker Desktop running; the job exposes only `docker` from `/usr/local/bin`, uses an empty `DOCKER_CONFIG`, selects Java 17, and keeps Maestro away from the host's `~/.android`) and is skipped for fork PRs. The host must keep `~/Library/Android` and `~/Library/Developer/CoreSimulator/Devices` on a disk the runner can read (not an exFAT USB drive): Xcode's build service and CoreSimulator hang or fail there. Concurrency never cancels a running suite: a new push waits for it. Failed jobs upload `artifact-path` (default `.e2e`). Spec: `docs/specs/2026-11-22-INF-1908-e2e-maestro/` |
| `auto-label.yml` | Pull request opened (adds the `decision-log` label to `feat/` and `fix/` branches; the calling job must grant `pull-requests: write`; this repo calls it from `labels.yml`) |
| `decision-dispatch.yml` | `workflow_call` on a merged PR (caller trigger `pull_request: closed`): when the PR has the `decision-log` label, sends a `new-decision` dispatch to `cheunjm/engineering-log` with the GitHub App token (needs `BOT_APP_ID` and `BOT_PRIVATE_KEY`; callers use `secrets: inherit` and `permissions: {}`). With caller job id `decisions` the check is `decisions / dispatch`. PR fields reach the script only through `env:` and the payload is built with `jq --arg`, so a title or body cannot inject shell. Optional `runner` input |

Every callable workflow takes an optional `runner` input that sets `runs-on` (default `ubuntu-latest`). Pass a self-hosted label (e.g. `runner: mac-studio`) to run on the Mac Studio. Self-hosted jobs run on macOS, so only use it on private repos and with steps that don't assume Linux, and register a `mac-studio` runner in the caller repo first, or the jobs queue forever. The three `changeset-*.yml` workflows default `runner` to empty and fall back to the calling repo's `CI_RUNNER` variable, then `ubuntu-latest`, so a repo that sets `CI_RUNNER=mac-studio` runs them on the Studio with no per-caller change, and a repo without the variable stays on hosted runners.

Local to this repo, not callable (no `workflow_call`): `ci.yml` (actionlint on workflow changes; the check is `ci / actionlint`).
