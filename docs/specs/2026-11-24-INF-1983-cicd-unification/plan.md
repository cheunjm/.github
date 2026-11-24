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
  - **Environment:** resolved from the trigger (D6, D20). A push to `main` and any prerelease tag (`vX.Y.Z-*`) deploy `develop`. A clean `vX.Y.Z` tag deploys `master`. A manual dispatch takes an explicit environment. There are exactly two environments.
  - **Release gate:** `master` deploys keep `verify-release`: the commit is on `main` and `ci / gate` passed on that SHA (D22.2).
  - **EAS:** chooses build or OTA by fingerprint (D8). Builds run with `eas build --local` on `mac-studio` (D9). Store submission on `master` is opt-in through a `submit` input. Platforms and a sideload APK are inputs too (D22.3).
  - **Web:** one Vercel project per environment, with project IDs and the Doppler token held in the GitHub Environments `develop` and `master` (D22.4).
  - **Storybook:** with `storybook: true`, the web target also builds the Storybook (`storybook_build_command`) and deploys it to its own Vercel project per environment, after the app's web deploy. A Storybook failure does not block EAS (D24).
  - **Other inputs:** Doppler app env sync and a `dry_run` input (D15).
  - **Slack:** a message for every run, success or failure, to the repo's notify-merge channel (D16).
  - **Internal blocks:** the per-target reusables are internal and not part of the `@v1` contract.
- **Native e2e:** `e2e-maestro` runs both iOS and Android on `mac-studio` (D13). The Android job is ported from Linux/KVM to macOS arm64. starlog's inline Android e2e moves onto it (D22.1). Web e2e stays on hosted runners.
- **Tags:** the app repos' release flow gains a step that creates `vX.Y.Z` tags with the arami-bot token, because nothing creates them today (D22.8).
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
   - Add the `v1` tag automation, the app-repo `vX.Y.Z` tagging step, the secrets manifest and sync script, the ruleset script, and `auto-resolve-conflicts`.
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

   Done when each app repo has had a develop deploy from a `main` push and a production deploy from a clean `vX.Y.Z` tag through `cd`, each posting to Slack, and ui's Storybook is live at both Storybook project URLs.
5. **`v2`.** Remove the `ci-node` wrapper and any other deprecated inputs. Done when no caller references `ci-node`, `.github` publishes `v2.0.0`, and callers move to `@v2`.

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
  - a real develop deploy from a `main` push, checking the Slack message, the Vercel URL, the EAS OTA on the develop channel, and that Supabase migrations ran first;
  - after the next Version PR, a production deploy from the `v*` tag;
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
- **Fingerprint:** the Expo native fingerprint used as `runtimeVersion`. A build is needed only when no build exists for it.
- **Studio:** the self-hosted `mac-studio` runner on Jace's Mac Studio.

## Later

- Move one-off workflows if a second repo ever needs them.
- Revisit D9 (local-only EAS builds) if the Studio becomes a release bottleneck.
- Shared Dependabot or Renovate config for action version bumps.
