# Decisions: CI/CD unification across cheunjm repos

Numbers are never reused, renumbered or deleted. Reverse a decision by adding a new entry that supersedes it.

D1–D18 were settled in a grilling session on 2026-11-23/24. Recommended answers were proposed by the AI; every choice below was made by Jace unless marked otherwise.

## D1: Where CI/CD logic lives
- **Problem:** "Organized and set in `.github`" can mean several bars of centralization.
- **Options:** A: all job logic in `.github`, repos keep thin callers that pass inputs and secrets only; B: A plus generated, synced callers; C: shared logic only where two or more repos duplicate it.
- **Choice:** A.
- **Rationale:** A behavior change is one `.github` PR. Thin, similar callers give most of B's benefit without a sync system.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** high

## D2: Single-repo workflows
- **Problem:** Strict D1 would move one-off workflows into `.github` with a single caller.
- **Options:** A: move everything; B: move anything reusable, keep repo-specific one-offs in their repo.
- **Choice:** B. `auto-resolve-conflicts.yml` (identical in maps-organizer, portfolio, star-organizer) moves to `.github`; `star-organizer/organize-stars.yml` and `engineering-log/receive-entry.yml` stay.
- **Rationale:** A shared workflow with one caller adds indirection and a cross-repo blast radius with no deduplication.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** low

## D3: Repos in scope
- **Problem:** Local checkouts include repos that no longer exist.
- **Options:** n/a (fact).
- **Choice:** 12 repos: arami, claude-statusline, clipsync, conventions, dotclaw, engineering-log, maps-organizer, mem0, portfolio, star-organizer, starlog, ui. Plus `.github` itself, which dogfoods everything. `stock-tracker` is deleted (Jace). `crosscheck` no longer exists on GitHub.
- **Rationale:** Scope follows what exists on GitHub, not stale local clones.
- **Proposed by:** human
- **Chosen by:** human
- **Impact:** low

## D4: How callers pin `.github`
- **Problem:** With all logic shared, one bad merge to `.github` breaks every repo, including production deploys.
- **Options:** A: `@main`; B: floating major tag `@v1`, moved when the Version Packages PR merges, breaking changes as `v2`; C: SHA pins plus Renovate/Dependabot bumps.
- **Choice:** B.
- **Rationale:** A deliberate "ship to all repos" step without N bump PRs. Breaking input changes become explicit majors.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** high

## D5: CI shape across stacks
- **Problem:** Repos are Node, Python, shell or mixed; six run inline CI that reinvents the paths filter and gate (named `gate` or `ci-status`).
- **Options:** A: one workflow per stack (`ci-node`, `ci-python`, `ci-shell`); B: one stack-agnostic `ci` with fixed slots (lint, typecheck, test, format, audit, build), toolchain inputs, a `preset` for default commands, built-in paths filter and `gate`; C: extend `ci-node` with Python.
- **Choice:** B. `ci-node` becomes a deprecated thin wrapper and is removed in `v2`. **Partly superseded by D30.1:** `ci-node` is deprecated as it is, not turned into a wrapper.
- **Rationale:** Identical check names in every repo (`ci / lint`, …, `ci / gate`), so rulesets and tooling treat all repos alike. Mixed repos combine commands within a slot.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** high

## D6: Promotion model for app repos
- **Problem:** arami and starlog deploy develop on push to `main` and production on `v*` tags; ui deploys production on `release: published`.
- **Options:** A: push to `main` → develop, `v*` tag (created by arami-bot when the Version Packages PR merges) → production; B: production on `release: published`; C: GitHub Environment approval (not available for private repos on Free).
- **Choice:** A. ui migrates. **Partly superseded by D26:** a push to `main` no longer deploys develop.
- **Rationale:** Same "Version PR is the release button" model as D4. A tag is harder to fire by accident than a UI release.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** high

