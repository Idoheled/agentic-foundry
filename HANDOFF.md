# Agentic Foundry v0.1.2: receiving-agent handoff

Read `README.md`, `docs/QUICKSTART.md`, `docs/R5_DELIVERY_WORKSPACE.md` and `docs/BOOTSTRAP_AND_LIFECYCLE.md` first. Agentic Foundry v0.1.2 packages the r5 deployment contract: actual delivery runtimes, private-source plan compilation, fresh-machine single-script setup, the preserved existing-machine Claude → OMP handoff, and a Git LFS payload workflow. From a repository checkout use `deploy.sh`; it hydrates the verified local LFS bytes and delegates to `setup.sh`. A complete extracted release can use `setup.sh` directly. See `docs/PAYLOADS.md` before transferring into the disconnected network.

The user already has telemetry, monitoring and backups. Do not install or qualify a replacement platform for those services. Retain only the existing migration/configuration originals and receipt-bound rollback needed for this upgrade; use established organization procedures for system/database protection. The `recovery` phase gate covers interrupted tasks, cancellation, process/session continuity and preserved configuration; a new backup/restore exercise is not an r5 delivery requirement.

For new machines, `setup.sh --config /private/site.json --state /private/states/setup-r5` performs the compiled installation. For existing machines, use `setup.sh agent` and the mandatory phase boundary below. Never replace the OMP executing phase 2. Apply/verify the selected r5 productivity scope after the original native/core steps; record its real acceptance alongside the existing gates. Unsupported OS/CPU/runtime routes or failed gates remain explicit blockers.

Prefer adequate existing/private tools and package-managed OS upgrades. Preserve working brain, skills, hooks, named profiles and disconnected model routes. Do not activate Codex hook trust until the packaged code is reviewed and its exact manifest hash is explicitly recorded. Do not auto-install a new brain, a second task scheduler, an unreviewed global RTK hook, or a public dependency downloader.

The project repository is `https://github.com/Idoheled/agentic-foundry`. Runtime installation needs no Git token embedded in the kit. Keep private site configuration and credentials outside Git. Future source publication or release changes require the operator's applicable authorization; deployment of this kit does not authorize unrelated repository or production changes. The revision sections below retain the original installation and acceptance details; their historical archive names and superseded ordering do not override this current entry point or the mandatory phase boundary.

---

## Revision r4: mandatory Claude-to-OMP sequence

The user now requires two separate agent phases. Read `docs/TWO_PHASE_UPGRADE.md` and use the delivered phase launcher/controller. These phase boundaries take priority over older all-in-one ordering below.

**Phase 1 runs in the existing working Claude Code.** Follow `docs/PHASE1_CLAUDE.md`: preserve the current profiles/brain/routes, upgrade and promote only OMP and its proven prerequisites, verify the actual internal model/tool/session/custom-capability behavior, and retire the exact old unmanaged active OMP copy only after consumer checks. Persist the passed checkpoint and a secret-free handoff, print the continuation command, then stop for the user's deliberate switch. Do not upgrade Claude or the rest of the stack, install the new shared profile bundle, call the broad full-stack coordinator, or automatically start phase 2.

**Phase 2 runs in the upgraded OMP after the user launches it.** Follow `docs/PHASE2_OMP.md` and the remaining installation/acceptance procedure below. Preserve the qualified OMP runtime while completing Claude, Codex, OpenCode, Paperclip/PostgreSQL, native tools/dependencies, and additive native skills/hooks. Recheck preservation and real model/tool/worker behavior before final completion.

Both phases preserve existing hooks, skills, brain/system/role instructions, memories, provider/model mappings, authentication sources, internal route/CA/proxy configuration, profile selection and session/history storage. Capture private baselines before mutation, extend the protected inventory to actual custom/external roots, merge settings minimally, and check behavioral continuity as well as file integrity. No template may replace the user's current working brain or route. Keep backups/evidence private and secret values out of handoffs.

“Upgraded” means the user's intended native command resolves to the verified selected installation. A namespaced launcher beside an unchanged old canonical command is only complete when that is the deliberately selected invocation. Promote inspected entry points, test the real consumers, then retire the old active unmanaged item recoverably. Use the native package manager for package-owned paths. Preserve adequate/newer internal tools and use kit payloads only with factual private-first fallback evidence.

Report actual gate results. A version/help check is not model/tool/session acceptance. A blocked phase is not permission to bypass the requested manual handoff boundary or erase existing configuration to make a test pass.


---

# Receiving-agent handoff: disconnected engineering workspace

## Mission and authorized scope

You are the AI agent running inside the user's disconnected network. Use the files in this bundle to install and qualify a local engineering workspace with:

