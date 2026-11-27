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
  - **Checklist (D40):** `backend` (Supabase `db push`, `functions deploy`), `app` (EAS), `web` (Vercel through the CLI with prebuilt output), `storybook` and `e2e`, ticked per run on the button. They always run in the order backend, app, web, storybook, e2e.
  - **Environment:** set by the button that calls `cd` (D40, D41). The release button deploys `develop`; the production button deploys `master` from a `vX.Y.Z` tag. Tags and pushes to `main` deploy nothing. There are exactly two environments.
  - **Release gate:** `master` deploys keep `verify-release`: the commit is on `main` and `ci / gate` passed on that SHA (D22.2). They also find the newest commit before the release with a green develop deploy (`cd/develop`), check that the release commit's code matches it, ignoring version fields, `CHANGELOG.md` and `.changeset/`, and that it passed develop e2e (`cd/e2e-develop`, D45). Otherwise the deploy fails with "press the release button first" (D46; this replaced the rc gate of D26/D27).
  - **App (D44):** per platform, an OTA when a build of the current fingerprint exists (D8), then always a new build with `eas build --local` on `mac-studio` (D9): develop goes to Firebase and the sideload APK, master to the App Store, Play Store and Firebase. `app.json`'s version equals `package.json`'s.
  - **Migrations (D42, D43):** expand, then contract; destructive SQL fails CI unless marked as a contract step with a `minor` changeset.
  - **Web:** one Vercel project per environment, with project IDs and the Doppler token held in the GitHub Environments `develop` and `master` (D22.4).
  - **Storybook:** with `storybook` ticked, `cd` builds the Storybook (`storybook_build_command`) and deploys it to its own Vercel project per environment, after the app's web deploy. A Storybook failure blocks nothing (D24).
  - **e2e (D45):** after the deploy, Maestro runs against the deployed app on the Studio: every flow on develop, `smoke` flows on master.
  - **Other inputs:** Doppler app env sync and a `dry_run` input (D15).
  - **Slack:** a message for every run, success or failure, to the repo's notify-merge channel (D16).
  - **Internal blocks:** the per-target reusables are internal and not part of the `@v1` contract.
- **Native e2e:** `e2e-maestro` runs iOS and Android side by side on the Studio, on per-platform runners `mac-studio-<repo>-ios` and `mac-studio-<repo>-android` (D13, D33, D36). The Android job is ported from Linux/KVM to macOS arm64 and boots from a saved quick-boot snapshot. starlog's inline Android e2e moves onto it (D22.1). Web e2e stays on hosted runners.
- **Tags:** the app repos' release flow gains a step that creates `vX.Y.Z` tags with the arami-bot token, because nothing creates them today (D22.8).
- **Release button (D26, D27):** a shared `release-candidate.yml`, plus a `workflow_dispatch` caller in arami, starlog and ui. It takes `channel: next | rc` (default `rc`) and requires `ci / gate` green on the `main` HEAD. It computes `X.Y.Z` from pending changesets, or the next patch when there are none, and pushes `vX.Y.Z-<channel>.N` (N from 0, per version and channel; the next N is the highest existing plus one) with the arami-bot token. In a repo that publishes a package, it also publishes `X.Y.Z-<channel>.N` under the matching npm dist-tag, setting the version in CI only. It refuses to run while `.changeset/pre.json` exists.
- **openwiki (D28):** `openwiki-update` runs in all 12 repos on the `mac-studio-openwiki` runner label, using the Studio's LiteLLM. The shared workflow defaults its runner, endpoint and model, so callers pass nothing.
- **`auto-resolve-conflicts` (D29):** removed from maps-organizer, star-organizer and portfolio. There is no shared version.
- **Versioning (D4):** a floating `v1` tag that moves when the `.github` Version Packages PR merges. All callers in all repos move from `@main` to `@v1`.
- **Fixtures (D15):** fixture projects (`fixtures/node`, `fixtures/python`, `fixtures/shell`) exercised by `.github`'s own PR CI, plus a `cd` `dry_run` job.
- **Secrets (D14):** a manifest at `secrets.manifest.toml` (D30) holding names, `op://` refs, repo lists and, where needed, a GitHub Environment (`develop` or `master`). A sync script that pushes values from 1Password to each repo with `gh secret set` over stdin. Secret names are standardized as part of this.
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
   - Mark `ci-node` deprecated (D30.1).
   - Add the `v1` tag automation, the app-repo `vX.Y.Z` tagging step, the `release-candidate` workflow, the secrets manifest and sync script, and the ruleset script.
   - Point `openwiki-update` at the `mac-studio-openwiki` label and set up that label in every repo (D28).
   - Have `.github` call its own shared `ci`.

   Done when `.github` PR CI runs the shared `ci` green against all three fixtures, the first Version PR merge creates the `v1.x.y` tag and moves `v1`, and the sync script dry-run lists every repo/secret pair with no missing `op://` ref.
3. **CI migration.** In each of the 12 repos, one PR that:
   - switches every `cheunjm/.github` caller to `@v1`;
   - replaces inline CI or `ci-node` with the shared `ci`;
   - deletes `auto-resolve-conflicts.yml` where present (D29);
   - adds an `openwiki-update.yml` caller (D28);
   - removes `.mergify.yml`.

   Before any repo gets its ruleset, `openwiki-update` must open its PRs with the arami-bot App token and drop `[skip ci]`; otherwise `ci / gate` never reports on wiki PRs and they wait forever (D31.3). After merge, apply that repo's ruleset, once Pro is active. Done when every repo reports `ci / gate` on a PR, has no `@main` reference to `.github`, and its ruleset blocks a merge while `ci / gate` is red.
4. **CD.**
   - **Spike (done 2026-11-27):** `eas upload --fingerprint <hash>` records the hash on a local build and `eas build:list --fingerprint-hash <hash>` finds it, so no GitHub deployment records are needed (D22.6). Uploaded builds carry no profile or channel, but `eas fingerprint:generate -e <profile>` differs per profile (arami Android: develop `7fe9c69…`, master `8f391fc…`), so the hash alone separates environments. `cd` must pass the hash it generated for the same profile; today's uploads pass none.
   - **Fingerprint checks first:** a version bump must not change the fingerprint, and the e2e test build must share the real build's runtime (D44, D45).
   - **`.github`:** the Studio lock and release gate, `e2e-maestro`'s installed-app mode, the migration and version guards, then `cd` with its checklist, gate, Slack and dry-run self-test (D37, D40–D45). `e2e-maestro` Android already runs on macOS (D36, v1.2.0).
   - **Already done (D38):** arami and starlog have the `release-candidate` caller, and nothing deploys on push to `main`.
   - **starlog, then arami, then ui, then give-and-take:** in each, the two button callers replace the EAS, web, Supabase and e2e workflows; register a `mac-studio` runner if missing; sync secrets and the per-platform test accounts. Then, per repo:
     - **starlog:** `package.json` first moves to `app.json`'s 1.3.0.
     - **give-and-take:** first CD (it ships by hand today): a `mac-studio` runner for EAS, GitHub Environments, Doppler and Vercel per environment, `release.yml` on `@v1`, and a smoke Maestro suite.
     - **arami:** the failing chat and logout flows are fixed or untagged first. `backend` stays off until a dry run shows the local and remote migration history match (D23).
     - **ui:** Storybook only, with new `ui-storybook-develop` and `ui-storybook-master` Vercel projects (D24); one Vercel project per environment; drops `stage`, Chromatic and contrast (D20, D21). It also leaves changesets pre mode, and its INF-1982 plan's versioning line is updated in the same PR (D27).

   Then drop `[skip ci]` from openwiki's merge subject, so wiki merges report `ci / gate` on `main` for the release button, and file the minimum-app-version issues (D42).

   Done when each app repo has had a develop deploy from the release button and a production deploy from the production button, each posting to Slack with e2e green, and a production deploy with code newer than the last develop deploy has failed with "press the release button first" (D46). ui's Storybook must be live at both Storybook project URLs.
