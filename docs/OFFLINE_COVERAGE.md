# Offline contents, source coverage and qualification boundaries

Revision r3 is an actual binary/source/dependency kit for a defined Linux profile. It is not a promise that every possible machine, private project, model protocol or upstream optional build can work without additional site information.

## Supported delivery profile

The main payload is Linux x86-64. The managed OMP baseline requires x86-64-v2 features. The native fallback package repository is Debian 13 amd64. Portable runtimes include their declared adjacent libraries/resources; the host still supplies a compatible kernel, dynamic loader where required, libc, shell utilities, permissions and container capabilities. Other compatible glibc distributions can reuse internal native dependencies and qualify the portable tools; they must not install the Debian 13 fallback repository blindly. ARM64, old x86 CPUs and a general musl desktop are not qualified by the main kit. Claude's additional musl archive is retained as a separately unqualified alternate.

The host catalog installs 19 selected runtime/tool/asset trees, including Codex, Claude Code, OMP, OpenCode, Herdr, complete Python quality and Node/pnpm environments, Bun, Rust, Zig, Docker/Compose, uv, Ruff, ripgrep, fd, jq, yq and native profile assets. OS tools and C/C++ dependencies are provisioned through the separate native package plan. See the generated `SOFTWARE_INVENTORY.md` and actual manifests for exact versions and filenames.

## What is present as real bytes

| Area | Included coverage |
| --- | --- |
| Control plane | Actual pinned Paperclip and PostgreSQL images, image/config/layer identities, upstream source snapshots and offline docs. |
| Existing worker stack | OpenCode and OMP executable distributions; original and separately identified offline OMP/adapter builds; source snapshots, patches and supplied dependency/build trees. |
| Codex | Complete official 0.171.0 Linux x86-64 package, helper executables, rg, bwrap, optional voice resources, licenses, pinned tracked source, official manual and schemas, config templates and source-preparation helper. |
| Codex Rust dependency graph | All 1,305 lockfile registry crate archives and 10 pinned Git snapshots supplying 14 packages. Offline resolution of the 1,493-package graph is tested. Matching Rust 1.99.1 distributions, installed relocatable toolchain, GNU/musl std, rust-src, compiler source and matching RustyV8 archive/bindings are present. |
| Claude Code | Official 2.1.329 glibc and musl release archives, publisher checksum list and detached signature, full published public repository snapshot, manuals and official skill/plugin reference snapshots. |
| Native profiles | All source for eight shared skills and native hooks/installers, complete Git bundle, native rendering and activation helpers, tests and validation evidence. Their runtime uses Python's standard library and the supplied OMP runtime; no additional pip/npm packages are needed. |
| Python quality environment | Complete Python 3.12.16 runtime, installed pytest/coverage/mypy/build/PyYAML tooling, all 16 pinned wheel files, exact source distributions and a hash-locked requirements file. |
| Other host tools | Full portable release packages, required runtime trees and pinned project sources for the supplied helpers. Node and pnpm are installed together. Rust and Zig retain their standard libraries. |
| OS dependencies | 275 Debian 13 amd64 binary packages, package metadata, SHA256 inventory and a generated local APT repository; this is a bounded native/build/runtime profile, not a full operating-system mirror. |
| Operation and recovery | Private-first plans, host installer, native package helper, profile installer, client staging, coordinator, handoff, migration/rollback guidance and acceptance procedures. |

The upstream project snapshots include the complete tracked tree at the pinned commit, including the shipped docs and license files. A snapshot does not contain every historical commit, issue, hosted website or Git LFS object unless explicitly recorded. Git bundles are supplied for the custom kit/profile projects and selected upstream projects; exact source coverage is indexed rather than inferred from a filename.

## Runtime completeness and rebuild completeness are different checks

The supplied application installation uses prebuilt executables, installed runtime trees and offline-importable images. It does not depend on compiling every upstream component from source.

The managed OMP and adapter offline builds were exercised. Codex's entire pinned Cargo dependency graph resolves offline, and its supplied installed Rust toolchain compiles a relocated canary. A complete Codex native release compilation was not performed. Full V8/Chromium bootstrap, full Rust/LLVM bootstrap and every optional upstream CI target are not certified. The small helper tools include pinned source snapshots and working prebuilt distributions; every transitive build-from-source toolchain for every helper is not separately mirrored. Native Debian packages include their distribution notices; this kit is not a complete Debian source archive.

**Claude Code's full executable implementation is proprietary and not published in the public claude-code repository.** The kit includes the available public source and actual official executable. It cannot provide an unpublished implementation or promise a source rebuild of that executable.

Herdr's optional source rebuild still has the recorded missing pinned Codeberg `translate-c` archive. Its complete working prebuilt binary is present. See `payload/dependencies/HERDR-ZIG-REBUILD-LIMITATION.md` for the exact missing source, identifiers and retained cache coverage.

Release asset digests and lockfile checksums were checked where recorded. Retained Sigstore or detached signature files are not labeled cryptographically verified unless the evidence explicitly says so. A local SHA256 proves correspondence with the delivered inventory, not independent publisher authenticity by itself.

## Site-specific inputs remain onsite

This archive does not contain the user's private Git repositories, model weights, internal endpoint credentials, internal CA secrets, private package contents or host operating system. The receiving agent must discover and reuse those existing services. Approved internal repository access is preferred and permitted in the disconnected environment; public internet access is unnecessary for the supplied runtime profile.

Codex requires a compatible **Responses** endpoint. Chat Completions compatibility alone is insufficient. Preserve the user's functioning Claude gateway and prove that the pinned client still works against it; arbitrary non-Claude models are not an officially supported Claude Code assumption. OMP and OpenCode have their own exact provider/tool/streaming contracts. A simple successful text reply is not evidence that tool calls and resumable agent work function.

The native host profile installer merges skills and hooks while preserving existing routing/authentication. Its success does not prove that Paperclip's generated per-agent homes contain those hooks. Codex's adapter generates managed homes and has explicit propagation/credential requirements described in `CODEX_PAPERCLIP_INTEGRATION.md`. Qualify those actual execution homes and native worker adapters before enabling them.

## Builder evidence and target acceptance

The consolidated r3 validation file records the actual host payload installation test, command/runtime checks, profile/hook probes, controller/helper tests and the exact checks not performed. Earlier r2 bounded integration evidence remains separately included.

The builder has no usable Docker-daemon deployment and cannot qualify the customer's actual internal models. Its Codex model-turn probe was blocked by bwrap's denied `NETLINK_ROUTE` request before reaching a provider. The sandbox was not bypassed to obtain a passing test. Native Codex hook schema and supported trust-API checks did pass. A real Codex model/tool/hook turn remains a target check.

Use `AIRGAP_ACCEPTANCE.md`, `CLAUDE_CODEX_OMP_NATIVE.md` and the receiving handoff to verify the actual Docker services, real model tool loops, OMP save/resume, generated worker profiles, multi-project worktrees, cancellation, restart and backup recovery. Record observable results and exact limitations. Installation reports do not evaluate their own truth.