- Paperclip as the authoritative project, task, agent-assignment and run-management service.
- OpenCode as the first-party integrated worker candidate.
- The user's existing oh-my-pi (OMP) installation retained as a working baseline. Qualify the included OMP adapter separately before enabling it for ordinary tasks.
- Codex and Claude Code installed as actual native tools with complete runtime resources; preserve and qualify the existing internal routes.
- Eight shared native skills and reviewed native hooks installed for Claude Code, Codex and OMP, including supported Codex hook activation.
- Existing internal model endpoints, Git, CI, artifact repositories and, where already deployed, Temporal.
- Herdr, if included, as an optional interactive terminal cockpit with its own clearly documented scope.

The intended outcome is an installed, restartable system that completes real code tasks against internal models and shows their outcome accurately. Provision usable tools on the Linux host as well as the container runtime. Installation alone is not success.

**Artifact policy: preserve suitable installed tools; otherwise prefer approved private repositories, registries and caches. Use this kit only when the internal artifact is unavailable, incompatible or insufficient, and record the evidence. There is no public-internet fallback.** Read `docs/PRIVATE_REPOSITORIES_AND_HOST_TOOLS.md` before choosing artifacts or installation paths. Apply this policy to executables, images, OS packages, language libraries, native dependencies, build tools and subsequent repairs.

## Revision r3: required completion work

This handoff is executable installation work. Do not stop after extracting archives, writing a plan, listing tools, or configuring only the container stack. The user authorized routine installation, native profile activation, necessary inspected replacement of an inadequate or misplaced unmanaged tool, command/symlink rewiring, verification, and removal of a superseded active copy after consumer checks. Do not request the same authorization again. Preserve adequate existing installations and unrelated state. Report an actual missing privilege, unavailable internal artifact or protocol incompatibility precisely; do not invent access or fabricate a passing result.

Read `docs/HOST_LAYOUT_AND_MIGRATION.md`, `docs/INSTALLATION_SEQUENCE.md`, `docs/CLAUDE_CODEX_OMP_NATIVE.md`, `docs/NATIVE_OFFLINE_SETTINGS.md`, `docs/CODEX_PAPERCLIP_INTEGRATION.md` and `docs/OFFLINE_COVERAGE.md`. These supplement the older runtime controller procedure below. They resolve an important distinction: installing a native host client does not automatically configure the generated profile used by an orchestrated worker.

Carry out this sequence using factual site-specific plans:

1. Verify the outer archive checksum if supplied and the extracted kit's `SHA256SUMS`. Inventory the OS/architecture, package ownership, existing tools and private repositories. Preserve the current working Claude Code and OMP model/session configuration as the recovery baseline.
2. Fill the private native-package, host-tool and core runtime artifact plans from the shipped examples. Inspect internal components as well as identically named bundles. Prefer existing/internal packages, images, tools and libraries when suitable. Download only from approved private sources using their existing trust/authentication. Record a factual reason for every kit fallback; there is no public fallback.
3. Plan and apply the native OS prerequisites through the correct distro package manager. The kit fallback is Debian 13 amd64 only. Existing internal packages for another supported host take priority; qualify their layout and dependencies. Do not force a foreign distro package onto the host.
4. Install or reuse the actual host capabilities using `config/host-catalog.json` and `scripts/hostctl.py`. The baseline includes complete Python quality, Node/pnpm, Bun, Rust and Zig environments; uv, Ruff, rg, fd, jq and yq; all selected agent clients and Docker/Compose. Provision the relevant Git, tmux, rsync, inspection tools and C/C++/native prerequisites through the native plan. Use namespaced commands plus inspected canonical links where needed. Verify the final tree and real commands; a file left inside the kit is not an installed capability.
5. Install the core Paperclip/PostgreSQL stack using the separate runtime source plan. Keep the existing internal endpoint, Git and artifact services. Use the client staging helper when native clients will run inside the controller container; it copies complete qualified trees and reports the immutable in-container paths.
6. Install native profiles **as the real operator**, using the permanent installed `native-profiles` assets and the selected verified Python. Fill the native plan's actual Claude configuration directory, Codex home/user skills directory, and OMP agent directory; honor existing environment overrides. Review the exact kit manifest and use supported native Codex activation for only the reviewed kit hooks. Preserve existing auth, providers, unrelated hooks and custom skills. Verify all eight skills are discovered by all selected clients and that the applicable hooks run; mere copied files are insufficient.
7. Apply the verified offline settings while preserving working model routes. Configure Codex with an actual compatible internal Responses provider and a static local model catalog. Qualify Claude's existing internal gateway with the pinned client. A Chat Completions-only endpoint is not a Codex Responses endpoint. If a client lacks a compatible internal route, finish installing its tools/profiles and report that routing gate; never silently send requests to a public provider.
8. Qualify the default OpenCode/OMP workers and, when requested protocols are available, enroll and qualify Codex/Claude workers through the supported native adapter APIs. The supplied core `seed` command creates OpenCode/OMP agents; the native examples explain explicit legacy/CLI selection. Inspect **effective worker homes**, especially Paperclip's generated Codex home. Ensure the local model catalog and native hooks exist, are trusted and execute there. Do not reset CODEX_HOME in a wrapper to bypass Paperclip's chosen skill/state isolation.
9. Complete the real model/tool, project-worktree, review, cancellation, restart and interrupted-task acceptance below. Start with bounded concurrency and measure accepted delivery before increasing it. Use reversible canary tasks instead of modifying an existing protected project branch to prove installation.
10. After the replacement and its real consumers pass, retire the exact obsolete unmanaged file or symlink from its old active path. `hostctl retire` preserves quarantine/rollback. Do not recursively delete an unknown shared runtime directory. Record any concrete unresolved consumer that prevents retirement.
11. Produce the full installation/capability report with sources, paths, versions, checks, native profile/hook activation, operational agents, protocol gates, retired paths and recovery commands. Distinguish installed, verified and operational states. Do not claim universal platform support or that every private project's dependencies were bundled before the project was inspected.

