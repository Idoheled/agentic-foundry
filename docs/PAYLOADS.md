# Offline payload and Git LFS

Agentic Foundry keeps readable setup source, tests, documentation and artifact
identities in ordinary Git. The complete selected offline payload is stored as
Git LFS objects in this same repository. A source-only checkout can be reviewed
and tested, but it cannot install missing tools until its LFS bytes or an approved
private payload mirror have been supplied.

## Prepare a checkout before disconnecting

Install Git LFS through your approved package source, then obtain the repository
and its objects while GitHub or your private mirror is reachable:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone --branch v0.1.1 --single-branch \
  https://github.com/Idoheled/agentic-foundry.git
cd agentic-foundry
git lfs install --local
git lfs pull
python3 scripts/offline_payload.py verify
```

Copy the complete working tree, including `offline/objects/`, to the disconnected
machine. Keep the selected tag or commit recorded. A normal GitHub source ZIP or
tar download is not a substitute for this step: obtain and verify actual LFS
bytes, rather than assuming its small pointer files are the payload.

The verification command checks each chunk, then reconstructs each complete
payload file's hash while streaming. It does not create `payload/` or run the
installer. Success reports include the payload release, file count, object count
and byte totals. A missing object, pointer in place of content, truncated data or
wrong hash blocks the operation.

## Deploy from the checkout

Existing workspace:

```bash
./deploy.sh agent --state "$HOME/.local/state/agentic-stack/setup-r5"
```

Fresh machine after its site declaration has been completed:

```bash
./deploy.sh --config /private/site.json --state /private/states/setup-r5
```

`deploy.sh` checks the maintained source checksum contract, materializes the local payload and forwards the arguments unchanged
to `setup.sh`. It never calls `git lfs pull`, a public package registry or a
downloader. Its `doctor` and help modes skip full payload materialization.

Payload materialization places files in the repository's ignored `payload/`
directory; native installation is a later, separate step with the existing
private-source and ownership checks. Supplying fallback bytes does not select
those bytes over an adequate existing or private installation.

Existing files are reused only when their hash, size and permission mode match.
Conflicting files are preserved and block materialization. Missing files are
staged and verified before an atomic no-replacement link creates the destination.
Interrupted materialization can be repeated after the actual missing or damaged
input is corrected.

For eligible single-chunk files, `deploy.sh` uses hardlinks when the existing
object mode already matches the required payload mode. This reduces disk use.
It does not change a shared inode's permission mode. Treat both `payload/` and
`offline/objects/` as immutable: make changes in the source/build tree and create
a newly identified artifact rather than editing installed fallback bytes.

## A machine without Python

Prefer a qualified existing or private Python 3.9+ interpreter:

```bash
AGENTIC_PYTHON=/absolute/private/python3 ./deploy.sh --config /private/site.json
```

When inspection establishes that private Python sources are unavailable or
insufficient, record the actual finding in
`AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON`. The shell entry point can then stage
the exact hash-verified standalone CPython archive from one LFS object and call
the existing private-first controller bootstrap. It does not need Python to
stage this one archive. The included bootstrap requires Linux x86-64 and normal
Bash, tar and coreutils tools. Other architectures need a matching qualified
interpreter and payload profile.

The controller bootstrap is distinct from final native Python provisioning and
does not replace an OS-owned interpreter.

## Format and audit contract

| Path | Purpose |
| --- | --- |
| `payload.lock.json` | Original selected payload identities, sizes and modes. |
| `offline/manifest.json` | Ordered chunk reconstruction map, bound to the exact payload lock hash. |
| `offline/objects/sha256/<hash>.chunk` | Complete content-addressed bytes tracked through Git LFS. |
| `payload/` | Ignored, materialized runtime/source/package/image layout consumed by installers. |
| `scripts/offline_payload.py` | Standard-library validator, packer, verifier and materializer. |
| `SOURCE_MANIFEST.json` | Maintained source inventory, including control-file hashes and portable executable modes. |
| `SHA256SUMS` | Runtime checksum list binding maintained source and all selected payload files. |

Objects are at most 512 MiB. Most artifacts use a single object; larger files use
ordered chunks. Identical file content and identical chunks share object IDs.
File modes belong to the reconstructed file, independently of the object's Git
mode. Empty files have the SHA-256 of empty content and no object references.

Every locked payload file must appear unchanged. Additional payload source
material is explicitly listed under `supplementalFiles`; it is not silently
treated as part of the original lock. Absolute paths, traversal, symlinks,
duplicate JSON keys, invalid hashes, unreferenced object definitions and
inconsistent sizes are rejected.

The manifest's payload revision and the repository's semantic version describe
different things. For example, a repository release can improve deployment
source while retaining the qualified `2026-11-20-r5` payload.

## Useful commands

Validate the source-controlled contract without LFS bytes:

```bash
python3 scripts/offline_payload.py validate
```

Verify all LFS content without materializing it:

```bash
python3 scripts/offline_payload.py verify
```

Materialize independently of native setup:

```bash
python3 scripts/offline_payload.py hydrate --link-objects
python3 scripts/payload.py verify
```

The older payload helper still supports qualified private extracted releases and
hash-verified tar archives. It is useful when a site mirrors `payload/` directly:

```bash
python3 scripts/payload.py hydrate --from-dir /mnt/private/extracted-release
./setup.sh --config /private/site.json --state /private/states/setup-r5
```

An already hydrated full release tar uses `setup.sh` directly. A Git checkout with
LFS objects uses `deploy.sh` as its convenient entry point.

## Build a new object set

In a qualified connected build environment, first prepare and verify the complete
release and its payload lock. Copy the same lock into the repository, then:

```bash
python3 scripts/offline_payload.py pack \
  --root /absolute/agentic-foundry \
  --source-root /absolute/qualified-release \
  --link-source

