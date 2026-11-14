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
| `auto-update-branches.yml` | Push to default branch (rebases open PRs) |
| `ci-autofix.yml` | `workflow_run` of `CI` / `changeset` (auto-fixes format/lint, adds missing changesets; optional `agent-fix` job attempts test/typecheck/build failures) |
| `agent-review.yml` | Pull request opened/synchronized (optional agent add-on: auto-review + PR body summary; nothing may depend on it) |
| `claude-review.yml` | Deprecated alias of `agent-review.yml`, removed once callers migrate (INF-1677) |
| `notify-merge.yml` | Push to default branch (parameterized: `slack_channel`, `repo_label`) |

Local to this repo, not callable (no `workflow_call`): `ci.yml` (actionlint on workflow changes), `auto-label.yml`.