`config/installation.example.json` composes these helpers. After completing the real private plans, use the coordinator's plan and apply commands described in `docs/INSTALLATION_SEQUENCE.md`. It installs host profiles but does not invent endpoint credentials, automatically enroll the optional native workers or certify their tool behavior. You are responsible for completing those concrete onsite acceptance steps using the included source/manuals.

For the user's misplaced-Python example: determine ownership and consumers first, install a complete suitable interpreter/runtime through its correct package or versioned prefix, switch the inspected entry point, verify imports and real service/project resolution, then retire the obsolete unmanaged active copy. Apply the same complete-runtime and ownership rules to Node, Rust, Java, Go, compilers, native libraries, Docker, every CLI and plugin. Never copy a Python library into `/usr/bin` or replace the distro loader/system Python with an isolated binary.

## Delivered entry points and paths

Run commands from the selected release's complete installation root: a hydrated Agentic Foundry checkout or the root produced by its offline tar. Use the current release manifest and `docs/PAYLOADS.md` for artifact names. `install.sh` dispatches to the Python 3 core controller; it must not fetch anything from the public internet. Approved internal repository access is allowed and preferred.

| Command | Purpose |
| --- | --- |
| `./install.sh sources --config /private/path/site.json` | Validate private-first selections and file identities without starting services. |
| `./install.sh preflight` | Check host Linux/CPU architecture, Python version, state-filesystem space and configured port values. This does not verify the payload or a running Docker daemon. |
| `./install.sh checksums` | Verify delivered payload files against the checksum manifest. |
| `./install.sh install --config /private/path/site.json` | Import/prepare the isolated installation using the recorded artifact plan. |
| `./install.sh configure --config /private/path/site.json` | Write private runtime/model configuration from the site-specific file. |
| `./install.sh start` | Start the dedicated Paperclip and PostgreSQL services. |
| `./install.sh status` | Show the observed service state. |
| `./install.sh model-smoke` | Call the actual configured internal model through the selected managed OpenCode and save the configuration-specific result; this is a text probe, not full task/tool acceptance. |
| `./install.sh seed --config /private/path/site.json` | Register the installation's company, projects, agents and local OMP adapter after the matching model smoke succeeds. Agent lifecycle hello probes can run during registration. |
| `./install.sh enable-agent --agent-id UUID --acceptance-report /private/path/report.json` | Enable on-demand execution for one accepted agent. The command requires an existing report but does not judge its evidence; the receiving agent must verify the report first. |
| `./install.sh verify` | Run the checks actually implemented by the delivered controller; complete the wider acceptance procedure separately. |
| `./install.sh stop` | Stop only this installation. |
| `./install.sh backup` | Create the supported consistent backup and record its location. |

Start from `config/site.example.json`, create a private site file, and fill it from the verified onsite discovery. The site file identifies provider/API type, base URL, main/helper model IDs, credential-source environment variable and project list. Set its `artifactPlan` to the absolute path of a completed private plan based on `config/artifact-plan.example.json`. Discover approved internal repositories using existing configuration/authentication, stage selected files locally, and record every runtime source decision before `install` or `configure`. Do not put a real credential into a checked-in template.

Default state is `$HOME/.local/share/agentic-stack`. Its managed runtime directory is mounted read-only at `/opt/agentic`, and managed workspaces under the state directory appear at `/workspaces`. Paperclip is initially loopback-only on port `3100` unless the site configuration deliberately selects a free alternative.

The host catalog also supplies Codex `0.171.0`, Claude Code `2.1.329` and the native profile bundle. Their source/license/compatibility boundaries are recorded in `docs/OFFLINE_COVERAGE.md`.

The core images are pinned Paperclip `2026.1117.0` and PostgreSQL `17`; workers are OpenCode `1.18.34` and isolated downstream OMP `19.0.1-offline.1`, with optional Herdr `0.9.5`. The OMP adapter is the downstream `0.7.0-offline.1` build. Original upstream sources and the separately identified offline patches are included; do not present these patched executables as unmodified upstream releases. Use the manifest's immutable image/source digests as the authority, rather than trusting a version label alone.