## D7: CD shape
- **Problem:** EAS build, EAS update, web and Supabase deploys are separate files with no ordering, so a migration can land after the code that needs it.
- **Options:** A: one public reusable per target; B: one `cd` orchestrator with target switches, fixed order Supabase → web → EAS, per-target reusables internal only; C: both public.
- **Choice:** B.
- **Rationale:** One caller per app repo, safe ordering, one place for environment resolution, Doppler sync and Slack. Internal blocks are not part of the `@v1` contract.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** high

## D8: EAS build vs OTA update
- **Problem:** arami and starlog use `runtimeVersion: { policy: "fingerprint" }` but decide build-vs-update with a path filter, which misfires both ways. ui hardcodes `runtimeVersion` to `major.minor`.
- **Options:** A: fingerprint-driven (build only if EAS has no build for the current fingerprint in that environment, then always publish the OTA); B: path filter as an input; C: `main` always OTA, `v*` always full build.
- **Choice:** A. ui moves to the fingerprint policy.
- **Rationale:** Correct by construction and removes per-repo path lists.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** med

## D9: Where EAS builds run
- **Problem:** arami builds locally to dodge the EAS cloud quota; starlog uses cloud builds.
- **Options:** A: cloud always; B: `eas build --local` on the Mac Studio always; C: input, default cloud.
- **Choice:** B.
- **Rationale:** Jace's call: no quota, fast builds. Accepted cost: releases depend on the Studio being online. Each app repo needs its own `mac-studio` runner registration (personal account, no org runners).
- **Proposed by:** ai (recommended C)
- **Chosen by:** human
- **Impact:** med
- **Labels:** revisit (if the Studio becomes a release bottleneck)

## D10: Runner policy for everything else
- **Problem:** Hosted Linux minutes cost about $86 for November 2026 (17.9k min). Self-hosted jobs depend on one machine.
- **Options:** A: hosted by default, Studio for EAS builds only; B: Studio for everything; C: per-repo `CI_RUNNER` switch.
- **Choice:** Shared workflows keep the `runner` input → `vars.CI_RUNNER` → `ubuntu-latest` fallback, but every repo stays on hosted runners. Only jobs that need the Studio's hardware use it, hardcoded in the shared workflow (see D11, D13). arami's `CI_RUNNER=mac-studio` is removed.
- **Rationale:** Ordinary CI and deploys must not depend on the Studio.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** high

## D11: Remove ci-autofix
- **Problem:** `ci-autofix` agent-fix calls a local LLM through `127.0.0.1` and so needs the Studio, conflicting with D10.
- **Options:** A: keep as a Studio exception; B: move to a cloud model; C: remove.
- **Choice:** C. Remove `ci-autofix.yml` and its callers (claude-statusline, conventions, dotclaw, mem0, ui).
- **Rationale:** Jace's call.
- **Proposed by:** human
- **Chosen by:** human
- **Impact:** med

## D12: openwiki runner
- **Problem:** `openwiki-update` calls LiteLLM on the Studio's localhost via dedicated `mac-studio-*-openwiki` runners.
- **Options:** A: keep on the Studio as a named exception; B: hosted, calling the model provider directly with a provider API key; C: remove.
- **Choice:** B. Deregister the orphaned `mac-studio-engineering-log-openwiki` runner. **Superseded by D28.**
- **Rationale:** Jace's call: no Studio dependency outside EAS builds and native e2e.
- **Proposed by:** ai (recommended A)
- **Chosen by:** human
- **Impact:** low

## D13: Native e2e runner
- **Problem:** iOS e2e needs macOS; hosted macOS bills at 10×.
- **Options:** A: hosted macOS; B: drop iOS e2e; C: Studio.
- **Choice:** C, extended by Jace to all native e2e: iOS and Android `e2e-maestro` jobs run on the Studio. Web e2e stays hosted.
- **Rationale:** Jace's call. Consequence: the Android job moves from hosted Linux (KVM, x86 AVD) to macOS (arm64 system image, Hypervisor.framework).
- **Proposed by:** ai (recommended A)
- **Chosen by:** human
- **Impact:** med

