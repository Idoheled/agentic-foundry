# Changelog

Notable changes to Agentic Foundry are recorded here. Repository releases use semantic version tags. The underlying offline payload retains its own revision and immutable artifact identities.

## [0.1.2] - 2026-11-20

Corrects local release-workflow materialization while retaining the same pinned `2026-11-20-r5` runtime payload and deployment behavior.

### Fixed

- Explicitly run `git lfs checkout` after fetching local-mode release objects and selecting the verified commit, so cached objects are materialized into the working tree before payload verification.
- Retain full object and reconstructed-file hash verification after materialization; fetching or checking out objects alone does not pass the integrity gate.
- Retain the raw committed-blob source archive correction from `0.1.1` and update recommended versioned checkout, deployment-state, tag, and standalone-export examples to `v0.1.2`.

### Publication history

The `v0.1.1` local-mode publication attempt fetched all LFS data into the cache, but a second checkout of the same commit left pointer files in the working tree. Payload verification blocked before release creation. The original `v0.1.0` and `v0.1.1` tags and their historical notes remain unchanged; the workflow correction uses a new patch version.

The change affects connected release preparation only. Locked runtime bytes, native setup behavior, private supply preference, configuration preservation, and the Claude → OMP phase boundary remain unchanged. It adds no native-host, browser, private-model, or project-task qualification claim.

## [0.1.1] - 2026-11-20

Corrects source-release packaging while retaining the same pinned `2026-11-20-r5` runtime payload and deployment behavior.

### Fixed

- Prevent the source release archive from expanding Git LFS pointers into large runtime objects during archive creation. The source asset retains the committed pointers; complete offline payload retrieval remains the explicit Git LFS or private-mirror step.
- Verify the source archive's content boundary before publication so an accidentally hydrated payload cannot be presented as the source-only asset.
- Update recommended checkout, deployment-state, tag, and standalone-export examples to `v0.1.1`.

### Publication history

The `v0.1.0` publication attempt verified every remote payload file before source-archive creation failed: `git archive` expanded LFS objects and the intended source asset exceeded 2 GiB. That attempt did not complete GitHub release publication. The original `v0.1.0` tag and historical evidence are preserved; the packaging correction uses a new patch version instead of moving the tag.

This correction does not change the locked tool/image/package bytes, supported platforms, or existing-machine Claude → OMP boundary. Remote payload integrity is not additional native-host, browser, private-model, or project-task qualification; those acceptance gates remain explicit.

## [0.1.0] - 2026-11-20

Initial Agentic Foundry repository/tag baseline, based on the `2026-11-20-r5` offline workspace kit. Its later GitHub release publication attempt did not complete; see the `0.1.1` packaging correction above. The original tag and committed release notes remain unchanged.

### Added

- A Git-checkout `deploy.sh` entry point that hydrates local LFS payload bytes before delegating to setup, with read-only discovery/help paths.
- A common `setup.sh` entry point for discovery, planning, scripted installation, and agent-driven setup.
- Private site compilation into explicit source, native-package, host-tool, core, profile, and productivity plans.
- Resumable setup state bound to selected input identities and installation receipts.
- A preserved existing-machine workflow: Claude qualifies OMP in phase 1, stops for the operator's manual handoff, and OMP completes phase 2.
- Native installation and profile integration for OMP, Claude Code, Codex, and OpenCode, with Paperclip/PostgreSQL orchestration and optional Herdr.
- Worktrunk, RTK OSS, Zoekt/Universal Ctags, seven language services, Trivy, Go, Inspect AI/native-agent benchmarking, and Playwright/Chromium capabilities.
- Explicit staging and qualification of portable productivity runtimes for Paperclip workers.
- Content-addressed Git LFS payload chunks, pinned reconstruction and artifact identities, hydration/verification tooling, source snapshots, dependencies, provenance, and release assembly checks.
- Source-only controller tests and deployment, operation, architecture, and receiving-agent documentation.

### Preservation and ownership

- Suitable existing tools and qualified private repositories take priority over the bundled fallback.
- OS package ownership is preserved; independent tools retain complete versioned runtimes and inspected command entry points.
- Existing model routes, authentication, CA trust, brain configuration, hooks, skills, named profiles, and sessions are covered by the preservation workflow.
- Codex hook activation requires review of the supplied code and the exact manifest identity.
- No new monitoring, telemetry, backup, or replacement memory platform is required.

### Qualification

- The r5 controller suite passed 197 tests in both the full kit and a source-only checkout.
- Eight productivity tool groups installed into an isolated prefix, exposing 27 commands and passing 89 verification checks.
- The native fallback contains 426 verified package files; empty-status APT resolution selected and locally acquired 353 packages without installing them on the builder.
- Real worktree, search, language-service, compact-output, offline scan, evaluation, and benchmark checks are recorded in the included provenance.

### Known boundaries

- The supplied complete native fallback and evaluation/browser profile target Debian 13 x86-64/glibc. Other platforms require matching qualified profiles.
- Actual target-machine upgrades, Docker worker execution, private model protocols, and project delivery require receiving-host acceptance.
- Chromium executable/dependency/relocation checks passed; real browser UI interaction was blocked by the builder environment and remains a mandatory target gate.
- Model weights, arbitrary future project dependencies, every upstream build graph/history, full browser/OS-library build sources, and the optional Trivy Java class index are outside the supplied payload scope.
- Bundled upstream products retain their own licenses; the public Claude Code repository is not the proprietary client's full implementation source.

See [r5 validation](provenance/r5/VALIDATION.json), [delivery scope](docs/R5_DELIVERY_WORKSPACE.md), and [offline coverage](docs/OFFLINE_COVERAGE.md) for the evidence and component-specific limits.
