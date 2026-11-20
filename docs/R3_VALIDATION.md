# Revision r3: what was actually verified

This report accompanies `provenance/r3/VALIDATION.json`. These are builder results, dated 20 November 2026. No access to the user's Linux machine, private repositories or real internal model service was available.

## Actual artifact installation and execution

| Check | Observed result |
| --- | --- |
| Host catalog installation | All **19** selected tool/asset trees were installed from their actual delivered archives into isolated user-owned workspace prefixes. |
| Managed commands | All **32** declared command entry points passed their probes, including fresh-shell resolution and complete-tree identity checks. |
| Python closure | Required SSL, SQLite, ctypes, venv, pytest, mypy, YAML and build imports passed. A real pytest test with coverage, a mypy check and a Ruff check passed using the installed runtime. |
| JavaScript closure | Node and Bun each ran a builtin-crypto canary from their installed paths. npm/npx/pnpm version probes passed with the matching Node tree. |
| Rust closure | The installed Rust 1.99.1 tree compiled and ran a canary after relocation. This uses the builder's existing native linker; it is not an actual Debian package-installation test. |
| Zig closure | The installed Zig 0.16.0 tree compiled a C canary for x86-64 Linux musl and the executable ran. |
| Native host profiles | The actual installed Python and permanent profile assets performed check/apply/check for all three clients: **24 shared skill copies**, **27 native files changed**. Existing synthetic Claude model/environment settings were preserved. |
| Codex hook activation | The actual installed Codex approved exactly **four reviewed kit definitions** through `hooks/list` and `config/batchWrite`; its report records them as trusted. |
| Complete client staging | Codex, Claude, Python and native-profile trees were copied into marked core state and their full identities verified. Exact immutable container paths were reported. No Docker execution was performed by this check. |
| Final integrity | Installed tool identities and declared commands were checked again after the canaries and native profile installation; they passed. |
| Local native repository | The actual APT helper resolved/simulated the **21-package requested baseline** against the included **275-package** Debian 13 repository. Global APT sources were not changed, and no native package transaction was applied. |

The raw host receipt, final checks, nine canary checks, native profile receipt, Codex activation report, staging report and APT simulation are under `provenance/r3/`. Builder absolute paths in those receipts describe the test installation; the receiving agent must produce its own receipt paths on the target.

## Focused code and recovery tests

The current kit's unittest suite passed **59 tests**, covering the runtime controller and private artifact policy, host installation/migration, native package policy, client staging and installation coordination. The tests cover such concrete risks as changed/uninspected command occupants, package-owned paths, unsafe archives/links, additive configuration, receipt binding, private-source selection, failed-stage behavior, recovery and use of the selected internal Docker client during backup.

The native profile project's separate suite passed **11 Python tests**, plus the OMP native module test. The update package's separate suite passed **18 synthetic integration/recovery tests**, including actual added-file publication, immutable old payloads, conflicts, idempotence and recovery after abrupt process termination.

The coordinator's seven focused sequence tests use mocked child installers, plus a real read-only wrapper invocation. The actual payload, native profile and staging checks above exercised their real helpers separately. This is not a claim that the entire production coordinator/Docker/model workflow ran on the builder.

System-mode sudo and actual native package transactions were not tested against a customer host. Migration/quarantine/rollback tests use owned fixture executables and fake system prefixes; the real target's existing tool consumers must still be inspected.

## Native engine checks

The supplied Claude Code and OMP CLIs each completed a deterministic local provider-fixture loop in their component validation. Both discovered all eight shared skills, included the hook context and emitted SessionStart, Stop and SessionEnd events. These fixtures exercise the client/profile mechanism, not the quality or protocol completeness of the customer's model.

Codex's native handler outputs were checked against the pinned schemas. Its actual supported hook inventory/trust API passed initial activation, idempotent reapplication and preservation of an unrelated untrusted hook. Rollback restored the previous hook definitions. A **full Codex model/tool/hook turn did not pass on this builder**: bwrap was denied a `NETLINK_ROUTE` socket before any provider request. The sandbox was not bypassed to manufacture a passing result.

The pinned Paperclip source was reviewed for native CLI selection, permission flags, credentials and generated profile behavior. Native examples explicitly choose the reviewed legacy/CLI path. Paperclip's generated Codex home does not automatically inherit `hooks.json`/`models.json`; the delivered integration guide describes the required actual-home preparation and verification. That integration remains a receiving-host gate, not an implemented and qualified automatic bridge.

## Source and artifact checks

Codex's official package digest matched the release asset digest. Its full pinned source, 1,305 registry crate archives and ten Git snapshots were acquired and checked; the resulting 1,493-package dependency graph resolved with offline locked Cargo metadata. The matching installed Rust tree, GNU/musl libraries, standard-library source and pinned V8 inputs are included. A complete Codex native release compilation was not performed.

The Claude release archive checksums matched the official list. The detached signature and Codex Sigstore bundle are retained, but independent cryptographic signature verification is not claimed. Claude's unpublished proprietary runtime implementation cannot be supplied by its public repository. Full public repository snapshots and native profile source/bundles are included.

All 16 Python quality wheel artifacts and matching source distributions were acquired with recorded hashes. The helper-tool releases and pinned tracked sources have per-component provenance. The outer kit checksum manifest covers every regular file except the top-level checksum file itself; archive-level checksums are delivered alongside the archive.

## Required target acceptance

Complete the handoff and `AIRGAP_ACCEPTANCE.md` on the actual machine. Required gates include the real container daemon/services, internal model API and structured tool loop, native worker effective profiles/hooks, OMP durable sessions, multi-project worktrees, independent review, cancellation, restart, backup restore and observed resource limits. The machine's native packages, PATH consumers and credentials are site-specific inputs.

The main profile is Linux x86-64, with x86-64-v2 required for the selected OMP baseline and Debian 13 amd64 for kit native packages. The archive cannot establish universal Linux/ARM compatibility, supply unknown private-project dependencies or guarantee perfect model output. `OFFLINE_COVERAGE.md` records the exact runtime/source-build boundaries and the pre-existing optional Herdr source gap.