## D14: Secrets source
- **Problem:** Personal account means per-repo secrets; names have drifted (`BOT_APP_ID` vs `APP_ID`, Vercel IDs as vars in one repo and secrets in others).
- **Options:** A: pipeline secrets with standard names in 1Password, pushed per repo by a manifest-driven sync script; app runtime env stays in Doppler; B: Doppler for everything; C: standard names, set by hand.
- **Choice:** A. The manifest (names, `op://` refs, repo lists, never values) and the sync script live in `.github`. Values reach `gh secret set` on stdin, never argv.
- **Rationale:** Each tool keeps its current role; rotating a token is one command; tool repos never need Doppler.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** med

## D15: Validating `.github` changes
- **Problem:** The only CI here is actionlint, so shared workflow bugs surface in real repos.
- **Options:** A: fixture projects in `.github` exercised by its own PR CI, plus a `cd` `dry_run` input; B: a sandbox repo; C: a canary repo on `@main`.
- **Choice:** A.
- **Rationale:** A PR proves itself before merge. After `@v1` moves, the next deploy is develop, so CD bugs surface before production.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** med

## D16: CD notifications
- **Problem:** Only ui posts deploy results to Slack.
- **Options:** A: production runs plus any failure; B: every run, success and failure; C: none.
- **Choice:** B, to the repo's existing notify-merge channel. ui's own Slack code goes away.
- **Rationale:** Jace wants to see successes and failures.
- **Proposed by:** ai (recommended A)
- **Chosen by:** human
- **Impact:** low

## D17: Rollout order
- **Problem:** Big bang vs phased.
- **Options:** A: phased, one PR per repo per phase; B: big bang.
- **Choice:** A: cleanup → `.github` foundation → CI migration ×12 → CD (starlog → arami → ui) → `v2` removes `ci-node`.
- **Rationale:** Each phase ships and rolls back on its own; CI is proven on 12 repos before CD touches production.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** med

## D18: Enforcing the gate
- **Problem:** Private repos on GitHub Free have no branch protection or rulesets (API returns 403), so `ci / gate` is advisory. Mergify's "keep up-to-date" rebase rule also collides with `auto-update-branches.yml`, which only merges.
- **Options:** A: GitHub Pro rulesets requiring `ci / gate` and `changeset / check`, remove Mergify; B: Mergify everywhere via `extends: .github`; C: leave it unenforced.
- **Choice:** A. Pro comes free with the GitHub Student Developer Pack (approved 2026-11-22, active about 2026-11-25). A repo gets its ruleset only after its CI migration merges and emits `ci / gate`.
- **Rationale:** The design assumes `ci / gate` is the one required check; only Pro makes that enforceable. Removes a tool.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** high

## D19: Calls made without asking
- **Problem:** Details the grilling left to the builder.
- **Options:** n/a.
- **Choice:** (1) conventions and engineering-log get the shared `ci` with non-applicable slots off, so every repo has `ci / gate`. (2) Web deploys use the Vercel CLI with prebuilt output (`vercel build` then `vercel deploy --prebuilt`), env from Doppler. (3) Rulesets are applied by a script that reads the same manifest as D14. (4) `.github` calls its own shared workflows.
- **Rationale:** Consistency with D5, D7 and D14. Jace saw these listed and confirmed the summary.
- **Proposed by:** ai
- **Chosen by:** ai
- **Impact:** low

D20–D23 came from the builder check on 2026-11-24.

## D23: arami Supabase target
- **Problem:** arami has a `supabase/` directory but no deploy workflow and no `SUPABASE_*` secrets. Enabling the target means the first automated `db push` to its production database.
- **Options:** A: enable it, gated on a clean migration-history check; B: leave it off; C: enable it without a check.
- **Choice:** A. arami's stage-4 PR first runs `cd` with `dry_run: true`, which compares local and remote migration history (`supabase migration list --linked`). The target is enabled only if that is clean. Drift becomes its own issue.
- **Rationale:** Brings arami to the same CD shape as starlog without risking an unreviewed push to production.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** med

