# Agentic Foundry documentation

Agentic Foundry has two deployment paths: scripted provisioning for a fresh machine and a preserved Claude → OMP upgrade for an existing workspace. Start with the path that matches the actual host, then qualify its selected tools and model routes.

## Start and deploy

| Guide | Read it when |
| --- | --- |
| [Quick start](QUICKSTART.md) | You are setting up or upgrading a machine. |
| [Offline payloads](PAYLOADS.md) | You need the full LFS-backed payload, a transferable tar, or a hydrated source checkout. |
| [Bootstrap and lifecycle](BOOTSTRAP_AND_LIFECYCLE.md) | You need configuration details, platform profiles, resume behavior, or exact setup status meanings. |
| [Receiving-agent handoff](../HANDOFF.md) | An internal agent is carrying out the deployment. |
| [Two-phase upgrade](TWO_PHASE_UPGRADE.md) | The machine already has working Claude/OMP configuration. |
| [Claude phase 1](PHASE1_CLAUDE.md) | Claude is selecting, upgrading, and qualifying OMP. |
| [OMP phase 2](PHASE2_OMP.md) | The upgraded OMP is completing the remaining installation. |

## Understand the workspace

| Guide | Scope |
| --- | --- |
| [Architecture](ARCHITECTURE.md) | Component ownership, source selection, state, and execution boundaries. |
| [Operations](OPERATIONS.md) | Project delivery, native tools, failed steps, and routine changes. |
| [Software inventory](SOFTWARE_INVENTORY.md) | Baseline components and pinned upstream identities. |
| [r5 delivery profile](R5_DELIVERY_WORKSPACE.md) | Worktrunk, search, language services, RTK, evaluation, browser verification, and offline scanning. |
| [Agent playbooks](AGENT_PLAYBOOKS.md) | Coordinator, implementer, reviewer, and verifier responsibilities. |

## Configure private supply and native tools

| Guide | Scope |
| --- | --- |
| [Private repositories and host tools](PRIVATE_REPOSITORIES_AND_HOST_TOOLS.md) | Existing/private/fallback selection and evidence requirements. |
| [Artifact-plan format](ARTIFACT_PLAN_FORMAT.md) | Detailed runtime artifact declarations. |
| [Host layout and migration](HOST_LAYOUT_AND_MIGRATION.md) | Package ownership, complete runtimes, entry points, and inspected replacement. |
| [Host provisioner](HOST_PROVISIONER.md) | Host catalog and native command installation. |
| [Installation sequence](INSTALLATION_SEQUENCE.md) | Detailed native/host/core/profile coordinator. |
| [Profile preservation](PROFILE_PRESERVATION.md) | Baselines, additions, migrations, and exact review bindings. |
| [Final cleanup](FINAL_CLEANUP.md) | Retirement of proven obsolete unmanaged paths after acceptance. |

## Integrate and verify clients

| Guide | Scope |
| --- | --- |
| [Native Claude, Codex, and OMP](CLAUDE_CODEX_OMP_NATIVE.md) | Native skills, hooks, client configuration, and capability discovery. |
| [Native offline settings](NATIVE_OFFLINE_SETTINGS.md) | Client-specific disconnected routes and update behavior. |
| [Codex and Paperclip](CODEX_PAPERCLIP_INTEGRATION.md) | Native provider compatibility and effective worker homes. |
| [Staged client runtimes](STAGED_CLIENT_RUNTIMES.md) | Complete client runtime exposure to workers. |
| [Native delivery tools](NATIVE-DELIVERY-TOOLS.md) | Added command runtimes and dependency groups. |
| [Offline evaluation and browser](OFFLINE-EVALUATION-AND-BROWSER.md) | Inspect AI, agent benchmarks, tokenizers, Chromium, and test inputs. |
| [Target browser handoff](TARGET-BROWSER-HANDOFF.md) | Mandatory real browser interaction on the receiving host. |
| [Air-gap acceptance](AIRGAP_ACCEPTANCE.md) | Model/tool/task/session and failure-path checks before worker admission. |

## Develop and maintain a release

Read [Contributing](../CONTRIBUTING.md), [agent instructions](../AGENTS.md), [Releasing](RELEASING.md), [Security](../SECURITY.md), and the [changelog](../CHANGELOG.md). Runtime setup uses local or approved private sources; connected release preparation is a separate process.

The [rebuild guide](REBUILD.md), [offline coverage](OFFLINE_COVERAGE.md), and [builder validation](BUILDER_VALIDATION.md) describe source and build boundaries. The [r5 validation report](../provenance/r5/VALIDATION.json) separates real delivered-runtime checks from fixtures and receiving-host-only acceptance.

## Version and precedence

The current documentation targets `v0.1.2`, which explicitly materializes cached LFS data before local release verification and retains the source-archive correction from `v0.1.1`. The initial `v0.1.0` baseline and both patches use the same pinned `2026-11-20-r5` offline runtime payload; the earlier tags and their evidence remain unchanged. Names such as `r3`, `r4`, and `r5` in existing files identify the kit revisions and their evidence; they are not separate current setup entry points.

For a deployment, use the selected release's actual scripts, catalogs, manifests, and current lifecycle guide. Earlier revision notes explain history and do not override the current Claude-to-OMP boundary, private-source policy, or target-platform checks. Site-specific instructions and the operator's authorized scope remain authoritative.