An existing usable Docker installation is preferred. If none is available, inspect the approved internal OS/container repositories and install a suitable internally supplied runtime through their supported mechanism. If a separate static daemon is the appropriate qualified route, `./scripts/bootstrap-docker.sh --artifact-plan /absolute/private/artifact-plan.json` consumes the plan's selected archive. Prefer an internal copy; use the kit archive only with documented fallback evidence. Run that helper as the intended ordinary operator account. It requires existing sudo authority and a running systemd host, creates a dedicated service, uses the selected static Docker with `overlay2`, and requires at least 40 GiB free under `/var/lib` for its separate data directory. It uses its own socket and does not replace the system daemon. Do not silently switch every Docker command to the host's default socket. The supplied runtime plan uses host networking without a bridge/iptables configuration; this is not network-namespace isolation. The controller separately requires at least 35 GiB free on the state filesystem. Plan about 100 GB total available storage for the archive, extracted artifacts, image layers, state, source builds and working repositories; repository/model requirements may need more. Model weights and GPU-serving capacity are additional.

Use this setup order after discovery: run `checksums` and `preflight`; finish internal repository searches and the artifact/host-tool plans; provision the required host capabilities; select or install the container runtime under that policy; create the private site file with its `artifactPlan` and provide its named credential environment variable without printing it; run `install --config /private/path/site.json`, `model-smoke`, then `seed --config /private/path/site.json`. Later configuration changes use `configure --config /private/path/site.json` followed by `start` and a fresh `model-smoke`. Run `verify` for its narrow controller checks and complete `AIRGAP_ACCEPTANCE.md` before ordinary task admission. Use the same `--state` and `--docker-host` selection consistently when overridden.

These commands are the bundle contract. Read the actual controller help/source if a command reports a different supported interface, and report the discrepancy rather than inventing an option.

The user has authorized installing this workspace, provisioning actual machine tools, performing isolated validation, and replacing an existing component when inspection shows that replacement is needed. Proceed with reversible setup, private configuration, necessary inspected tool upgrades, an isolated smoke repository and local Paperclip bootstrap without repeatedly asking for permission. Record the reason, affected consumers, backup and rollback before replacement. If a necessary fact, artifact, privilege or resource is unavailable, complete the independent authorized work and report the exact remaining constraint. Changes to unrelated production behavior remain outside this setup scope.

Preserve adequate existing OMP/Claude Code installations and other working tools. Retain the current working agent until a necessary replacement has passed validation and a rollback is available. Reuse existing inference services, Git/CI, Artifactory and Temporal; provisioning this workspace does not authorize replacing those shared services or production applications. Do not run firmware operations, modify production clusters, publish repositories, send messages, or make unrelated changes. Do not expose this service publicly.

## What the bundle does and does not establish

Treat the delivered manifest, pinned source and actual scripts as authoritative for versions, filenames and supported commands. Read them before starting. Do not improvise API routes or adapter configuration keys from an online example or an older release.

This bundle does not include model weights or the user's credentials. It expects the internal network to provide at least one already usable model service, or a separately provisioned local model. A local executable is not proof of local inference.

Source availability is not the same as an executable offline installation. Confirm that the selected runtime path has every required image, dependency, native module and executable before enabling agents. An included source archive or Git bundle is for inspection, reconstruction and future changes; it does not by itself replace a missing dependency cache.

The exact host, Linux distribution, runtime, endpoint protocol and available capacity were not validated when this bundle was assembled. The receiving-host checks below are required qualification work, not assumptions you may silently mark as passed.

## 1. Verify and inventory before changing anything

1. Read START_HERE.md, checksums, manifest, installation scripts and this handoff.
2. Verify all checksums with the delivered verification command. Reject missing or mismatching payload files. Record the archive identity and source revisions.
3. Record architecture, OS, kernel, libc, CPU, memory, available disk and existing container runtime versions. Linux x86-64 is the default target; do not try to execute these binaries on a different architecture.
4. Identify available Docker or Podman and whether the current user can operate it without changing privileges. Do not silently install a second runtime or substitute a Docker-only lifecycle with Podman commands until verified.
5. Check port conflicts and identify a dedicated installation directory and state directory. Use separate project-specific names for containers, volumes, networks and systemd units.
6. Inspect the manifest's exact runtime requirements. Where Paperclip Runner or an agent binary needs a newer glibc, use a compatible delivered container image or explicitly select the verified alternative execution path. Do not upgrade the host libc to make a binary run.
7. Identify current OMP/Claude Code executable versions and their launch methods. Record executable paths, package ownership, hashes where practical, symlink targets, configuration locations and known consumers. Preserve them when adequate; qualify any necessary replacement under the host-tool policy.
8. Inventory the host tools needed to run and develop the selected projects: Git, transfer/archive/checksum tools, search/JSON tools, Python and Node runtimes, container tools, relevant package managers, compilers and project-specific libraries. Use `config/host-capabilities.example.json` as a receiving-agent checklist, add actual project requirements, and implement missing capabilities. A list of source archives does not satisfy this step.

