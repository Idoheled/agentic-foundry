# Offline development and rebuilding

## Source selection applies to builds too

Follow `PRIVATE_REPOSITORIES_AND_HOST_TOOLS.md` for every compiler, runtime, native library, package and cache below. Reuse suitable installed tools, then approved internal repositories; use kit inputs only with recorded fallback evidence. The commands below describe the supplied, pinned **kit fallback recipes**, not a reason to skip internal supply. Substitute a qualified internal copy/build where available and record its identity and compatibility tests. Internal networking is allowed for staged acquisition; the actual reproducibility test may then run without networking.

The bundled Debian 13 build packages belong to the matching disposable build environment. Do not install them blindly onto a different host distribution or replace host libc/Python to make the build work. Use that host's approved native packages or a compatible builder container. Preserve lockfiles and transitive dependency closure when choosing internal packages.


## Start with the supplied runtimes

The normal installation uses the supplied Paperclip and PostgreSQL images and the pinned worker binaries. **No source build is needed to install or operate that baseline.** Rebuild when you need a specific adaptation, a reviewed source fix, or a different runtime configuration.

The archive root is `agentic-offline/`. Paths below are relative to that root unless an example explicitly uses `/work` inside a development container. Keep this original kit intact. Make changes in a separate checkout and Git branch; produce a new local image or binary name and a new checksum record. Do not replace the kit's original images, source archives, patches or manifests in place.

Run the kit's checksum verification before extracting build inputs. Use the same local Docker daemon selected for installation; if the private daemon is in use, select its recorded Unix socket with `DOCKER_HOST`. A development build must not accidentally use a remote daemon or alter the running production instance.

## What is included

| Material | Location and purpose |
| --- | --- |
| Installed Paperclip application | The pinned Paperclip image contains `/app`, including source, compiled outputs and its installed `node_modules` tree. This is the practical starting point for an offline modification. |
| Pristine source | `payload/sources/` contains pinned complete source snapshots. Paperclip and the community OMP adapter also have Git bundles. The documentation snapshot is included; its separate full-history Git bundle is not required for development. |
| Paperclip source snapshot | `payload/sources/paperclip-c0f132898d2a.tar.gz`, based on release `v2026.1117.0`, commit `c0f132898d2a2677312d8c72096187b27a3d9a38`. |
| Paperclip documentation snapshot | `payload/sources/paperclip-docs-7a2663ad9662.tar.gz`, commit `7a2663ad9662915bb394d075be0a1b360b72297d`. |
| JavaScript tools | `payload/packages/node-v24.22.3-linux-x64.tar.xz` and `payload/packages/pnpm-9.15.4.tgz`. Paperclip specifies Node `>=24.11.0` and pnpm `9.15.4`. Worker Bun versions are recorded in the worker manifests. |
| Paperclip Rust toolchain | `payload/packages/rust-1.97.1-x86_64-unknown-linux-gnu.tar.xz`, matching the pinned Runner's `rust-toolchain.toml`. |
| Paperclip Rust sources | `payload/build-deps/paperclip-runner-rust-vendor.tar.gz`: all 333 registry packages from its Cargo lock, with licenses and Cargo directory-source checksums. The two workspace packages are in the Paperclip source. |
| Community adapter build cache | `payload/build-deps/paperclip-omp-adapter-npm-cache.tar.gz`: the original adapter lock's npm dependencies, including TypeScript development dependencies. |
| Integration patches | `payload/patches/`: the Paperclip OMP adapter patch and the separate OMP binary patch, recipes and tests. These are distinct modifications. |
| Native operating-system build packages | `payload/packages/debian13-amd64/`: captured Debian 13 packages and dependency material for GCC/libc development files, pkg-config, CMake, Clang, protobuf and musl tooling. Use the package manifest for the exact versions present. |
| Worker source and dependency inventory | `payload/manifests/worker-artifacts.json` and `payload/manifests/worker-dependencies.json`. These are the authority for exact archive names, toolchain versions, cache layouts and validation limits. |

