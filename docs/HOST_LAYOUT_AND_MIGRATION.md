# Install usable tools in the correct Linux locations

This is a required receiving-agent procedure, not an instruction to replace every executable. The user has authorized installation, necessary inspected replacements, command rewiring and removal of superseded active copies. Continue autonomously within that scope. A path that looks unusual is evidence to investigate; it is not proof that its installation is broken.

## Installation ownership determines the destination

| Component | Correct destination and installation method |
| --- | --- |
| Distro-managed executables | Install the approved native package with the distro package manager. It owns `/usr/bin`, `/bin` and its configured alternatives. Do not overwrite its files with `cp` or an unmanaged symlink. |
| Distro-managed libraries, headers and loaders | Keep the package's architecture-specific `/usr/lib`, `/lib`, include and loader layout. Resolve missing libraries with matching native packages. Never copy an arbitrary `.so` into a global library directory or replace the dynamic loader. |
| Standalone runtimes and toolchains | Install the **complete tree** into `/opt/agentic-stack/tools/<tool>/<version>-<hash>`. Keep Python's standard library and extension modules, Node's npm/pnpm trees, Rust's target libraries, Zig's library tree and Codex's helper resources together. |
| Managed command entry points | `/usr/local/bin/agentic-<command>` always identifies the selected managed command. Create or repoint `/usr/local/bin/<command>` only after inspecting its current occupant and the PATH/service resolution that will use it. |
| Python project libraries | Use the intended project's `.venv` or an explicit versioned virtual environment; install from the approved internal index or the supplied wheelhouse with hashes. The quality runtime's bundled libraries remain inside its own `lib/python3.12/site-packages`. Libraries do **not** belong in `/usr/bin`. |
| Node project libraries | Use that project's locked `node_modules` and the approved package store. Keep npm/pnpm coupled to their selected Node. Avoid an unrelated global npm install. The package store, cache and executable prefix are different paths. |
| Rust, Go, Java and other project libraries | Respect the language's configured package/module/cache conventions and project lockfiles. Reuse a functioning approved tool-manager installation. Install new standalone toolchains in versioned trees, with explicit project toolchain selection when multiple versions are required. |
| Container clients and Compose | Prefer the existing managed Docker/Podman installation where compatible. The kit supplies verified Docker/Compose fallback artifacts. An installed CLI does not imply a running compatible daemon; qualify the actual daemon separately. |
| Application state and model profiles | Use the actual operator/service account's native configuration and persistent state locations. Keep credentials private and outside source or immutable runtime trees. |
| Native skills and hooks | Use each client's supported profile directories, described in `CLAUDE_CODEX_OMP_NATIVE.md`. Shared handler assets live in the permanent versioned `native-profiles` tree, not in a temporary extraction directory. |

Explicit user mode uses the operator's `.local/share/agentic-stack/tools` and `.local/bin`. It is an available, deliberately selected alternative when appropriate, not a silent substitute for an authorized system installation. If system privilege is unavailable, finish independent work and report that exact capability gap.

## Private supply comes before the kit

Inspect existing package-manager configuration, approved private OS repositories, OCI registries, language indexes, source mirrors and caches using their existing credentials and CA trust. Record repository names, immutable identifiers, versions and factual outcomes without credentials. Do not scan unrelated private data.

Evaluate whether internal **components** can supply the capability. For example, an internal Python package plus internal pytest/mypy wheels may be sufficient even if no internal artifact has this kit's monolithic Python-runtime filename. Assemble and qualify a complete runtime or use appropriate native packages/virtual environments. Do not declare the internal repository insufficient merely because its packaging or version differs from this kit.

Source plans use `existing`, `internal`, or `kit` per tool. `kit` requires an actual reason: unavailable, incompatible or insufficient. The example plans deliberately contain rejected placeholders. The receiving agent must replace them with real findings before applying them. These scripts never fetch public alternatives on the destination.

## Correct a misplaced executable or stale symlink

