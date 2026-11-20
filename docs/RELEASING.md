# Releases and repository maintenance

## Version contract

`VERSION` contains the repository version without `v`. An immutable annotated tag named `v<version>` identifies the corresponding committed source. The committed notes live at `releases/v<version>.md`.

The repository version and payload lineage are separate. Agentic Foundry `v0.1.0` begins with the qualified `2026-11-20-r5` payload. The payload lock and offline manifest record that identity; changing a repository document does not silently rename an upstream binary.

Before 1.0, compatibility changes may occur between minor versions and must be called out in the notes. Use a patch version for compatible fixes. Published tags and assets are not moved or replaced; corrections get a new version.

## Continuous integration

`Source checks` runs for pull requests, pushes to `main` and manual dispatch. It checks out source with LFS downloads disabled, validates the manifest-to-lock contract and source deployment checksums, and runs `bash ci/check.sh`. No installation, model call or public package install is part of this job.

`Release` runs its read-only validation job on version-tag pushes. It requires an existing annotated tag, exact `VERSION` match, committed release notes and the expected tag commit. It also validates the payload manifest and runs the source suite. A tag push does not publish a release.

The official checkout action is pinned to its full verified commit. `ci/action-pins.json` records the upstream release and verification source. Review action updates as code changes. Hosted CI is a connected repository-maintenance service; disconnected deployment does not depend on Actions.

## Preparing a version

1. Complete the change and the applicable source, payload and runtime checks.
2. Update `VERSION`, `CHANGELOG.md` and `releases/v<version>.md` together. Describe the supported profiles and actual qualification limits.
3. If payloads changed, rebuild the manifest and lock through the payload tooling, verify real bytes, and review the LFS object set. Preserve upstream notices. After all source edits, run `python3 scripts/refresh-checksums.py --write` and `--check`; commit `SOURCE_MANIFEST.json` and `SHA256SUMS` with the change.
4. Inspect the staged changes for private configuration, state and credentials. Commit using the intended maintainer identity.
5. Create an annotated tag on the verified commit and push the branch, LFS objects and exact tag. Confirm that the remote tag resolves to that commit and that LFS transfer succeeded.

Example after the release commit is complete:

```bash
git tag -a v0.1.0 -m "Agentic Foundry v0.1.0"
git push origin main
git push origin v0.1.0
```

Use the next unused version for later releases. Do not force-push a published tag. Keep release mutations sequential so a failed LFS upload cannot be mistaken for a complete publication.

## Manual publication workflow

In Actions, run **Release** with the existing tag and `publish: true`. Choose `prerelease` explicitly. The workflow defaults to a prerelease until the maintainer selects otherwise; this flag does not waive any verification.

Choose `payload_source: local` to verify an LFS checkout, or `payload_source: remote` to stream the same bytes from the repository without retaining a full checkout. Both modes verify every declared object and reconstructed payload-file hash; neither treats an upload receipt as proof of the file contents.

Local mode needs Python 3.12, Bash, Git, Git LFS and sufficient disk. Before downloading LFS content the workflow checks for approximately **twice the distinct object bytes plus 2 GiB**: the LFS cache, checked-out objects and working margin. For the initial payload this is more than a small hosted runner's free-space budget may permit. Select remote streaming mode or an approved larger runner label when the capacity check blocks. The workflow does not delete unrelated runner files to manufacture space.

Publication then:

1. Checks out the exact source commit accepted by the validation job.
2. Obtains the complete LFS object set through the chosen local checkout or remote streaming mode.
3. Streams and verifies all objects and reconstructed payload-file hashes without materializing another `payload/` tree.
4. Checks that the remote tag still identifies the validated commit and that no release already exists for that tag.
5. Creates a draft and attaches the source archive, offline manifest, payload lock, integrity evidence and asset checksums.
6. Confirms the uploaded asset set, sizes and available server digests, then publishes and reads back the release state.

Remote mode uses at most four concurrent file verifications by default (configurable from one to eight). It streams large chunks in bounded blocks, coalesces identical full-file reconstructions and retains only a bounded small-object memory cache. Repository credentials are sent only to the exact repository's GitHub LFS batch endpoint. Download actions must use HTTPS on the reviewed GitHub download hostname; redirects, unexpected hosts and forwarded repository credentials are rejected. Signed download URLs and authorization values are not logged. An upstream hostname change requires review of `ci/remote_lfs.py`.

The standalone publisher supports the same mode after the source commit, annotated tag and LFS upload have been verified:

```bash
python3 ci/release.py publish \
  --tag v0.1.0 \
  --expected-sha EXACT_COMMIT_SHA \
  --repository Idoheled/agentic-foundry \
  --payload-source remote \
  --github-user idoheled \
  --workers 4 \
  --prerelease true
```

Supply `GH_TOKEN` through a private process environment. This connected release-maintenance command is not part of disconnected runtime setup.

Only the publishing job has `contents: write`. Pull-request checks and tag validation use read-only access. The source checkout does not retain Git credentials.

A failure after draft creation leaves the draft and any uploaded assets for inspection. The workflow does not overwrite, delete or automatically retry a release with an uncertain outcome. Inspect the tag, draft and assets before choosing a recovery action.

## Release downloads and offline deployment

The source release archive and GitHub's generated ZIP/tar source downloads are not substitutes for verified LFS payload bytes. The explicit source asset contains LFS pointers. Obtain the full payload by cloning the exact tag with Git LFS, or use an approved private mirror of the same manifest and objects. Follow [payload management](PAYLOADS.md) to verify and assemble the offline deployment bundle. From a hydrated, clean checkout at the exact release tag, `build-tools/export-release.py --ref v0.1.0 --output ABSOLUTE_OUTPUT_PATH` creates a standalone tar with source and one payload copy, excluding Git metadata and duplicate LFS object storage. It verifies every archived member. Keep generated archives outside the tracked source tree. The earlier r5 `build-tools/release.py` is retained for historical builder provenance and is not the Git-checkout export path.

Release integrity verifies the supplied files; it does not install them. Native package installation, private model routing, real worker probes, configuration preservation and browser interaction remain target-machine acceptance checks. Never describe a source-only CI pass as a completed machine upgrade.

## Maintainer checklist

Before marking a release ready for use, record the tag commit, successful source run, complete LFS transfer, payload verification, supported OS/architecture and remaining target acceptance. Confirm the README links and release assets resolve. Keep private site data out of release notes and verification reports.