Write a brief private discovery report. It should contain versions, availability, paths, protocol choices and blockers, without credentials or full configuration dumps.

Maintain `reports/host-tool-inventory.json`, `reports/artifact-decisions.json`, `reports/host-installation-report.md` and `reports/rollback.md` under the private state directory, or record equivalent explicit paths. Include source searches, selections, destination paths, link changes, preservation/replacement decisions and actual verification results. These are receiving-agent deliverables, not reports the controller automatically certifies.

## 2. Discover existing internal configuration without exposing secrets

Start with locations the current tools already use: their own documented configuration files, the current project's documented endpoint settings, existing service definitions and the user's stated internal paths. Do not indiscriminately crawl home directories, credential stores or unrelated repositories.

Read configuration programmatically. Extract a permitted inventory such as provider name, model identifier, base URL, API protocol, context limit, certificate file path, configured credential source and executable path. A credential source may be recorded as `environment variable`, `private file` or `existing credential helper`; never print its value.

Do not use `cat .env`, `env`, shell tracing, verbose HTTP headers, whole-file search excerpts or terminal command arguments to display secrets. Avoid embedding tokens in URLs or process arguments. If authentication is necessary, load it into the process environment or a private configuration file through a supported mechanism; do not place it into prompts, task descriptions, source files, reports or Git commits. Ensure secret-bearing files are owned by the service account and have restrictive permissions.

Use existing internal CA trust. The site file supports a top-level `caCertPath` pointing to the approved internal CA PEM; the controller copies it into this installation and configures the relevant runtime trust variables. Mount or configure the appropriate CA for every relevant runtime instead of disabling TLS verification globally. Container trust stores and Node/Python trust configuration may differ from the host's trust store; prove the selected route works.

Inspect the configured internal artifact services and caches: distro repositories, OCI registries, PyPI/npm equivalents, Git source mirrors, native/build caches and any existing Artifactory configuration. Use their existing credential helpers and trust configuration. Record sanitized repository identities, searches and findings in the artifact plan's `privateRepositoriesChecked` list and decision report. Search transitive dependencies as well as top-level packages. Authentication failure or a missing repository configuration must be recorded accurately; it is not evidence that an artifact does not exist.

Discover existing Git repositories by inspecting the user-designated project roots and repository metadata. Report which repositories have uncommitted changes. Do not read or modify their application secrets to register them.

If you cannot determine a usable model endpoint, protocol, model identifier or authentication source, report the specific missing values. Do not guess a public fallback or fabricate a successful model probe.

## 3. Choose and isolate the installation

Keep suitable existing tools. Prefer artifacts from approved internal repositories and caches for anything missing or insufficient. Stage and verify those artifacts locally before runtime setup. Use kit artifacts only after recording `fallbackReason` as `unavailable`, `incompatible` or `insufficient`, with specific evidence and the internal repositories checked. Public registries, public model endpoints and automatic public downloads are not fallback sources.

The delivered controller accepts explicit runtime choices for `docker`, `compose`, `omp`, `herdr`, `opencode`, `ompAdapter`, and the `paperclip`/`postgres` images through the site's `artifactPlan`. The plan uses `schemaVersion: 1`, a nonempty `privateRepositoriesChecked` list, and factual `evidence` for every selection. A file choice with `source: internal` or `source: existing` supplies an absolute `path` and `sha256` matching the shipped tested artifact; its local filename may differ. Image choices supply an immutable `imageRef` containing `@sha256:` and `expectedConfigDigest` matching the shipped image config digest. The supplied hook supports internal mirrors of this tested build, plus a separately qualified existing/internal host Docker or Compose executable. For host Docker use `format: executable` and the required `qualificationReport`; if the separate daemon helper is needed, supply the selected daemon archive as `files.dockerDaemon` and invoke the helper with `--artifact-plan /absolute/private/artifact-plan.json`. Read `config/artifact-plan.example.json` and the actual controller for the exact schema and report checks.

A different internally supplied version is not automatically insufficient just because its bytes differ. Inspect its compatibility and required offline behavior. When it is the appropriate choice, qualify it onsite and adapt the included controller/configuration in an explicit recorded change before using it. Do not weaken digest checks, substitute an untested image or claim the shipped validation applies to a different build. If required capabilities or dependency closure cannot be established, record the exact gap before selecting the kit fallback.

