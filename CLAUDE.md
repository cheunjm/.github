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

## Reusable Workflows

Other repos call these via `uses: cheunjm/.github/.github/workflows/{name}.yml@main`. Available:

| Workflow | Trigger |
|----------|---------|
| `claude.yml` | `@claude` mentions in issues/PRs |
| `claude-code-review.yml` | PR opened/updated |
| `claude-pr-description.yml` | PR opened |
| `claude-changelog.yml` | PR merged |
| `claude-dependency-check.yml` | Dependency file changes |
| `claude-db-migration.yml` | Migration file changes |
| `notify-merge.yml` | Push to default branch (parameterized: `slack_channel`, `repo_label`) |
