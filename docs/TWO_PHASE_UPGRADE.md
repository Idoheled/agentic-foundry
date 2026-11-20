# Two-phase native upgrade: Claude first, then OMP

**Command paths:** examples written as `./upgrade.sh` or `python3 scripts/...` are relative to the extracted kit. When the agent's working directory is the user's project, invoke the corresponding absolute kit paths. Preserve the recorded project working directory for model/profile checks; do not globally change to the kit directory.


Revision r4 adds the user's explicit transfer of control. Claude performs a bounded OMP upgrade. The upgraded OMP completes the remaining workspace only after the user starts the continuation.

## Order and responsibilities

| Phase | Executing agent | Authorized work | Required stopping point |
| --- | --- | --- | --- |
| 1 | Existing, working Claude Code | Inspect and preserve current state; select and install/reuse the qualified OMP upgrade; promote the intended command; test the actual internal route, tools, existing capabilities and durable sessions; retire the obsolete active OMP copy when supported by consumer evidence | Persist a passed checkpoint and secret-free OMP handoff, print the continuation command, then stop for the user's manual switch |
| 2 | The qualified upgraded OMP | Complete the remaining clients, native tools/dependencies, Paperclip/PostgreSQL, skills/hooks, model routing qualification, worker registration and whole-stack acceptance | Persist the final report and evidence; distinguish any blocked capability from completed work |

Claude must not run the full-stack coordinator during phase 1, upgrade itself, install the new shared native profile bundle, or start phase 2 automatically. Bounded OMP acceptance invocations are permitted within phase 1. They do not authorize an autonomous handoff past the user's requested boundary.

OMP in phase 2 must keep its own qualified runtime and effective profile stable while installing the other components. An unexpected need to upgrade OMP again requires a new controlled checkpoint and targeted verification.

## Starting and continuing

The phase launcher creates or uses a private state directory, supplies the appropriate complete handoff, and records where the durable evidence lives. Use the actual launcher help and the commands printed by the phase controller. Do not infer phase success from an agent's conversational claim.

Use an absolute path to the extracted kit when launching from the user's usual project/workspace. The launcher preserves the launch working directory; that matters for project instructions and profile selection. Do not change to an unrelated directory merely to make a command shorter.

Start phase 1 from the intended workspace:

```bash
/absolute/path/to/agentic-offline/upgrade.sh start-claude
```

The default state is the operator's `~/.local/state/agentic-stack/upgrade-r4`. An explicit `--state /absolute/private/state/path` selects another private state directory. Use the same state selection throughout both phases.

After Claude reports that the acceptance gates passed, end that Claude installation run. The user then starts the exact command printed in its handoff:

```bash
/absolute/path/to/agentic-offline/upgrade.sh start-omp \
  --state /absolute/private/state/path
```

Inspect status without launching either agent:

```bash
/absolute/path/to/agentic-offline/upgrade.sh status \
  --state /absolute/private/state/path
```

`launch-handoff.sh claude` and `launch-handoff.sh omp` delegate to these phase-specific launchers. The OMP launcher requires completed phase-1 evidence and uses the recorded absolute canonical command, profile arguments and working directory. It does not choose whichever unverified `omp` happens to appear first on a new PATH.

## Agent-facing phase operations

The receiving agents create factual plans and evidence from onsite inspection. These interfaces orchestrate the existing component helpers; they do not discover credentials or fabricate acceptance results:

| Operation | Purpose |
| --- | --- |
| `upgrade.sh begin --state ABS --plan FLOW_PLAN` | Record the inspected preservation plan, effective OMP context and evidence before mutation. |
| `upgrade.sh install-omp --state ABS --site PHASE1_SITE` | Execute the restricted OMP installation with the completed private-first site plan. |
| `upgrade.sh record-check --state ABS --phase omp --name GATE --spec CHECK_JSON` | Run and retain a required OMP acceptance command and its selected proof artifacts. |
| `upgrade.sh complete-omp --state ABS --evidence ACCEPTANCE_JSON` | Validate the phase-1 gates and identities, write `OMP_HANDOFF.md`, and finish at the manual-switch boundary. |
| `upgrade.sh install-rest --state ABS --site PHASE2_SITE` | Execute the remaining installation after the user enters phase 2. Focused `--only host`, `--only native` or `--only profiles` invocations support staged plan completion. |
| `upgrade.sh record-check --state ABS --phase stack --name GATE --spec CHECK_JSON` | Run and retain a remaining-stack acceptance command and proof artifacts. |
| `upgrade.sh complete-stack --state ABS --evidence ACCEPTANCE_JSON` | Check required final evidence and preservation, then write the final completion record. |

`ABS`, `FLOW_PLAN`, `PHASE1_SITE`, `PHASE2_SITE`, `CHECK_JSON`, `ACCEPTANCE_JSON` and `GATE` describe arguments; replace them with actual paths/names. Read the delivered examples and controller help for the exact schema. A check specification uses `schemaVersion: 1`, an absolute executable argument array in `argv`, an absolute `cwd`, bounded `timeoutSeconds` and a factual `purpose`. Keep secret values out of arguments and evidence summaries; commands inherit the approved credential environment.

OMP gate names are `profile-rehearsal`, `internal-model`, `tool-roundtrip`, `session-resume`, `existing-skills-hooks-brain` and `canonical-command`. Stack gate names are `native-tools`, `client-model-tool-loops`, `native-skills-hooks`, `orchestration`, `multi-project`, `recovery` and `canonical-commands`. Agent-written acceptance summaries supplement the recorded command evidence; they do not replace it.

