# r5 entry point

Start with [README.md](README.md) and [the r5 delivery guide](docs/R5_DELIVERY_WORKSPACE.md). The current entry point is `./setup.sh`; the two-phase upgrade remains mandatory for an existing Claude/OMP machine. The following historical r4 notes remain useful for the preserved phase controller.

---

# Offline agent operations kit — revision r4

Dated 20 November 2026. This is the complete Linux x86-64 stack with the user's requested **Claude → manual switch → OMP** upgrade workflow. All r3 runtime/source/dependency payloads are retained unchanged; r4 adds phase control, configuration preservation, fresh acceptance evidence and final retired-file cleanup.

## Start in your normal project/workspace

Verify the delivered archive checksum, then extract the single tar. Use an absolute kit path when launching from the directory where your current agent normally works. Do not change to the kit directory merely to shorten the command: OMP can load project-specific configuration from its working directory.

```bash
sha256sum -c agentic-offline-linux-amd64-2026-11-20-r4.tar.sha256
tar -xf agentic-offline-linux-amd64-2026-11-20-r4.tar

# From the normal project/workspace:
/absolute/path/to/agentic-offline/upgrade.sh start-claude
```

This starts your existing configured Claude in the requested unattended mode. Claude discovers the machine and private supply, snapshots current profiles/brain/routes/hooks/skills, rehearses the OMP upgrade against a private profile copy, upgrades and promotes the canonical OMP command, then executes real internal model/tool/session/capability checks. It upgrades only OMP and proven necessary prerequisites in this phase. It keeps the running Claude and remaining stack untouched.

When phase 1 passes, Claude writes a private `OMP_HANDOFF.md`, prints a continuation command and **stops**. End that Claude installation run, then manually run the printed command:

```bash
/absolute/path/to/agentic-offline/upgrade.sh start-omp \
  --state /absolute/private/workflow/state
```

OMP uses its recorded, qualified canonical command, working directory and profile arguments. It completes the other clients, native tools/dependencies, Paperclip/PostgreSQL services, additive skills/hooks and actual worker qualification. It preserves its own qualified runtime while doing so. The launcher will not start phase 2 before phase 1 passes.

The default state is `${XDG_STATE_HOME:-$HOME/.local/state}/agentic-stack/upgrade-r4`. You can select another private absolute directory with `--state`. Keep the same value and approved credential environment throughout both phases. State, secrets and backups stay on your machine. No internal endpoint credentials are in this kit.

```bash
/absolute/path/to/agentic-offline/upgrade.sh status --state /absolute/private/workflow/state
```

`launch-handoff.sh claude|omp` is a compatibility entry point to the same phase-aware launchers. The Claude launcher also accepts `-- CLAUDE_PROFILE_ARGS...` for inspected existing Claude invocation options.

## Read these instructions

- `docs/TWO_PHASE_UPGRADE.md`: exact responsibilities, commands, evidence contract and failure boundaries.
- `docs/PHASE1_CLAUDE.md`: full bounded Claude brief.
- `docs/PHASE2_OMP.md`: full OMP continuation brief.
- `HANDOFF.md`: shared component/operation instructions; the two-phase ordering takes precedence.
- `docs/PROFILE_PRESERVATION.md`: baseline snapshots, active profiles, external symlinks, native migrations, additive changes and drift detection.
- `docs/FINAL_CLEANUP.md`: exact retired-file deletion, private rollback archives and recovery.
- `docs/R4_VALIDATION.md`: what the new code was tested to do and what remains an onsite check.

## Source selection and native paths

Reuse sufficient existing components, then prefer approved private repositories/registries/caches, including the site's Artifactory. Use the kit only with factual evidence that internal supply is unavailable or insufficient. There is no public download fallback.

CLIs and toolchains are host-native complete runtime trees. Distribution packages own `/usr/bin` and native library paths. Standalone tools use versioned `/opt/agentic-stack/tools` trees with inspected canonical entrypoints in `/usr/local/bin`. Python libraries stay in their intended interpreter/virtual environments. Skills/hooks go into each engine's actual active profile. Paperclip and PostgreSQL remain the supplied container deployment.

The phase controller requires ordinary canonical commands to resolve to the qualified selections, not merely the added `agentic-*` names. It refuses an old command earlier on PATH. The receiving agent additionally inspects shell aliases/functions, wrappers and actual consumers.

After verification and consumer checks, exact superseded unmanaged active files/links move into quarantine. After full acceptance, `complete-stack` archives and deletes those individual quarantine objects. A private verified rollback archive remains. Package-managed upgrades use the package manager. Unknown directories, active runtime trees, brain/profile state and shared libraries are not recursively deleted. If final cleanup is blocked, inspect status and use `cleanup-old` after resolving the documented issue.

