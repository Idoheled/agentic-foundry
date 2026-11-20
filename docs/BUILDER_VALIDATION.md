> Revision r3 adds the actual host/runtime/profile checks in `R3_VALIDATION.md` and `provenance/r3/VALIDATION.json`. The earlier evidence below retains its original scope.

# Builder integration validation — 20 November 2026

## Result and scope

A bounded integration test ran the delivered Paperclip image runtime with the delivered PostgreSQL image binary and the bundled OpenCode executable. It verified application readiness, the bootstrap API contracts, loading the patched OMP adapter, a real OpenCode local tool call and continuation, run recording, and persistence after a quiescent application restart. The model was a deterministic local HTTP fixture. This establishes concrete protocol and integration evidence; it does not qualify the receiving Linux host, its model, the full installer, or production operation.

## Environment adaptation that limits the result

The builder has no usable Docker daemon and restricts netlink metadata syscalls. Image contents were extracted into disposable root-filesystem copies and run in a user, mount and network namespace with only loopback enabled. The official archive bytes were left unchanged. Every image manifest/config/layer digest was independently checked. Extraction normalized ownership for the ordinary builder account, rewrote absolute symlinks to equivalent internal-relative targets, and added a temporary PostgreSQL passwd entry. Device/proc mounts and dedicated test data were provided locally. PostgreSQL used a fresh test password and TCP loopback with SCRAM authentication; Unix sockets were disabled for this test.

**The unmodified Paperclip startup did not pass in this builder.** It reached the database and applied migrations, then failed on `os.networkInterfaces()` with the builder's `EPERM` restriction. Its failure report is retained as `unmodified-result.json`.

For API and worker validation only, an explicitly test-only Node preload returned a fixed loopback interface description for that metadata call. It did not change security permissions or external networking. This fixture is not part of the production runtime. The passing test therefore must not be described as a Docker Compose test or unmodified-image startup qualification. External routing was unavailable in the test namespace.

## What ran

- Paperclip official image tag `2026.1117.0`; health reported commit `c0f132898d2a2677312d8c72096187b27a3d9a38` and version `0.3.1+0.git.c0f1328`.
- Actual PostgreSQL 17.12 binary from the delivered PostgreSQL 17 Alpine image.
- Bundled OpenCode `1.18.34` baseline executable, classic `opencode_local` adapter with `runner:legacy`.
- Downstream OMP adapter `0.7.0-offline.1`, installed from its local compiled payload. OMP execution itself was outside this test.
- A local OpenAI Chat Completions mock, streamed through the real OpenCode provider/tool path.

The test used the installer seed schema: local project workspace plus `executionWorkspacePolicy` with `isolated_workspace`, serialized shared workspace mode and a `git_worktree` strategy; an OpenCode agent with `instructionsFilePath`, `permissions.canCreateAgents:false`, and explicit heartbeat fields. Synthetic names, model ID and test instructions were used. A temporary `/opt/agentic` layout pointed to the delivered executable and adapter. This checks API contract compatibility; it does not validate final controller packaging, actual multi-project worktree realization or the substantive playbook content.

## Observed checks

| Check | Outcome |
| --- | --- |
| network_namespace_has_no_external_route | PASS |
| postgres_official_image_binary_boot | PASS |
| paperclip_official_runtime_health | PASS |
| company_create_api | PASS |
| project_create_api | PASS |
| compiled_omp_adapter_registration | PASS |
| legacy_opencode_agent_create | PASS |
| seed_task_scheduling_disabled | PASS |
| agent_lifecycle_verification | PASS |
| heartbeat_dispatch | PASS |
| opencode_integrated_mock_completion | PASS |
| opencode_real_bash_tool_roundtrip | PASS |
| control_plane_restart_persistence | PASS |
| scope_limit | PASS |

### Observable worker evidence

The lifecycle probe received `hello` and the agent reached `lifecycleState:ready`. A manual heartbeat then ran OpenCode. The synthetic model issued a structured `bash` tool call; the actual tool wrote the expected string to an isolated smoke-workspace file. OpenCode sent the tool result back to the mock and completed. Paperclip recorded `status:succeeded`, `exitCode:0`, JSONL worker output, token usage and a summary.

