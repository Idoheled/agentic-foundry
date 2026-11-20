# Shipped software and host capabilities

Exact baseline: 20 November 2026, revision r3. The private plan may select a qualified existing/internal equivalent; a version difference alone does not justify a kit fallback.

## Host catalog

| Catalog tool | Kit version | Managed commands | Whole-tree artifact |
| --- | --- | --- | --- |
| python | 3.12.16-quality-r3 | `agentic-python3`, `agentic-pip3`, `agentic-pytest`, `agentic-mypy`, `agentic-coverage`, `agentic-pyproject-build` | `payload/dependencies/python-quality/python-3.12.16-quality-runtime.tar.gz` |
| node | 24.22.3-pnpm-9.15.4 | `agentic-node`, `agentic-npm`, `agentic-npx`, `agentic-pnpm` | `payload/host-tools/node-v24.22.3-pnpm-9.15.4-runtime.tar.gz` |
| bun | 1.4.4 | `agentic-bun` | `payload/toolchains/bun-v1.4.4-linux-x64-baseline.zip` |
| rust | 1.99.1 | `agentic-rustc`, `agentic-cargo`, `agentic-rustfmt`, `agentic-cargo-fmt`, `agentic-cargo-clippy`, `agentic-clippy-driver` | `payload/dependencies/codex/rust-1.99.1-linux-x86_64-installed.tar.gz` |
| zig | 0.16.0 | `agentic-zig` | `payload/toolchains/zig-x86_64-linux-0.16.0.tar.xz` |
| codex | 0.171.0 | `agentic-codex` | `payload/dependencies/codex/codex-package-x86_64-unknown-linux-musl.tar.gz` |
| claude | 2.1.329 | `agentic-claude` | `payload/dependencies/native-profiles/claude/claude-linux-x64.tar.gz` |
| omp | 19.0.1-offline.1 | `agentic-omp` | `payload/host-tools/omp-v19.0.1-offline.1-host-runtime.tar.gz` |
| opencode | 1.18.34 | `agentic-opencode` | `payload/binaries/opencode-v1.18.34-linux-x64-baseline.tar.gz` |
| herdr | 0.9.5 | `agentic-herdr` | `payload/binaries/herdr-v0.9.5-linux-x86_64` |
| docker | 29.10.0 | `agentic-docker` | `payload/packages/docker-29.10.0.tgz` |
| compose | 5.8.0 | `agentic-docker-compose` | `payload/packages/docker-compose-v5.8.0-linux-x86_64` |
| uv | 0.13.9 | `agentic-uv`, `agentic-uvx` | `payload/host-tools/uv-x86_64-unknown-linux-musl.tar.gz` |
| ruff | 0.17.6 | `agentic-ruff` | `payload/host-tools/ruff-x86_64-unknown-linux-musl.tar.gz` |
| ripgrep | 15.2.0 | `agentic-rg` | `payload/host-tools/ripgrep-15.2.0-x86_64-unknown-linux-musl.tar.gz` |
| fd | v10.5.2 | `agentic-fd` | `payload/host-tools/fd-v10.5.2-x86_64-unknown-linux-musl.tar.gz` |
| jq | jq-1.8.2 | `agentic-jq` | `payload/host-tools/jq-linux-amd64` |
| yq | v4.54.3 | `agentic-yq` | `payload/host-tools/yq_linux_amd64.tar.gz` |
| native-profiles | 2026-11-20-r3 | Permanent assets; invoked by the profile installer | `payload/dependencies/native-profiles/native-profiles-2026-11-20-r3-source.tar.gz` |

The system prefix is `/opt/agentic-stack/tools`; managed commands live in `/usr/local/bin`. Canonical entry points require inspection in the private plan. Native packages own their standard distro locations. `pnpx` remains in the complete Node/pnpm tree; its upstream `--help` and `--version` are interpreted as package names, so the catalog does not use them as offline probes. Use the verified `agentic-pnpm` interface and the documented private/offline package workflow.

## Python quality dependencies

The runtime contains these exact packages. All matching wheel archives and source distributions are retained under `payload/dependencies/python-quality`; `requirements.lock` records hashes. Project dependencies belong in the relevant virtual environment.

