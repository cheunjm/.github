# CI/CD unification across cheunjm repos

Issue: [INF-1983](https://linear.app/jaemincheun/issue/INF-1983/cicd-unification-all-cicd-logic-in-cheunjmgithub-v1). Decisions and their reasons: [decisions.md](decisions.md).

## Background and constraints

PR plumbing (labels, changesets, releases, branch auto-update, decision log, merge notifications) is already shared from `cheunjm/.github`. CI and CD are not:

- **CI:** 5 repos call `ci-node`. 6 run inline CI that reinvents the paths filter and gate. 2 have no CI.
- **CD:** each app repo carries its own EAS build, EAS update, Vercel and Supabase files, about 900 lines across arami, starlog and ui, with no deploy ordering.

The goal (D1) is that every CI/CD behavior is defined once in `.github`. Each repo holds only thin callers that pass inputs and secrets.

Constraints:
- **Account:** `cheunjm` is a personal account. There are no org-level required workflows, org secrets or org runners, so secrets and self-hosted runners are registered per repo.
- **Enforcement:** private repos on GitHub Free have no branch protection or rulesets. GitHub Pro, through the Student Developer Pack, is active from about 2026-11-25 (D18).
- **Cost:** hosted Linux minutes cost about $86 in November 2026. Everything runs hosted except EAS local builds and native e2e, which run on the `mac-studio` runner (D9, D10, D13).
- **Push rules:** the global pre-push hook blocks pushes to `main`. Every change goes through a PR.

Repos in scope (D3): arami, claude-statusline, clipsync, conventions, dotclaw, engineering-log, maps-organizer, mem0, portfolio, star-organizer, starlog, ui, and `.github` itself.

| Repo | Stack | CI today | CD today |
|---|---|---|---|
| arami | Expo, Supabase, Vercel | `ci-node` | EAS build (local) and update, Vercel web; native e2e on the Version PR |
| starlog | Expo, Supabase, Vercel | `ci-node`, inline e2e | EAS build (cloud) and update, Vercel web, Supabase |
| ui | Expo library, Storybook, Vercel | `ci-node` + inline jobs, web e2e | EAS build and update on `release: published` |
| maps-organizer, portfolio | Node | `ci-node` | none |
| mem0, star-organizer | Python | inline | none (star-organizer has a cron) |
| claude-statusline, clipsync | Shell | inline | none |
| dotclaw | Shell and Python | inline | none |
| conventions, engineering-log | Docs, Node | none | none |

## Scope

**In scope**
- **Shared `ci`:** stack-agnostic (D5), with fixed slots lint, typecheck, test, format, audit and build. It has toolchain inputs (`node_version`, `python_version`, apt packages), a `preset` input (`node`, `python` or `shell`) that supplies default commands, per-slot command overrides, a built-in paths filter, and a `gate` job. It also carries over `ci-node`'s extras: private registry, test reports, Codecov and the Turborepo cache.
- **Shared `cd` orchestrator (D7):**
  - **Targets:** Supabase (`db push`, `functions deploy`), web on Vercel through the CLI with prebuilt output, and EAS. They always run in the order Supabase, then web, then EAS.
  - **Environment:** resolved from the trigger (D6, D20, D26). Any prerelease tag (`vX.Y.Z-*`, normally `vX.Y.Z-next.N` or `vX.Y.Z-rc.N` from the button) deploys `develop`. A clean `vX.Y.Z` tag deploys `master`. A manual dispatch takes an explicit environment. A push to `main` deploys nothing. There are exactly two environments.
  - **Release gate:** `master` deploys keep `verify-release`: the commit is on `main` and `ci / gate` passed on that SHA (D22.2). They also check that the latest prerelease of `X.Y.Z` is an `rc` (D27) and that the release commit's code matches it, ignoring version fields, `CHANGELOG.md` and `.changeset/`. On a mismatch the deploy fails with "cut a new rc first" (D26).
  - **EAS:** chooses build or OTA by fingerprint (D8). Builds run with `eas build --local` on `mac-studio` (D9). Store submission on `master` is opt-in through a `submit` input. Platforms and a sideload APK are inputs too (D22.3).
  - **Web:** one Vercel project per environment, with project IDs and the Doppler token held in the GitHub Environments `develop` and `master` (D22.4).
  - **Storybook:** with `storybook: true`, the web target also builds the Storybook (`storybook_build_command`) and deploys it to its own Vercel project per environment, after the app's web deploy. A Storybook failure does not block EAS (D24).
  - **Other inputs:** Doppler app env sync and a `dry_run` input (D15).
  - **Slack:** a message for every run, success or failure, to the repo's notify-merge channel (D16).
  - **Internal blocks:** the per-target reusables are internal and not part of the `@v1` contract.
- **Native e2e:** `e2e-maestro` runs both iOS and Android on `mac-studio` (D13). The Android job is ported from Linux/KVM to macOS arm64. starlog's inline Android e2e moves onto it (D22.1). Web e2e stays on hosted runners.
- **Tags:** the app repos' release flow gains a step that creates `vX.Y.Z` tags with the arami-bot token, because nothing creates them today (D22.8).
- **Release button (D26, D27):** a shared `release-candidate.yml`, plus a `workflow_dispatch` caller in arami, starlog and ui. It takes `channel: next | rc` (default `rc`) and requires `ci / gate` green on the `main` HEAD. It computes `X.Y.Z` from pending changesets, or the next patch when there are none, and pushes `vX.Y.Z-<channel>.N` (N from 1, per version and channel) with the arami-bot token. In a repo that publishes a package, it also publishes `X.Y.Z-<channel>.N` under the matching npm dist-tag, setting the version in CI only. It refuses to run while `.changeset/pre.json` exists.
- **openwiki:** `openwiki-update` moves to hosted runners and calls the model provider directly (D12).
- **`auto-resolve-conflicts`:** moves into `.github` (D2).
- **Versioning (D4):** a floating `v1` tag that moves when the `.github` Version Packages PR merges. All callers in all repos move from `@main` to `@v1`.
- **Fixtures (D15):** fixture projects (`fixtures/node`, `fixtures/python`, `fixtures/shell`) exercised by `.github`'s own PR CI, plus a `cd` `dry_run` job.
- **Secrets (D14):** a manifest at `secrets.manifest.yml` holding names, `op://` refs, repo lists and, where needed, a GitHub Environment (`develop` or `master`). A sync script that pushes values from 1Password to each repo with `gh secret set` over stdin. Secret names are standardized as part of this.
- **Rulesets (D18, D19):** a script that applies the standard ruleset (require `ci / gate` and `changeset / check`, plus `e2e / web` for ui, with admin bypass) to the repos in the manifest. It runs per repo only after that repo emits `ci / gate`.
- **Removals:**
  - `ci-autofix.yml` and its callers (D11);
  - Mergify configs (D18);
  - arami's `CI_RUNNER` variable (D10);
  - the orphaned `mac-studio-engineering-log-openwiki` runner (D12);
  - ui's `stage` environment: EAS profile and channel, Doppler config, `DOPPLER_TOKEN_STAGE` and domain (D20);
  - ui's `ci / contrast` and `visual / chromatic` jobs and the Chromatic secret (D21).
- **Docs:** this repo's `CLAUDE.md` workflow table, and the `new-repo-bootstrap` skill and conventions docs that reference the old setup.

**Out of scope** (will not do)
- Moving one-off repo workflows into `.github`, such as `organize-stars` and `receive-entry` (D2).
- Caller generation or sync tooling. Callers are hand-written and thin (D1).
- EAS cloud builds or a cloud/local switch (D9).
- Changing app runtime env management. Doppler stays as it is.
- Adding Storybook to arami ([INF-1987](https://linear.app/jaemincheun/issue/INF-1987)) and starlog ([INF-1988](https://linear.app/jaemincheun/issue/INF-1988)). That is app work; each turns on `storybook: true` once it lands (D24).
- Chromatic or any visual regression check (D21, D24).
- Any repo that no longer exists on GitHub (`stock-tracker`, `crosscheck`).

## Stage goals

Each stage is one PR per repo it touches. In `.github`, a stage may be a small stack.

1. **Cleanup.** Remove `ci-autofix.yml` from `.github` and its callers from claude-statusline, conventions, dotclaw, mem0 and ui. Unset arami's `CI_RUNNER`, and hardcode `mac-studio` in its current `eas-build.yml` so builds stay on the Studio until stage 4 (D22.7). Deregister the orphaned openwiki runner. Done when no repo's `origin/main` references `ci-autofix` or a deleted workflow, and arami CI runs on `ubuntu-latest`.
2. **`.github` foundation.**
   - Add the shared `ci` with presets and gate, plus the fixtures.
   - Turn `ci-node` into a wrapper over `ci`.
   - Add the `v1` tag automation, the app-repo `vX.Y.Z` tagging step, the `release-candidate` workflow, the secrets manifest and sync script, the ruleset script, and `auto-resolve-conflicts`.
   - Move `openwiki-update` to hosted runners.
   - Have `.github` call its own shared `ci`.

   Done when `.github` PR CI runs the shared `ci` green against all three fixtures, the first Version PR merge creates the `v1.x.y` tag and moves `v1`, and the sync script dry-run lists every repo/secret pair with no missing `op://` ref.
3. **CI migration.** In each of the 12 repos, one PR that:
   - switches every `cheunjm/.github` caller to `@v1`;
   - replaces inline CI or `ci-node` with the shared `ci`;
   - adds `auto-resolve-conflicts` where the repo used it;
   - removes `.mergify.yml`.

   After merge, apply that repo's ruleset, once Pro is active. Done when every repo reports `ci / gate` on a PR, has no `@main` reference to `.github`, and its ruleset blocks a merge while `ci / gate` is red.
4. **CD.**
   - **Spike first:** check whether `eas build --local` plus `eas upload` records the fingerprint in EAS. If not, the fingerprint lookup uses GitHub deployment records (D22.6).
   - **`.github`:** build `cd` and its internal blocks, add the `dry_run` fixture job, and port `e2e-maestro` Android to macOS.
   - **starlog, then arami, then ui:** in each, replace the EAS, web and Supabase workflows with one `cd.yml` caller, register a `mac-studio` runner if missing, and sync secrets. Then, per repo:
     - **starlog:** its inline Android e2e moves to `e2e-maestro`.
     - **arami:** its native e2e caller uses the Studio for both platforms. The Supabase target is switched on only after a `dry_run` shows the local and remote migration history match (D23).
     - **ui:** moves to the fingerprint `runtimeVersion` and the clean-tag trigger, moves to one Vercel project per environment, and drops `stage`, Chromatic and contrast (D20, D21). It turns on `storybook: true` with new `ui-storybook-develop` and `ui-storybook-master` Vercel projects (D24).

   In each app repo, the stage-4 PR also adds the `release-candidate` caller and removes the deploy-on-push triggers. ui also leaves changesets pre mode, and its INF-1982 plan's versioning line is updated in the same PR (D27).

   Done when each app repo has had a develop deploy from an rc tag cut by the button, and a production deploy from a clean `vX.Y.Z` tag through `cd`, each posting to Slack. A master deploy with code newer than the latest rc must have failed with "cut a new rc first". ui's Storybook must be live at both Storybook project URLs.
5. **`v2`.** Remove the `ci-node` wrapper, `changeset-prerelease.yml` (D27) and any other deprecated inputs. Done when no caller references `ci-node`, `.github` publishes `v2.0.0`, and callers move to `@v2`.

## Verification

- **`.github` PRs:**
  - actionlint;
  - shared `ci` against `fixtures/node`, `fixtures/python` and `fixtures/shell`, each with one deliberately failing slot run in a separate job that is expected to fail, so `gate` is shown to catch failures;
  - `cd` with `dry_run: true` against a fixture Expo config, checking environment resolution and the fingerprint lookup.
- **Repo migration PRs:**
  - the PR's own run shows `ci / gate` and the expected slots;
  - a docs-only change skips the slots and `gate` passes;
  - after merge, a test PR with a red slot cannot be merged under the ruleset.
- **CD, per app repo:**
  - `workflow_dispatch` with `dry_run: true`;
  - a push to `main` that deploys nothing;
  - a real develop deploy from an rc tag cut with the button, checking the Slack message, the Vercel URL, the EAS OTA on the develop channel, and that Supabase migrations ran first;
  - the button refusing to tag while `ci / gate` is red on the `main` HEAD;
  - in ui, a `next` cut publishes `X.Y.Z-next.N` to the `next` dist-tag, and a master deploy whose latest prerelease is a `next` fails;
  - after the next Version PR, a production deploy from the `vX.Y.Z` tag when its code matches the latest rc;
  - a merge after the last rc, then the Version PR: the master deploy fails with "cut a new rc first", and passes after a new rc;
  - a native change, to confirm the fingerprint triggers a Studio build;
  - for ui, the develop and master Storybook URLs serve the current build.
- **Secrets:** a sync script dry-run, then a real run. For each repo, `gh secret list` shows the manifest's names.

## Assumptions

- GitHub Pro from the Student Developer Pack activates around 2026-11-25 and enables rulesets on private repos. If it doesn't, stage 3 ships without rulesets and D18 is revisited.
- The Mac Studio can run `eas build --local` for iOS and Android, and an arm64 Android emulator, for every app repo. Each app repo can have its own `mac-studio` runner (most already do).
- A tag pushed with the `arami-bot` App token triggers workflows in the app repo. Tags pushed with `GITHUB_TOKEN` do not.
- A build-existence record per fingerprint and environment is available, either from EAS or from GitHub deployment records (settled by the stage-4 spike, D22.6).
- Every pipeline secret exists in 1Password vault `Openclaw` or can be added there before stage 2.

## Terms

- **Caller:** a workflow file in a product repo whose job is only `uses: cheunjm/.github/.github/workflows/<name>.yml@v1` plus `with:` and `secrets:`.
- **Slot:** one fixed CI job in the shared `ci` (lint, typecheck, test, format, audit, build), switched on by its command or preset.
- **Gate:** the `ci / gate` job. It fails if any slot fails or is cancelled, and skipped slots pass. It is the only CI check a ruleset requires.
- **develop / master:** the two deploy environments. They are also Doppler configs, EAS profiles and channels, GitHub Environments, and one Vercel project each.
- **Release button, `next`, `rc`:** a `vX.Y.Z-next.N` or `vX.Y.Z-rc.N` tag on `main`, cut by running the repo's `release-candidate` workflow. It is the only thing that deploys develop (D26). Only an `rc` can ship to master (D27).
- **Fingerprint:** the Expo native fingerprint used as `runtimeVersion`. A build is needed only when no build exists for it.
- **Studio:** the self-hosted `mac-studio` runner on Jace's Mac Studio.

## Later

- Move one-off workflows if a second repo ever needs them.
- Revisit D9 (local-only EAS builds) if the Studio becomes a release bottleneck.
- Shared Dependabot or Renovate config for action version bumps.

---

# Stage 1 implementation: cleanup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** remove `ci-autofix` everywhere, take arami off `CI_RUNNER`, and remove orphaned Studio runners, so stage 2 starts from a clean baseline.

**Architecture:** one PR per repo touched. Callers are removed before the shared workflow, so no caller ever points at a deleted file. arami's EAS build job is pinned to the Studio before `CI_RUNNER` is unset. Runner cleanup is operational, with no PR.

**Tech stack:** GitHub Actions YAML, `gh` CLI, `actionlint`, launchd on the Studio (`ssh jaemincheun@100.86.100.15`).

## Global constraints

- **Branch:** `chore/INF-1983-<slug>` in a worktree created from `origin/main`. Never edit or push on `main`.
- **Commits:** `chore(ci): [INF-1983] <imperative>` (`docs(...)` for docs-only), ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Changeset:** every PR adds `.changeset/inf-1983-<slug>.md`. Use an empty one (`---` / `---`) everywhere except `.github`, which uses `".github": major` (precedent: INF-1924's `agent-review` removal).
- **PRs:** draft first, then `gh pr ready` after verification. Body ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- **Order:** Tasks 1–3 may run in parallel. Task 4 waits for Tasks 1 and 2 to merge. Task 5's variable delete waits for its own PR to merge.

## Review focus

1. **A caller left behind:** when `ci-autofix.yml` is deleted from `.github`, any remaining caller fails on every CI run. Task 4 step 1 greps all 12 repos first.
2. **arami EAS build leaving the Studio:** if `CI_RUNNER` is unset before the hardcode PR merges, the next native build runs `eas build --local` on Linux and fails. Task 5 orders merge, then unset.
3. **arami jobs that silently needed the Studio:** `deploy-web` and `eas-update` move from the Studio to `ubuntu-latest`. Task 5 dispatches both against `develop` to prove they still pass.
4. **Docs that still describe `ci-autofix`:** conventions, the bootstrap skill and `.github`'s `CLAUDE.md` would then tell agents to add a workflow that no longer exists. Tasks 2–4 grep for zero hits.
5. **Removing a runner that is still used:** `mac-studio-starlog-openwiki` is still live (starlog's `OPENWIKI_RUNNER`) until stage 2 and must not be touched. Task 6 lists the exact runners to remove.

---

### Task 1: Remove the `ci-autofix` caller from claude-statusline, dotclaw, mem0 and ui

**Files**, per repo, at `/Users/jaemincheun/Documents/aramiworks/<dir>`, where dir is `claude-statusline`, `dotclaw`, `mem0-repo` (remote `cheunjm/mem0`) or `ui`:
- Delete: `.github/workflows/ci-autofix.yml`
- Create: `.changeset/inf-1983-remove-ci-autofix.md` (empty)

**Interfaces:** produces "no caller in this repo", which Task 4 relies on.

- [ ] **Step 1:** create a worktree per repo on `chore/INF-1983-remove-ci-autofix` from `origin/main`.
- [ ] **Step 2:** delete the caller and add the empty changeset.
- [ ] **Step 3:** verify `git grep -n "ci-autofix" -- .github` prints nothing. Leftover `.changeset/*` text in dotclaw and `CHANGELOG.md` mentions are history, so leave them.
- [ ] **Step 4:** commit `chore(ci): [INF-1983] remove the ci-autofix caller`, push, and open a draft PR.
- [ ] **Step 5:** verify the PR's checks are green except for checks already red on `main`. Then `gh pr ready`.

### Task 2: conventions, remove the caller and the `ci-autofix` docs

**Files** (`/Users/jaemincheun/Documents/aramiworks/conventions`):
- Delete: `.github/workflows/ci-autofix.yml`
- Modify:
  - `architecture/ci-check-naming.md`: drop the `autofix / <step>` row (line 30) and the "`ci-autofix` keys off workflow names" bullet (line 50).
  - `architecture/ci-tooling.md`: drop the `autofix:` job from the example caller (around 173–181) and the whole `## ci-autofix System` section (225 up to the next `##`). Reword lines 294, 366, 384 and 389 so they no longer name `ci-autofix`, and delete any sentence that only existed for it.
  - `project-structure.md:143`: drop the `ci-autofix.yml` runner note.
  - `versioning.md:77`: drop the `changeset-fix` sentence.
- Create: `.changeset/inf-1983-remove-ci-autofix.md` (empty)

- [ ] **Step 1:** worktree on `chore/INF-1983-remove-ci-autofix`.
- [ ] **Step 2:** make the edits above.
- [ ] **Step 3:** verify `git grep -n -i "ci-autofix\|autofix /\|changeset-fix\|agent-fix" -- . ':!CHANGELOG.md' ':!.changeset'` prints nothing. Read each edited section once more so the text still flows.
- [ ] **Step 4:** commit `docs(ci): [INF-1983] remove ci-autofix and its docs`, then push, open a draft PR, and move it to ready once checks are green.

### Task 3: dotfiles, update the `new-repo-bootstrap` skill

**Files** (`~/dotfiles`):
- Modify: `agents/skills/new-repo-bootstrap/SKILL.md`. Line 89 changes to name `agent-review.yml` only; `agent-review` is gone too (INF-1924), so drop the bullet if nothing else needs it. Line 97 loses the "(ci-autofix keys off that name)" parenthetical. Keep line 54: `CI_RUNNER` still drives `changeset-*.yml` until stage 2.
- Create: `.changeset/inf-1983-bootstrap-no-autofix.md` (empty)

- [ ] **Step 1:** worktree, then make the edits.
- [ ] **Step 2:** verify `git grep -n -i "ci-autofix\|agent-review" -- agents` prints nothing.
- [ ] **Step 3:** commit `docs(skills): [INF-1983] drop ci-autofix from new-repo-bootstrap`, push, open a PR and mark it ready. After merge, watch the `Sync` workflow with `gh run watch`.

### Task 4: `.github`, delete `ci-autofix.yml`

**Depends on:** Tasks 1 and 2 merged.

**Files** (stack layer `chore/INF-1983-remove-ci-autofix` on top of the spec branch, PR #120):
- Delete: `.github/workflows/ci-autofix.yml`
- Modify:
  - `CLAUDE.md`: drop the `ci-autofix.yml` table row. Drop "; `ci-autofix` keys off that name" from the `changeset-check.yml` row. In the paragraph after the table, drop "`ci-autofix.yml` defaults to `mac-studio`" and every sentence about agent-fix, `script-fix`, `changeset-fix` and the macOS venv.
  - `.github/workflows/changeset-check.yml:7`: drop the `ci-autofix` reason from the comment. Keep asking for workflow name `Changeset` (Title Case, per ci-check-naming), and say the required context `changeset / check` comes from the job id `changeset`.
- Create: `.changeset/inf-1983-remove-ci-autofix.md` containing `".github": major` and `chore(ci): [INF-1983] remove the reusable ci-autofix.yml; callers must drop their ci-autofix workflow`.

- [ ] **Step 1:** verify no caller remains. For each of the 12 repo dirs, run `git -C <dir> fetch -q origin` and then `git -C <dir> grep -n ci-autofix origin/main -- .github`. Every run must print nothing. If one prints, stop: that repo's Task 1 or 2 PR hasn't merged.
- [ ] **Step 2:** make the edits above.
- [ ] **Step 3:** verify `actionlint` passes and `git grep -n -i "ci-autofix\|agent-fix\|script-fix\|changeset-fix" -- . ':!docs/specs' ':!CHANGELOG.md' ':!.changeset'` prints nothing.
- [ ] **Step 4:** commit, then `gh stack submit --auto`. After `ci / actionlint` and `changeset / check` pass, mark the PR ready.

### Task 5: arami, pin the EAS build to the Studio and unset `CI_RUNNER`

**Files** (`/Users/jaemincheun/Documents/aramiworks/arami`):
- Modify `.github/workflows/eas-build.yml`:
  - the `gate` job's `runs-on` becomes `ubuntu-latest`;
  - the `build` job's `runs-on` becomes `[self-hosted, mac-studio]`;
  - the comment on line 10 changes "(CI_RUNNER=mac-studio)" to "(`mac-studio`)".
- Modify every other `${{ vars.CI_RUNNER || 'ubuntu-latest' }}` in `.github/workflows/` to `ubuntu-latest`: `auto-label.yml`, `auto-update-branches.yml`, `deploy-web.yml` (two jobs), `dispatch-decision-log.yml`, `eas-update.yml` (two jobs) and `notify-merge.yml`.
- Create: `.changeset/inf-1983-drop-ci-runner.md` (empty)

- [ ] **Step 1:** worktree on `chore/INF-1983-drop-ci-runner`, then make the edits.
- [ ] **Step 2:** verify `git grep -n CI_RUNNER -- .github` prints nothing and `actionlint` passes.
- [ ] **Step 3:** commit `chore(ci): [INF-1983] pin EAS builds to mac-studio and drop CI_RUNNER`, push, open a draft PR and mark it ready once checks pass.
- [ ] **Step 4 (after merge):** run `gh variable delete CI_RUNNER --repo cheunjm/arami`. `gh variable list --repo cheunjm/arami` must not show it.
- [ ] **Step 5:** run `gh workflow run deploy-web.yml --repo cheunjm/arami -f environment=develop` and `gh workflow run eas-update.yml --repo cheunjm/arami -f channel=develop`. Add any other required inputs the workflow declares. Both must finish green on `ubuntu-latest`. Check this with `gh run view <id> --json jobs`, whose `labels` must show `ubuntu-latest`. If either fails because it needed the Studio, pin that job to `[self-hosted, mac-studio]` in a follow-up commit and record the reason in `decisions.md`.
- [ ] **Step 6:** the next arami PR's `ci / gate` runs on `ubuntu-latest`. This is the stage done criterion.

### Task 6: remove orphaned Studio runners

Runners to remove (and nothing else):

| Runner dir on Studio | GitHub runner | Why |
|---|---|---|
| `~/actions-runner-engineering-log-openwiki` | `cheunjm/engineering-log` id 22 | engineering-log calls no openwiki workflow (D12) |
| `~/actions-runner-crosscheck` | repo deleted | D3 |
| `~/actions-runner-stock-tracker` | repo deleted | D3 |

**Do not touch** `mac-studio-starlog-openwiki`; stage 2 removes it.

- [ ] **Step 1:** for each dir, on the Studio: `cd <dir>` and run `./svc.sh stop`, then `./svc.sh uninstall`. Verify with `ls ~/Library/LaunchAgents | grep -E "openwiki|crosscheck|stock-tracker"`: it shows only the starlog-openwiki plist.
- [ ] **Step 2:** `gh api -X DELETE repos/cheunjm/engineering-log/actions/runners/22`. `gh api repos/cheunjm/engineering-log/actions/runners --jq '.runners[].name'` then shows only `mac-studio-engineering-log`.
- [ ] **Step 3:** `gh variable delete OPENWIKI_RUNNER --repo cheunjm/engineering-log`.
- [ ] **Step 4:** move the three dirs to `~/backups/runners-removed-2026-11/` rather than deleting them. Delete that folder after stage 2.

### Stage 1 done

- No repo's `origin/main` references `ci-autofix` (Task 4 step 1 grep plus the `.github` grep).
- arami has no `CI_RUNNER` variable or reference, and its `ci / gate` and `eas / build-gate` run on `ubuntu-latest`. Its `eas / build` is pinned to `mac-studio`.
- The Studio runs no service for engineering-log openwiki, crosscheck or stock-tracker.