5. **`v2`.** Remove the deprecated `ci-node.yml`, `changeset-prerelease.yml` (D27), the `OPENWIKI_RUNNER` fallback (D28) and any other deprecated inputs. Done when no caller references `ci-node`, `.github` publishes `v2.0.0`, and callers move to `@v2`.

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
  - a real develop deploy from the release button, checking the Slack message, the Vercel URL, the build and Firebase distribution, that the OTA was skipped on the first run and published on the second, that Supabase migrations ran first, and that e2e passed on the deployed app;
  - the button refusing to tag while `ci / gate` is red on the `main` HEAD;
  - in ui, a button press publishes `X.Y.Z-next.N` to the `next` dist-tag with `N` from the registry, and creates no git tag (D46);
  - after the next Version PR, a production press with `web` off: store submission, Firebase and smoke e2e, with no data left in production; then a press with only `web`;
  - a merge after the last develop deploy, then the Version PR: the production press fails with "press the release button first", and passes after a new develop deploy;
  - a destructive migration without the contract marker fails CI;
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
- **Release button:** the repo's `release-candidate` workflow, which deploys the `main` HEAD to develop with its checklist in the same run and marks that commit with `cd/develop` (and `cd/e2e-develop`). It is the only thing that deploys develop (D26, D40), and production ships only code a press deployed (D46). It creates no tag; the earlier `next`/`rc` prerelease tags are retired.
- **Production button:** the repo's `release-production` workflow; it deploys a `vX.Y.Z` tag to master with the same checklist (D41).
- **Fingerprint:** the Expo native fingerprint used as `runtimeVersion`. An OTA is published only to a fingerprint that already has a build (D44).
- **Expand / contract:** changing a column over two releases: add the new shape first, remove the old one once no supported app reads it (D42).
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

---

# Stage 2 implementation: `.github` foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** everything stage 3 and 4 callers need exists in `.github`, is tested by `.github`'s own CI, and ships as `v1`.

**Architecture:** five independent PR groups in `.github`, plus Studio runner setup:
- **A** (stack): the shared `ci` (Task 1), then deprecating `ci-node` (Task 2).
- **B** (stack): tagging and `v1` (Task 3), then `release-candidate` (Task 4).
- **C** (stack): the secrets manifest and sync (Task 5), then rulesets (Task 6).
- **D** (single PR): openwiki (Task 7).

Callers still use `@main` until stage 3, so every change to an existing workflow must keep current callers working.

**Tech stack:** GitHub Actions YAML, bash, Python 3 stdlib only (`tomllib`, `json`, `subprocess`), `gh`, `op`, `actionlint` (CI runs `-shellcheck=""`), `@changesets/cli` 3.0.3.

## Global constraints

- **Names:** check names are `<caller job> / <job name>`, and the shared CI's job names are exactly `lint`, `typecheck`, `test`, `format`, `audit`, `build` and `gate` (D5).
- **Permissions:** no job-level `permissions:` inside reusable workflows (conventions `ci-tooling.md`). Callers grant them.
- **Untrusted input:** inputs reach `run:` only through `env:`, never `${{ }}` inside the script.
- **Third-party actions:** pinned by SHA with a version comment.
- **Secrets:** never in argv or logs. Values go `op read` → stdin → `gh secret set` (D14).
- **Backward compatibility:** existing inputs of `ci-node.yml`, `changeset-version.yml` and `openwiki-update.yml` keep their meaning and defaults until `v2`.
- **Branches and commits:** `feat/INF-1983-<slug>` per layer, `feat(workflows): [INF-1983] …`. Each layer adds a `.changeset/*.md`: `".github": minor` for new workflows, `patch` otherwise.

## Review focus

1. **`@main` callers break on merge:** the 5 `ci-node` callers, every `changeset-version` caller and starlog's openwiki caller pick up changes immediately. Task 2 changes only comments. Task 3's new input defaults to off. Task 7 proves the change from starlog, pinned to the PR branch, before merge.
2. **A skipped or absent slot passes the gate, but a cancelled one must not:** Task 1's self-test covers a red slot. The gate must also treat `cancelled` as a failure, so it checks `toJSON(needs)` results for both values.
3. **A docs-only PR:** every slot is skipped by the paths filter and `gate` still reports success. This is required, or rulesets deadlock docs PRs. Task 1 has a self-test case for it.
4. **Prerelease counter collisions:** two button presses racing, or an existing tag. Task 4 must fail rather than overwrite: tag creation through the refs API returns 422 if the tag exists.
5. **A missing 1Password item:** the sync dry-run must list every missing ref and exit non-zero, without printing any value. Task 5 tests this with a deliberately bad ref.

---

### Task 1: shared `ci.yml`, fixtures and self-test

**Files:**
- Rename: `.github/workflows/ci.yml` (local actionlint) → `.github/workflows/self.yml` (`name: CI`)
- Create: `.github/workflows/ci.yml` (reusable, `on: workflow_call`)
- Create: `fixtures/node/{package.json,package-lock.json,index.js}`, `fixtures/python/{app.py,test_app.py}`, `fixtures/shell/{tool.sh,test_tool.sh}`

**Interfaces (produces):** `ci.yml` inputs. Empty means the preset default. The literal `none` turns a slot off.

| Input | Default |
|---|---|
| `preset` (required) | `node` \| `python` \| `shell` |
| `runner` | `ubuntu-latest` |
| `working_directory` | `.` |
| `node_version` | `20` |
| `python_version` | `3.12` |
| `ruff_version` | `0.16.8` |
| `mypy_version` | `1.19.1` |
| `apt_packages` | (empty) |
| `install_command` | node `npm ci`; python `pip install ruff==$RUFF mypy==$MYPY` plus `-r requirements.txt` if present; shell nothing |
| `lint_command` | node `npm run lint`; python `ruff check .`; shell `git ls-files -z '*.sh' \| xargs -0 -r shellcheck -S warning` |
| `typecheck_command` | node `npm run typecheck`; python and shell none |
| `test_command` | node `npm run test`; python `python3 -m unittest discover -s . -p "test_*.py" -v`; shell none |
| `format_command` | node `npm run format:check`; python `ruff format --check .`; shell none |
| `audit_command` | node `npm audit --audit-level=critical --omit=dev`; others none |
| `build_command` | none for all presets |
| `paths_ignore` | `**/*.md` `.changeset/**` `docs/**` (newline-separated) |

- Carried over from `ci-node`: `registry_scope` + `PKG_READ_TOKEN`, `test_reports`, `codecov` + `codecov_directory` + `codecov_flags` + `CODECOV_TOKEN`, `turbo_team` + `TURBO_TOKEN`.
- **`expect_failure`** (boolean, default false; for self-test only): `gate` passes only if a slot failed.
- **Jobs:**
  - `plan` resolves the paths filter (`dorny/paths-filter`, SHA-pinned, `predicate-quantifier: every`) and the effective command per slot. It outputs the JSON list of slots to run.
  - One `slot` job runs a matrix over that list, with `name: ${{ matrix.slot }}`, so the checks read `ci / lint` and so on.
  - `gate` needs `[plan, slot]` and runs `if: always()`.

- [ ] **Step 1:** write `self.yml` with these jobs:
  - `ci` calls `./.github/workflows/ci.yml` with `preset: shell` and `lint_command: actionlint -shellcheck=""` (it keeps actionlint coverage).
  - `node`, `python` and `shell` call it with `working_directory: fixtures/<x>`.
  - `red` calls it on `fixtures/shell` with `test_command: exit 1` and `expect_failure: true`.
  - `docs-only` is the paths-only case: it calls it with `paths_ignore: '**'`, so every slot skips.
- [ ] **Step 2:** open the layer as a draft PR before `ci.yml` exists. Expected: `self.yml` fails to resolve the reusable workflow, which is the red baseline.
- [ ] **Step 3:** implement `ci.yml` and the three fixtures. Each fixture passes its preset's defaults with no overrides; the node fixture has scripts `lint`, `typecheck`, `test` and `format:check` that run `node -e` one-liners and no dependencies.
- [ ] **Step 4:** push and check the PR's checks. Expected:
  - `ci / lint`, `node / *`, `python / *` and `shell / *` pass.
  - The gates `ci / gate`, `node / gate`, `python / gate`, `shell / gate`, `red / gate` and `docs-only / gate` are all green.
  - `red / test` is red, which is intended.
  - `docs-only` has no slot checks.
- [ ] **Step 5:** add `ci.yml` to `CLAUDE.md`'s table, update the `self.yml` line, add the changeset (`minor`), commit and mark ready.

### Task 2: deprecate `ci-node.yml`

`ci-node.yml` is not rewritten as a wrapper (D30.1). A nested reusable call would rename every caller's checks to `ci / ci / <slot>`.

**Files:** modify `.github/workflows/ci-node.yml` (header comment only) and `CLAUDE.md` (its row says "deprecated: use `ci.yml` with `preset: node`; removed in v2").

