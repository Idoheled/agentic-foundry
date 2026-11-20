# Bootstrap and offline lifecycle

For a Git checkout, `deploy.sh` validates and hydrates the local Git LFS payload before forwarding to `setup.sh`; its `doctor` and help paths avoid full hydration. See [Offline payloads](PAYLOADS.md) for retrieval and verification. `setup.sh` is the common entry point for an already hydrated or extracted complete offline kit. It wraps the existing private-first native installers, original configuration-preservation mechanism, two-phase agent workflow, productivity installer, and explicit acceptance results. It does not add a telemetry, monitoring, or backup platform.

## Choose the path for this machine

| Situation | Entry | Result |
| --- | --- | --- |
| New machine with a factual private site file | `./setup.sh --config /private/site.json --state /private/states/setup-r5` | Compile or validate the site, install selected tools/services, install requested productivity tools, and verify the declared scope. |
| Existing Claude/OMP workspace | `./setup.sh agent --config /private/site.json --state /private/states/setup-r5` | Launch the original Claude phase. Claude upgrades and qualifies OMP, writes the exact handoff, and stops. The operator switches to OMP. |
| Existing qualified phase-2 host plan | `./setup.sh apply --config /private/setup.json --state /private/states/setup-r5` | Apply a plan that omits OMP or reuses its qualified runtime, with the original preservation baseline. |
| Productivity additions after the existing phase-2 installer | `./setup.sh apply --only productivity --config /private/setup.json --state /private/states/setup-r5` | Install and verify only the requested productivity additions, with preservation checks. It does not report whole-stack completion. |
| Inspect before choosing | `./setup.sh doctor` | Report platform, command locations and candidate profile roots without invoking the coding clients. |

`--config` without a subcommand means `apply`. Paths are absolute. Run as the ordinary Linux operator who owns the existing agent configuration; the system installers use the host's existing `sudo` capability where required. Never launch the entire workflow as root.

An existing command does not prove that its version, runtime, plugins, effective model route or shell wrapper is suitable. The discovery report lists candidates. Private artifact selection and the preserved launch context determine which candidate is reused or upgraded.

## Target support

The shipped compiled payload is for **Linux x86-64 with glibc**. A source repository can be extended with additional target builds; the presence of source code is not a runnable ARM64, musl, or arbitrary-distro payload.

| `target.profile` | Native prerequisites | Limits |
| --- | --- | --- |
| `debian13-x86_64` | Existing adequate packages, approved internal APT, or the exact bundled Debian 13 fallback set after inspection | OS and major release must match. |
| `apt-x86_64-internal` | Explicit approved internal APT on Debian or Ubuntu | No Debian 13 package fallback on a different distro/release. |
| `linux-x86_64-internal` | Adequate existing prerequisites, or a separately prepared matching private native-package procedure | This kit's APT helper does not provide RPM or other package-manager automation. Disable that helper only after satisfying and documenting the required native capabilities. |

The per-tool catalog checks its own architecture and glibc constraints. Those checks can be stricter than the setup profile's minimum. A dedicated Docker service additionally needs systemd, existing noninteractive sudo access, the documented disk capacity, and compatible kernel/container capabilities. A usable existing local Docker daemon can be reused.

## No Python preinstallation requirement

`setup.sh` uses `scripts/python.sh`. It selects a suitable existing Python 3.9 or later first. An explicit choice can be supplied as:

```bash
export AGENTIC_PYTHON=/absolute/qualified/python3
./setup.sh doctor
```

If none exists, inspect the private operating-system and artifact repositories first. When their Python is unavailable or inadequate, provide the factual finding through `AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON` and rerun. The existing bootstrap verifies and extracts the included x86-64 CPython into an operator cache. It does not overwrite `/usr/bin/python3` or treat this temporary controller choice as the final host installation decision.

`./setup.sh --help` works without Python. On an unsupported architecture the shell entry stops before trying to execute the bundled x86-64 interpreter. A fresh minimal base still needs its normal shell/core utilities to extract and run an offline release.

## First run with a minimal private site

1. Extract the complete offline release and verify its externally supplied digest and included `SHA256SUMS`.
2. Copy `config/site-minimal.example.json` to a private path outside the source repository. Complete the fields with actual local findings.
3. Supply the existing internal model credential environment variable named by `model.apiKeyEnv`. Do not put the secret value into JSON, shell command arguments, Git, a handoff, or a report.
4. Run discovery and planning. If a source, route, tool capability or platform is missing, resolve the explicit blocker first.
5. Apply using the same private site and state. Repeat the same command after a transient failure; successful installer stages are reverified instead of silently accepted.

