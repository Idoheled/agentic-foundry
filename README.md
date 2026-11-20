# Agentic Foundry

**Build the workspace. Coordinate the agents. Deliver the work.**

[![Source checks](https://github.com/Idoheled/agentic-foundry/actions/workflows/ci.yml/badge.svg)](https://github.com/Idoheled/agentic-foundry/actions/workflows/ci.yml)

Agentic Foundry provisions and upgrades Linux workspaces for multiple AI agents and projects. It brings together project orchestration, native coding tools, offline dependencies, shared skills, and an explicit installation and acceptance workflow.

Use it to improve an existing Claude Code / OMP workspace or provision a fresh machine. Suitable installed tools and approved private repositories take priority. Existing model routes, credentials, brain configuration, hooks, skills, and sessions stay under the site's control.

[Quick start](docs/QUICKSTART.md) · [Documentation](docs/index.md) · [Offline payloads](docs/PAYLOADS.md) · [Architecture](docs/ARCHITECTURE.md) · [Operations](docs/OPERATIONS.md) · [Releasing](docs/RELEASING.md) · [Changelog](CHANGELOG.md)

## What you get

| Area | Included capabilities |
| --- | --- |
| Project and task coordination | Paperclip with PostgreSQL; project registration, assignments, runs, and explicit worker admission. |
| Coding clients | OMP, Claude Code, Codex, and OpenCode, with optional Herdr for interactive terminal sessions. |
| Parallel development | Isolated task workspaces and Worktrunk for interactive Git worktrees. |
| Code understanding | Zoekt, Universal Ctags, and language services for Python, TypeScript, Bash, YAML, JSON, HTML, and CSS. |
| Efficient execution | RTK OSS for selected command output; native language runtimes, build tools, and reusable dependency closures. |
| Verification | Inspect AI, a native-agent benchmark, Playwright with Chromium, and Trivy with an offline database. |
| Deployment | Private-first artifact selection, native package ownership, complete runtime installation, checksums, resumable setup, and configuration preservation. |

The [software inventory](docs/SOFTWARE_INVENTORY.md), [r5 delivery profile](docs/R5_DELIVERY_WORKSPACE.md), and pinned catalogs identify the selected versions. Model weights and arbitrary dependencies for future projects are separate site inputs.

## Choose your deployment path

| Your machine | Start here |
| --- | --- |
| Existing working Claude Code and OMP | [Preserved two-phase upgrade](docs/QUICKSTART.md#upgrade-an-existing-workspace). Claude upgrades OMP, writes the checked handoff, and stops for your manual switch to OMP. |
| Fresh machine with a prepared private site configuration | [Single-command setup](docs/QUICKSTART.md#provision-a-fresh-machine). The controller installs and verifies the selected stack. |
| Contributor reviewing or changing the installer | [Source-only development](CONTRIBUTING.md). The controller tests run without downloading the large payload. |

### 1. Obtain the source and offline payload

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone --branch v0.1.2 --single-branch \
  https://github.com/Idoheled/agentic-foundry.git
cd agentic-foundry
git lfs install --local
git lfs pull
git lfs checkout
```

Git LFS retrieves the pinned content-addressed payload chunks. `deploy.sh` hydrates those local bytes before setup; it does not download from public sources. Follow [Offline payloads](docs/PAYLOADS.md) for verification, transfer, and release assembly. A source-only checkout or GitHub-generated source ZIP does not establish that the offline payload is present. Fetch and verify the complete release before moving into a disconnected environment.

### 2. Inspect the machine

From the repository root:

```bash
./deploy.sh doctor
```

Discovery reports the platform, commands, and candidate profile locations without launching newly selected coding clients. Follow the [quick start](docs/QUICKSTART.md) for prerequisites and private configuration.

### 3. Set up or upgrade

**Fresh machine**, after completing a private site file:

```bash
./deploy.sh --config /private/site.json \
  --state "$HOME/.local/state/agentic-foundry/setup-v0.1.2"
```

**Existing workspace**, starting in the current working Claude environment:

```bash
./deploy.sh agent --config /private/site.json \
  --state "$HOME/.local/state/agentic-foundry/setup-v0.1.2"
```

The existing-machine flow deliberately stops after OMP qualification. Start the OMP continuation using the exact command in the generated handoff. OMP then completes the rest of the stack without replacing the runtime executing that continuation.

## Deployment principles

- **Private supply first.** Reuse a qualified existing tool, select an appropriate private artifact, then use the bundled fallback only with factual unavailability or insufficiency evidence. Runtime setup has no public-registry fallback.
- **Native ownership.** Package-owned files are upgraded by the native package manager. Independent tools retain complete versioned runtimes and inspected command entry points.
- **Preserved configuration.** Existing hooks, skills, brain files, model routes, authentication sources, internal CA trust, and launch profiles are inventoried and checked throughout the upgrade.
- **One task authority.** Paperclip owns managed tasks and top-level runs. Git owns code changes. A coding harness owns its model/tool session. Worktrunk does not compete with Paperclip for ownership of the same worktree.
- **Evidence before activation.** Installed files, functional tool checks, real internal-model tasks, and production worker admission are distinct states.

No new telemetry, monitoring, backup platform, or replacement memory service is introduced. Transaction records and retained configuration originals support the upgrade itself.

## Supported targets and qualification

| Target | v0.1.2 coverage |
| --- | --- |
| Debian 13, x86-64, glibc | Included native fallback and the supplied evaluation/browser profile. |
| Other Debian/Ubuntu x86-64 systems | Explicit approved internal APT plans and compatible tool profiles; Debian 13 packages are not used as a foreign-distro fallback. |
| Other Linux distributions | Adequate existing prerequisites or a separately qualified private native-package procedure and matching tool profiles. |
| ARM64 or musl | Separate payload builds and qualification required. |

Host detection is dynamic; binary compatibility is established per profile. The included browser passed executable, dependency, and relocation checks, but real UI interaction was blocked by the builder's socket policy. Real browser interaction, Docker worker execution, internal model protocols, and target-machine upgrades remain receiving-host acceptance gates. See [validation evidence](provenance/r5/VALIDATION.json) and [coverage](docs/OFFLINE_COVERAGE.md).

`requested_setup_steps_completed` means the selected setup stages and their checks passed. It does not automatically enable production dispatch or certify every project workload.

## Repository map

| Path | Purpose |
| --- | --- |
| `deploy.sh` | Git-checkout entry point: hydrate local LFS bytes, then run the selected setup operation. |
| `setup.sh` | Setup controller entry point for a hydrated tree: `doctor`, `plan`, `apply`, and `agent`. |
| `upgrade.sh`, `HANDOFF.md` | Claude-to-OMP phase boundary and receiving-agent instructions. |
| `scripts/` | Setup, source selection, installation, preservation, payload, and verification controllers. |
| `config/` | Public examples, catalogs, and task playbooks. |
| `docs/` | Deployment, operation, integration, and qualification guides. |
| `tests/`, `ci/` | Source-only behavioral tests and validation entry point. |
| `build-tools/` | Release assembly and integrity tooling. |
| `offline/` | LFS-backed content-addressed payload and its reconstruction manifest. |
| `payload.lock.json`, `provenance/` | Pinned artifact identities and build evidence. |

Keep live site configuration, credentials, private supply indexes, runtime state, and project data outside the repository.

## Contributing and licensing

Run the source checks with:

```bash
./ci/check.sh
```

Read [CONTRIBUTING.md](CONTRIBUTING.md) before changing installation behavior, artifact identities, or a release profile. Follow [AGENTS.md](AGENTS.md) when working through an AI agent, [RELEASING.md](docs/RELEASING.md) for tags and publication, and [SECURITY.md](SECURITY.md) for security reports.

The custom integration code uses the [MIT license](LICENSE). Bundled upstream tools, source, documentation, dependencies, and client distributions retain their own licenses. This project's license does not relicense Claude Code or other bundled products.