```text
ast_serialize==0.13.1 --hash=sha256:9f99786e0d62082a5b121b3437f3167562133711df22128de1e9886f57f0b226
build==1.6.1 --hash=sha256:ecd351a4be9d35a9eaaba244a7687143c9c7d4aea6ac964e7e7ddab20cbcf4e7
coverage==7.17.3 --hash=sha256:0860a5f27ceccd53ee4070acc182588ed4f15b7401cdcca09d8c0cece9c2ad7d
iniconfig==2.3.1 --hash=sha256:9121e2c1fdb355232495be3194c8dfe87ccc2d5dee45947b78e68f499790d7a7
librt==0.17.0 --hash=sha256:afa8a6a1916f155e6f35c48d6cb547849af79e07060e36b6aaec1d1c63dc3c7e
mypy==2.4.1 --hash=sha256:a20ff6cd2af7a670c64f089bfa5fbcebe8ff3bf896c5e6ac7c9862c7960e4494
mypy_extensions==1.2.0 --hash=sha256:993e7a20aa5671eb41a7132cf555af30062da99729601601b9a8382b11cae768
packaging==26.3 --hash=sha256:d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c
pathspec==1.1.1 --hash=sha256:a00ce642f577bf7f473932318056212bc4f8bfdf53128c78bbd5af0b9b20b189
pluggy==1.7.0 --hash=sha256:7dd7b0d8832ba3cb632c306926ded123429211b83641b35dc5c41ad2d34f9bec
Pygments==2.21.0 --hash=sha256:2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377137d9
pyproject_hooks==1.3.3 --hash=sha256:5fc53fdac9f7bd63fbcdc868fb5f90b4784d78a53a3d3388cd738b807441a20b
pytest==9.2.0 --hash=sha256:07acdcf88ec174f907dc01af70bf52d49b014bbab03faeeade31c96b18c2e588
pytest-cov==7.1.0 --hash=sha256:a0461110b7865f9a271aa1b51e516c9a95de9d696734a2f71e3e78f46e1d4678
PyYAML==6.0.3 --hash=sha256:ba1cc08a7ccde2d2ec775841541641e4548226580ab850948cbfda66a1befcdc
typing_extensions==4.16.0 --hash=sha256:481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8
```

## Native OS tools

The local `payload/packages/debian13-amd64` repository contains 275 pinned binary packages and dependencies, including the selected Git, tmux, rsync, lsof, strace, socat, file, unzip/zip, ninja, ShellCheck, bubblewrap, jq, ripgrep, fd-find, Python venv/pip and native C/C++ build capabilities. The complete filenames/versions/hashes are in `provenance/r3-native-packages.json`; the actual internal/distro package plan decides which are needed. This is not a full OS repository.

## Primary stack and source indexes

- Paperclip `2026.1117.0`, PostgreSQL `17.12`, OpenCode `1.18.34`, OMP `19.0.1` original and `19.0.1-offline.1` managed build, adapter `0.7.0-offline.1`, Herdr `0.9.5`: main manifest and `payload/sources`/`payload/manifests`.
- Codex `0.171.0`: `payload/dependencies/codex/provenance.json`, `README-INSTALLER.md`, `SOURCE-REBUILD.md`, `docs/` and native schemas.
- Claude `2.1.329` and all three native profiles: `payload/dependencies/native-profiles/PACKAGE_INDEX.json`, `INSTALL_CONTRACT.json`, `sources/`, `docs/` and `validation/`.
- Python runtime/quality dependency provenance: `payload/dependencies/python-quality/python-quality-provenance.json`.
- Portable helper upstream source/asset pins: `provenance/host-tools.json`.
- Selected source rebuild toolchains may use different pinned Rust/Bun versions from the host default; keep those explicit project profiles. Their original archives and replay guidance remain in `payload/toolchains` and `docs/REBUILD.md`.

## License and source boundaries

Keep upstream license/notice files with every redistributed runtime and source tree. The Codex and Claude signature materials are retained; only the digest/signature checks explicitly recorded in provenance are claimed. Claude’s unpublished proprietary runtime source is unavailable. Complete tracked project snapshots do not certify every upstream optional native build; see `OFFLINE_COVERAGE.md`.