```bash
./setup.sh doctor
./setup.sh plan --config /private/site.json --state /private/states/setup-r5
./setup.sh apply --config /private/site.json --state /private/states/setup-r5
```

The minimal compiler accepts `schemaKind: "minimal"`; its example and current schema are authoritative. It discovers actual local private supply roots or a configured private index and compiles the detailed r4 plans. It must not claim to have checked an unavailable repository. A missing credential, endpoint, approved source or native prerequisite remains a structured blocker.

The `setup` schema remains available for sites that already maintain detailed plans. `config/setup.example.json` references an existing installation plan and optional Docker/productivity/enrollment stages. Placeholders deliberately fail validation. Neither example is a claim that a repository, credential or endpoint exists.

For trusted native Codex hooks, the minimal site requires `profiles.activateReviewedCodexHooks: true` and the exact `profiles.reviewedAssetManifestSha256`. The receiving agent can inspect the included hook source and manifest, record that hash, and enable the authorized hooks as part of its existing task. The compiler does not fabricate that code-review acknowledgement. Existing hook configuration remains subject to the preservation and additive-installation checks.

### Private-first resolution

The ordering is an inspected adequate existing installation, then a suitable approved private package/image/library/artifact, then the kit fallback when the private candidates are absent or insufficient. The source policy and exact file/image identities remain authoritative. The kit is not a runtime package registry.

No setup command adds a public package mirror, runs an unbounded `npm install`, downloads a `latest` dependency, or manufactures a private-source decision. Existing internal APT access uses the approved repository declarations, existing credential helpers and CA trust. Disconnected operation can use already mirrored local artifacts and the complete fallback payload.

### Native paths and ownership

Package-manager-owned executables and libraries are installed or upgraded by their native package manager. This preserves ownership, dependencies, ABI relationships and package-database consistency. A Python, OpenSSL, libc or other file under `/usr/bin` or `/usr/lib` is not replaced by copying an unrelated standalone binary over it.

Complete independent tool runtimes live in versioned managed directories such as `/opt/agentic-stack/tools/<tool>/<identity>` for a system install. Inspected canonical entry points live in `/usr/local/bin`; a user install uses the equivalent user-owned locations. Scripts, native modules, support libraries and resource files stay with their selected runtime. Catalog launchers resolve that runtime explicitly instead of borrowing an arbitrary `node`, `python`, or library from `PATH`.

An odd-looking original executable path is evidence to inspect, not permission to delete it. A canonical link can change only after its current occupant is inspected and the replacement is verified. Old-runtime retirement is a separate ownership- and receipt-bound step after complete acceptance. Setup rejects `retireOldTools: true`; use the established final cleanup gate, not a path-based `rm`.

## Existing-machine preservation and the Claude → OMP handoff

Use `setup agent` when the workspace already contains Claude/OMP routes, profile flags, hooks, skills, memory, brain files or sessions. The initial engine defaults to Claude. The launcher preserves the current working directory and inherited environment and delegates to the original upgrade flow.

The flow must inspect actual aliases, shell functions, wrapper scripts, named profiles, project-level agent directories and custom brain/hook targets. A default home directory alone does not identify every effective profile. Take the original preservation baseline **before invoking the new OMP binary**, including a seemingly harmless version/config query that could initialize or migrate configuration.

Claude completes only phase 1: select and upgrade OMP, verify exact command/runtime bindings, qualify the preserved model/tool/session behavior, verify the original baseline, then produce the bound `OMP_HANDOFF.md`. Claude stops there. Start OMP using the exact command in that handoff, normally:

```bash
./upgrade.sh start-omp --state /private/states/upgrade-r5
```

`agent.engine: "omp"` delegates to this same already-qualified continuation; it cannot skip phase 1 or override its recorded arguments. Phase 2 preserves the qualified OMP runtime while completing the rest of the stack.

For additive r5 installation, the launcher exports `AGENTIC_SETUP_CONFIG` and `AGENTIC_SETUP_STATE`. These contain paths, not credentials. The phase-2 agent reads those paths, validates the selected productivity plan, and invokes the productivity-only setup scope after the existing core/native work. It must not run a full setup plan that would replace the OMP process executing the handoff.

### Explicit preservation plans

Direct existing-machine apply requires:

```json
{
  "preservation": {
    "plan": "/private/preservation-reviewed.json",
    "state": "/private/states/original-upgrade/preservation",
    "additionReviews": [],
    "migrationReviews": []
  }
}
```

Use the **original** baseline already created by the phase workflow. Setup verifies that the reviewed plan matches that original baseline; it never refreshes the baseline to hide a change. If no baseline exists, a new explicit plan can be snapshotted before the first mutation. Existing profile roots discovered by setup must be covered by that plan.