1. **Identify what actually runs.** Record `type -a`, `command -v`, literal and resolved symlink targets, hashes, ownership, package-manager ownership, executable version, interpreter/loader and linked-library requirements. Check the user's shell, service account, scheduled jobs and containers that need it; they can have different PATHs.
2. **Determine its ownership and consumers.** Distinguish a package-managed file, a tool-manager installation, a virtual environment and an unmanaged standalone runtime. Search the scoped service/project configuration for references to the old path. Check relevant running processes and scheduled tasks. A valid virtual-environment interpreter pointing into its base runtime is not automatically misplaced.
3. **Select and stage the replacement.** Prefer suitable existing/internal supply. For a standalone runtime, migrate a complete qualified archive. For OS-owned files, use the native package manager or supported alternatives mechanism. Preserve the original configuration, source identity and a recoverable backup.
4. **Install before switching.** Run the new runtime's own commands and dependency probes from its final versioned location. Exercise a representative project import/build/test. Do not copy just a Python executable, `node`, `rustc`, a shared library or Codex's main binary and assume the missing adjacent tree is optional.
5. **Switch the inspected entry point.** The host plan's `canonicalLinks` records the exact old file hash or literal symlink target, owner and reason. The installer refuses changed, uninspected or package-owned occupants. Update only the reviewed shell/service/project consumers, preserving their previous values.
6. **Verify actual resolution.** Use a fresh shell and the real service/container environment. Record the command path, resolved executable, version, library/import checks and project canary. An interactive `hash -r` can clear a stale shell command cache; existing long-lived services may require a scoped restart.
7. **Retire the obsolete active copy.** Once replacement and consumer checks pass, use the receipt's explicit `retire` entries. The helper moves the exact unmanaged file or link out of the old active path into quarantine. The old active location is gone, while recovery remains possible. It never recursively removes an unknown shared runtime directory. A complete obsolete tree requires its own inspected inventory, proof that no retained consumer uses its libraries, verified backup and scoped removal; do not infer that proof from one executable test.
8. **Keep recovery usable.** Record the replacement, prior target, quarantined path and rollback command. Verify recovery on a harmless canary before retiring an important runtime. Later edits to managed files block automatic rollback rather than being overwritten.

The host provisioner implements artifact selection, complete-tree staging, checked entry-point promotion, identities, receipts, quarantine and rollback. The receiving agent supplies the contextual consumer inspection. It must not copy the example evidence strings into a real report.

## Use the shipped installers

Read `HOST_PROVISIONER.md`, `INSTALLATION_SEQUENCE.md` and the exact configuration examples. The central catalog is `config/host-catalog.json`; the private host plan is based on `config/host-plan.example.json`. The coordinator uses the same validated helpers, not a second implementation of file replacement.

The native package helper supports approved internal APT repositories on the configured matching Debian/Ubuntu target and the kit's exact **Debian 13 amd64** fallback repository. It simulates first, rejects removals, keeps existing conffiles and requires a recorded host recovery mechanism before an actual package transaction. The target agent must use that machine's approved native workflow for a different distro; Debian packages must not be force-installed into RPM, Alpine or a different Debian release.

`hostctl` keeps all 19 catalog trees available as choices. Select the capabilities required by this stack and the actual projects. When staging native clients into the Paperclip runtime, `codex`, `claude`, `python` and `native-profiles` must be complete qualified trees. A bare reused `/usr/bin/python3` is not a portable container runtime. A separate namespaced portable Python for those clients can coexist with an adequate OS Python without changing its canonical entry point.

The managed Python launchers disable bytecode writes into the immutable runtime and require virtual environments for pip installs. The Claude and OpenCode launchers apply their verified offline/update-discovery controls while preserving model and credential variables. The OMP host launcher preserves the chosen native profile and enables the pinned offline mode. Native model settings still require the actual internal endpoint and protocol; see `NATIVE_OFFLINE_SETTINGS.md`.

## What “complete” means on the receiving machine

The final capability report must list installed/reused tools, chosen internal/kit sources, resolved paths, versions, dependency checks, native profile locations, hook activation, retirement results, remaining blockers and rollback references. Check that `agentic-*` commands work from the operator's environment and that intentionally selected canonical commands resolve correctly. Do not report the machine as fully provisioned while a required tool is merely present inside the unopened kit.

The kit cannot infer every dependency of private projects it has never seen. Resolve their lockfiles and build/test requirements through private repositories, then retain any additional admitted artifacts in the site's own mirror. Report a concrete missing dependency if neither internal supply nor this kit contains it; do not replace it with a similarly named package or try a public registry.