The controller gives each check a fresh token and unique proof path through `AGENTIC_UPGRADE_PROBE_TOKEN` and `AGENTIC_UPGRADE_PROOF_PATH`. `AGENTIC_UPGRADE_PHASE` and `AGENTIC_UPGRADE_CHECK` identify the phase/gate. After the actual test passes and its outputs have been inspected, the check command writes a JSON proof to that exact path with `schemaVersion: 1`, `passed: true`, `runToken` copied from the supplied token, the supplied `phase` and `check`, and a nonempty `observations` array containing factual findings. Optional `evidenceFiles` entries contain the absolute `path` and actual `sha256` of retained evidence. The profile-rehearsal proof must include the exact selected OMP artifact, or the reused executable, among those bound files.

A successful exit code without the current unique proof does not pass. A stale token, another gate's proof, missing observations or changed bound evidence fails. The native proof mechanism records what actually ran; it cannot turn a script that merely writes “passed” into a valid model/tool test. Check implementations must execute the real required tests before writing success.

The phase acceptance document must contain `schemaVersion: 1`, `passed: true`, a factual `summary`, factual `oldToolDisposition`, `realInternalEndpoints: true`, `preservedExistingConfiguration: true`, and a passing factual finding under every required `checks.<gate>`. Set those assertions only after observing the corresponding target behavior. The command records, native runtime identity and preservation reports are independently required.

## What a native upgrade means

The final installed capability must work through the user's intended command and the actual service/project consumers. A new binary in a versioned directory is a staging result until those entry points resolve to it and the required checks pass.

Correct placement depends on ownership:

- OS packages own the distribution's executable/library layout and are upgraded through its package manager.
- Complete standalone runtimes live under the qualified versioned prefix, with inspected entry points in `/usr/local/bin` for a system installation.
- Libraries remain with their owning native package, runtime or project environment.
- Skills, hooks, configuration, brain/instruction files and sessions live in the correct native profile/state locations for the real operator or worker identity.

The ordinary sequence is **inspect → preserve → select private supply → stage → verify → promote → test consumers → retire the old active copy → verify again**. Suitable existing tools remain usable; a newer sufficient internal package is not downgraded to match the kit. Record the actual outcome.

Retirement removes the exact obsolete unmanaged file/link from its active path into recoverable quarantine. Backups and receipts remain available. Whole runtime trees need their own scoped inventory and proof that no retained consumer uses them. Package-owned files are handled by the package manager. The workflow does not blindly delete a directory because its name looks unusual.

## Preserve the user's current brain and routes

Both phases must preserve existing custom skills, hook behavior, brain/system/role instructions, memories, provider/model mappings, authentication sources, internal routes, CA/proxy settings, permissions, native profile selection and durable session storage. Phase 2 adds the kit's namespaced skills/hooks through the native installer.

Preservation has two parts:

1. **Data integrity:** private baseline snapshots/hashes, reviewed structural changes, exact-path ownership checks, backups, receipt-bound migration and change-aware recovery.
2. **Behavioral continuity:** actual native discovery, critical hook execution, correct instruction loading, internal model/tool requests, durable session resume, and fresh-shell/service command resolution.

A hash comparison alone cannot prove that the client uses the intended profile. A successful model reply alone cannot prove that prior skills, hooks or sessions survived. Both forms of evidence are required.

Discover actual configured roots and external references before snapshotting. The helper cannot infer unknown custom memory directories or credentials hidden in an external service. Keep secret-bearing snapshots in private state; expose only sanitized evidence paths and credential-source names in handoffs. Legitimate conversation/log growth is expected and must not be confused with destructive configuration changes.

## Evidence and resumability

The phase-1 checkpoint binds the kit identity, selected OMP executable/entry point, operator/profile, installation receipt, preservation evidence and required acceptance results. The durable handoff records remaining work without copying secrets. The phase-2 entry rechecks the qualified selection and blocks unexplained changes before further mutation.

Rerunning a blocked phase resumes from the recorded state and existing component receipts. It does not reset the machine or erase earlier evidence. A completed phase may be revalidated; it must not silently select a different active OMP or generate a fresh default profile.

The controller checks structure, identities and supplied evidence according to its implemented contract. The receiving agent remains responsible for executing real site-specific tests and judging their observed outcomes. A fabricated report cannot become genuine evidence merely because it is well-formed JSON.

## Failure boundaries

No phase may declare “perfect” or “everything works” without the corresponding observed checks. A missing required capability leaves the phase blocked or partially completed, with its reason recorded. Do not disable custom hooks, drop configuration keys, delete sessions, bypass certificate validation, switch to public model endpoints or discard safeguards to obtain a green status.

Use the preceding working agent/runtime and the component's recorded recovery mechanism where needed. Recovery must detect later user edits and avoid overwriting them. Keep native package recovery distinct from file/link rollback; package transactions do not have an invented universal undo.

The bundle's platform and source coverage remain as documented in `OFFLINE_COVERAGE.md`. This phase mechanism improves upgrade ordering, preservation and evidence; it does not create unknown project dependencies, credentials, compatible model protocols or universal hardware support.


## Final deletion after acceptance

`upgrade.sh complete-stack` commits immutable acceptance and then invokes exact receipt-bound retired-file cleanup for both host receipts. It archives the already-retired files into private verified rollback archives and deletes their individual quarantine objects. Package-owned old versions still use their package manager; unknown directories and old managed version trees are not recursively purged. The active old paths were already removed by retirement.

If cleanup is blocked, the accepted installation and cleanup status remain distinct. Inspect `upgrade.sh status --state ABS`, fix only the documented blocker, then run `upgrade.sh cleanup-old --state ABS`. Do not rerun retirement on already-purged receipts. See `FINAL_CLEANUP.md` for recovery.