Source archives alone are not dependency caches. Preserve the installed dependency tree copied from the image, and use the supplied caches for the components that have a verified clean offline installation path. Adding a new dependency or changing its version requires importing that dependency and its transitive closure separately.

## Obtain an editable Paperclip tree

After the image has been loaded, copy `/app` from a temporary, never-started container. This does not run the application, contact a model, or copy the production database.

```bash
# Run from the extracted agentic-offline directory.
TASK_KIT_ROOT="$(pwd -P)"
TASK_DEV_ROOT="$HOME/agentic-development/paperclip-2026.1117.0"
mkdir -p "$TASK_DEV_ROOT"
TASK_COPY_CONTAINER="$(docker create --network none agentic-offline/paperclip:2026.1117.0 true)"
docker cp "$TASK_COPY_CONTAINER:/app/." "$TASK_DEV_ROOT/"
docker rm "$TASK_COPY_CONTAINER"
```

If you want the retained history, clone the matching `.bundle` into a separate directory first, check out the pinned commit, then overlay the copied application tree while preserving `.git`. Inspect `git status` before committing. The image build may contain generated files and a lockfile resolved by the official build; **do not silently replace that lock with the pristine repository lock while retaining the image's dependencies.** Record any difference as part of the new build's provenance.

Read `AGENTS.md` and the relevant repository rules before editing. Make a branch for the adaptation. Keep project workspaces, production credentials and the production PostgreSQL volume outside this development checkout.

## Use a compatible offline build environment

The official Paperclip image is based on Debian 13 and Node 24. Its installed dependencies can include platform-specific binaries. The most reliable development environment is a disposable container based on that image, with the editable checkout mounted at `/work/paperclip` and the kit mounted read-only at `/kit`.

Use `--network none` for build and dependency-closure checks. Do not use the upstream Dockerfile unchanged: it contains online package installation and toolchain retrieval steps. Build a separate local builder image from the already-loaded Paperclip image, using only the supplied archives and `.deb` files. Use a Dockerfile without an external `# syntax=` frontend requirement, then invoke Docker with `--pull=false --network=none`.

Install Debian packages only into that disposable Debian 13 builder, not indiscriminately onto the host. A local package installation can use:

```bash
apt-get --no-download --yes install /kit/payload/packages/debian13-amd64/*.deb
```

This command does not update repository indexes or download missing packages. If it reports an unresolved dependency, stop and identify the missing package or version from the local manifests. Do not follow the error with an online repair command. The package set supports the supplied build workflows; it is not a certificate that every optional upstream build target or host distribution is covered.

Install the bundled pnpm package directly. **Do not rely on a first-use Corepack download.** Inside the builder, the following creates a launcher ahead of any Corepack shim:

```bash
mkdir -p /opt/offline-pnpm /opt/offline-bin
tar -xzf /kit/payload/packages/pnpm-9.15.4.tgz -C /opt/offline-pnpm
cat > /opt/offline-bin/pnpm <<'SH'
#!/bin/sh
exec node /opt/offline-pnpm/package/bin/pnpm.cjs "$@"
SH
chmod 0755 /opt/offline-bin/pnpm
export PATH="/opt/offline-bin:$PATH"
export NPM_CONFIG_OFFLINE=true
pnpm --version
```

Expected pnpm version: `9.15.4`. Keep the copied `node_modules` tree intact. `pnpm install --offline` is not guaranteed to recreate all of Paperclip from an empty directory: this kit's primary Paperclip JavaScript closure is the installed tree in the official image, rather than a separately qualified empty-store reinstall.

For a UI-only change, run the repository's scoped UI build. Server changes can trigger Runner preparation and require the Rust setup below:

```bash
cd /work/paperclip
pnpm --filter @paperclipai/ui build
# When changing server code, after preparing the needed native build tools:
PAPERCLIP_TSC_EMIT_ONLY=1 pnpm --filter @paperclipai/server build
pnpm --filter @paperclipai/server build:runtime
```

