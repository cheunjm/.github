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
- **Choice:** B. `ci-node` becomes a deprecated thin wrapper and is removed in `v2`.
- **Rationale:** Identical check names in every repo (`ci / lint`, …, `ci / gate`), so rulesets and tooling treat all repos alike. Mixed repos combine commands within a slot.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** high

## D6: Promotion model for app repos
- **Problem:** arami and starlog deploy develop on push to `main` and production on `v*` tags; ui deploys production on `release: published`.
- **Options:** A: push to `main` → develop, `v*` tag (created by arami-bot when the Version Packages PR merges) → production; B: production on `release: published`; C: GitHub Environment approval (not available for private repos on Free).
- **Choice:** A. ui migrates.
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
- **Choice:** B. Deregister the orphaned `mac-studio-engineering-log-openwiki` runner.
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