## D20: Prerelease tags and ui's `stage` environment
- **Problem:** ui uses changesets pre mode. `-dev.N` tags deploy develop, and `-rc.N` tags deploy a third environment, `stage`. Under D6 as written, any `v*` tag deploys production.
- **Options:** A: keep `stage` as a third environment; B: drop `stage`, so prerelease tags deploy develop and only clean `vX.Y.Z` tags deploy master; C: drop pre mode.
- **Choice:** B. This refines D6: the production trigger is a tag matching `vX.Y.Z` with no prerelease suffix. ui's `stage` EAS profile and channel, Doppler config, `DOPPLER_TOKEN_STAGE` and stage domain are removed.
- **Rationale:** Jace: "ui shouldn't have stage." Every repo then has exactly two environments.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** med

## D21: ui CI jobs outside the six slots
- **Problem:** ui runs `ci / contrast`, `visual / chromatic` and web e2e outside `ci-node`. Once rulesets require only `ci / gate`, these would stop blocking.
- **Options:** A: new shared slots; B: keep them as repo-local jobs; C: fold them into existing slots; D: remove them.
- **Choice:** Remove `ci / contrast` and `visual / chromatic` (and the Chromatic secret). Web e2e stays a separate `e2e-maestro` caller, and ui's ruleset also requires `e2e / web`.
- **Rationale:** Jace's call. No slot is added for a single repo.
- **Proposed by:** human
- **Chosen by:** human
- **Impact:** low

## D22: Builder-check details settled by the AI
- **Problem:** Gaps found by the builder check that do not change what gets built.
- **Options:** n/a.
- **Choice:**
  1. starlog's inline Android e2e moves to `e2e-maestro` on the Studio (follows D13 and D1).
  2. `cd` keeps the existing release gate for master (`verify-release`: the commit is on `main` and `ci / gate` passed on that SHA). Develop deploys run on push without it.
  3. Store submission stays opt-in per repo through a `submit` input. Platforms and arami's sideload APK are inputs too.
  4. Vercel uses one project per environment (the arami and starlog model). Project IDs and the Doppler token live in the GitHub Environments `develop` and `master`. ui moves to this model, and the secrets manifest gains an environment column.
  5. Rulesets allow admin bypass for emergencies. Verification checks the block for non-bypass actors.
  6. Stage 4 starts with a spike on whether `eas build --local` plus `eas upload` records the fingerprint in EAS. If not, built fingerprints are recorded as GitHub deployment records.
  7. Stage 1 hardcodes `mac-studio` in arami's current `eas-build.yml`, so unsetting `CI_RUNNER` does not move its builds off the Studio before stage 4.
  8. Nothing creates `v*` tags in the app repos today. The release flow gains a tagging step that uses the arami-bot token.
- **Rationale:** Each follows from an earlier decision or preserves current behavior.
- **Proposed by:** ai
- **Chosen by:** ai
- **Impact:** low

## D24: Storybook per environment
- **Problem:** Jace wants each app's Storybook published for both develop and master. Only ui has a Storybook today. D21 removed Chromatic as a PR check.
- **Options:** A: `cd` deploys the Storybook to its own Vercel project per environment; B: serve it at a subpath of the app's web deploy; C: publish to Chromatic per environment.
- **Choice:** A. The `cd` web target gains `storybook: true` and `storybook_build_command` (default `npm run storybook:build`). After the app's web deploy, it deploys the Storybook output to a separate Vercel project per environment (`<app>-storybook-develop`, `<app>-storybook-master`), with project IDs in the GitHub Environments. A Storybook failure is reported but does not block EAS. Both Storybooks may be public. D21 stands: Chromatic stays removed.
- **Rationale:** Reuses the web target and the per-environment project model (D22.4) with no snapshot quota and no second vendor. Chromatic's advantages (private access, visual baselines) aren't needed, since Jace accepted public Storybooks and D21 dropped visual checks. arami and starlog turn it on once they have a Storybook, which is app work tracked outside this spec.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** low