Provision the host as directed in `docs/PRIVATE_REPOSITORIES_AND_HOST_TOOLS.md`: use internal distro packages for package-manager-owned `/usr/bin` and system libraries; place standalone tools under versioned `/opt` paths and expose inspected `/usr/local/bin` entry points; install Python libraries through distro packages or dedicated virtual environments. Never copy a Python library into `/usr/bin` or blindly redirect the OS Python. Inspect and back up an existing file or link before any necessary replacement. Verify the actual executable, version, runtime dependencies and configured internal-service access from a fresh shell and from its real service/container environment.

Use a dedicated service identity and private state/configuration directories. Keep Paperclip application data, database data, agent home/session data, workspaces and logs in explicit persistent locations. Keep agent output away from the bundle's immutable payloads.

Bind the UI to localhost or an explicitly selected internal interface. Configure the supported authentication mode for access from other machines. Verify that the observed mode protects the actual API, not only a frontend page. Use existing internal reverse-proxy or identity infrastructure where available; do not invent a new public DNS or certificate dependency.

Do not mount the host root, all home directories, production kubeconfigs or an unrestricted container-runtime socket into coding workers. Worktree separation prevents accidental file collisions; it is not a security boundary. Prefer a dedicated VM or appropriately scoped containers for executable isolation.

Keep all external-provider fallback routes disabled. Do not run automatic package/plugin updates. Use the pinned local executable path for adapters rather than a command that resolves `latest` or downloads a package on launch.

Choose the access mode deliberately:

| Mode | Intended use | Requirements |
| --- | --- | --- |
| `local_trusted` | Automatic first setup for one trusted Linux host | The pinned source requires `PAPERCLIP_DEPLOYMENT_MODE=local_trusted`, `PAPERCLIP_BIND=loopback` and `HOST=127.0.0.1`; it rejects an all-interface bind. Local clients act as the board administrator. With a Linux host-network container, use the host's loopback URL. Do not expose this mode through an unprotected proxy. |
| Authenticated deployment | Direct browser access from other internal machines | Configure supported authentication and the public/internal base URL. Complete the local owner-account/claim flow before allowing ordinary use. |

For the authenticated Docker path in Paperclip `v2026.1117.0`, persist two independently generated private values: `BETTER_AUTH_SECRET` for sessions and `PAPERCLIP_TOOL_ACTION_SIGNING_SECRET` for governed tool-action approvals. Do not regenerate them on each restart. Use the delivered image's compiled entry point and allow its documented 90-second shutdown grace. The official Docker guide uses a local **Create Account → Claim this instance** flow for the first owner; it explicitly says `paperclipai auth bootstrap-ceo` does not work inside that container. Use the supported local flow, or the bundle's verified implementation of it. If owner setup requires information or an interactive capability you do not have, finish the remaining independent installation work and report the exact local step that remains. Do not invent a cloud-login dependency.

For OpenShift, stop and qualify the actual deployment path if this bundle was only prepared for a standalone Linux runtime. UID restrictions, volume ownership, security-context constraints, job execution, process cancellation and network rules must be validated. The existence of an upstream Kubernetes plugin is not proof that it is qualified on this cluster.

## 4. Configure internal models and prove protocol compatibility

Create two logical model roles using the exact configuration schema of the delivered harness:

| Role | Work | Selection rule |
| --- | --- | --- |
| Main | Planning, implementation, difficult debugging, substantive review | Use the strongest already approved internal coding model that works with this harness. |
| Helper | Summaries, bounded classification, simple extraction and inexpensive checks | Use a smaller compatible internal model when available; otherwise use the main model with separate limits. |

These role names are configuration policy, not presumed provider model IDs. Preserve the real IDs returned by the internal service. Do not silently label two endpoints as distinct models when they serve the same model.

Set `model.api` to the actual endpoint protocol: `openai-completions`, `openai-responses` or `anthropic-messages`. The controller supports these configuration paths; the builder integration used only an OpenAI Chat Completions mock. Responses and Anthropic Messages must pass their own onsite tests before use. Test the exact endpoint API required by each harness. Chat Completions compatibility does not imply Responses API compatibility, and a normal text completion does not prove working tool calls, streaming, context management or agent session continuation.

For each enabled worker, verify: authenticated access, ordinary generation, a structured tool call, tool-result continuation, streamed response if used, timeout behavior, explicit provider failure, and reported model identity. Verify that a configured local route never falls back to a public service.

### Paperclip OpenCode gateway path in the pinned release

For the documented gateway-configuration route in `v2026.1117.0`, explicitly choose the classic adapter: `adapterType: "opencode_local"` with `runner: "legacy"` on the supported create/hire request, or the documented CLI `--runner legacy`. Otherwise, new agents on supported hosts may be saved as `paperclip_runner` automatically. These two execution paths do not have interchangeable configuration behavior.

The documented classic gateway injection applies only to a **local target with `dangerouslySkipPermissions: true`**. It uses a temporary OpenCode configuration and replaces that copy's tool permission rules with full automatic permission. This is why OS/container isolation and limited mounted data are required. Do not claim the user's usual OpenCode approval rules remain in force on this path.

