# Changelog

Notable changes to Agentic Foundry are recorded here. Repository releases use semantic version tags. The underlying offline payload retains its own revision and immutable artifact identities.

## [0.1.0] - 2026-11-20

Initial Agentic Foundry repository release, based on the `2026-11-20-r5` offline workspace kit.

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
