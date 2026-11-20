# Qualified native productivity payloads

This directory supplies real Linux x86-64 runtimes, pinned upstream source snapshots, selected source dependency closures, and qualification evidence for the r5 kit. `native-artifacts.json` is the installation contract. It does not install software by itself; the kit's hostctl transaction and private-first resolution policy remain authoritative.

## What is ready

| Component | Pinned selection | Native capability | Qualification |
|---|---|---|---|
| Worktrunk | 0.82.0 | Parallel Git worktrees, branch navigation, per-worktree agent execution | Created and listed a disposable worktree; verified its branch; removed it through Git after inspection |
| RTK | 1.2.1, OSS release asset | Compact command output and hook rewriting | Git status fixtures and successful/failing command execution; failure status 7 preserved |
| Zoekt | source commit 7b032f67ffad36d228a7f793ab90c3b1acd920c1 | Fast local repository indexing, symbol search, CLI and optional loopback web search | Five binaries compiled offline from vendor; actual Git index with mandatory Ctags; symbol and content queries; HTTP search |
| Universal Ctags | static nightly 2026.10.08, source 82494361bb3e7d4f7cf1d2bdc0d0e9001c926e45 | Local code symbol extraction | Python function extraction; Zoekt's interactive Ctags protocol and required-symbol analysis |
| Language services | Python/Pyright 1.1.414; TypeScript LS 6.1.0 with TypeScript 6.0.3; Bash 5.8.1; YAML 2.0.0; extracted VSCode services 4.10.0 | Local Python, JS/TS, Bash, YAML, JSON, HTML, CSS code understanding | Seven actual JSON-RPC initialize→document-open→hover→shutdown flows; fresh offline npm replay installed 81 packages |
| Trivy | 0.76.2 | Offline dependency vulnerability and local configuration checks | General vulnerability DB plus actual checks bundle; closed-proxy fixture found 6 vulnerabilities and 4 misconfigurations; first-user cache materialization succeeded |
| Go SDK | 1.27.4 | Native compiler, standard library source, gofmt, offline Zoekt rebuild | Official archive SHA matched published metadata; compiled Zoekt using this exact SDK |

TypeScript 7.0.2 was tested and rejected for this bundle: its server layout did not initialize with the chosen typescript-language-server. The compatible TypeScript 6.0.3 source tag resolves to the same commit advertised by its npm metadata. A newer version is not automatically a working upgrade.

## Install and resolve tools correctly

Use a compatible, verified private package or artifact first. Use these kit runtimes when an internal candidate is missing or insufficient. Preserve the actual machine's hooks, brain, skills, model endpoints, authentication, proxy settings and package ownership. The payloads do not overwrite these settings.

System package ownership determines the installation method. Upgrade distro-owned files such as `/usr/bin/*` through that distribution's package manager. Standalone tools belong in the kit's managed version directories with verified command promotion, normally through `/usr/local/bin/agentic-*` and any separately approved canonical aliases. Do not move an interpreter executable alone or delete a managed package directory just because its path looks unusual. Inspect the interpreter's standard library, extension modules, dynamic libraries, shebang consumers and package owner before migration. The parent kit's transaction gates determine switching and cleanup; none of these payloads bypass those gates.

All paths in the manifest are relative to this directory. The archive prefix is explicit. The runtimes are relocatable. Language launchers choose explicit `AGENTIC_NODE`, then `agentic-node` in PATH, then `node`; Node>=22.22.2 is required, and the kit's Node 24.22.3 was used for qualification. Universal Ctags is inside the Zoekt tree at `bin/universal-ctags`. The indexer wrappers select this local executable unless `CTAGS_COMMAND` already names an explicit private alternative.

The binaries for Worktrunk, RTK, Ctags, Zoekt, Trivy and Go are statically linked; the `file`/Go build metadata checks found no dependency on host glibc symbols. Shell wrappers still require normal Linux shell/coreutils. Worktrunk needs Git>=2.43. Zoekt and Trivy are GOAMD64=v1. This is a Linux x86-64 delivery; there are no ARM64 binaries, no claim of support for every Linux kernel, and no target-machine qualification yet.

## Immutable runtimes and external state

Executable prefixes are immutable after staging. Worktrees, indexes, caches and working files are created outside the runtime tree. No setup step changes your Git config or runs Worktrunk shell integration automatically.

Zoekt indexes should live in a project or machine work directory such as `$XDG_CACHE_HOME/agentic/zoekt/<project>`, with write access for the user who refreshes them. Start a web UI only if wanted; bind loopback by default. Indexes are disposable build products and should be refreshed after a meaningful worktree change. They are a search accelerator, not the task coordinator or source of truth. Ctags errors can be made fatal with `-require_ctags`; this was enabled during qualification.

The Trivy wrapper seeds a missing user cache from `share/trivy-cache`, defaults to `$XDG_CACHE_HOME/agentic/trivy` or `$HOME/.cache/agentic/trivy`, and honors an explicit `TRIVY_CACHE_DIR`. Existing private cache content takes precedence. It never writes into the installed prefix. A first cache seed requires about 1.7 GiB additional disk unless reflinks are supported. Database and policy timestamps/hashes are in the manifest. Updates, release checks and API-based dependency discovery are disabled by default. The default image source list is local Docker/Podman, with no registry fallback. Local image tar files can be scanned with `image --input`.

