# Source, Git LFS, and offline releases

Agentic Foundry separates reviewable deployment source from immutable artifact bytes while keeping both available through the repository. The source contains controllers, schemas, catalogs, preservation/migration logic, task playbooks, tests, documentation, and provenance. Git LFS carries the content-addressed offline payload objects.

## Work with source only

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/Idoheled/agentic-foundry.git
cd agentic-foundry
./ci/check.sh
```

The controller test suite does not require the full payload, production credentials, Docker, or an internal model endpoint. Keep a source-only checkout for ordinary review and development when runtime qualification is unnecessary.

## Prepare a deployment checkout

```bash
git lfs install --local
git lfs pull
python3 scripts/offline_payload.py verify
```

`offline/manifest.json` maps pinned payload files to content-addressed objects under `offline/objects/sha256/`. The payload verifier checks actual bytes; an LFS pointer is not an archive. `deploy.sh` hydrates the local objects into the ignored `payload/` tree before invoking the selected setup operation. No public download is part of that deployment path.

The complete offline tar already contains hydrated artifacts and uses `setup.sh` directly. A checkout can also hydrate from a qualified private extracted release or a verified full tar with the existing `scripts/payload.py` interface. See [Offline payloads](docs/PAYLOADS.md) for exact commands, disk considerations, and transport details.

## Maintain identities

`payload.lock.json` identifies the expected runtime and source dependency artifacts. The LFS reconstruction manifest must bind to that lock and reconstruct the exact file sizes, bytes, and executable modes. A changed artifact is an explicit release change, not a reason to regenerate identities around an unexplained mismatch.

`SOURCE_MANIFEST.json` binds the maintained source controls. `SHA256SUMS` covers those controls, the source manifest, and every reconstructed file in `offline/manifest.json`, including supplemental payload files. After reviewed source changes, run `python3 scripts/refresh-checksums.py --write` and then `--check` before committing. The standalone exporter emits an external `.sha256` and `.validation.json` after rereading every archive member. `RELEASE_FILES.sha256` belongs to the historical pre-Git r5 packaging contract and is excluded from the current source/export inventory.

Versioned upstream snapshots, original artifacts, licensing, and declared vendor closures support debugging and controlled rebuilds. They do not imply that every upstream Git history, optional source-build graph, Chromium/OS-library source tree, or arbitrary future project dependency is present. The [delivery guide](docs/R5_DELIVERY_WORKSPACE.md), [coverage guide](docs/OFFLINE_COVERAGE.md), and per-component manifests describe the limits.

## Keep private state outside Git

Do not commit site declarations, credential values, private supply-index contents, model route files, runtime state, transaction receipts, private logs, acceptance reports, or project workspaces. Use existing credential helpers or process-private mechanisms for repository access; never embed a token in a remote URL or release artifact.

Read [Contributing](CONTRIBUTING.md), [agent instructions](AGENTS.md), and [the changelog](CHANGELOG.md) before changing installation behavior or preparing a new tagged release. Source CI, artifact integrity, target runtime qualification, and real model/task acceptance are distinct checks.
