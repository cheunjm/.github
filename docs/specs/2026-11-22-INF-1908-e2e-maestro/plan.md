# Shared Maestro e2e workflow

## Background and constraints
arami, stock-tracker and ui each run Maestro UI e2e with their own setup: different Maestro versions (2.12.1, 2.5.1, unpinned), different device and browser handling, different artifacts. arami's Android suite also rarely finishes, because its `cancel-in-progress` concurrency kills the 28-minute run on every push to the Version PR.

Constraints:
- iOS needs macOS and Xcode. arami's suite also needs Docker for a local Supabase stack. GitHub-hosted macOS has no Docker and costs 10x minutes, so iOS runs on the Mac Studio (D3).
- The Studio runner's `PATH` is `~/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:...`. Docker lives in `/usr/local/bin`, which is missing, and Maestro needs Java 17 (`/usr/libexec/java_home -v 17`).
- Callers are private repos on the free plan: hosted Linux minutes are limited, so e2e stays opt-in and release-time where the caller chooses.

## Scope
**In scope**
- `.github/workflows/e2e-maestro.yml` (`workflow_call`) with:
  - `platforms` (comma list of `android`, `ios`, `web`) fanning out to one job per platform.
  - Caller hooks: `setup-command` (e.g. start local Supabase), `build-command`, `test-command`, `serve-command` and `web-url` for web, `flows-path`, `artifact-path`.
  - Device boot owned by the workflow (D7): Android emulator (KVM, cached AVD, `reactivecircus/android-emulator-runner`), iOS simulator (create, boot, delete), headless Chrome for web. The device id reaches `test-command` as `E2E_DEVICE`, the platform as `E2E_PLATFORM`.
  - Default `test-command` when empty: `maestro test <flows-path>` with JUnit output to `<artifact-path>/report.xml`.
  - Pinned Maestro (`maestro-version`, default 2.12.1, D8), Node (`node-version`, default 22), Java 17.
  - Per-platform runners: `android-runner` and `web-runner` default `ubuntu-latest`, `ios-runner` default `mac-studio`.
  - Concurrency per workflow and ref with `cancel-in-progress: false` (D5).
  - Fork-PR guard on the iOS job (D9).
  - Failure artifacts from `artifact-path`.
- README table entry for the new workflow in `CLAUDE.md`.
- arami: replace `e2e.yml` with a caller for `android,ios`, keeping its release-PR-only trigger.

**Out of scope** (will not do)
- stock-tracker and ui web callers (separate PRs, see Later).
- Backend, subgraph and router e2e (app-specific npm scripts).
- A self-test harness for .github's reusable workflows (D1, Later).
- Changing what arami's flows test, or its local `npm run e2e:*` scripts.
- Registering runners: arami's `mac-studio` runner already exists.

## Stage goals
1. .github workflow: `e2e-maestro.yml` exists, passes actionlint, and is documented. Done when: the .github PR is green (`Validate workflow YAML` / actionlint) and merged.
2. arami Android: arami's `e2e.yml` calls the shared workflow for `android`. Done when: a `workflow_dispatch` run of arami's E2E passes the Android job end to end (all four flows).
3. arami iOS: the same caller adds `ios` on the Studio. Done when: the iOS job passes on the Studio in the same dispatch run, and the simulator it created is deleted afterwards.
4. Concurrency: a push during a running e2e queues instead of cancelling. Done when: observed on arami's Version PR, or on a dispatch run started while another runs.

## Verification
- Stage 1: actionlint (the .github `ci.yml` check) plus `act`-free review. A reusable workflow cannot be run until a caller calls it, so stage 1 is proven by stage 2.
- Stage 2-3: `gh workflow run E2E --repo cheunjm/arami --ref <branch>` on the arami PR branch, then `gh run watch`. The arami caller points at the .github branch (`@feat/INF-1908-e2e-maestro`) until stage 1 merges, then is switched to `@main` before arami merges.
- Stage 4: start a second dispatch while the first runs; the first must complete, not be cancelled.

## Assumptions
- Docker Desktop is running on the Mac Studio when the iOS job starts. If it is not, `supabase start` fails and the job fails with that error (no auto-start).
- The arami `mac-studio` runner is online and has the `mac-studio` label (checked: `mac-studio-arami`, labels `self-hosted,macOS,ARM64,mac-studio`).
- arami's iOS build works on Xcode 26.4 with one of the Studio's runtimes. arami's docs warn that Xcode 27 builds fail on the iOS 27 simulator; an `ios-runtime` input lets arami pin `iOS-17-0` if 26.4 fails.
- ~~No other local Supabase stack on the Studio holds the default ports while the iOS job runs.~~ False: stock-tracker's stack restarts with Docker Desktop. Callers move their CI stack to other ports (D11).
- The Studio's Docker config (keychain credential helper, Scout hooks) does not work in a runner service; the iOS job uses an empty `DOCKER_CONFIG` (D10).

## Terms
- **Caller**: an app repo workflow that `uses:` the shared workflow.
- **Device**: the Android emulator serial, iOS simulator UDID, or web URL the suite runs against.

## Later
- stock-tracker `e2e-frontend` and ui `e2e / web` move to `platforms: web`.
- Self-test harness for .github's own reusable workflows (D1 option B).
- Bump arami `e2e.yml`'s leftover `actions/*@v4` steps (removed by the migration anyway).