These are the pinned package commands used by the upstream image build. They are a starting point for your adaptation, not a claim that every modified source tree has already passed a complete rebuild. Run the relevant focused tests and inspect build output before creating a replacement runtime image.

## Rebuild the Paperclip Rust Runner offline

Extract the standalone Rust distribution into a temporary builder directory. Its `install.sh` can install into a dedicated prefix without rustup or an Internet connection; select `rustc`, `cargo`, and `rust-std-x86_64-unknown-linux-gnu`. Put that prefix's `bin` first on `PATH`, and check that both `rustc --version` and `cargo --version` report `1.97.1`.

Extract `paperclip-runner-rust-vendor.tar.gz` into `/work/runner-vendor`. Its directory-source path is then `/work/runner-vendor/paperclip-runner-rust-vendor/vendor`. In the builder:

```bash
mkdir -p /work/runner-vendor /work/cargo-home
tar -xzf /kit/payload/build-deps/paperclip-runner-rust-vendor.tar.gz -C /work/runner-vendor
cat > /work/cargo-offline.toml <<'TOML'
[source.crates-io]
replace-with = "offline-vendor"
[source.offline-vendor]
directory = "/work/runner-vendor/paperclip-runner-rust-vendor/vendor"
[net]
offline = true
TOML
export CARGO_HOME=/work/cargo-home
export CARGO_NET_OFFLINE=true
cargo --config /work/cargo-offline.toml metadata --offline --locked \
  --format-version 1 \
  --manifest-path /work/paperclip/packages/paperclip-runner/runner/Cargo.toml \
  > /work/runner-metadata.json
cargo --config /work/cargo-offline.toml build --offline --locked --release \
  --manifest-path /work/paperclip/packages/paperclip-runner/runner/Cargo.toml \
  -p paperclip-runner-core --bin paperclip-runnerd
```

The direct Rust build produces `runner/target/release/paperclip-runnerd` relative to the Runner package. Its package build then stages the binary and other assets into the package distribution. When invoking package scripts that call Cargo themselves, make the same source replacement available through the dedicated Cargo home's `config.toml` or the checkout's `.cargo/config.toml`.

Preserve matching native binaries, JavaScript contracts and provider assets. The official image includes a stamped `/opt/paperclip-runner/provider-pack`; changing one part does not make an old remote-provider stamp valid for the new build. Rebuild and qualify the matching provider pack before using altered native remote execution. The kit's default legacy CLI adapters do not require you to replace this native pack for ordinary configuration changes.

**Verified here:** all 333 crate archive checksums matched the pinned lock, and Cargo 1.97.1 resolved all 335 packages with `--offline --locked` and an initially empty Cargo home. **Not verified here:** a full native Runner compile/link/test cycle or every provider build mode. GCC, libc headers and pkg-config mirror the upstream Linux prerequisites; optional native paths can also need the supplied CMake/Clang/protobuf/musl tools.

## Rebuild the Paperclip OMP adapter

This adapter is separate from the OMP executable. The pristine community source is version `0.7.0`, commit `0f0864332d953ecd56839f8a60afcb8aa6d1e351`. The installed integration is the downstream `0.7.0-offline.1` build.

In a new development directory, extract the source snapshot and the npm cache, apply the included patch, then build using Node 24:

```bash
mkdir -p /work/omp-adapter /work/omp-adapter-npm-cache
tar -xzf /kit/payload/sources/paperclip-omp-adapter-0f0864332d95.tar.gz -C /work/omp-adapter
tar -xzf /kit/payload/build-deps/paperclip-omp-adapter-npm-cache.tar.gz -C /work/omp-adapter-npm-cache
cd /work/omp-adapter/paperclip-omp-adapter
git apply --check /kit/payload/patches/paperclip-omp-adapter-0.7.0-offline.1.patch
git apply /kit/payload/patches/paperclip-omp-adapter-0.7.0-offline.1.patch
npm ci --offline --ignore-scripts --no-audit --no-fund --cache /work/omp-adapter-npm-cache
npm run typecheck
npm run build
node test/offline-models.mjs
npm prune --omit=dev --ignore-scripts --offline --no-audit --no-fund --cache /work/omp-adapter-npm-cache
```

