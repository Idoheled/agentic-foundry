# Phase 1 — Claude upgrades OMP and hands control back to the user

**Command paths:** examples written as `./upgrade.sh` or `python3 scripts/...` are relative to the extracted kit. When the agent's working directory is the user's project, invoke the corresponding absolute kit paths. Preserve the recorded project working directory for model/profile checks; do not globally change to the kit directory.


## Your assignment

You are the user's existing Claude Code agent, running against the already configured disconnected model route. Complete **only the OMP upgrade and its qualification**. Preserve Claude as the working installer and recovery path. After a successful OMP upgrade, write the durable handoff and stop. The user will deliberately switch to the upgraded OMP for phase 2.

The user authorized unattended execution of this bounded phase, necessary inspected OMP replacement, canonical command promotion, verification, and retirement of the exact obsolete unmanaged active copy after consumer checks. Do not ask again for routine installation permission. Do not invent missing privileges, credentials, artifacts, or successful checks.

Read `START_HERE.md`, `docs/TWO_PHASE_UPGRADE.md`, `docs/HOST_LAYOUT_AND_MIGRATION.md`, `docs/NATIVE_OFFLINE_SETTINGS.md`, `docs/OFFLINE_COVERAGE.md`, and the actual phase controller help. The two-phase ordering in these instructions takes priority over older instructions that describe installing the entire stack in one run.

**Stop boundary:** phase 1 must not install or upgrade Claude, Codex, OpenCode, Paperclip, PostgreSQL, Herdr, the shared skill/hook profile bundle, or unrelated language toolchains. Install a prerequisite only when the selected OMP upgrade actually needs it, after identifying the dependency and preserving its existing consumers. Do not run the broad `install-all.sh` workflow during this phase. A short OMP acceptance invocation is allowed; starting the remaining installation in OMP is not.

## 1. Establish the existing working state

Work as the real operator. Record the selected user, home, shell, effective PATH, invocation context and phase-state directory. Identify the existing Claude executable, launcher, profile and internal route without printing credential values. Keep that installation, route, model settings, brain instructions, skills and hooks unchanged during phase 1.

Inspect all ways the user actually launches OMP: aliases or shell functions, PATH commands, absolute-path launchers, service commands, named profiles, and relevant project wrappers. Record `type -a`, `command -v`, literal and resolved links, ownership, package-manager ownership, version and hashes. Inspect scoped consumers before deciding that an unusual path is obsolete; tool-manager shims, virtual environments and project-specific versions can be intentional.

Discover the current profile using the current working binary, documented environment and existing configuration before invoking the new client. In the pinned OMP source, even the `config` command family initializes settings; `config path` is not a guaranteed read-only migration-free probe. Do not call a new binary's configuration commands against the live profile before preservation and rehearsal. Avoid configuration getters that print secret values.

Identify OMP's **actual active agent directory and named profile**. Preserve `PI_CODING_AGENT_DIR`, applicable profile selectors, role/model mappings and native-module choices. Do not silently use a fresh default profile because it is easier to configure. The host wrapper and the container wrapper serve different environments; a host `omp` command must not be pointed at the container profile wrapper.

Discover and privately preserve the operator's existing configuration before changing tools:

- OMP, Claude, Codex and OpenCode model/provider configuration, authentication source, internal CA/proxy settings and effective configuration overrides, including any engines already present but not being upgraded yet.
- Existing skills, hook definitions and implementations, plugin/extension registrations, custom commands, permissions, role definitions and helper-model settings.
- Existing brain/instruction sources: global and scoped `AGENTS.md`/`CLAUDE.md`, custom system prompts, memory or knowledge files, role instructions, project-level instructions, and externally referenced files discovered from actual configuration.
- Session/history storage, profile selection and the relevant currently running processes. Session history is living state: preserve it and its compatibility, but do not treat legitimate append-only activity as an instruction-file replacement.
- Existing private package/OCI/source repository configuration, including JFrog Artifactory when configured. Use the existing trust and authentication mechanism.

Use the delivered preservation helper for the explicitly inventoried roots and environment names. Store raw backups, where required, only in private operator-owned state with restrictive permissions. Do not put credential values, complete configuration dumps or private project content in the handoff. Extend the inventory to external symlink targets and referenced instruction/configuration files that the helper does not automatically follow. Record those limits explicitly.