python3 scripts/offline_payload.py verify --root /absolute/agentic-foundry
```

`--link-source` reuses immutable whole files when the filesystem permits it.
Larger chunks try filesystem range cloning, then copying; `--reflink never`
forces copying, while `--reflink always` blocks if cloning is unsupported. Source
file modes are never changed by a hardlink optimization. The packer preserves an
existing differing manifest or object so that release replacement requires an
explicitly inspected new build location.

For publishers with limited temporary storage, `pack --manifest-only` streams
and hashes every source chunk and writes the exact same manifest without making
object files. Its success only establishes the manifest and source identities;
it does not prove objects were uploaded or can be downloaded. Such a publisher
must use normal Git LFS upload semantics, supply each exact object and verify the
remote set before publishing. Object offsets are the cumulative sizes of each
file's ordered `chunks` entries.

Do not commit an entire multi-gigabyte release tar as an ordinary Git blob or
duplicate the same payload again in a second LFS representation. Git LFS has
per-object and account storage limits, and the release publisher must report any
actual hosting or quota blocker.

## Maintain runtime checksums

After reviewed source, documentation or workflow changes, regenerate the source
inventory and runtime checksum list before committing:

```bash
python3 scripts/refresh-checksums.py --write
python3 scripts/refresh-checksums.py --check
```

The command reads maintained Git source and the unchanged locked payload
identities. It does not require LFS content or modify `payload.lock.json`.
`SOURCE_MANIFEST.json` records source hashes, sizes and portable Git file modes;
`SHA256SUMS` combines those controls with the pinned payload hashes. The checksum
files exclude their own self-references. Git metadata, LFS object copies,
generated output and private state are excluded. Keep new generated reports in
ignored `reports/`, `dist/` or `release-evidence/` directories; retained historical
provenance remains covered source.

Ordinary CI runs `--check`. An exported release can also run this check using its
included source inventory without Git. Updating that authority is reserved for a
reviewed Git checkout; an installed machine does not regenerate it merely to make
a changed file pass. To check actual materialized bytes and modes as well:

```bash
python3 scripts/refresh-checksums.py --check --payload
```

## Export one standalone tar

With sufficient disk space, a fully materialized checkout at the exact release
tag can produce an original-style, single-file offline kit:

```bash
git checkout v0.1.1
git lfs pull
python3 scripts/offline_payload.py hydrate --link-objects
python3 build-tools/export-release.py \
  --ref v0.1.1 \
  --output /private/releases/agentic-foundry-0.1.1-linux-amd64.tar.gz
```

The exporter requires a clean source checkout whose `HEAD`, tag and `VERSION`
agree. It validates source and hydrated payload identities, includes one copy of
each source/payload file, and excludes `.git` and `offline/objects`. It rereads
every tar member to verify content, size and executable permissions, then emits
the archive checksum and a validation report identifying the source commit/tag.
This is archive qualification, not a claim that target model or browser tasks ran.

After transferring and checking the tar, extract it and use `setup.sh` with the
same existing-machine or fresh-machine workflow. Git and Git LFS are not needed
to access the extracted payload.

`build-tools/release.py` is retained for the original pre-Git release layout; use
`build-tools/export-release.py` for a repository checkout. Pointing the original
packer directly at the Git tree would include the wrong storage layout or reject
Git metadata.

## Disk planning

Plan from the actual manifest totals. A standard connected clone can hold both
the LFS cache and checked-out object files, roughly twice `objectBytes` before
hydration. Materializing with copies adds up to `payloadBytes`; hardlink reuse
can reduce that cost on a shared filesystem. Large split artifacts still need
space for their reconstructed output. Runtime installation and image loading
need additional target space beyond the distribution itself.

Do not delete the only verified source to make an incomplete transfer fit. A
publisher can stream separate objects from a retained qualified source and keep
the working tree as valid LFS pointers until a fully hydrated checkout is needed.
