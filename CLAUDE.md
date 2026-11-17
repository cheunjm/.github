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
| `ci-autofix.yml` | `workflow_run` of `CI` / `changeset` (auto-fixes format/lint on files the PR changed only, adds missing changesets, skips fork PRs; optional `agent-fix` job attempts test/typecheck/build failures; `engine: openclaw` replaces Claude with a tool-less openclaw patch loop: model call on the `runner`, patch validated, applied and checked by `verify_command` on a hosted runner, pushed only if it passes; `engine: none` turns agent-fix off) |
| `agent-review.yml` | Pull request opened/synchronized (optional agent add-on: auto-review + PR body summary; nothing may depend on it). `engine: openclaw` + `runner: mac-studio` runs it as a tool-less openclaw model call on the Studio instead of Claude |
| `notify-merge.yml` | Push to default branch (parameterized: `slack_channel`, `repo_label`) |
| `auto-label.yml` | Pull request opened (adds the `decision-log` label to `feat/` and `fix/` branches; the calling job must grant `pull-requests: write`; this repo also triggers it directly) |

Every callable workflow takes an optional `runner` input (default `ubuntu-latest`) that sets `runs-on`. Pass a self-hosted label (e.g. `runner: mac-studio`) to run on the Mac Studio. Self-hosted jobs run on macOS, so only use it on private repos and with steps that don't assume Linux. Jobs that give an agent tools (`agent-fix`, the Claude engine of `agent-review`) ignore the input and always run on GitHub-hosted `ubuntu-latest`: the Studio has no isolation, so a tool-using agent there would run as your user. `ci-autofix.yml` handles this for its Python path: on macOS it skips `actions/setup-python` (its installer hardcodes `/Users/runner`) and installs into a venv on the host `python3`.

Local to this repo, not callable (no `workflow_call`): `ci.yml` (actionlint on workflow changes).