The automatic inventory cannot discover an unknown custom brain directory merely from its name. Read effective configuration and the user's existing workspace instructions to locate such state before declaring the preservation baseline complete.

Complete the flow plan's `preservationPlan`, `ompContext` and factual evidence, then run `./upgrade.sh begin --state ABS --plan FLOW_PLAN`. Preserve the original working directory and any explicit profile arguments. All phase operations must use this same state. Read the delivered example and helper schema instead of guessing field names.

## 2. Select and install the OMP upgrade

Verify the kit's manifest and required payload hashes. Use this source order:

1. Reuse the current installation if it already meets the selected, verified upgrade target and capabilities.
2. Prefer a sufficient approved internal OMP package, release artifact, source mirror or assembled dependency closure.
3. Use the verified kit OMP runtime only after recording why internal supply is unavailable, incompatible or insufficient.

There is no public registry, public model or public download fallback. A different internal filename or packaging layout does not make the internal artifact insufficient.

The kit's managed OMP is `19.0.1-offline.1`, identified separately from pristine upstream. Read its included change and compatibility information. A suitable newer internal release must not be downgraded merely to match that string. Record the actual selected source, version, hash, required native module, CPU compatibility and declared dependencies.

Create a **phase-1 host plan restricted to OMP** and the exact prerequisite work justified above. Use the shipped host provisioner, not an ad hoc binary copy. For a package-managed OMP installation, use its supported native package workflow and preserve its configuration. For a standalone installation, stage its complete runtime under the selected versioned tool prefix and keep adjacent native resources together.

Before invoking the live installer below, stage the exact selected candidate in an owned rehearsal location, run it against an isolated private profile copy, and record the `profile-rehearsal` gate with the exact candidate artifact in its `evidenceFiles`. The controller requires that gate before any live installer probe.

Use `./upgrade.sh install-omp --state ABS --site PHASE1_SITE` for the restricted site plan. A prerequisite outside that helper's supported bounded scope must be separately inspected and recorded; do not add unrelated tools to make the broad coordinator run.

Run the staged runtime from its final location before promotion. Confirm the loader/native-module requirements, basic CLI behavior and the selected offline wrapper. Preserve the current working native profile; do not replace `config.yml`, `models.yml`, auth files or a brain directory with the kit examples. If the new release requires a schema migration, make the smallest documented structural migration, retain every prior semantic setting, record the before/after identity and verify the effective values. An unsupported migration blocks completion; it is not permission to start from defaults.

Rehearse the selected release against an isolated, private copy of the relevant profile before allowing a client with automatic configuration migration to write the live profile. Record any file or semantic changes, preserve references needed for the same internal route, and use the pinned native migration behavior. A copied profile alone does not establish compatibility: run the real new client against it and inspect the result. The rehearsal must not create another live process on the user's active session or mutate an external symlink target shared with the original profile.

Record the `profile-rehearsal` gate before `install-omp`. Its generated proof must bind the exact selected OMP package/archive or reused executable in `evidenceFiles`, using the inspected absolute path and SHA256. This prevents a rehearsal of one artifact from authorizing the live installation of another. Read the current unique-token proof contract in `TWO_PHASE_UPGRADE.md`; an old JSON “pass” file is insufficient.

Promote the inspected canonical OMP entry point so the user's intended `omp` command resolves to the selected upgrade. Clear only the applicable shell command cache and test from a fresh shell with the real operator environment. A working `agentic-omp` alongside an unchanged old `omp` is not a completed canonical upgrade unless the operator's actual invocation deliberately uses the namespaced command and the receipt states that selection.

## 3. Prove the upgraded OMP works in the actual environment

Run bounded, reversible canaries in a separate temporary repository/worktree. Keep ordinary workloads and production branches untouched. Capture sanitized evidence and exit status for each check; version output alone does not pass this phase.

Required acceptance:

1. **Identity and resolution:** fresh-shell resolution, selected canonical entry point, immutable runtime identity, actual version and required native resources agree with the installation receipt.
2. **Preservation:** the existing active profile, brain/instruction sources, hooks, skills, plugin/extension configuration and internal route/auth source survive. Review every allowed configuration difference. Legitimate history/log additions are recorded separately.
3. **Real internal model:** the upgraded client completes a request against the same intended internal service and model role. Confirm no public fallback, authentication substitution, CA bypass or unrequested provider change occurred.
4. **Structured tool loop:** OMP reads a known canary file, makes a bounded change in the canary directory, runs a deterministic local check and interprets its result. Verify the resulting files yourself.
5. **Existing custom capabilities:** native discovery lists or loads the prior skills/extensions without new load errors; exercise a representative existing skill and each critical existing lifecycle hook. Check actual hook evidence and profile paths. Do not suppress a failing custom hook to obtain a pass.
6. **Brain/instruction continuity:** establish that the same relevant instruction files and configured roles are loaded. Use a harmless canary instruction when needed, then remove only that canary addition. Do not ask a model to disclose private instruction text as a test.
7. **Durable session behavior:** save and resume a dedicated canary session across a fresh OMP process; verify canary context and a subsequent tool operation. Verify cancellation and clean restart. Preserve prior real sessions without concurrently opening the same live session or deleting unexplained lock files.
8. **Consumer checks:** test the actual intended launch paths and scoped services/scripts that previously depended on the old OMP location. A background process still using the old binary is a retirement constraint to handle deliberately.

Record the required command checks using `./upgrade.sh record-check --state ABS --phase omp --name GATE --spec CHECK_JSON`. The fixed gates are `profile-rehearsal`, `internal-model`, `tool-roundtrip`, `session-resume`, `existing-skills-hooks-brain` and `canonical-command`. Map the detailed checks above into those gates and retain their concrete proof artifacts. Use actual internal-model calls and independently inspect the canary outputs; a script that merely writes a “pass” file is not an acceptance test.

Only after the replacement and consumer checks pass, retire the exact superseded unmanaged active file/link using the provisioner's receipt-bound quarantine operation. Verify canonical resolution and run a final bounded canary again. Keep the recovery copy and prior configuration available. Package-managed old versions are removed or replaced through their package manager. Do not recursively delete shared runtime directories or discard session stores.

## 4. Commit the phase-1 checkpoint and stop

Use the phase controller to record completion only when every required gate is supported by actual evidence. The checkpoint and handoff must identify:

- The kit revision/digest and phase-state location.
- The installed OMP runtime and canonical entry point, resolved path, version and hashes.
- The real operator, effective agent directory and named-profile selection.
- The host installation receipt, private-source decisions, preservation baseline and after-check report.
- Sanitized internal provider/model identifiers and credential-source **names/types**, without secret values.
- The actual model/tool/skill/hook/session tests, their evidence locations and outcomes.
- Every allowed configuration migration, retired active path, quarantine location and rollback reference.
- The exact remaining phase-2 scope, any independent blockers, and a safe command for the user to launch the upgraded OMP into the next phase.

Write the secret-free OMP handoff to the phase controller's reported path. Keep supporting evidence and any secret-bearing backups private. The handoff is a durable record on disk, not only text in this Claude conversation.

Complete the factual acceptance JSON, including the real-internal-endpoint and preserved-existing-configuration assertions and the actual old-tool disposition, then run `./upgrade.sh complete-omp --state ABS --evidence ACCEPTANCE_JSON`. This validates recorded phase evidence and writes the durable `OMP_HANDOFF.md`; it must not automatically launch the next agent. Use `./upgrade.sh status --state ABS` to inspect the resulting state and copy its actual continuation command into the final message.

The final Claude message must say, in substance:

> Phase 1 complete: OMP is upgraded and passed the recorded internal-route, tool, profile and session checks. Your existing configuration is preserved. The phase-2 handoff is ready at the reported path. End this Claude run, then use the printed command to continue in the upgraded OMP.

Use the observed version and paths. Do not say “works perfectly” or imply tests that were not performed. **Stop after this message. Do not launch phase 2, continue installing the other clients, or send work to another agent to bypass the user's switch.**

## Failure and recovery

If a required check fails, leave phase 1 blocked, preserve evidence and do not issue a success handoff. Restore the prior command/profile through the recorded recovery mechanism when needed to keep the operator working. Keep Claude usable. Correct a scoped, understood problem and rerun the failed checks; do not hide a failing hook, reset model configuration, disable TLS checks, delete history or substitute a public endpoint.

A missing privilege, incompatible model protocol, unavailable required dependency, unsupported host or unresolved consumer is a concrete blocker. Report its exact effect and the recovery state. Independent read-only diagnosis may continue, but phase 2 must remain unavailable until phase 1's required gates pass.
