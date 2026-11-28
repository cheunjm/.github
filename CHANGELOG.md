# .github

## 1.5.2

### Patch Changes

- [#178](https://github.com/cheunjm/.github/pull/178) [`886d0e6`](https://github.com/cheunjm/.github/commit/886d0e621f3b0b57083788ae3eaab5c4c86ae61a) Thanks [@cheunjm](https://github.com/cheunjm)! - Reuse the Android APK built by this run as the e2e build instead of building e2e-<env> again.

- [#175](https://github.com/cheunjm/.github/pull/175) [`50b53e4`](https://github.com/cheunjm/.github/commit/50b53e49e3911c250d343ae3a3ec1d7ccc08cff0) Thanks [@cheunjm](https://github.com/cheunjm)! - Pass the Maestro test account and installed app id to flows as MAESTRO_E2E_EMAIL, MAESTRO_E2E_PASSWORD and MAESTRO_APP_ID.

## 1.5.1

### Patch Changes

- [#173](https://github.com/cheunjm/.github/pull/173) [`0805eb6`](https://github.com/cheunjm/.github/commit/0805eb6c176e02f0263fdab3c1b70eac32408c55) Thanks [@cheunjm](https://github.com/cheunjm)! - changeset-version.yml drops pending changesets when every one is empty (e.g. the OpenWiki bot's openwiki-docs.md), so the release run publishes instead of stopping at "All changesets are empty".

## 1.5.0

### Minor Changes

- [#167](https://github.com/cheunjm/.github/pull/167) [`1c3dd0b`](https://github.com/cheunjm/.github/commit/1c3dd0b351c65af875cfdf7c04702ca8dbcfd869) Thanks [@cheunjm](https://github.com/cheunjm)! - cd.yml runs the D46 master release gate in plan and posts one Slack release summary from a notify job.

- [#167](https://github.com/cheunjm/.github/pull/167) [`1c3dd0b`](https://github.com/cheunjm/.github/commit/1c3dd0b351c65af875cfdf7c04702ca8dbcfd869) Thanks [@cheunjm](https://github.com/cheunjm)! - cd.yml gains working_directory, and this repo self-tests it with dry runs against an Expo fixture; the release and production button callers ship as templates in fixtures/callers.

- [#167](https://github.com/cheunjm/.github/pull/167) [`1c3dd0b`](https://github.com/cheunjm/.github/commit/1c3dd0b351c65af875cfdf7c04702ca8dbcfd869) Thanks [@cheunjm](https://github.com/cheunjm)! - Add the shared `cd.yml` deploy workflow (backend, app, web, Storybook and e2e checkboxes for the develop and master buttons) with its `scripts/cd_plan.py` and `scripts/cd_app.py` helpers.

- [#166](https://github.com/cheunjm/.github/pull/166) [`b09f437`](https://github.com/cheunjm/.github/commit/b09f437751306606e8ee33e5768d2bd2e4c6ed75) Thanks [@cheunjm](https://github.com/cheunjm)! - The release button no longer cuts rc tags or GitHub prereleases, and the production gate checks the newest commit deployed to develop instead of the latest rc.

### Patch Changes

- [#171](https://github.com/cheunjm/.github/pull/171) [`8c0a15d`](https://github.com/cheunjm/.github/commit/8c0a15d2d89fa0fa9b3192bad04dd1f3a433bc6b) Thanks [@cheunjm](https://github.com/cheunjm)! - The release gate now proves develop deploys from the release-button run jobs (develop-status, e2e-status) instead of commit statuses, so a forged status cannot unlock production.

## 1.4.0

### Minor Changes

- [#161](https://github.com/cheunjm/.github/pull/161) [`6586952`](https://github.com/cheunjm/.github/commit/65869528b170695e04b413701a5df533bf582f2d) Thanks [@cheunjm](https://github.com/cheunjm)! - Add migration contract guard (`block_destructive`, `migration_paths`) and the `app-json` version sync for the Version PR.

### Patch Changes

- [#163](https://github.com/cheunjm/.github/pull/163) [`4650516`](https://github.com/cheunjm/.github/commit/46505165e508f2980c79c9d4508853edc4348d54) Thanks [@cheunjm](https://github.com/cheunjm)! - `openwiki-update.yml`: when the OpenWiki planner exits without a plan (a model flake), the run retries once from a clean `openwiki/` instead of failing.

## 1.3.0

### Minor Changes

- [#160](https://github.com/cheunjm/.github/pull/160) [`9efb021`](https://github.com/cheunjm/.github/commit/9efb02108853cb48b20a5d7ccf3bbc0f0cd39ec8) Thanks [@cheunjm](https://github.com/cheunjm)! - `e2e-maestro.yml` takes a Studio slot on macOS and gains `app-artifact` (install a same-run build), `include-tags`, `environment` and the `E2E_TEST_ACCOUNTS` secret.

- [#158](https://github.com/cheunjm/.github/pull/158) [`88ab46a`](https://github.com/cheunjm/.github/commit/88ab46a583b12d5a41a2de0c34794a8222053e46) Thanks [@cheunjm](https://github.com/cheunjm)! - Add the `studio-lock` and `release-gate` composite actions for the CD stage.

### Patch Changes

- [#162](https://github.com/cheunjm/.github/pull/162) [`ba76471`](https://github.com/cheunjm/.github/commit/ba7647108c57ca7953fb5ef42e4d0de084d61187) Thanks [@cheunjm](https://github.com/cheunjm)! - `openwiki-update.yml`: the publish job bases the docs PR on the latest default branch instead of the triggering commit, so a queued run no longer opens a PR that conflicts with the docs the previous run merged.

## 1.2.1

### Patch Changes

- [#155](https://github.com/cheunjm/.github/pull/155) [`b445710`](https://github.com/cheunjm/.github/commit/b445710e5efd3f33fa496f7de937a9a1fb18015f) Thanks [@cheunjm](https://github.com/cheunjm)! - `openwiki-update.yml`: a failed generation no longer pushes its partial output over the open docs PR, and the merge waits for GitHub to compute mergeability before trying.

## 1.2.0

### Minor Changes

- [#151](https://github.com/cheunjm/.github/pull/151) [`a29d417`](https://github.com/cheunjm/.github/commit/a29d41742df0fcfd507bb4168636ea570b76b451) Thanks [@cheunjm](https://github.com/cheunjm)! - e2e-maestro: run Android on the Mac Studio (macOS arm64 emulator with a saved quick-boot snapshot) and default `android-runner` to `mac-studio-android` and `ios-runner` to `mac-studio-ios`.

## 1.1.2

### Patch Changes

- [#148](https://github.com/cheunjm/.github/pull/148) [`9d3726b`](https://github.com/cheunjm/.github/commit/9d3726bd819649a64d7dd3a0f3aef46613aaeff8) Thanks [@cheunjm](https://github.com/cheunjm)! - `openwiki-update.yml`: init PRs also carry the empty changeset, so `changeset / check` passes on them.

## 1.1.1

### Patch Changes

- [#146](https://github.com/cheunjm/.github/pull/146) [`4f7fe4e`](https://github.com/cheunjm/.github/commit/4f7fe4e8922a20987bc0cb92196693f8dbaab7a1) Thanks [@cheunjm](https://github.com/cheunjm)! - `openwiki-update.yml`: a repo whose `CLAUDE.md` is a symlink to `AGENTS.md` no longer fails with duplicated OpenWiki markers; only the link target is updated.

## 1.1.0

### Minor Changes

- [#143](https://github.com/cheunjm/.github/pull/143) [`142f6d9`](https://github.com/cheunjm/.github/commit/142f6d91d5b1440b38d8d8b457acc480e36e2b90) Thanks [@cheunjm](https://github.com/cheunjm)! - feat(workflows): [INF-1983] ci.yml is one job (`ci / gate` is the only check); the per-slot layout moves to ci-matrix.yml; caller workflows are named Checks and Release notes

- [#142](https://github.com/cheunjm/.github/pull/142) [`57a2806`](https://github.com/cheunjm/.github/commit/57a2806fc41c9c2d08f725a78f70c0aba920d947) Thanks [@cheunjm](https://github.com/cheunjm)! - feat(workflows): [INF-1983] ci.yml runs its slots in one job by default (`layout: single`, about 2 billed minutes per run; `matrix` keeps a check per slot) and ignores `openwiki/**`; openwiki-update opens wiki PRs with the arami-bot App and an empty changeset so they pass rulesets

### Patch Changes

- [#136](https://github.com/cheunjm/.github/pull/136) [`0447dfc`](https://github.com/cheunjm/.github/commit/0447dfc4769d0bf3484f057a5809b52a4739706c) Thanks [@cheunjm](https://github.com/cheunjm)! - fix(workflows): [INF-1983] major-tag.yml looks up the major tag exactly (git/ref) and resolves the release commit, so the first v1 is created; add a workflow_dispatch to point a major tag at an existing release

- [#138](https://github.com/cheunjm/.github/pull/138) [`4880ae6`](https://github.com/cheunjm/.github/commit/4880ae6f49276d6eae818d84a59a29a6ad0994f8) Thanks [@cheunjm](https://github.com/cheunjm)! - fix(workflows): [INF-1983] push major and prerelease tags with git instead of the refs API, which answers 403 for the App on commits that carry workflow files

## 1.0.0

### Major Changes

- [#115](https://github.com/cheunjm/.github/pull/115) [`1905423`](https://github.com/cheunjm/.github/commit/1905423e75b28432190ecb7511a751fafe8a2409) Thanks [@cheunjm](https://github.com/cheunjm)! - chore(ci): [INF-1924] remove the reusable agent-review.yml (Review / openclaw); callers must drop their agent-review job

- [#122](https://github.com/cheunjm/.github/pull/122) [`f4d59ed`](https://github.com/cheunjm/.github/commit/f4d59ed18db0fd09ad53a77b951376b626b0a9dc) Thanks [@cheunjm](https://github.com/cheunjm)! - chore(ci): [INF-1983] remove the reusable ci-autofix.yml; callers must drop their ci-autofix workflow

### Minor Changes

- [#89](https://github.com/cheunjm/.github/pull/89) [`3de9ea3`](https://github.com/cheunjm/.github/commit/3de9ea3e6a77e44d58b8b077f60787629a5f1338) Thanks [@cheunjm](https://github.com/cheunjm)! - feat(ci): add reusable OpenWiki update workflow and caller template

- [#90](https://github.com/cheunjm/.github/pull/90) [`dbb7cb6`](https://github.com/cheunjm/.github/commit/dbb7cb6314f8e85f068d60a83e0d83c3d649fe1d) Thanks [@cheunjm](https://github.com/cheunjm)! - feat(ci): [INF-1775] add reusable changeset-check, changeset-version and changeset-prerelease workflows

- [#92](https://github.com/cheunjm/.github/pull/92) [`3f874fd`](https://github.com/cheunjm/.github/commit/3f874fd684ff9fc0ef975f9597337e2de7b718b1) Thanks [@cheunjm](https://github.com/cheunjm)! - feat(ci): [INF-1782] openclaw is the only agent engine in agent-review and ci-autofix; runner now defaults to mac-studio and the PR-body markers are renamed to agent-review-summary

- [#113](https://github.com/cheunjm/.github/pull/113) [`aa5f39b`](https://github.com/cheunjm/.github/commit/aa5f39b535fdce8c3d9128d24a68eae487726d21) Thanks [@cheunjm](https://github.com/cheunjm)! - Add the reusable `e2e-maestro.yml` workflow: Maestro e2e on Android, iOS (Mac Studio) and web, with the device booted by the workflow and the app's setup, build and test passed in as commands.

- [#124](https://github.com/cheunjm/.github/pull/124) [`cdc1a5e`](https://github.com/cheunjm/.github/commit/cdc1a5e6b95d4993e3bde7b7aa4fd9a0022bb692) Thanks [@cheunjm](https://github.com/cheunjm)! - feat(ci): [INF-1982] add an opt-in trusted-publishing input to changeset-version for npm OIDC publishing without a token

- [#135](https://github.com/cheunjm/.github/pull/135) [`e018f70`](https://github.com/cheunjm/.github/commit/e018f7072dbd06407a8538a609607232ff6f6857) Thanks [@cheunjm](https://github.com/cheunjm)! - feat(workflows): [INF-1983] openwiki-update defaults to the mac-studio-openwiki runner label and the Studio LiteLLM (:4001, gpt-6.1-sol, Responses API), so callers pass nothing

- [#130](https://github.com/cheunjm/.github/pull/130) [`8052264`](https://github.com/cheunjm/.github/commit/8052264ddbee0981b5beb4e01d17729157995ab8) Thanks [@cheunjm](https://github.com/cheunjm)! - feat(workflows): [INF-1983] add release-candidate.yml, the button that cuts vX.Y.Z-next.N or vX.Y.Z-rc.N, deploys develop through the tag and, in package repos, publishes the prerelease under the matching npm dist-tag

- [#129](https://github.com/cheunjm/.github/pull/129) [`fb56c0d`](https://github.com/cheunjm/.github/commit/fb56c0d1c6443823b6b957198f8aecf625744d2b) Thanks [@cheunjm](https://github.com/cheunjm)! - feat(workflows): [INF-1983] add a `tag` input to changeset-version.yml that creates vX.Y.Z tags when the Version PR merges, and move the floating v<MAJOR> tag on each release

- [#133](https://github.com/cheunjm/.github/pull/133) [`325d36b`](https://github.com/cheunjm/.github/commit/325d36bf64a81a8a746cd11a91b36fe156c32166) Thanks [@cheunjm](https://github.com/cheunjm)! - feat(scripts): [INF-1983] add scripts/apply-rulesets.py, which applies the default-branch ruleset (ci / gate, changeset / check, extras; admin bypass) from the manifest

- [#132](https://github.com/cheunjm/.github/pull/132) [`447383b`](https://github.com/cheunjm/.github/commit/447383ba0d63bc12c85eae775f61669230384dad) Thanks [@cheunjm](https://github.com/cheunjm)! - feat(scripts): [INF-1983] add secrets.manifest.toml and scripts/sync-secrets.py, which push pipeline secrets from 1Password to every repo over stdin

- [#126](https://github.com/cheunjm/.github/pull/126) [`4c8c463`](https://github.com/cheunjm/.github/commit/4c8c463a6ffbd543a2e2bffebe05f3cb0cabb648) Thanks [@cheunjm](https://github.com/cheunjm)! - feat(workflows): [INF-1983] add the shared stack-agnostic ci.yml (presets node, python, shell; one gate) and run it on fixtures in this repo's own CI (self.yml)

### Patch Changes

- [#94](https://github.com/cheunjm/.github/pull/94) [`de237b1`](https://github.com/cheunjm/.github/commit/de237b1618450171d2a06f67c8a7ac075c01cd38) Thanks [@cheunjm](https://github.com/cheunjm)! - feat(ci): [INF-1775] run the changeset workflows on the calling repo's CI_RUNNER (Mac Studio) when set

- [#91](https://github.com/cheunjm/.github/pull/91) [`91f6132`](https://github.com/cheunjm/.github/commit/91f613222c0b5d8a8a3822ecfdb5de17dbcfce20) Thanks [@cheunjm](https://github.com/cheunjm)! - fix(ci): [INF-1775] keep the ephemeral changesets install out of the Version Packages commit

- [#93](https://github.com/cheunjm/.github/pull/93) [`47a9bc2`](https://github.com/cheunjm/.github/commit/47a9bc2bf351e08aae664ff1f8d28f1f163a7742) Thanks [@cheunjm](https://github.com/cheunjm)! - docs(ci): [INF-1793] point the changeset-check error message at the cheunjm/.github docs instead of a file name

- [#95](https://github.com/cheunjm/.github/pull/95) [`5739822`](https://github.com/cheunjm/.github/commit/5739822935ccf2d37466b48cd9fc17b2d42f4c96) Thanks [@cheunjm](https://github.com/cheunjm)! - feat(ci): [INF-1795] add install-tooling input to changeset-version for repos that already install changesets

- [#96](https://github.com/cheunjm/.github/pull/96) [`fbcdc00`](https://github.com/cheunjm/.github/commit/fbcdc00c7fd5ad097ddea5fcb5e621400c723e35) Thanks [@cheunjm](https://github.com/cheunjm)! - chore(ci): [INF-1807] add changesets with the shared check and version workflows

- [#98](https://github.com/cheunjm/.github/pull/98) [`d9ab190`](https://github.com/cheunjm/.github/commit/d9ab190bea4753bae0d56a0494881fda1f5b6baf) Thanks [@cheunjm](https://github.com/cheunjm)! - chore(ci): [INF-1815] pin changesets/action to a commit SHA in changeset-version

- [#127](https://github.com/cheunjm/.github/pull/127) [`bac2a0f`](https://github.com/cheunjm/.github/commit/bac2a0f43f08e9ec7221c1158b56f59959f9a92d) Thanks [@cheunjm](https://github.com/cheunjm)! - chore(workflows): [INF-1983] mark ci-node.yml deprecated in favour of ci.yml with preset: node (removed in v2)

- [#121](https://github.com/cheunjm/.github/pull/121) [`954b057`](https://github.com/cheunjm/.github/commit/954b0579f05bde237d82747486009819b4830614) Thanks [@cheunjm](https://github.com/cheunjm)! - The e2e-maestro install steps no longer append a PATH line to a self-hosted runner's ~/.zshrc and ~/.bash_profile on every run.

- [#13](https://github.com/cheunjm/.github/pull/13) [`f32c5c1`](https://github.com/cheunjm/.github/commit/f32c5c159910bab244c392d05eb9d4273781be36) Thanks [@cheunjm](https://github.com/cheunjm)! - chore: migrate org references from cheunjm to aramiworks

- [#16](https://github.com/cheunjm/.github/pull/16) [`630ac5f`](https://github.com/cheunjm/.github/commit/630ac5f18ec8ff91ec590043df80456851adab6b) Thanks [@cheunjm](https://github.com/cheunjm)! - chore: rename org from Arami-Works to aramiworks

- [#18](https://github.com/cheunjm/.github/pull/18) [`205ac47`](https://github.com/cheunjm/.github/commit/205ac478e0732603f7963737aacb0e1cf2cf441e) Thanks [@cheunjm](https://github.com/cheunjm)! - chore(ci): remove claude-code-review workflow (replaced by Greptile)