Preserved files and effective route/auth/permission/brain configuration remain unchanged unless a deliberately reviewed additive scope or native migration applies. New files need exact addition identities; migrations need the retained original bytes and the existing semantic-equivalence evidence. `record-additions` and `record-migration` are the existing mechanisms. A post-install preservation blocker is actionable evidence, not a reason to exclude a directory or reset a baseline.

Reviewed specifications can be supplied in the two arrays above when their exact identities are known. An agent can also inspect a blocker, record a narrowly scoped approval directly through `profile-preservation.py`, then rerun the same setup input. Adding a new review to an already pinned setup JSON changes its identity; use the original baseline and a new setup transaction if the input itself changes.

## Execution and completion

For the full scope, setup validates source/configuration files before creating its private state. It then checks preservation, reuses a usable local Docker daemon or bootstraps the separately scoped service when explicitly enabled, runs the existing native/host/core/client/profile coordinator, verifies preservation, installs and verifies productivity tools, optionally registers company/projects/agents, and verifies preservation again.

The dedicated Docker helper selects the same private-first artifact plan as core. It does not overwrite a working existing daemon. An explicit unusable socket blocks setup so the selected route can be repaired or reviewed. The helper's own systemd, disk, source-integrity and state-ownership checks remain active.

`enrollment.enabled: true` invokes the existing `seed` operation only when core and model smoke are configured. Seed verifies the exact smoke fingerprint and rejects incompatible existing company/project/agent settings. Newly registered agents have task-triggered and periodic wakes disabled. Existing company approval policy is preserved.

Status meanings are deliberately scoped:

| Result | What it establishes |
| --- | --- |
| `plan_validated` | Selected declarations and source identities passed the available planning checks; no model connection or task was proved. |
| `requested_setup_steps_completed` | The configured installation/productivity/enrollment steps completed and their required checks passed. |
| `productivity_completed` | The configured productivity-only scope completed and passed verification. |
| `blocked` | A required validation, installation, preservation or verification gate failed; later stages did not continue. |

Real task acceptance and actual worker/profile activation are reported separately. Native Claude and Codex need protocol-compatible internal routes and valid existing authentication. An OpenAI-compatible completions route is not proof of Anthropic Messages or Responses compatibility. The kit does not invent credentials or change an existing route to make a version check pass. Complete the supplied real-model/tool/session/project acceptance gates before enabling agents for production tasks.

## Resume, changes and failed steps

Setup state is private, operator-owned and locked. It includes the original selected file hashes, the minimal source binding when applicable, completed stage records, exact installer results and private logs. Detailed child output stays in those logs rather than being copied into a public handoff.

The same command and inputs can be rerun. A completed installation is verified through its exact host receipt, installed profile binding and applicable core/model checks. Completed productivity installation is verified through the productivity installer. Enrollment is reconciled by the idempotent seed operation. Failed stages remain incomplete and are retried through their underlying guarded installer.

An input-file change blocks reuse of that setup transaction. This includes the original minimal JSON, compiled plans, selected catalogs and review specifications. Review the new input, choose a fresh setup state, and continue to use the original profile-preservation baseline when improving the same workspace. Never delete a baseline or transaction merely to obtain a green result.

Setup does not automatically remove a failed tool directory, erase logs, replace an unrelated state folder, remove a package-owned binary, or rewrite a failing service. The underlying installers retain their existing transaction recovery and rollback mechanisms. These safeguards support the upgrade; they are not a new general backup system.

## Repository source and offline releases

The repository versions the setup/compiler/installer source, templates, documentation, meaningful tests, pinned manifests and provenance. Its `offline/` content-addressed objects use Git LFS; `offline/manifest.json` maps those objects to the exact payload files. A complete private release is an alternative hydration source. Keep site secrets, private plans, state, receipts, local route definitions and model credentials outside Git. Follow [Offline payloads](PAYLOADS.md) for retrieval, hydration, and the selected release assembly procedure; ordinary Git objects must not contain the multi-gigabyte runtime payload.

A source-only checkout or a checkout containing only LFS pointers is not an offline installation bundle. Before transferring or publishing a release, retrieve the actual objects, assemble the matching pinned payload, verify closure and checksums, and test the supported target profile. Distribute the complete tar and its independently retained digest through the approved release mechanism; transport chunks, when required by a hosting limit, must reconstruct that exact tar. Runtime setup must work without a public fetch. A new target platform requires its own complete build and acceptance results.

The current bundle includes official source and documentation for debugging and controlled improvements. When modifying vendored components, preserve their licenses, upstream identity and patch provenance. Build changes in a connected preparation environment or with complete internal build mirrors; export the resulting immutable package/image and source evidence into the next offline release.