## The selected stack

| Component | Delivered role and version |
| --- | --- |
| Paperclip | Central project, task, agent, run and evidence service; official `2026.1117.0` image and source commit `c0f132898d2a2677312d8c72096187b27a3d9a38` |
| PostgreSQL | Actual Linux image containing PostgreSQL `17.12`, pinned by image/config digests; source archive included |
| OpenCode | Native Paperclip worker, pinned `1.18.34` baseline executable, full source snapshot and installed dependency closure |
| OMP | Original official `19.0.1` executable and source, plus a separately identified `19.0.1-offline.1` managed build that disables automatic model-catalog discovery |
| OMP adapter | Community adapter `0.7.0`, with explicit `0.7.0-offline.1` patch for static model selection and disabled live quota discovery; compiled package and dependencies included |
| Herdr | Optional terminal cockpit, `0.9.5` static Linux executable and source |
| Codex | Official `0.171.0` complete package, source, native helpers, manual, Cargo dependency inputs and Rust toolchain; internal Responses endpoint required. |
| Claude Code | Official `2.1.329` distributions, available public source/docs, native skills/hooks; preserve and qualify the working internal gateway. |
| Native profiles | Eight curated shared skills and native hooks for Claude, Codex and OMP; additive installer with supported Codex hook activation and recovery. |
| Host capabilities | 19 versioned runtime/tool/asset choices, 32 managed command entry points, native OS dependency repository, correct-path migration and rollback helpers. |
| Runtime/bootstrap | Docker static `29.10.0`, Compose `5.8.0`, Node `24.22.3`, pinned pnpm, and supporting build materials; see the manifest for exact archives |

Paperclip owns operational state. Herdr shows its own terminal sessions. It is not a universal mirror of every Paperclip subprocess. Existing internal Git, CI, model serving, artifact repositories and Temporal remain the systems to reuse. This kit does not introduce a second issue tracker or another competing agent orchestrator.


## Machine and model qualification

Run as the ordinary operator; native installers use existing noninteractive sudo authority where required. The main payload targets Linux x86-64; the selected OMP baseline requires x86-64-v2. The fallback native package repository is Debian 13 amd64. Other distributions must use qualified internal native packages. This is not an operating-system image or an ARM build.

The receiving agent discovers internal endpoint protocols, model IDs, context/capacity, credential sources, internal CA/proxy settings, existing Git/CI/Temporal services and projects. Codex requires a compatible Responses endpoint. Preserve your working Claude route and qualify the supplied client against it. Protocol, tool-loop and session behavior must be observed on the actual service.

Plan space for the archive, extraction, installed runtime trees, container data, source development and projects. The retained core preflight checks its own storage requirements. Do not infer capacity from archive size alone. `docs/OFFLINE_COVERAGE.md` records exact platform/source boundaries; private project dependencies, model weights and credentials are onsite inputs.

## Installation plans and component helpers

The receiving agents compose the actual plans from `config/upgrade-flow.example.json`, `phase1-installation.example.json`, `phase1-host-plan.example.json`, `phase2-installation.example.json`, `phase2-host-plan.example.json` and the existing core/native/profile schemas. Placeholders deliberately do not run as completed inspections. You do not need to fill all templates before starting Claude.

Phase 1 uses `upgrade.sh begin`, `record-check`, `install-omp` and `complete-omp`. Phase 2 uses `install-rest` (optionally staged with `--only native|host|profiles`), recorded checks, `complete-stack` and cleanup. Underlying component helpers remain for diagnosis, native package handling, registration and recovery; their success does not replace the phase gates.

The preserved detailed component guides include `INSTALLATION_SEQUENCE.md`, `HOST_LAYOUT_AND_MIGRATION.md`, `SOFTWARE_INVENTORY.md`, `CLAUDE_CODEX_OMP_NATIVE.md`, `CODEX_PAPERCLIP_INTEGRATION.md`, `AIRGAP_ACCEPTANCE.md`, `OPERATIONS.md` and rebuild/source coverage documents. Native host profiles do not automatically prove Paperclip-generated worker homes contain the same hooks; qualify those actual homes before activation.

The delivered payload includes actual images, binaries, complete runtime distributions, source snapshots, source/build dependency inputs, upstream docs/licenses, patches, Git bundles, manifests and scoped validation evidence. `SHA256SUMS` covers the complete extracted managed file set. Preserve the private workflow receipts and original configuration backups after installation.
