# .github

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