Set `PAPERCLIP_OPENCODE_PROVIDERS` to the explicit internal provider definition with its `baseURL`, actual `models` map and supported credential reference. Keep real secrets out of the JSON using the documented `{env:VARIABLE_NAME}` form or the shipped secret mechanism. Set the agent's `model` to the exact `provider/model` ID. Also set `PAPERCLIP_OPENCODE_SMALL_MODEL` to an internal model: auxiliary title/helper calls must not retain an unavailable external default. For models absent from the public catalog, the documented `OPENCODE_ALLOW_ALL_MODELS=true` bypasses the availability probe; the real model/tool test remains mandatory.

Inspect the bundled OpenCode version's own configuration for provider/metadata/update controls and apply only verified options. The `npm` field in a custom provider can cause package resolution; confirm that the selected provider implementation is available from the delivered offline artifacts before the first run.

For the delivered OpenCode `v1.18.34` baseline executable, the inspected offline controls are `OPENCODE_DISABLE_AUTOUPDATE=1`, `OPENCODE_DISABLE_MODELS_FETCH=1`, `OPENCODE_DISABLE_DEFAULT_PLUGINS=1` and `OPENCODE_DISABLE_LSP_DOWNLOAD=1`. The generated private config should whitelist the internal provider through `enabled_providers`, set both `model` and `small_model` to internal IDs, set `share: "disabled"` and `autoupdate: false`, and select the matching bundled provider implementation. `openai-completions` selects `@ai-sdk/openai-compatible`; the other two protocol paths select their corresponding OpenAI/Anthropic SDKs and still require onsite qualification. These settings are defense against unwanted optional fetches; the real disconnected test remains the acceptance gate.

If the bundled downstream OMP `v19.0.1-offline.1` is used, give it isolated `PI_CODING_AGENT_DIR` and `PI_NATIVES_DIR` locations. Its inspected offline/minimal launch controls include `--offline --no-title --no-judge --no-spotlight --no-lsp --no-pty`; a bounded programmatic call uses `--mode json -p` with the configured `--model provider/model`. The bundled OMP patch also suppresses identified background model discovery in offline mode. The adapter patch uses the provisioned static internal-model list and disables live provider-quota probes. These changes are explicit offline adaptations, not a firewall or proof of zero outbound DNS; verify actual target routing. Preserve the existing OMP as the user's baseline and do not point the new executable at its working session/config directories. Use the adapter's supported flags and the delivered wrapper rather than blindly appending incompatible arguments.

Start conservatively: one active implementation run and one active review/verification run. Increase concurrency only after measuring latency and accepted throughput on the actual endpoint. Dollar budgets with zero-priced local models do not limit GPU usage. Apply queue/concurrency, token/context and wall-clock controls where supported, and record where the controls are enforced.

## 5. Bootstrap Paperclip with verified interfaces

Read the shipped Paperclip documentation and source for the pinned version. Use its supported onboarding CLI, API or included bootstrap script. If an expected route or field does not exist, inspect the delivered schema and report a concrete incompatibility; do not create a superficially similar custom endpoint.

Create one workspace/company for this installation and one project per actual engineering project. A large organization chart is unnecessary. Begin with these responsibilities, implemented using supported agent fields and role descriptions:

1. **Coordinator:** triage goals, choose ready tasks, assign ownership, track dependencies and escalate blockers.
2. **Implementer:** produce scoped changes in an isolated checkout and report evidence.
3. **Reviewer:** review the diff and acceptance criteria in a separate context.
4. **Verifier:** run deterministic checks and report observed results; this may be a tool/CI workflow rather than another continuously running LLM agent.

Configure the first-party OpenCode adapter from the shipped schema. Configure the community OMP adapter only after checking its compatibility with both the pinned Paperclip version and the installed OMP version. Upstream Pi support does not by itself establish OMP support.

Seed agents with task execution disabled until their model path is qualified. Creating a new agent starts Paperclip lifecycle verification, including a real model hello probe; disabling heartbeats does not suppress these configuration probes. Seed only after the internal model route has passed its smoke test, then check that each agent reaches lifecycle state `ready`. A failed lifecycle probe can leave a requested run queued until configuration is repaired. In the pinned Paperclip source, `runtimeConfig.heartbeat.enabled=false` disables only interval wakes; task/event wakes still occur when `wakeOnDemand` is true. The initial policy should therefore explicitly include:

```json
{
  "heartbeat": {
    "enabled": false,
    "intervalSec": 0,
    "wakeOnDemand": false,
    "maxConcurrentRuns": 1
  }
}
```