Keep `dist`, production `node_modules`, `package.json`, the lock, license and `OFFLINE-PATCH.md` together in the replacement adapter directory. Register it by an absolute container-visible path with `isLocalPath: true`; that registration path performs no npm installation.

The patch makes the provisioned `PAPERCLIP_OMP_OFFLINE_MODELS` catalog authoritative and disables live quota probes by default. Do not restore automatic global model discovery merely to populate a picker. The focused test uses a sentinel executable to prove that startup/list/refresh/quota paths do not launch OMP.

**Verified here:** pristine patch applicability, clean npm installation from the cache with `--offline`, typecheck, build and focused offline tests, including the final production-dependency layout. Those tests do not replace target-host Paperclip/OMP session persistence and actual internal-model acceptance.

## Rebuild OMP, Herdr or OpenCode

Follow `payload/manifests/worker-artifacts.json`, `payload/manifests/worker-dependencies.json`, and `payload/patches/OMP-OFFLINE-PATCH.md`. Use the exact versions and archive layouts recorded there; these projects do not share one interchangeable toolchain.

- **OMP 19.0.1:** pinned Bun 1.4.4, the supplied upstream source and the separate binary patch. Its verified recipe uses the extracted `bun-cache-omp` directory with `BUN_INSTALL_CACHE_DIR` and `bun install --offline --frozen-lockfile --ignore-scripts`. The supplied builder materializes a managed binary using the official baseline native addon. That successful binary build is distinct from recompiling all native addons. Native source work uses the recorded nightly Rust toolchain and Cargo closure.
- **Herdr 0.9.5:** pinned Rust 1.96.1 and Zig 0.16.0, including Ghostty-related source/dependency material. Use the manifest's final closure and validation status; do not infer a complete Herdr rebuild from a successful executable version check or Cargo metadata resolution.
- **OpenCode 1.18.34:** pinned Bun 1.3.14 and the supplied installed-dependency overlay. Preserve its lock and platform-specific dependencies. A reinstall with a different Bun version is not equivalent: an attempted Bun 1.4.4 cache replay encountered an upstream Photon patch issue. Do not claim that an arbitrary empty-cache reinstall or every OpenCode packaging target is qualified.

The combined worker Cargo vendor contains 1,154 registry packages. Offline, locked metadata checks with an empty Cargo home resolved 1,021 packages for OMP and 297 for Herdr. These checks validate dependency resolution, not native compilation; use each project's own pinned compiler for a real build. The manifests describe the completed checks and any remaining generated/native steps. Lifecycle scripts were initially controlled to avoid optional downloads. Read those notes before enabling scripts, adding packages or changing build targets.

## Qualify and promote a changed build

Use a new local image or binary name, record its source commit, applied patches, tool versions and SHA-256, and retain the baseline for rollback. Run build checks with networking disabled; run model integration checks only against the explicitly configured internal endpoint. Never test an altered control plane against the production database first.

Use a separate disposable Paperclip state/database and disposable Git project for startup, adapter loading, task execution, worktree isolation, cancellation, recovery and session save/resume checks. Preserve the original OMP installation until the replacement passes on the target host. The build host could not qualify OMP's persistent-session path because its AF_UNIX socket restrictions interrupted native lock handling; an ephemeral inference success is not a durable-session pass.

The archive contains application source, dependency material and supporting Docker/Node/PostgreSQL source/provenance for inspection and adaptation. It does not claim a from-scratch rebuild of every supporting component, every upstream CI matrix, GPU/model weights, arbitrary future dependencies, or every operating system. Host kernel, container support, permissions, disk, internal CA trust and local model capabilities remain part of target qualification. If a build fails under `--network none`, preserve the log, identify the exact missing input, and import an approved artifact; do not silently turn the build into an online installation.
