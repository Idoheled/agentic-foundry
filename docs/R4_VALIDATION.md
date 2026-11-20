# Revision r4 validation — 20 November 2026

Revision r4 changes the installation workflow while preserving the r3 executable/image/source/dependency payload. The builder did not access the user's machine, private repositories or actual internal model service.

## New builder checks

| Check | Observed result |
| --- | --- |
| Current kit suite | **150 passing tests**: 59 retained installer/controller tests, 42 phase-workflow tests, 35 preservation tests, 14 final-cleanup tests. |
| Update recovery suite | **18 passing tests**, using the same checked additive update/recovery implementation with r3→r4 revision identities. |
| Actual phase CLI | Real subprocess invocations of `begin`, `record-check`, `status` and premature `start-omp`; a unique local proof passed, an unexpected brain-file change blocked, and phase 2 could not start early. No actual host tools or internal model were used by this fixture. |
| Syntax/configuration | Current Python scripts parsed, shell wrappers passed `bash -n`, JSON configuration templates parsed. |
| Source/payload integrity | The packaging process retains all r3 payload records unchanged, inventories the complete final kit, verifies every tar member and emits an outer SHA256. Source and final archive reports are separately recorded. |

The phase tests execute real tiny proof commands while mocking expensive installers and some preservation callbacks. The preservation tests use actual temporary configurations, symlinks, backups and semantic evidence. Cleanup tests actually archive/delete/restore temporary retired executables and reject an observed live old executable. Timeout tests verify that a probe child ignoring TERM is no longer running after timeout. Printed 'model' passes in retained fixture logs refer to local test fixtures, not the user's provider.

## Concrete failures covered

- Broader phase-1 tool installation, early retirement or phase-2 OMP replacement is refused.
- Live installation requires a successful rehearsal bound to the exact selected OMP artifact.
- Missing, wrong, stale or unsuccessful proof files cannot pass a gate. A failed rerun invalidates prior success before execution.
- A changed source plan/catalog or unexpected installed OMP version leaves a failed attempted installation, rather than stale passing state.
- Canonical commands resolving to old/unqualified locations block completion.
- The manual OMP continuation retains its working directory/profile arguments and revalidates the complete runtime tree and phase-1 evidence.
- Final completion requires the remaining catalog, core installation and all three native client profiles, plus real onsite acceptance records.
- Existing routes, credentials, hooks, brain files, mode/ownership and external symlink targets cannot silently change. New files require exact review; native migrations need retained originals and source-bound equivalent semantic exports.
- Explicit reviewed timestamp/session/usage scalar metadata can change without invalidating configuration identity. Model/provider/auth/security/control values cannot use this exemption.
- Cleanup is possible only after final acceptance and exact receipt binding. It archives and deletes only declared quarantine file/link objects; it preserves later occupants and supports interrupted deletion/restore.

## What is still a target-machine gate

The real native package transactions, sudo policy, installed consumers, all internal model/tool/streaming/session behavior, actual existing custom skills/hooks/brains, Docker deployment, worker profiles, multi-project operation and backup recovery remain target acceptance. The handoff requires the agent to observe these results before declaring phase completion.

The preservation helper certifies the declared configuration scope. Discover every effective path and credential source, and use native consistent backups for live databases. A fabricated proof file is not genuine operational evidence merely because its JSON and hash are valid. The receiving agent must implement the tests, inspect results and record factual findings.

The original `R3_VALIDATION.md` and `OFFLINE_COVERAGE.md` remain accurate for delivered runtime binaries, dependency closure, platform limits and upstream source-build gaps. No new universal Linux support or unpublished source coverage is claimed.