The Java class-to-Maven lookup index is not included. Do not advertise Java binary discovery as qualified. The included general DB can match vulnerabilities for dependencies already identified from supported lockfiles or SBOMs. The dated snapshot is not live vulnerability intelligence; reuse the organization's existing private refresh process. This kit adds no monitoring, telemetry or backup service.

## Source and rebuild coverage

Each upstream source archive contains the repository's tracked tree at a recorded commit, including its checked-in docs, license texts and lockfiles. These are source snapshots, not complete Git history or every submodule/LFS object by implication. Installed npm packages also preserve their distributed license texts and their complete installed runtime files.

* **Zoekt:** the source-vendor archive contains the complete Go vendor tree for the selected source. Five binaries were built with `GOTOOLCHAIN=local CGO_ENABLED=0 GOAMD64=v1 GOPROXY=off GOSUMDB=off`, an empty Go module cache, `-mod=vendor -buildvcs=false -trimpath -ldflags=-s`, and the included Go 1.27.4 SDK. `rebuild-zoekt.sh` replays the same build flags. It produces binaries in a caller-selected output directory; it does not promote them over an installed version.
* **Worktrunk:** the source-vendor archive contains 498 registry crates pinned by Cargo.lock. Every vendored file was checked against its Cargo checksum manifest and every package checksum against the lock. Rust>=1.98 is declared upstream. The parent kit's Rust 1.99.1 meets that version requirement. Compiler/linker/toolchain qualification for a full rebuild remains separate; the runtime supplied here is the official musl release.
* **RTK OSS:** the source-vendor archive contains 339 locked registry crates with the same full checksum validation. The official runtime asset is `rtk-oss-...`, not the default full edition. A rebuild must select the `rtk` package with `--no-default-features`. The complete official source snapshot includes separately licensed BUSL engine/proxy directories; those are not linked into the OSS binary. Read their individual license files before modifying or redistributing a different edition. The proxy workspace and its separate dependency graph are not certified by this payload.
* **Language servers:** the installed node_modules tree, exact package-lock, and npm cache support a fresh `npm ci --offline --ignore-scripts --no-audit --no-fund` for this Linux runtime. This replay was executed successfully. Source snapshots are included for all six top-level package projects. Their entire upstream development, website, test, and release pipelines are not all cached. The extracted package includes optional ESLint/Markdown servers as upstream extras; they are not part of the seven-server protocol qualification. ESLint still needs the project's compatible ESLint dependency.
* **Universal Ctags:** the static official nightly binary includes JSON and interactive modes used by Zoekt. Its exact source and upstream receipt-matched libiconv, Jansson, libxml2, libyaml and zlib source archives are included. Build recipes and transitive license metadata ship in `share/doc/universal-ctags/build-provenance`. A clean Ctags compiler/toolchain rebuild was not executed.
* **Trivy:** the official static runtime, full source snapshot, real vulnerability DB and checks content are included. The full Trivy compiler/Go module graph is not vendored in this addon. The supplied executable runs offline and was exercised; arbitrary source rebuilds are a separate coverage limit.
* **Go:** the official SDK includes standard library/compiler sources under `go/src` plus licensing. An arbitrary project's dependencies must still come from its private registry or project-specific vendor/lock closure.

These limits distinguish installed runtime completeness from universal source-build completeness. Do not tell an internal agent that every arbitrary project's dependencies, external service, model, browser and build graph is included merely because these tools are present.

## Language-server client configuration

Run `pyright-langserver --stdio`, `typescript-language-server --stdio`, `bash-language-server start`, `yaml-language-server --stdio`, or the JSON/HTML/CSS server with `--stdio`. These are stdio LSP servers; an agent host/editor still needs a compatible client integration. Do not pretend that exposing a CLI automatically makes all agents use that capability.

Disable public schema-store fetches and automatic TypeScript typing acquisition in the relevant client/server initialization settings. Preserve internal schema URLs and project configuration. `client-config.example.json` inside the runtime is illustrative; actual client schemas differ. Bash's optional ShellCheck/shfmt integration uses installed tools. Python analysis uses project-provided interpreters/stubs; a type checker is not a Python runtime or package resolver.

## Evidence and files to retain

`validation/` contains real outputs and machine-readable outcomes. `metadata/` preserves release/API provenance and source identities. `artifacts/` contains ready-to-install runtime trees and separate source/cache closures; `sources/` has original commit snapshots and Ctags dependency sources; `downloads/` preserves original release assets including the Go SDK. `SHA256SUMS` covers retained delivery files. Ignore the transient `build/` staging directory when integrating the kit; it is deliberately removed after archive verification to avoid shipping duplicate caches and source trees.

This addon introduces no global hook rewrites and no independent orchestrator. Let the parent kit choose which workflows use Worktrunk, Zoekt, RTK and language services, retain existing successful behavior, and qualify the real machine before declaring the upgrade complete.

`build-tools/` retains connected assembly helpers for maintainers. They are not part of offline target installation and must not be invoked automatically on a disconnected machine.