The application was stopped after completion and restarted using the same PostgreSQL database and Paperclip home. Health returned `status:ok` with `startupRecovery.phase:ready`; the original agent and succeeded run were still available. This was a quiescent restart, not an active-worker recovery test.

## API and operational findings

1. HTTP 200 from `/api/health` alone is insufficient: the initial response had `status:starting` and `startupRecovery.phase:recovering`. Readiness must wait for `status:ok` and recovery ready.
2. New-agent `adapterConfig.promptTemplate` is rejected by this release. The supported explicit `instructionsFilePath` form was accepted.
3. Creating an agent starts lifecycle verification, including a real model hello probe. `heartbeat.enabled:false` and `wakeOnDemand:false` suppress task scheduling, not these configuration probes.
4. A hello probe that returns unrelated text produces `harness_probe_unexpected_output` and can leave a requested run queued. This happened with the first mock fixture and was resolved by making the mock honor the actual hello-probe protocol; no production validation bypass was used.
5. The provided local compiled OMP adapter registered without npm or an external fetch. This is registration evidence, not OMP task qualification.

## Not established here

- The Docker daemon/Compose lifecycle, overlay2 bootstrap, target permissions, target CA or target operating-system compatibility.
- Any real internal model's reasoning, code quality, tool reliability, context limits or throughput.
- Responses or Anthropic Messages protocol integration; only Chat Completions was exercised.
- OMP persistent sessions and a Paperclip-dispatched OMP task.
- Real issue completion and independent code review, two-project concurrency/worktree isolation, nested-agent visibility, cancellation, model outage handling or active-worker recovery.
- Database backup restore or rollback.
- Browser UI rendering and interaction.
- A claim of zero attempted external connections across every optional subsystem.

Complete `AIRGAP_ACCEPTANCE.md` on the receiving host before ordinary task admission. Builder mock success must not be copied into the onsite report as a real-model pass.

## Evidence files

`result.json` contains the machine-readable check outcomes and readiness state. `run-detail.json` contains the complete synthetic run record and JSONL output. `paperclip-rootfs-integrity.json` and `postgres-rootfs-integrity.json` contain independent digest checks. `unmodified-result.json` records the pre-fixture startup failure. The test script is `research/integration/run_smoke.py` in the build workspace; any retained copy is a builder test harness, never a runtime dependency.

Only these selected reports should be included as deliverable evidence. The temporary root filesystems, test database/home, fixture payload and temporary signing material should not be packaged.

## Revision r2: private-first selection and path preservation

The application/image/source payload is unchanged. This revision changes the receiving-agent policy, source-selection input, controller selection/preservation behavior and bootstrap requirements.

- **23 focused tests passed:** 14 new source-policy/preservation tests and the 9 existing controller contract tests. Synthetic local artifacts and mocked Docker calls cover source selection, documented fallback requirements, image references, failure without automatic fallback, host-tool qualification, same-size changed binaries, backup, file/symlink preservation, and required bootstrap choices. The exact log and tested source hashes are in `provenance/r2-controller-tests.log` and `provenance/r2-controller-validation.json`.
- **8 actual-payload checks passed:** Docker client, Compose, OpenCode, OMP and Herdr version execution; actual Compose configuration parsing; repeated preparation preserving managed binary content/mtime; and all runtime file selections coming from the existing verified local builder cache. See `provenance/r2-controller-payload-test.json`.
- The source-policy fixture did **not** inspect the user's internal repositories. Image-reference tests did not contact a real private registry. No destination-host packages or global symlinks were changed, and no Docker-daemon deployment or real internal-model acceptance was performed in this revision.

The receiving agent must make real internal supply and compatibility decisions, install the required host capabilities, and complete target acceptance. A filled-in sourcing or qualification report is evidence for review, not an automatic assertion that the underlying checks happened.
