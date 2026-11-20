# Contributing to Agentic Foundry

Agentic Foundry provisions and upgrades disconnected workspaces. Contributions must preserve working machines, private supply preference and the distinction between installation evidence and real task acceptance.

## Development setup

Clone with LFS smudging disabled when working only on source:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/Idoheled/agentic-foundry.git
cd agentic-foundry
python3 scripts/offline_payload.py validate
python3 scripts/refresh-checksums.py --check
bash ci/check.sh
```

The source suite uses Python's standard library, Bash and Git. Python 3.12 is used in the hosted CI job. It does not require the 13 GB offline payload, a model connection, Docker installation, public package downloads or production credentials. See [payload management](docs/PAYLOADS.md) before changing or testing bundled runtimes.

After changing committed controls, refresh their manifest with `python3 scripts/refresh-checksums.py --write`, then verify it with `--check`. This preserves the pinned payload identities; it does not qualify new runtime bytes. Keep generated reports in ignored `reports/` or `dist/` paths so they do not create checksum self-reference.

For a focused change, start with the tests that cover its actual risk. Run the complete source suite before a pull request or release. Behavioral tests must use isolated fixtures and must not mutate the operator's profiles, package database or daemon.

## Preserve the installation contract

Keep one operator-facing deployment path and the minimal-site configuration flow. Extend schemas compatibly, document changed behavior and fail with a concrete blocker when a requested capability is unavailable. Do not silently omit a component to obtain a passing result.

Runtime setup stays offline and private-first. Every artifact selection needs an explicit source decision, pinned identity and target compatibility. Public acquisition belongs to controlled release preparation. Preserve upstream licenses, exact source provenance and declared rebuild limitations.

Existing route, authentication, profile, brain, hook and skill values must not be overwritten by examples. Existing OMP upgrades stay within Claude's phase 1. OMP's phase 2 must preserve its qualified command, runtime and launch context. The operator's manual handoff remains a deliberate boundary.

Manage package-owned files through the operating system's package manager. Independent tools retain their complete versioned runtime and use inspected managed command entry points. Retire obsolete files only through the ownership- and receipt-bound cleanup procedure after acceptance.

## Repository hygiene

Commit setup code, public examples, tests, documentation, payload locks, LFS pointers, licenses and source provenance. Keep live site files, credential values, internal route details, private supply indexes, runtime state, receipts, user workspaces and unredacted logs outside the repository.

Large payload objects belong under the declared Git LFS policy. Do not put an offline tar or runtime archive into ordinary Git history. Validate the manifest, LFS objects and reconstructed payload when replacing a dependency; source tests alone do not establish that a new binary works. Never move a published release tag or overwrite a published payload under the same version.

Inspect the staged diff before committing. Use the intended maintainer identity, a credential helper or process-private credentials, and a token-free remote URL. Repository publication requires the operator's authorization for the actual target; a generic agent instruction is not permission to publish another repository.

## Pull requests and verification

Explain the concrete problem, the change and the resulting behavior. Include the relevant test commands and results, supported platform, preservation impact and remaining qualification.

Separate these evidence levels:

1. **Source behavior:** isolated controller tests and syntax checks.
2. **Payload integrity:** declared artifact bytes, native dependency closure and source identities.
3. **Runtime capability:** real commands on the selected operating system and architecture.
4. **Target acceptance:** the organization's real model routes, workers, hooks, browser interaction and project tasks.

A source check or reachable dashboard is not evidence of completed target acceptance. New task dispatch remains gated by the actual acceptance procedure.

## Releases

See [the release procedure](docs/RELEASING.md) for annotated tags, versioning, CI, LFS verification and publication. A release must identify its complete pinned payload and document how to obtain one offline deployment bundle.

No new telemetry, monitoring or backup platform is a prerequisite for this stack. Retain the transaction recovery and configuration originals needed for correct upgrades.