## D25: Stage 1 details settled by the AI
- **Problem:** Writing the stage 1 tasks found gaps the spec did not cover.
- **Options:** n/a.
- **Choice:**
  1. The Studio also runs launchd services for `cheunjm/crosscheck` and `cheunjm/stock-tracker`, whose repos are deleted (D3). Stage 1 removes them with the engineering-log openwiki runner, and unsets engineering-log's `OPENWIKI_RUNNER`. Runner dirs are moved to a backup folder, not deleted.
  2. arami's other `CI_RUNNER` uses (`deploy-web`, `eas-update`, the PR plumbing callers) become `ubuntu-latest` in the same PR, and `deploy-web` and `eas-update` are dispatched to develop to prove they don't need the Studio.
  3. Docs that describe `ci-autofix` (conventions `ci-tooling.md`, `ci-check-naming.md`, `project-structure.md`, `versioning.md`, the `new-repo-bootstrap` skill and `.github`'s `CLAUDE.md`) are cleaned in stage 1, in the same PRs as the removal.
  4. The `.github` removal is a `major` changeset, following the INF-1924 `agent-review` precedent.
- **Rationale:** Each follows from D3, D10 or D11, and leaving them would leave dead services or docs pointing at a deleted workflow.
- **Proposed by:** ai
- **Chosen by:** ai
- **Impact:** low

## D26: Develop deploys from rc tags, master only ships rc-tested code
- **Supersedes:** D6's "push to `main` deploys develop".
- **Problem:** Deploying develop on every push to `main` is too heavy (Jace).
- **Options:** A: a "cut rc" button tags `main`, and master builds from the Version PR tag; B: changesets pre mode, with a Version PR per rc and a release PR for master; C: a nightly scheduled rc.
- **Choice:** A, and master is gated on the rc.
  - **Button:** a shared `release-candidate.yml` with a thin `workflow_dispatch` caller in each app repo (arami, starlog, ui). It tags the `main` HEAD as `vX.Y.Z-rc.N` with the arami-bot token, and that tag triggers `cd` for develop (D20 routing).
  - **Production:** merging the Version PR still creates the clean `vX.Y.Z` tag (D22.8). `cd` builds master fresh with master config, because Doppler env is baked in per environment, so no develop artifact is reused. Before building, it checks that the release commit's code matches the latest `vX.Y.Z-rc.N`. Only `package.json` and lockfile versions, `CHANGELOG.md` and `.changeset/` may differ. Any other change fails the deploy with "cut a new rc first".
  - **Main push:** runs only CI and the Version PR update.
- **Calls made by the AI while recording this:**
  1. The button refuses to tag unless `ci / gate` passed on that SHA, the same check as `verify-release`.
  2. `X.Y.Z` is the version the pending changesets would produce (`changeset status`), or the next patch when there are none. `N` starts at 0 and counts up per `X.Y.Z` (D27 makes it per version and channel), matching changesets and `npm version prerelease`.
  3. **Superseded by D27.** ui leaves changesets pre mode in stage 4 and uses the same button. `changeset-prerelease.yml` stays for any npm package that needs real prerelease versions.
- **Rationale:** One click per develop deploy and no extra PRs. Production stays tied to the Version PR already merged today, and production only ships code that ran on develop. Pre mode exists for published npm prereleases, and these apps read no rc version.
- **Proposed by:** human (rc tags), ai (button, rc check)
- **Chosen by:** human
- **Impact:** high

## D27: One release flow for every repo, with `next` and `rc` channels
- **Supersedes:** D26 point 3; extends D26's button.
- **Problem:** ui is the published npm package `@cheunjm/ui` and uses changesets pre mode (`next`). Apps pin exact prereleases from it. D26 point 3 would have taken ui off pre mode without a way to publish prereleases. Jace wants every repo on the same flow.
- **Options:** A: ui keeps pre mode as an exception; B: every repo uses pre mode; C: every repo uses the button, and package repos also publish what it cuts.
- **Choice:** C, with two channels.
  - **Button:** `release-candidate` takes `channel: next | rc` (default `rc`). It tags `vX.Y.Z-<channel>.N` (N counts per version and channel) and deploys develop. In a repo that publishes a package, it also publishes `X.Y.Z-<channel>.N` under the npm dist-tag of the same name. The version is set in CI only and never committed.
  - **Master gate:** the latest prerelease tag for `X.Y.Z` must be an `rc`, and its code must match the release commit (D26). A `next` can never ship.
  - **Stable:** merging the Version PR tags `vX.Y.Z`, publishes to `latest` in package repos, and deploys master.
  - **No pre mode anywhere.** `changeset-prerelease.yml` is removed in stage 5.
- **Calls made by the AI while recording this:**
  1. The button refuses to run while a repo still has `.changeset/pre.json`, so its tags never collide with changesets' own prerelease tags.
  2. ui leaves pre mode in its stage 4 PR, once the button exists, so it is never left without a way to publish prereleases. Until then ui keeps publishing `1.0.0-next.N` through pre mode. After it exits, ui's Version PR reads `1.0.0` and stays unmerged until ui's INF-1982 plan says ship. It must stay manual, with no auto-merge.
  3. ui's INF-1982 plan, which leaves pre mode through `release-stable` at its own stage 4, is updated in that same ui PR.
- **Rationale:** This matches common practice: SemVer, a release PR for stable, and per-release prerelease channels like React's (`canary`, `rc`) or TypeScript's (`beta`, `rc`). There is no phase state in the repo and no enter or exit PRs. `rc` versus `next` lets a develop build be marked as not shippable.
- **Proposed by:** human (same flow everywhere, keep next and rc), ai (channel input, rc-only master gate)
- **Chosen by:** human
- **Impact:** med

## D28: openwiki in every repo, on the Studio
- **Supersedes:** D12.
- **Problem:** openwiki's model access is the Studio's LiteLLM (`:4001`, `chatgpt/gpt-6.1-sol`), which uses Jace's ChatGPT subscription login, not an API key. Hosted runners (D12) would need a paid API key, and Jace wants openwiki in more repos, which would multiply that cost. A runner runs one job at a time, so sharing the app repos' `mac-studio` runner would queue wiki runs against EAS builds and native e2e.
- **Options:** A: hosted with a paid API key; B: the Studio, using the subscription; C: remove openwiki.
- **Choice:** B, in all 12 repos.
  - **Runner label:** every caller runs on `mac-studio-openwiki`. arami, starlog and ui get a second runner, `mac-studio-<repo>-openwiki`; starlog already has one. The other 9 repos add the label to their existing, now idle `mac-studio-<repo>` runner; portfolio first gets a runner registered.
  - **Trigger:** push to `main`, ignoring docs-only and `.changeset`-only pushes. Runs queue rather than cancel.
  - **Model:** the shared workflow defaults to `http://127.0.0.1:4001/v1`, `gpt-6.1-sol` and the Responses API, so callers pass nothing.
  - **Compatibility:** `vars.OPENWIKI_RUNNER` is still honored until stage 3 moves starlog's caller, and is removed in stage 5.
- **Rationale:** No per-token cost, and the wiki is not on any release path. A dedicated label keeps mobile work from waiting.
- **Proposed by:** human (more repos), ai (label scheme)
- **Chosen by:** human
- **Impact:** low

## D29: Remove `auto-resolve-conflicts`
- **Supersedes:** the part of D2 that moved `auto-resolve-conflicts` into `.github`.
- **Problem:** The workflow, in maps-organizer, star-organizer and portfolio, posts `@claude` comments asking for a rebase and a force-push. No repo has a responder (`claude.yml` was removed in INF-1658), so it only adds comments. It also breaks the conventions rule that CI/CD must not depend on an agent.
- **Options:** A: remove it; B: share a deterministic comment-and-label version; C: share it as is.
- **Choice:** A. The three copies are deleted in stage 3, and no shared version is built.
- **Rationale:** It has done nothing since its responder was removed, and GitHub already shows conflicts on the PR.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** low


## D30: Stage 2 details settled by the AI
- **Problem:** Gaps found while writing the stage 2 tasks.
- **Options:** n/a.
- **Choice:**
  1. **`ci-node` is not a wrapper** (supersedes that part of D5). A reusable workflow that calls another adds a level to check names (`ci / ci / lint`). Rewriting it would rename every `ci-node` caller's checks, so it stays as it is, marked deprecated, and is removed in v2 as planned.
  2. **The manifest is TOML** (`secrets.manifest.toml`), read with stdlib `tomllib`. The Studio's Python has no PyYAML, and the scripts stay dependency-free.
  3. **File names:** the shared CI is `ci.yml` (callers write `uses: …/ci.yml@v1`), and `.github`'s own PR CI is renamed `self.yml`.
  4. **Slot design:** a `plan` job resolves the preset defaults, overrides and paths filter, then one matrix job runs the slots, named per slot so the checks stay `ci / <slot>`. An empty command means the preset default, and `none` turns a slot off.
  5. **Self-test:** an `expect_failure` input inverts `gate`, so the deliberately red self-test leaves a green gate. Its slot check is red by design.
  6. **The `CI_RUNNER` fallback is not carried into presets.** No repo sets it (D10), and the presets assume hosted Ubuntu.
  7. **ui's extra inline jobs** (`ci / api`, `ci / stories`) become required through the manifest's `extra_checks` for ui (Task 6), rather than through new slots (consistent with D21).
- **Rationale:** Each keeps current callers working, keeps the tooling dependency-free, or follows an earlier decision.
- **Proposed by:** ai
- **Chosen by:** ai
- **Impact:** low

## D31: Stage 2 review findings settled by the AI
- **Problem:** The final review of the stage 2 PRs found gaps the plan did not cover.
- **Options:** n/a.
- **Choice:**
  1. **The release button lives in each repo's `release.yml`**, as a `workflow_dispatch` path next to the push-triggered Version PR job. npm trusted publishing matches the caller's workflow file, and ui's trusted publisher is `release.yml`. `release-candidate.yml` gains `trusted_publishing`.
  2. **openwiki's `publish` job runs on `ubuntu-latest` by default**, including for starlog, which used to publish on the Studio. The job holds the write token and needs no model, so it should not share a persistent runner with the agent. This is a deliberate hardening.
  3. **openwiki PRs and rulesets:** wiki PRs are opened with `github.token` and merged with `[skip ci]`, so `ci / gate` never reports on them. Stage 3 switches openwiki to the App token without `[skip ci]` before applying any ruleset.
  4. **CI callers also run on push to the default branch**, because the button needs `ci / gate` on that branch's HEAD.
  5. **The button allows a repo exiting pre mode** (`pre.json` mode `exit`) and computes versions like `semver.inc`, so ui can cut rcs of `1.0.0` while its stable Version PR is held.
  6. **Node 20 stays the `ci.yml` default** for parity with `ci-node`, even though Node 20 is past end of life. Moving to 22 is a per-repo change in stage 3, not a silent default change.
- **Rationale:** Each closes a review finding with the smallest change that keeps current callers working.
- **Proposed by:** ai
- **Chosen by:** ai
- **Impact:** low

## D32: The arami-bot App has the Workflows permission
- **Problem:** Creating `v1` failed. GitHub refuses any tag a GitHub App creates or moves, through git or the refs API, when the tagged commit contains workflow files, unless the App has the Workflows permission. Every `.github` release commit, and an app repo's rc after any workflow change, hits this.
- **Options:** A: grant the App Workflows (read and write); B: create such tags with a personal token.
- **Choice:** A. Jace granted it on 2026-11-25. `major-tag.yml` then created `v1` at `v1.0.0` (`3b6145c`).
- **Rationale:** The release button and the major tag must work in every repo without a personal token. Tradeoff: the App, whose key is in every repo (D14), can also edit workflow files.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** med

## D33: e2e runs only on the Version PR, every platform on the Studio
- **Supersedes:** D13's "web e2e stays on hosted runners", and D21's requirement that ui's ruleset include `e2e / web`.
- **Problem:** Jace: "e2e should only run on versioning, and it should run on mac studio." arami and starlog already run e2e only on the Version PR (`changeset-release/main`) and by dispatch, but Android runs on hosted Linux. ui no longer has an e2e workflow, yet its manifest entry still lists `e2e / web` as a required check, which would block every ui PR. Rulesets also can't require e2e: on a normal PR the caller job is skipped, so only a check named `e2e` appears, never `e2e / android`.
- **Options:** A: Version PR only, on the Studio, enforced at release time; B: also on every PR; C: keep Android hosted.
- **Choice:** A.
  - **Trigger:** e2e runs on the Version PR (opened by arami-bot, same-repo) and by `workflow_dispatch`, never on other PRs.
  - **Runners:** `e2e-maestro.yml` defaults `android-runner` and `web-runner` to `mac-studio`. The Android job is ported from the Linux KVM x86_64 emulator to the macOS arm64 emulator (pulled forward from stage 4 into stage 3). starlog's inline Android job moves onto `e2e-maestro`.
  - **Enforcement:** not through rulesets. Jace merges the Version PR by hand and sees the e2e result. In stage 4 the master deploy also checks that e2e passed on the Version PR that produced the release.
  - **ui:** `e2e / web` is removed from its `extra_checks`. ui has no e2e until it adds one.
- **Rationale:** The Studio already does the iOS run. Running every platform there keeps one environment, and the Version PR is the one point where a release is decided.
- **Proposed by:** human (trigger, runner), ai (enforcement, port timing)
- **Chosen by:** human
- **Impact:** med

## D34: Shared CI runs its slots in one job by default
- **Problem:** Every job bills at least one minute. starlog's 7-job CI ran 244 times in November 2026, about 1,700 billed minutes (~$10). The shared `ci.yml` would bill up to 8 jobs per run (`plan`, six slots, `gate`).
- **Options:** A: a `layout` input, default `single` (one job runs the slots one after another), with `matrix` as an opt-in; B: CI on the Studio (reverses D10, and CI would queue behind EAS builds and e2e); C: keep the matrix.
- **Choice:** A. `ci.yml` gains `layout: single | matrix`, default `single`.
  - In `single`, one job named `checks` (`ci / checks`) runs the resolved slots in order, each in its own log group, with a pass/fail line per slot in the job summary.
  - It runs every slot even after one fails, so one run reports every failure, and the job fails if any slot failed.
  - `gate` is unchanged, so `ci / gate` stays the only required check.
  - `matrix` keeps one check per slot (`ci / lint` and so on).
- **Rationale:** About 2 billed minutes per run instead of up to 8, with no new Studio dependency. Rulesets only require `ci / gate`.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** med

## D35: CI is one job; caller workflows are `Checks` and `Release notes`
- **Refines:** D34.
- **Problem:** GitHub shows a check from a reusable workflow as `<workflow> / <caller job> / <job>`. With the workflow named `CI` and the caller job `ci`, every check read `CI / ci / ...` (Jace: "two cis, not good"). The single layout also showed a separate `ci / plan` check (an extra billed minute) and a skipped `ci / matrix.slot` placeholder.
- **Options:** A: `ci.yml` as one job named `gate`, matrix in its own file, caller workflows renamed; B: rename the caller job (required checks change everywhere); C: keep it.
- **Choice:** A.
  - `ci.yml` is one job, `gate`: it resolves, sets up, runs the slots in order and gates, so a normal PR shows only `Checks / ci / gate`.
  - The per-slot layout moves to `ci-matrix.yml` (opt-in), and the `layout` input is dropped.
  - Caller workflows are named `Checks` (was `CI`) and `Release notes` (was `Changeset`, shown as `Release notes / changeset / check`).
  - The required checks stay `ci / gate` and `changeset / check`.
- **Rationale:** One check, one billed minute, no repeated names. Rulesets, the manifest and the release button are untouched.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** low