To run the first Paperclip qualification task, temporarily enable only the designated smoke agent using the supported `PATCH /api/agents/{id}` API: preserve its existing runtime configuration and set `runtimeConfig.heartbeat.wakeOnDemand` to `true`, keeping `enabled:false`, `intervalSec:0` and `maxConcurrentRuns:1`. Restore `wakeOnDemand:false` after the bounded test, including on failure. This temporary test step does not depend on the final admission command. Complete the real task/review and recovery checks, write the acceptance report, then use `enable-agent --agent-id UUID --acceptance-report PATH` for ordinary work. The command checks that a report exists; it does not evaluate whether that report establishes success. Leave idle interval wakes off. Set concurrency explicitly: this release's otherwise applicable default is 20 concurrent runs per agent. A limit of one per agent is not a global limit; four agents can still run four top-level jobs, and a harness may create additional internal work.

Initial registrations may issue several lifecycle model probes; serialize registration or allow adequate inference capacity before creating the complete team.

Every task must have one authoritative owner, a project, a bounded objective, acceptance criteria, a workspace/branch, execution limits and evidence links. Preserve statuses supported by the product. If the product cannot represent a desired intermediate state, use a documented field or label rather than introducing an undocumented enum.

Keep scheduling ownership in Paperclip for these coding tasks. Do not allow Herdr, a cron job and Temporal to independently redispatch the same task. Existing Temporal workflows continue to own their established operational processes.

## 6. Register existing repositories without changing them

Register discovered repository metadata and internal remote URLs only. Do not rewrite remotes, modify repository instructions, install hooks, move branches, commit or push to make registration succeed.

Perform all acceptance tests in a new dedicated smoke repository. For real tasks, use a dedicated clone or an isolated checkout explicitly associated with that task. Creating a Git worktree under an existing repository changes that repository's metadata; if preserving it strictly is required, create a dedicated clone first. Preserve uncommitted work and document that ordinary clones do not contain it.

Provide agents the project's existing instructions, test entry points, architecture notes and relevant internal documentation. Keep task context scoped. Do not inject every project, every tool definition or the entire organization's documentation into every agent prompt.

Use `AGENT_PLAYBOOKS.md` for the proposed working conventions. Apply them to this installation's own configuration first; changing existing project policy files is a separate project change.

## 7. Qualify actual delivery and recovery

Execute `AIRGAP_ACCEPTANCE.md` and retain sanitized evidence. Required proof includes:

- A task visible in Paperclip that triggers the configured worker, changes the isolated smoke repository, runs tests, and reports the actual result.
- A separate review or verification outcome.
- Accurate top-level run visibility and an honest statement of which child-agent events are exposed.
- Model-service failure producing a visible failure or blocked state without external fallback.
- Cancellation stopping the worker and its owned child processes.
- Worker/control-layer restart with preserved state and no duplicate uncontrolled work.
- Persistence after normal service restart.
- A fresh launch with external egress unavailable and all required artifacts already imported.

If Herdr is enabled, verify it separately. It is not an automatic Paperclip task/event bridge. Do not claim its sessions appear in Paperclip unless the delivered integration demonstrably creates that mapping.

## 8. Complete the handoff

Produce a concise final report with:

1. Internal UI URL and access method, without passwords/tokens.
2. Installed versions/revisions and selected runtime path.
3. Configured main/helper model IDs and internal routing, with credential values redacted.
4. Projects registered, and confirmation that their sources were left unchanged.
5. Which adapters passed a real task and which remain disabled or unqualified.
6. Acceptance results with evidence paths and any known visibility or recovery limitations.
7. Exact operational commands for start, stop, status, logs and backup. Also document the separately tested restore and rollback procedure; the controller does not promise automatic restore or rollback commands.
8. Host tools actually reused, installed or replaced; their sources, final executable/library paths, symlink targets, fresh-shell/service checks and recovery evidence. Include the completed artifact plan and specific reasons for kit fallbacks. State remaining missing capabilities precisely.
9. The next safe real task to assign.

Use one of these outcomes: **qualified for the tested workflow**, **installed with explicit blockers**, or **installation incomplete**. Do not call the complete workspace production-ready merely because the UI opens. Complete every supported, authorized step before reporting a blocker; explain exactly what evidence or missing artifact is needed to resolve it.

## Primary references for the version-specific notes

The matching source documentation is included with the bundle. Upstream references are for provenance, not network requirements inside the disconnected environment:

- [Paperclip Docker deployment](https://github.com/paperclipai/paperclip-docs/blob/main/docs/reference/deploy/docker.md)
- [Paperclip OpenCode adapter](https://github.com/paperclipai/paperclip-docs/blob/main/docs/reference/adapters/opencode.md)
- [Paperclip Runner](https://github.com/paperclipai/paperclip-docs/blob/main/docs/reference/adapters/paperclip-runner.md)
- [Paperclip external adapters](https://github.com/paperclipai/paperclip-docs/blob/main/docs/reference/adapters/external-adapters.md)

Use the included documentation's recorded commit rather than assuming these upstream `main` URLs still describe the same release.
