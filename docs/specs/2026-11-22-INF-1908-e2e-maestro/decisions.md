# Decisions: Shared Maestro e2e workflow

Numbers are never reused, renumbered or deleted. Reverse a decision by adding a new entry that supersedes it.

## D1: What "e2e on .github" means
- **Problem:** "e2e on .github" could mean a reusable e2e workflow that app repos call, or a harness that tests .github's own reusable workflows before merge.
- **Options:** A: shared e2e workflow for app repos; B: self-test harness for the reusable workflows; C: both, shared workflow first.
- **Choice:** A.
- **Rationale:** arami, stock-tracker and ui each carry their own Maestro setup that has drifted (Maestro 2.12.1, 2.5.1 and unpinned). .github exists to de-duplicate exactly this.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** high
- **Labels:** revisit (the self-test harness, B, is still worth doing; see plan Later)

## D2: Platforms covered
- **Problem:** Which e2e jobs the shared workflow covers.
- **Options:** A: Maestro Android + web; B: Android only; C: generic e2e runner with no Maestro specifics; D: Maestro Android, iOS and web.
- **Choice:** D (the human's own answer).
- **Rationale:** All three repos already use Maestro for UI e2e. arami's scripts already support iOS locally. Backend/subgraph e2e (stock-tracker) are app-specific npm scripts and stay repo-local.
- **Proposed by:** human
- **Chosen by:** human
- **Impact:** high

## D3: Where the iOS job runs
- **Problem:** iOS needs macOS with Xcode; arami's suite also needs Docker for its local Supabase stack. GitHub-hosted macOS runners have no Docker and bill at 10x on private repos.
- **Options:** A: Mac Studio self-hosted (`mac-studio` label); B: GitHub-hosted `macos-latest` with a hosted Supabase test project; C: no iOS in CI.
- **Choice:** A.
- **Rationale:** Free, and the Studio already has Xcode 26.4, iOS 17.0 and 26.4 simulators, Docker Desktop, the Supabase CLI and Java 17, so the same local-Supabase suite runs unchanged. e2e is release-time only for arami, so a single runner per repo is not a bottleneck.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** high

## D4: Workflow shape and caller contract
- **Problem:** One workflow or several, and how each app supplies its own setup and build.
- **Options:** A: one workflow, `platforms` input fanning out per platform, app steps as command inputs; B: one workflow calling fixed `scripts/e2e/*.sh` in every caller; C: three separate workflows.
- **Choice:** A.
- **Rationale:** Keeps the Maestro pin, device boot, artifacts and concurrency in one place without forcing a file layout on stock-tracker and ui. arami's existing scripts plug in as commands.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** high

## D5: Concurrency
- **Problem:** arami's e2e cancels in-progress runs on every push to the Version PR, which is rewritten on every merge to main, so a 28-minute run rarely finishes (7 cancellations since the last success).
- **Options:** A: `cancel-in-progress: false` (running finishes, only the newest pending push waits); B: caller-chosen input; C: keep cancelling.
- **Choice:** A.
- **Rationale:** A long suite always produces a result, at most one push behind. Callers still choose their triggers.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** med

## D6: Rollout order
- **Problem:** Which callers move first.
- **Options:** A: .github workflow, then arami (android + ios), then web repos separately; B: all three repos at once; C: .github only.
- **Choice:** A.
- **Rationale:** arami has a real, passing Android suite and iOS scripts, so it proves the workflow end to end before stock-tracker and ui depend on it.
- **Proposed by:** ai
- **Chosen by:** human
- **Impact:** med

## D7: Who boots the device
- **Problem:** arami's `test.sh` installs the build and runs Maestro on a device it is handed; something must create and boot that device.
- **Options:** A: the shared workflow boots the emulator / simulator / browser and passes its id to the caller's `test-command` as `E2E_DEVICE`; B: the caller boots its own device.
- **Choice:** A.
- **Rationale:** Device boot (KVM, AVD cache, simulator create and delete, headless Chrome) is the part every caller duplicates and gets wrong. Callers keep install and Maestro flags via `test-command`, with a plain `maestro test` default.
- **Proposed by:** ai
- **Chosen by:** ai
- **Impact:** med

## D8: Maestro version
- **Problem:** The three repos pin different Maestro versions.
- **Options:** A: pin 2.12.1 (arami's, newest in use) as the default input; B: install latest.
- **Choice:** A, overridable per caller with `maestro-version`.
- **Rationale:** Reproducible runs; stock-tracker pinned 2.5.1 for web-driver stability, so it can keep its pin until its flows are checked on 2.12.1.
- **Proposed by:** ai
- **Chosen by:** ai
- **Impact:** low

## D9: Guarding the self-hosted iOS job
- **Problem:** The iOS job runs PR code on the Mac Studio as the user's account.
- **Options:** A: skip the job for pull requests from forks; B: no guard.
- **Choice:** A.
- **Rationale:** Same rule as `ci-autofix.yml`: only same-repo branches reach self-hosted runners. All callers are private repos.
- **Proposed by:** ai
- **Chosen by:** ai
- **Impact:** med

## D10: Docker config on the Mac Studio
- **Problem:** The first iOS run hung for 24 minutes in `supabase start`, stuck on four `docker pull`s. The Studio's `~/.docker/config.json` uses `credsStore: desktop` (the macOS keychain helper) and a Docker Scout hook on every pull; in a runner service with no GUI session these cannot complete. The pulled images are public.
- **Options:** A: the iOS job uses an empty `DOCKER_CONFIG` and `DOCKER_HOST` pointing at Docker Desktop's socket; B: edit the user's `~/.docker/config.json`; C: pre-pull images by hand.
- **Choice:** A.
- **Rationale:** Scoped to the job, needs no change to the user's own Docker setup, and keeps working when images change. Verified on the Studio: the same pull completes in seconds with an empty config.
- **Proposed by:** ai
- **Chosen by:** ai
- **Impact:** med

## D11: Local backend ports on a shared runner
- **Problem:** Starting Docker Desktop brought back stock-tracker's local Supabase stack, which holds the default 54321/54322 ports, so arami's stack could not start beside it. The plan had assumed no other stack would be running.
- **Options:** A: callers move their local stack off the default ports in CI (Supabase CLI reads `SUPABASE_<PATH>` overrides); B: the workflow stops other stacks; C: require the Studio to run no other stack.
- **Choice:** A, done in arami's `scripts/e2e/env.sh` (5532x when `CI` is set).
- **Rationale:** Never touches another project's stack, and local runs keep the defaults. The shared workflow cannot know a caller's backend, so the fix sits with the caller.
- **Proposed by:** ai
- **Chosen by:** ai
- **Impact:** low