- [ ] **Step 1:** edit the header and the row, add a `patch` changeset, and commit on top of Task 1's layer.
- [ ] **Step 2:** check that `git diff origin/main -- .github/workflows/ci-node.yml` touches comment lines only, so the `@main` callers can't be affected.

### Task 3: `vX.Y.Z` tags on Version PR merge, and the floating `v1`

**Files:**
- Modify: `.github/workflows/changeset-version.yml`. Add input `tag` (boolean, default false). When it is true and `publish` is empty, the action's `publish-script` is `npx changeset tag`.
- Create: `.github/workflows/major-tag.yml`. Trigger: `push: tags: ['v[0-9]+.[0-9]+.[0-9]+']`. It force-moves `v<MAJOR>` to the pushed commit through `PATCH repos/{repo}/git/refs/tags/v<MAJOR>` (`force: true`), creating the ref if it is missing, with the arami-bot token.
- Modify: `.github/workflows/release.yml`. Pass `tag: true`.

- [ ] **Step 1 (spike, local):** in a scratch dir under the session scratchpad, `git init` a single private package `{name: x, version: 1.0.0, private: true}` with `.changeset/config.json` set to `privatePackages: {version: true, tag: true}`. Run `npx @changesets/cli@3.0.3 tag`. Expected: the tag `v1.0.0` is created, and stdout has a `New tag:` line, which `changesets/action` parses to create the GitHub release. Record the exact output in the PR body.
- [ ] **Step 2:** implement the three changes. Run `actionlint`.
- [ ] **Step 3:** after merge, merge the standing `.github` Version PR, https://github.com/cheunjm/.github/pull/97 (Jace merges it). Expected: tag `v1.0.0` and a GitHub release; `major-tag.yml` runs and `v1` points at `v1.0.0`. Check with `gh api repos/cheunjm/.github/git/refs/tags/v1`. This is stage 2's first done criterion.

### Task 4: `release-candidate.yml`

**Files:** create `.github/workflows/release-candidate.yml` (reusable), and add a `release-candidate` job to `self.yml` with `dry_run: true`.

**Interfaces (produces):**
- **Inputs:** `channel` (`next` \| `rc`, default `rc`), `publish` (boolean, default false), `registry_url`, `scope`, `node_version` (`22`) and `dry_run` (boolean).
- **Secrets:** `BOT_APP_ID`, `BOT_PRIVATE_KEY`, `NODE_AUTH_TOKEN` (for publish).
- **Outputs:** `tag` (for example `v1.4.0-rc.0`) and `version`.

- [ ] **Step 1:** add the self-test job (`dry_run: true` against `.github` itself). Expected red: the workflow doesn't exist yet.
- [ ] **Step 2:** implement the steps, in order. Each check fails the job with a one-line message:
  1. If `.changeset/pre.json` exists, fail with "repo is in changesets pre mode".
  2. If the `ci / gate` check run on `github.sha` isn't `success` (`gh api repos/{repo}/commits/{sha}/check-runs?check_name=ci%20/%20gate`), fail with "ci / gate is not green on <sha>".
  3. Set `X.Y.Z` to the single entry's `newVersion` from `npx @changesets/cli@3.0.3 status --output=status.json`; if there are no releases, use the patch after `package.json`'s version.
  4. Set `N` to 1 + the highest existing `vX.Y.Z-<channel>.<n>` from `git ls-remote --tags`, or 0 if there is none.
  5. Unless `dry_run`, create the tag with `POST repos/{repo}/git/refs` using the bot token (a 422 means the tag exists, so fail and don't retry), then `gh release create <tag> --prerelease --generate-notes`.
  6. If `publish`, run `npm version <version> --no-git-tag-version`, then `npm publish --tag <channel>`.
- [ ] **Step 3:** push. Expected: the self-test prints `tag=v<next>-rc.0`, and nothing is created (`gh api repos/cheunjm/.github/git/refs/tags` is unchanged).
- [ ] **Step 4:** add a `CLAUDE.md` row and a `minor` changeset, then commit.

### Task 5: secrets manifest and sync

**Files:** create `secrets.manifest.toml` and `scripts/sync-secrets.py`; test with `scripts/test_sync_secrets.py` (stdlib `unittest`).

**Interfaces (produces):**
- **Manifest:** one `[[secret]]` table per value, with `name`, `ref` (an `op://Openclaw/...` path), `repos` (a list, or `"all"`), an optional `env` (`develop` or `master`), and `kind` (`secret` default, or `variable`).
- **Per-repo settings:** `[repos.<name>]` with `ruleset = true|false` and `extra_checks = [...]`, consumed by Task 6.
- **Script:** `sync-secrets.py [--dry-run] [--repo R] [--name N]`. It exits 1 if any `op read` fails, and it prints only `name repo [env] ok|missing|set`.

- [ ] **Step 1:** write the tests with a fake `op` and `gh` on `PATH` (shell stubs in a temp dir that record argv and stdin).
  - `test_value_goes_to_stdin_never_argv`: the recorded `gh` argv must not contain the value, and its stdin must equal it.
  - `test_missing_ref_reported_and_exit_1`: `op` exits 1 for one ref; the output has `missing` and the exit code is 1.
  - `test_env_and_variable_kinds`: they map to `gh secret set N --repo cheunjm/R --env E` and `gh variable set N --repo cheunjm/R`.
- [ ] **Step 2:** run `python3 -m unittest scripts/test_sync_secrets.py`. Expected: FAIL (no module).
- [ ] **Step 3:** implement the script.
- [ ] **Step 4:** rerun. Expected: PASS.
- [ ] **Step 5:** fill the manifest from the stage 2 inventory, standardized:
  - `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID` become `variable`s, the project ID per environment.
  - `DOPPLER_TOKEN` is per environment.
  - `LITELLM_API_KEY` goes to all 12 repos (D28).
  - `SLACK_BOT_TOKEN` stays on all 12.

  Old names stay in GitHub until their callers move (stages 3 and 4). There's no prune in this stage.
- [ ] **Step 6:** run `python3 scripts/sync-secrets.py --dry-run`. Expected: every pair is `ok`. Any `missing` is listed for Jace, because 1Password needs those values and GitHub can't return them. This blocks the real sync only.
- [ ] **Step 7:** commit, open the PR, and run the real sync after merge. `gh secret list` per repo shows the manifest names.

### Task 6: ruleset script

**Files:** create `scripts/apply-rulesets.py`, with tests in `scripts/test_apply_rulesets.py`.

**Interfaces:**
- **Consumes:** the manifest's `[repos.*]`.
- **Produces:** `apply-rulesets.py [--dry-run] --repo R | --all`. It upserts a ruleset named `default-branch`:
  - target `~DEFAULT_BRANCH`;
  - a `required_status_checks` rule with `ci / gate`, `changeset / check` and the repo's `extra_checks`;
  - bypass actor `RepositoryRole` 5 (admin) with `bypass_mode: always`.

- [ ] **Step 1:** tests:
  - `test_payload_has_gate_changeset_and_extras` (ui → also `e2e / web`);
  - `test_upsert_uses_put_when_named_ruleset_exists` (fake `gh` returns an existing id).
- [ ] **Step 2:** run them, expect FAIL, implement, run them, expect PASS.
- [ ] **Step 3:** apply to `cheunjm/.github`. It is public, so rulesets work without Pro, and `self.yml` now emits `ci / gate`. Then open a test PR with a red `ci / lint` and confirm the merge button is blocked for a non-admin view (`gh pr view --json mergeStateStatus` shows `BLOCKED`).
- [ ] **Step 4:** set `ruleset = false` for the other repos until each one's stage 3 PR merges.

### Task 7: openwiki on `mac-studio-openwiki`

**Files:** modify `.github/workflows/openwiki-update.yml`.
- Change the defaults: `runner` to `mac-studio-openwiki`, `base_url` to `http://127.0.0.1:4001/v1`, `model_id` to `gpt-6.1-sol` (it was required, so it becomes optional) and `use_responses_api` to `true`.
- Keep `vars.OPENWIKI_RUNNER` as the first choice until stage 5.

**Runner setup (no PR):**
- For the 9 tool repos: `gh api -X POST repos/cheunjm/<repo>/actions/runners/<id>/labels -f 'labels[]=mac-studio-openwiki'`.
- Register `mac-studio-arami-openwiki`, `mac-studio-ui-openwiki` and `mac-studio-portfolio` (also labelled `mac-studio-openwiki`) with the conventions registration-token-over-stdin recipe.

- [ ] **Step 1:** prove the current caller still works. Dispatch starlog's `openwiki-update.yml` pinned to the PR branch. Expected: it runs on `mac-studio-starlog-openwiki`, still chosen through `OPENWIKI_RUNNER`.
- [ ] **Step 2:** do the runner setup. Expected: in every repo, `gh api repos/cheunjm/<repo>/actions/runners --jq '[.runners[].labels[].name]'` contains `mac-studio-openwiki`.
- [ ] **Step 3:** update the `CLAUDE.md` row, add a `patch` changeset, commit and mark ready.

### Stage 2 done

The criteria from the stage goals:
- `self.yml` is green across all three fixtures, plus the red and docs-only cases.
- `v1` points at the first release.
- The sync dry-run is all `ok`.

And:
- `release-candidate` dry-runs on `.github`.
- `.github` has its ruleset.
- Every repo has a `mac-studio-openwiki` runner.

---

# Stage 3 implementation: CI migration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** every repo runs the shared `ci.yml@v1`, reports `ci / gate`, calls everything in `.github` at `@v1`, has an openwiki caller, has no Mergify and no `auto-resolve-conflicts`, and is protected by its ruleset.

**Architecture:**
- **Task 1** fixes openwiki for rulesets in `.github` and ships it as `v1.1.0`.
- **Tasks 2–13** are one PR per repo, all following the same recipe. Only the `ci.yml` caller's inputs differ, and those come from the table.
- **Task 14** turns rulesets on, per repo, after that repo's PR merges.

**Tech stack:** GitHub Actions YAML, `gh`, `actionlint`, `scripts/apply-rulesets.py`, `scripts/sync-secrets.py`.

## Global constraints

- **CI caller:** `.github/workflows/ci.yml`, `name: Checks` (D35), job id `ci`, triggered on `pull_request` (`opened, synchronize, reopened, ready_for_review`) and on `push` to `main`. It grants `contents: read`, plus `checks: write` only with `test_reports`. It uses `secrets: inherit`.
- **Pins:** every `cheunjm/.github/.github/workflows/*.yml@main` becomes `@v1`.
- **Changeset caller:** `name: Release notes` (D35), job id `changeset`.
- **Naming docs:** conventions `ci-check-naming.md` (Task 2) and the dotfiles `new-repo-bootstrap` skill switch to the `Checks` and `Release notes` workflow names.
- **No `CI_RUNNER`:** `vars.CI_RUNNER` fallbacks are replaced with `ubuntu-latest` (D10). The exceptions stay: arami's pinned `eas / build`, starlog's `eas-build` Studio job, and engineering-log's `receive-entry` (one-off, D2).
- **Branches:** `chore/INF-1983-ci-migration` with an empty changeset. Draft first, then ready once CI shows `ci / gate`.
- **Never:** change app deploy workflows beyond `@v1` pins and `CI_RUNNER` (that is stage 4).

## Review focus

1. **Lost coverage:** a check that ran before and doesn't run after (an inline job dropped, a path filter too broad). Each PR body lists old checks → new checks.
2. **openwiki loops:** a wiki merge must not set off another wiki run. Callers ignore `openwiki/**`, and so does `ci.yml`'s default `paths_ignore`.
3. **Ruleset on before `ci / gate` exists on `main`:** apply a ruleset only after the repo's migration PR has merged and a push run on `main` shows `ci / gate`.
4. **Secrets missing for openwiki:** each new caller needs `LITELLM_API_KEY`. It's synced only to repos that lack it, so the existing values in starlog and engineering-log aren't overwritten.
5. **pip on Ubuntu 24.04 is externally managed:** shell-preset repos that need Python tools use `pipx run`, not `pip install`.

---

### Task 1: `.github`, openwiki ready for rulesets, then `v1.1.0`

**Files:**
- Modify `.github/workflows/openwiki-update.yml`:
  - `use_app` defaults to `true`;
  - the App secrets are renamed to `BOT_APP_ID` / `BOT_PRIVATE_KEY`, keeping the old names as fallbacks until v2;
  - the merge subject drops `[skip ci]`, so the wiki PR and its merge push both report `ci / gate`.
- Modify `.github/workflows/ci.yml`: `paths_ignore` gains `openwiki/**`, and it gains `layout` (`single` by default, or `matrix`, D34). `self.yml` covers both layouts: `node` stays `matrix`, and `python` and `shell` use the default `single`. The `red` case runs in `single`, to show that a failed slot inside `ci / checks` still turns `gate` red.
- Changeset: `".github": minor`.

- [ ] **Step 1:** make the edits. Run `actionlint -shellcheck=""`. Self-test: `self.yml` stays green.
- [ ] **Step 2:** PR, CI, merge. Then Jace merges the Version PR, and `v1` moves to `v1.1.0` on its own. Verify that `gh api repos/cheunjm/.github/commits/v1` equals `v1.1.0`'s commit.
- [ ] **Step 3:** `python3 scripts/sync-secrets.py --name LITELLM_API_KEY --repo <r>` for each repo without it (all except starlog and engineering-log).

### Tasks 2–13: one migration PR per repo

Recipe for each repo, in this order:
- [ ] **Step 1:** worktree from `origin/main`. Record the PR's current check names (`gh pr checks` on its latest merged PR) as "before".
- [ ] **Step 2:** replace inline CI or the `ci-node` caller with the caller below.
- [ ] **Step 3:** switch every `@main` to `@v1`, and replace each `vars.CI_RUNNER || 'ubuntu-latest'` with `ubuntu-latest`.
- [ ] **Step 4:** delete `.mergify.yml` and `auto-resolve-conflicts.yml` where they exist.
- [ ] **Step 5:** add `.github/workflows/openwiki-update.yml`: `on: push: branches: [main], paths-ignore: ['openwiki/**', '**/*.md', '.changeset/**']` plus `workflow_dispatch` with `init`. Grant `contents: write` and `pull-requests: write`, and use `secrets: inherit`. Repos with no wiki yet get `init: true` on their first dispatch.
- [ ] **Step 6:** `actionlint`, draft PR. Expected: `ci / gate` green, plus the slots in the table's "checks" column. The PR body lists before → after.
- [ ] **Step 7:** mark ready, then Jace merges. After merge, the push run on `main` shows `ci / gate`.

| # | Repo | `ci.yml` inputs | Slots run inside `ci / gate` | Also |
|---|---|---|---|---|
| 2 | conventions | `preset: shell` | lint | Mergify |
| 3 | engineering-log | `preset: shell` | lint | Mergify |
| 4 | clipsync | `preset: shell` | lint | — |
| 5 | claude-statusline | `preset: shell`, `lint_command: shellcheck statusline.sh install.sh`, `test_command: bash tests/statusline.sh` (new script holding the 4 inline jq checks) | lint, test | Mergify |
| 6 | dotclaw | `preset: shell`, `lint_command: find . -name "*.sh" -not -path "./.git/*" -not -name start-tmux.sh -exec shellcheck -S error {} + && pipx run ruff==0.16.8 check --select E9,F821,F811 scripts/ hooks/ workspace*/` | lint | Mergify |
| 7 | mem0 | `preset: python`, `install_command: python3 -m pip install "ruff==$RUFF_VERSION"`, `test_command: python3 -c "import ast, pathlib; [ast.parse(p.read_text()) for p in pathlib.Path('.').rglob('*.py')]"` | lint, test, format | — |
| 8 | star-organizer | `preset: python`, `lint_command: ruff check organize_stars.py test_organize_stars.py`, `typecheck_command: mypy organize_stars.py test_organize_stars.py --ignore-missing-imports`, `format_command: none` | lint, typecheck, test | auto-resolve; `organize-stars.yml` to ubuntu |
| 9 | maps-organizer | `preset: node`, `format_command: none`, `audit_command: none` | lint, typecheck, test | auto-resolve |
| 10 | portfolio | `preset: node`, `node_version: "22"`, `typecheck_command: npm run check`, `build_command: npm run build`, lint/test/format/audit `none` | typecheck, build | auto-resolve; needs a `mac-studio-portfolio` wiki run (D28) |
| 11 | arami | `preset: node`, `typecheck_command: npm run check-types` | lint, typecheck, test, format, audit | Mergify; `e2e.yml` → `@v1` (Version PR and dispatch only, unchanged) |
| 12 | starlog | `preset: node`, `typecheck_command: npm run check-types` | lint, typecheck, test, format, audit | openwiki caller becomes thin; drop `OPENWIKI_RUNNER`; `db-migration-check` → `@v1` |
| 13 | ui | `preset: node`, `test_command: npm test -- --ci --coverage`, `build_command: npm run storybook:build`, `codecov: true`, `codecov_directory: coverage` | all six | Mergify; `ci / contrast` removed (D21); `ci / api` and `ci / stories` stay as local jobs in the same workflow; no e2e (D33) |

### Task 13b: Android e2e on the Studio (D33)

Runs after arami (Task 11) and starlog (Task 12) have moved to `@v1`, so `@main` changes to `e2e-maestro.yml` can't reach them before a release.

- [ ] **Step 1:** in `.github`, port `e2e-maestro.yml`'s `android` job to macOS arm64.
  - Remove the KVM step and `reactivecircus/android-emulator-runner`.
  - Install the emulator and `system-images;android-<api>;google_apis;arm64-v8a` with `sdkmanager` under `~/Library/Android` (the host-path rules in `CLAUDE.md` apply), and boot headless (`-no-window -no-audio -no-boot-anim`) using HVF.
  - Delete a throwaway AVD in an `always()` step, like the iOS simulator.
  - `android-arch` defaults to `arm64-v8a`. `android-runner` and `web-runner` default to `mac-studio`.
- [ ] **Step 2:** prove it with arami: dispatch arami's `e2e.yml` pinned to the PR branch, with `E2E_ANDROID_ARCH=arm64-v8a`. Expected: `e2e / android` green on `mac-studio-arami`.
- [ ] **Step 3:** merge, then Jace merges the `.github` Version PR, and `v1` moves.
- [ ] **Step 4:** follow-up PRs. In arami, `E2E_ANDROID_ARCH=arm64-v8a`. In starlog, replace the inline Android job with an `e2e-maestro@v1` caller, `platforms: android`, triggered on the Version PR and by dispatch. Dispatch each once: green on the Studio.

### Task 14: rulesets

- [ ] **Step 1:** after each repo's PR merges and `main` shows `ci / gate`, set `ruleset = true` for it in `secrets.manifest.toml` (one `.github` PR can batch several repos).
- [ ] **Step 2:** apply with `python3 scripts/apply-rulesets.py --repo <r>` (Jace runs it if it's denied for the AI). Check with a throwaway PR whose `ci / gate` is red: `mergeStateStatus` must be `BLOCKED`. Close it.

### Stage 3 done

- No repo references `@main` or `ci-node`, and none has a `.mergify.yml` or `auto-resolve-conflicts`.
- Every repo's latest PR shows `ci / gate`, and its ruleset blocks a red gate.
- Every repo has an openwiki caller that has run once on `mac-studio-openwiki`.


---

# Stage 4 implementation: CD

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** every app repo deploys only from its two buttons, release (develop) and production (master). Each button is a checklist of backend, app, web, storybook and e2e that runs in that order in one run of the shared `cd.yml@v1`. The app step decides OTA and builds by itself, and e2e tests the deployed app (D40–D45).

**Architecture:**
- **Task 1 first:** fingerprint checks in each app. A failure there changes Tasks 5 and 8–11 before any code is written.
- **`.github`, two releases.** v1.3.0: the `studio-lock` and `release-gate` actions, the lock and installed-app mode in `e2e-maestro`, the migration and version guards, and dropping prerelease tags (Tasks 2–4b, D46). v1.4.0: `cd.yml`, its gate and Slack, the Expo fixture and the button self-test (Tasks 5–7). `cd`'s blocks are jobs inside `cd.yml`; tested logic lives in actions and workflows that ship one release earlier, so `cd` can pin them to `@v1` (D39.1).
- **Buttons are callers.** Each app repo has `release-candidate.yml` (job `cut` calls `release-candidate.yml@v1`, which checks and computes the version and creates no tag (D46); job `cd` calls `cd.yml@v1` with `environment: develop` and `ref: <the cut job's ref output>`) and `release-production.yml` (job `cd` with `environment: master` and a `vX.Y.Z` tag). Tags trigger nothing.
- **Repos, one PR each, in order:** starlog (Task 8), arami (Task 9), ui (Task 10), give-and-take (Task 11). Then openwiki drops `[skip ci]` (Task 12) and the follow-up issues are filed (Task 13).

**Tech stack:** GitHub Actions YAML, bash, Python 3 stdlib (lock and gate scripts), `eas-cli` 27.11.0, Supabase CLI 3.2.0, `vercel@65`, `firebase-tools@15.8.0`, Doppler CLI, Maestro 2.12.1, `gh`, `actionlint`.

## Global constraints

- **Order:** backend → app → web → storybook → e2e → notify. A failed backend skips app, web and e2e. A Storybook failure blocks nothing. e2e runs only when app, and web if ticked, succeeded (D40, D42).
- **Environment:** only `cd`'s `environment` input, set by the button caller (`develop` or `master`). Empty deploys nothing; `cd` has no push or tag trigger (D40, D41).
- **Checklist:** booleans `backend`, `app`, `web`, `storybook`, `e2e`, plus `ignore_pending_migrations` (default false). Each caller's `workflow_dispatch` defaults them to what the repo has; e2e defaults on in both buttons (D40).
- **Master gate (D46):** the commit is on `main`; `ci / gate` passed on it; the newest commit in its first-parent history (itself included, at most 100 back) that a `workflow_dispatch` run of `release-candidate.yml` on the default branch deployed (its `… / develop-status` job succeeded, D47) is the tested commit; the code matches it except version fields (`package.json`, `package-lock.json`, `app.json`), `CHANGELOG.md` and `.changeset/`; and, in repos with e2e, that run's `… / e2e-status` job also succeeded. Every failure message ends in `press the release button first`.
- **Develop proof (D46, D47):** the release run's `develop-status` and `e2e-status` jobs (skipped in dry runs) are the proof; `cd` also sets statuses `cd/develop` and `cd/e2e-develop` on the deployed commit as visible markers, which the gate does not read. The production caller grants `actions: read`. No prerelease tags anywhere.
- **App step, per platform (D44):**
  1. `eas fingerprint:generate -p <p> -e <env> --json`.
  2. If a finished build with that hash exists (`eas build:list --fingerprint-hash`), publish the OTA first: `doppler run -- eas update --channel <env> --environment <preview|production> --platform <p> --message <tag>`.
  3. Always `eas build --local -p <p> -e <env>` inside a Studio slot (D37), then `eas upload --fingerprint <hash>`.
  4. Distribute: develop → Firebase (`firebase_groups`) and the sideload APK (`sideload_apk`); master → `eas submit` to Play and the App Store (`store_submit`) and Firebase.
  A failing platform fails the job after the other platform finishes.
- **Version (D44):** `app.json` `expo.version` equals `package.json` `version`. The Version PR writes it (`changeset-version` input `app-json`). Develop builds set `X.Y.Z`, without the prerelease suffix, in CI only. Build numbers come from EAS (`cli.appVersionSource: remote`, `autoIncrement: true` on `develop` and `master`).
- **e2e (D45):** per platform, the environment's test build (profile `e2e-<env>`, extending `<env>`: Android `buildType: apk`, iOS `simulator: true`) for the current fingerprint, built only when missing. It pulls the environment's OTA, so it runs the shipped JS. develop runs every flow; master runs `--include-tags smoke`. Each platform signs in with its own test account from the environment secret `E2E_TEST_ACCOUNTS`. Flows tagged `smoke` delete what they create.
- **Migrations (D42, D43):** expand, then contract. `DROP COLUMN`, `DROP TABLE`, `RENAME` and column type changes fail CI unless the file carries `-- contract: safe after vX.Y.Z` and the PR's changeset is `minor`. App repos never use `major`.
- **Names:** caller job id `cd`, so checks read `cd / plan`, `cd / backend`, `cd / app`, `cd / web`, `cd / storybook`, `cd / e2e`, `cd / notify`.
- **Secrets:** per-environment values (`DOPPLER_TOKEN`, `VERCEL_PROJECT_ID`, `SUPABASE_*`, `PLAY_SERVICE_ACCOUNT_JSON`, `ASC_API_KEY_P8`, `ASC_KEY_ID`, `ASC_ISSUER_ID`, `FIREBASE_*`, `E2E_TEST_ACCOUNTS`) live in the GitHub Environments `develop` and `master`; IDs are variables, tokens are secrets (D14, D22.4). Values go through `scripts/sync-secrets.py` only.
- **Pins:** `eas-cli` 27.11.0, Supabase CLI 3.2.0, `vercel@65`, `firebase-tools@15.8.0`; third-party actions by SHA. No `permissions:` inside reusable workflows; inputs reach `run:` only through `env:`.
- **Branches and commits:** `feat/INF-1983-<slug>`, `feat(workflows): [INF-1983] …` in `.github`, `ci(cd): [INF-1983] …` in the app repos. `.github`: `minor` changesets; app repos: empty changesets.

## Review focus

1. **Something deploys without a button:** `cd / plan` outputs `environment=''` when the input is empty, and every target job skips. Task 7's self-test covers it.
2. **A stale lock blocks the Studio forever:** a slot whose owner process is gone is free. Task 2 tests this.
3. **An OTA to a runtime nobody has:** the OTA publishes only when a build for that fingerprint existed before this run. Task 7's dry run prints the lookup; each repo's first develop press (Tasks 8–9) must show "no build: skip OTA, build".
4. **A version bump changes the fingerprint,** cutting existing users off OTA on every release, or the e2e test build gets a different runtime and never sees the OTA. Task 1 checks both before anything is built.
5. **Production e2e leaves data or collides:** `smoke` flows must delete what they create, and the two platforms use different accounts. Task 8 Step 6 checks the production test accounts after the run.
6. **Version-only diffs misread as code:** `package.json`, `package-lock.json` and `app.json` differing only in version fields pass the gate; any other line fails it. Task 2 tests both.
7. **A store refuses the first synced version:** starlog's `app.json` is 1.3.0 while `package.json` is 1.2.1, and the stores reject a lower version. Task 8 Step 1 aligns them first.

---

### Task 1: fingerprint checks

No code unless a check fails. Run in a scratch worktree of starlog, arami and give-and-take after `npm ci`.

- [ ] **Step 1 (version):** for `p` in `android`, `ios`: `eas fingerprint:generate -p <p> -e develop --json` → `H1`; set `expo.version` to `9.9.9`; regenerate → `H2`. Expected: `H1 == H2` (the `balanced` preset skips `ExpoConfigVersions`).
- [ ] **Step 2 (test build):** add profile `e2e-develop` (`extends: develop`, Android `buildType: apk`, iOS `simulator: true`) and regenerate with `-e e2e-develop` → `H3`. Expected: `H3 == H1`.
- [ ] **Step 3 (on failure):** Step 1 fails → a per-app PR adds `fingerprint.config.js` whose `sourceSkips` adds `SourceSkips.ExpoConfigVersions` to the default; re-run Step 1. Step 2 fails → diff the two `--debug` outputs; if the difference can't be removed from the profile, stop and bring the diff to Jace (the D45 test-build design depends on it).
- [ ] **Step 4:** record the hashes and result under D44 "Verified" in `decisions.md`.

### Task 2: `studio-lock` and `release-gate` actions

**Files:**
- Create: `.github/actions/studio-lock/{action.yml,lock.py}`, `scripts/test_studio_lock.py`, `.github/actions/release-gate/{action.yml,gate.py}`, `scripts/test_release_gate.py`
- Modify: `.github/workflows/self.yml` (a `studio-lock` job; both unittest runs in the `ci` job's `test_command`), `CLAUDE.md` (one line each under the workflow table)

**Interfaces (produces):**
- `lock.py acquire --dir <d> --slots 2 --timeout-minutes <n> --owner <json>` prints `slot=<i>`; exit 1 with `no Studio slot in <n> min` on timeout.
- `lock.py release --dir <d> --slot <i> --owner-id <run_id>-<job>` removes the slot only if it holds that owner id.
- A slot is the directory `<d>/slot-<i>` created with `os.mkdir` (atomic), holding `owner.json` `{id, pid, repo, run_url, acquired_at}`. `pid` is the job's `Runner.Worker` process (nearest ancestor with that name). A slot whose `pid` is not alive is free.
- `studio-lock` inputs: `mode` (`acquire` | `release`), `slots` (default `2`), `timeout-minutes` (default `120`), `slot` (release only). Output `slot`. Lock dir: `~/Library/Caches/cheunjm-studio-lock`.
- (Shipped as below in #158, then replaced by Task 4b's develop-deploy gate, D46.) `gate.py --sha <sha> --tag <tag|''> --version <X.Y.Z> [--require-e2e]` (needs `GH_TOKEN`, full-history checkout). Fails in this order: not on `main` (`git merge-base --is-ancestor`); `ci / gate` not `success` on the SHA; the highest-`N` prerelease tag of `X.Y.Z` across channels is not `-rc.` (`latest prerelease of X.Y.Z is not an rc: cut a new rc first`); the diff from that rc minus `CHANGELOG.md` and `.changeset/*` touches anything but `package.json`, `package-lock.json`, `app.json`, or their changed lines aren't all `"version": ` lines (`code differs from <rc>: cut a new rc first`); with `--require-e2e`, the rc's commit has no `success` status `cd/e2e-develop` (`<rc> has no green develop e2e: cut a new rc first`). The GitHub API call is an injected function, so tests need no network.

- [ ] **Step 1:** `scripts/test_studio_lock.py` (unittest, temp dirs): `test_two_owners_get_different_slots`, `test_third_owner_times_out` (timeout 0 → exit 1 and the message), `test_dead_owner_slot_is_reused` (owner pid 999999 → acquired), `test_release_ignores_foreign_owner`, `test_release_frees_slot`.
- [ ] **Step 2:** `python3 -m unittest scripts/test_studio_lock.py`. Expected: fails (no `lock.py`).
- [ ] **Step 3:** implement `lock.py` (poll every 15 s) and `action.yml` (runs `python3 "$GITHUB_ACTION_PATH/lock.py"`, writes `slot` to `GITHUB_OUTPUT`, prints the holder of each busy slot while waiting). Tests pass. Add the `self.yml` job `studio-lock` (ubuntu): acquire twice with `slots: 2`, release both, via `uses: ./.github/actions/studio-lock`.
- [ ] **Step 4:** `scripts/test_release_gate.py` on a temp git repo: `test_version_only_diff_passes` (including `app.json`), `test_dependency_change_fails`, `test_next_latest_fails`, `test_no_prerelease_fails`, `test_changelog_and_changeset_ignored`, `test_missing_e2e_status_fails`, `test_green_e2e_status_passes`. Run; expected fail; implement `gate.py` and `action.yml`; run; expected pass.
- [ ] **Step 5:** `minor` changeset, commit, draft PR (stack bottom for v1.3.0).

### Task 3: `e2e-maestro`: Studio lock and an installed-app mode

**Files:** modify `.github/workflows/e2e-maestro.yml` (android and ios jobs), `CLAUDE.md` (e2e row).

**Interfaces (produces):** new inputs `studio-lock` (boolean, default true), `app-artifact` (string, default `''`: the name prefix of a same-run artifact holding the app to install, `<prefix>-android` with one `.apk`, `<prefix>-ios` with one `.app` directory tarred; when set, `build-command` and `setup-command` are skipped and the app is installed on the booted device), `include-tags` (string, default `''`, passed as `--include-tags` to the default test command).

- [ ] **Step 1:** in both native jobs, when `runner.os == 'macOS'` and `studio-lock`: an acquire step (`uses: cheunjm/.github/.github/actions/studio-lock@v1`) before `Build` (or before install), and a release step `if: always() && steps.lock.outputs.slot != ''` after the suite.
- [ ] **Step 2:** `app-artifact` install path: `actions/download-artifact` by name, then `adb -s "$E2E_DEVICE" install -r` or `xcrun simctl install "$E2E_DEVICE"`.
- [ ] **Step 3:** `include-tags` in the default test command. `actionlint` clean; commit on the stack.

### Task 4: migration and version guards

**Files:** modify `.github/workflows/db-migration-check.yml`, `.github/workflows/changeset-check.yml`, `.github/workflows/changeset-version.yml`, `self.yml`, `CLAUDE.md` (three rows); create `fixtures/migrations/` test cases.

**Interfaces (produces):**
- `db-migration-check` input `block_destructive` (boolean, default false): fails the job when an added line matches `DROP (TABLE|COLUMN)`, `RENAME (TO|COLUMN)` or `ALTER COLUMN … TYPE` in a file that has no line `-- contract: safe after v<semver>`. Error text: `<file>:<line> is a contract change: add "-- contract: safe after vX.Y.Z" and a minor changeset`. Input `base_ref` (default the PR base SHA) lets the self-test scan fixtures.
- `changeset-check` input `migration_paths` (default `''`): when a PR adds a migration with a `-- contract:` line, its new changeset must give the package `minor`; otherwise fail with `a contract migration needs a minor changeset`.
- `changeset-version` input `app-json` (default `''`): after `changeset version`, set `.expo.version` in that file to the new `package.json` version, in the same Version PR commit.

- [ ] **Step 1:** self-test jobs over `fixtures/migrations/`: additive only → pass; `DROP COLUMN` without marker → fail (inverted like `red`); with marker → pass; a contract migration with a `patch` changeset → fail; with `minor` → pass.
- [ ] **Step 2:** implement; all self-test gates green.
- [ ] **Step 3:** `app-json`: a fixture run of the version script on `fixtures/expo` shows `app.json` at the bumped version. Then merge the v1.3.0 stack (Tasks 2–4), merge the Version PR, confirm `v1` moved.
- [ ] **Step 4:** prove the lock: dispatch arami `e2e.yml` while a second heavy Studio job runs. Expected: `slot=0`/`slot=1`, a third heavy job waits with the holder named, and `ls ~/Library/Caches/cheunjm-studio-lock` is empty afterwards.

### Task 4b: drop prerelease tags (D46)

**Files:** modify `.github/workflows/release-candidate.yml`, `.github/actions/release-gate/{action.yml,gate.py}`, `scripts/test_release_gate.py`, `rc-selftest.yml`, `CLAUDE.md` (two rows); `minor` changeset. Ships in v1.3.0 with Tasks 2–4.

**Interfaces (produces):**
- `release-candidate.yml`: same checks as today (default branch, `ci / gate` green, not in pre mode); no tag, no GitHub prerelease. Outputs `version` (`X.Y.Z`), `ref` (the SHA), `tag` (always `''`, kept for callers until v2). `channel` is accepted; with `publish: true` it publishes `X.Y.Z-next.N` under dist-tag `next`, `N` = highest `X.Y.Z-next.*` from `npm view <pkg> versions --json` plus one (0 when none).
- `gate.py --sha <sha> --version <X.Y.Z> [--require-e2e]` (`--tag` accepted, ignored): on `main`; `ci / gate` from app 15368; tested commit = newest in `git rev-list --first-parent -n 100 <sha>` with a `cd/develop` `success` status from `github-actions[bot]` (`no develop deploy before <sha7>: press the release button first`); code equal except the allowed files and fields, as today (`code differs from the last develop deploy <t7>: press the release button first`); with `--require-e2e`, `cd/e2e-develop` success from `github-actions[bot]` on the tested commit (`<t7> has no green develop e2e: press the release button first`). The prerelease/releases API logic is removed.

- [ ] **Step 1:** tests first: replace the prerelease tests with `test_no_develop_deploy_fails`, `test_newest_develop_deploy_is_used`, `test_code_after_develop_deploy_fails`, `test_version_only_after_develop_deploy_passes`, `test_develop_status_from_other_creator_ignored`, `test_missing_e2e_on_tested_commit_fails`; keep the rename, JSON, type-strict and CI-app tests. Run; expected fail.
- [ ] **Step 2:** implement; tests pass. `release-candidate.yml` dry run in `rc-selftest.yml` prints `version`, `ref` and no tag; `actionlint` clean.
- [ ] **Step 3:** PR, review, merge; then release v1.3.0 (Task 4 Step 3's release step moves here).

### Task 5: `cd.yml`

**Files:** create `.github/workflows/cd.yml`.

**Interfaces (produces), inputs:**

| Input | Default | Use |
|---|---|---|
| `environment` | `''` | `develop` \| `master`, set by the button caller |
| `tag` | `''` | master: the `vX.Y.Z` tag to check out and deploy |
| `ref` | `''` | develop: the SHA to check out and deploy (the button's `ref` output, D46) |
| `dry_run` | `false` | resolve and print; deploy nothing |
| `backend` | `false` | `supabase link`, then `migration list --linked` (fail on a remote-only migration, D23), `db push --yes`, `functions deploy --use-api --yes` |
| `ignore_pending_migrations` | `false` | when `backend` is off and local migrations are missing remotely, `plan` fails unless this is set |
| `app` | `false` | the app step (Global constraints) |
| `platforms` | `android,ios` | |
| `store_submit` | `false` | master: `eas submit` both stores |
| `firebase_groups` | `''` | Firebase App Distribution per built artifact |
| `sideload_apk` | `false` | also build profile `<env>-apk` |
| `web` | `false` | `doppler run -- <web_build_command>`, `<web_postbuild_command>`, `npx --yes vercel@65 deploy <web_output_dir> --prod --yes` |
| `web_build_command` | `npx expo export --platform web` | |
| `web_postbuild_command` | `''` | arami: `scripts/web-postbuild.sh` |
| `web_output_dir` | `dist` | |
| `storybook` | `false` | `<storybook_build_command>`, then `vercel deploy storybook-static --prod` with `vars.STORYBOOK_VERCEL_PROJECT_ID` |
| `storybook_build_command` | `npm run storybook:build` | |
| `e2e` | `false` | the e2e job |
| `e2e_platforms` | `android,ios` | |
| `e2e_flows` | `.maestro` | |
| `eas_runner` | `mac-studio` | |
| `node_version` | `20` | |
| `install_command` | `npm ci` | |
| `slack_channel` | `''` | Task 6 |

Secrets: those in Global constraints plus `EXPO_TOKEN`, `VERCEL_TOKEN`, `SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD`, `SUPABASE_PROJECT_REF`, `SLACK_BOT_TOKEN` (all optional). Outputs: `environment`, `tag`, `version`. Callers grant `contents: read`, `statuses: write`, `checks: read`.

Jobs (each target job `needs: plan`, `environment: ${{ needs.plan.outputs.environment }}`, skipped when it is `''` or its checkbox is off):
- **`plan`** (ubuntu): validates `environment` and `tag`, computes `version`, runs the pending-migrations guard, and for master the gate (Task 6). Prints the checklist as a table.
- **`backend`** (ubuntu).
- **`app`** (`eas_runner`, timeout 180): `needs: [plan, backend]`, `if: !failure() && !cancelled()`. Syncs Doppler `EXPO_PUBLIC_*` into the EAS environment (port of `scripts/sync-doppler-to-eas.sh`), sets `expo.version` to `version`, then the app step per platform. When `e2e` is on, it also makes sure the `e2e-<env>` build for the fingerprint exists (build and upload when missing) and uploads it as artifact `e2e-app-<platform>`.
- **`web`**, **`storybook`** (ubuntu): `needs: [plan, backend]`; storybook also `needs: web` without blocking on its failure.
- **`e2e`**: `needs: [plan, app, web]`, `if: !failure() && !cancelled()`; `uses: cheunjm/.github/.github/workflows/e2e-maestro.yml@v1` with `platforms: e2e_platforms`, `app-artifact: e2e-app`, `flows-path: e2e_flows`, `include-tags: smoke` on master, `secrets: inherit`. Test accounts reach flows as `E2E_EMAIL` and `E2E_PASSWORD` for the job's platform.
- **`develop-status`** (ubuntu, develop only, after every ticked target succeeded): sets commit status `cd/develop` = `success` on `ref`, with `GITHUB_TOKEN`.
- **`e2e-status`** (ubuntu, develop only, after `e2e` succeeds): sets commit status `cd/e2e-develop` = `success` on `ref`, with `GITHUB_TOKEN` (the gate trusts only `github-actions[bot]`).
- With `dry_run`, every job prints its commands and the fingerprint lookup and writes nothing.

- [ ] **Step 1:** write the file; `actionlint` clean.
- [ ] **Step 2:** commit on `feat/INF-1983-cd` (stack bottom for v1.4.0).

### Task 6: master gate and Slack

**Files:** modify `.github/workflows/cd.yml` (`plan` gate step, `notify` job).

- [ ] **Step 1 (gate):** in `plan`, when the environment is `master`, check out the tag with `fetch-depth: 0` and run `cheunjm/.github/.github/actions/release-gate@v1` with the tag's SHA, its `X.Y.Z`, and `require-e2e: <e2e input>` (D46 gate, Task 4b).
- [ ] **Step 2 (`notify`, ubuntu, `if: always() && inputs.slack_channel != ''`):** one `chat.postMessage` (same curl/jq pattern as `notify-merge.yml`) with repo, environment, tag, each checklist item's result (or "off"), per platform "OTA + build" or "build only", and the run URL.
- [ ] **Step 3:** `actionlint`; commit.

### Task 7: Expo fixture, button self-test, release v1.4.0

**Files:** create `fixtures/expo/{package.json,app.json,eas.json}` and `fixtures/callers/{release-candidate.yml,release-production.yml}` (the caller templates repos copy); modify `self.yml`, `CLAUDE.md` (`cd.yml` row, caller templates), changeset `minor`.

- [ ] **Step 1:** `self.yml` jobs calling `./.github/workflows/cd.yml` with `dry_run: true` and `eas_runner: ubuntu-latest` against `fixtures/expo`:
  - `cd-develop`: `environment: develop`, all checkboxes on. Expected: plan `develop`; each step prints its commands; the app step prints "no build: skip OTA, build".
  - `cd-empty`: no environment. Expected: `environment=''` and every target job skipped (Review focus 1).
  - `cd-master-gate`: `environment: master` against `.github`'s own latest `vX.Y.Z`, which has no `cd/develop` status. Expected: `plan` fails with `no develop deploy before <sha7>: press the release button first`; `continue-on-error` and a follow-up assertion, like `red`.
  - `cd-pending-migrations`: `backend: false` with a fixture migration missing remotely (dry-run stub). Expected: `plan` fails; with `ignore_pending_migrations: true`, it passes.
- [ ] **Step 2:** the caller templates pass `actionlint`. Push; all self-test gates green. Merge, merge the Version PR, confirm `v1` → v1.4.0.

### Task 8: starlog on `cd`

**Files (starlog):**
- Create: `.github/workflows/release-production.yml` (from the template).
- Modify: `release-candidate.yml` (checklist inputs and the `cd` job), `release.yml` (`app-json: app.json`), the migration-check caller (`block_destructive: true`) and the `Release notes` caller (`migration_paths: supabase/migrations/**`), `eas.json` (`appVersionSource: remote`, `autoIncrement`, profiles `e2e-develop` and `e2e-master`), `.maestro/` (tag the smoke flows `smoke`; flows read `E2E_EMAIL`/`E2E_PASSWORD`), `docs/deployment.md`, `CLAUDE.md`.
- Delete: `deploy-web.yml`, `eas-build.yml`, `eas-update.yml`, `deploy-supabase.yml`, `e2e.yml`, `.github/actions/verify-release/`, `scripts/sync-doppler-to-eas.sh`, the local e2e backend scripts.
- `.github` `secrets.manifest.toml`: `FIREBASE_SERVICE_ACCOUNT`, `FIREBASE_APP_ID`/`FIREBASE_APP_ID_IOS`, `ASC_*`, `E2E_TEST_ACCOUNTS`, both environments.

Checklist defaults (both buttons): `backend`, `app`, `web`, `e2e` on; `storybook` off (INF-1988). Repo config: `platforms: android`, `firebase_groups: testers`, `sideload_apk: true`, `store_submit: true`, `slack_channel: C0AJD47H6R4`.

- [ ] **Step 1:** align versions: a PR sets `package.json` to `app.json`'s 1.3.0 (stores reject a lower version).
- [ ] **Step 2:** test accounts: one per platform in develop and in master Supabase (Jace creates the master ones if denied); 1Password items; manifest PR; `sync-secrets.py --repo starlog --dry-run`, then a real run. Expected: `VERCEL_ORG_ID`/`VERCEL_PROJECT_ID` exist as variables.
- [ ] **Step 3:** starlog PR; dispatch the PR branch's `release-candidate.yml` with `dry_run`. Expected: the checklist table, Supabase lists no remote-only migration, the fingerprint lookup printed.
- [ ] **Step 4:** merge; a push to `main` deploys nothing.
- [ ] **Step 5:** release button, all defaults. Expected: backend, app (first run: build only, then Firebase and the APK), web, e2e green on both test builds, `cd/develop` and `cd/e2e-develop` on the deployed commit, no new tag, one Slack message. A second press with no native change: "OTA + build".
- [ ] **Step 6:** after the next Version PR (with `app.json` bumped in it): production button with `web` off. Expected: gate passes, backend, build, store submission and Firebase, smoke e2e green, and the production test accounts hold no leftover data. Then a press with only `web`.
- [ ] **Step 7:** refusals: the release button on a red `ci / gate`; the production button after a merge past the last develop deploy (`press the release button first`).

### Task 9: arami on `cd`

As Task 8, with: `web_postbuild_command: scripts/web-postbuild.sh`, `platforms: android` (iOS once its credentials exist), no Firebase, `store_submit` once the store listings exist (until then off), and `SUPABASE_*` manifest entries from new 1Password items Jace creates.

- [ ] **Step 1:** the chat and logout flows that fail on `main` (INF-1982) are fixed or untagged first, so develop e2e can pass.
- [ ] **Step 2:** the caller defaults `backend` off and the dry run checks D23: `migration list --linked` shows no remote-only migration in either environment. If drift shows, open an issue and keep `backend` off.
- [ ] **Step 3:** once clean, a follow-up PR defaults `backend` on; then Task 8 Steps 4–7.

### Task 10: ui on `cd` (Storybook only) and the button with publish

ui has no EAS project or app web deploy, so its checklist is `storybook` only (D39.3).

**Files (ui):** modify `release.yml` (the button path gains the `cd` job with `storybook`; `cut` keeps `publish: true, trusted_publishing: true`, so npm's trusted publisher stays `release.yml`); create `release-production.yml` (storybook only); delete `prerelease.yml` and `.changeset/pre.json` (leave pre mode, D27); update the INF-1982 plan's versioning line; `CLAUDE.md` (drop `stage` and `ci / contrast`). GitHub Environments `develop` and `master` with `STORYBOOK_VERCEL_PROJECT_ID` for new Vercel projects `ui-storybook-develop`/`ui-storybook-master` (Jace creates projects and environments if denied); delete the leftover `Preview*`/`Production*` environments and the unused repo secrets `CHROMATIC_PROJECT_TOKEN`, `DOPPLER_TOKEN_*`, `VERCEL_PROJECT_ID*`.

- [ ] **Step 1:** environments and secrets (manifest PR in `.github`, then sync).
- [ ] **Step 2:** check the counter: `npm view @jaemincheun/ui versions` shows `1.0.0-next.7` as the highest `1.0.0-next.*`, so the button's registry counter (D46) picks 8. No tag is pushed.
- [ ] **Step 3:** ui PR; after merge, button `next`. Expected: `@jaemincheun/ui@1.0.0-next.8` on `next` and Storybook live at the develop URL.
- [ ] **Step 4:** the production button on a commit whose code is newer than the last develop deploy fails with `press the release button first`. The Version PR (`1.0.0`) stays unmerged until INF-1982 says ship (D27.2).

### Task 11: give-and-take, first CD and e2e

Prerequisite check (Jace): hosted Supabase projects for develop and master, Doppler `give-and-take` configs `develop`/`master`, Vercel projects `give-and-take-develop`/`give-and-take`, store listings. Missing pieces are created first; the task does not invent them.

**Files (give-and-take):** `release.yml` (`@v1`, `tag: true`, `app-json: app.json`), both button callers (checklist defaults `backend`, `app`, `web`, `e2e`; `platforms: android`), migration-check and `Release notes` callers as in Task 8, `eas.json` as in Task 8, `.maestro/flows/smoke.yaml` (tag `smoke`), `docs/release.md`. Studio runners `mac-studio-giveandtake` (label `mac-studio`), `-android`, `-ios`. Manifest entries for every secret above in both environments; GitHub Environments `develop`/`master`.

- [ ] **Step 1:** runner, environments, manifest and sync.
- [ ] **Step 2:** the smoke suite: launch, sign-in screen shows its Apple and Google buttons (D39.4); it creates no data, so it runs in both environments without test accounts.
- [ ] **Step 3:** dry runs of both buttons, then Task 8 Steps 4–7.

### Task 12: openwiki merges report `ci / gate`

Once Tasks 8–11 merged: `openwiki-update.yml` drops `[skip ci]` from its squash subject (`patch` changeset, release). Check: the next wiki merge on `main` in arami shows `ci / gate`, so the button works right after a wiki merge.

### Task 13: follow-up issues

- [ ] One Linear issue per app (arami, starlog, give-and-take): a minimum-app-version gate. The app compares its JS `expo.version` with a `min_app_version` the backend serves and shows an update-required screen below it. A contract migration may merge only once that minimum is at or past its `safe after` version (D42).
- [ ] give-and-take: a test-only auth path so signed-in flows can run (D39.4).
- [ ] Automate releasing an approved store version (App Store phased release, Play managed publishing) if pressing release in the stores becomes a chore.

### Stage 4 done

The stage goal's done criteria (`plan.md` stage 4) hold for starlog, arami, ui and give-and-take, and no app repo has `deploy-web`, `eas-build`, `eas-update`, `deploy-supabase`, `verify-release` or a Version PR e2e trigger left.
