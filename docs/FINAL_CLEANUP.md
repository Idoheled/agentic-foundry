# Final deletion of retired tool files

The host provisioner first stages and verifies a replacement, promotes its entrypoint and moves an exact inspected obsolete unmanaged file/link out of its active path into quarantine. Final cleanup is a later, separate operation, after the complete two-phase target acceptance has passed.

`scripts/cleanup-retired.py` turns the exact hostctl quarantine files into a private verified rollback archive and then **deletes the individual quarantined filesystem objects**. A SHA-bound cleanup receipt records what was deleted. The backup archive remains; the active old paths and individual quarantine files are absent.

This is bounded cleanup of declared obsolete files. It does not recursively delete directories, remove unknown tools, purge old managed version trees, or run package-manager removals. Distribution-owned files use their native package manager. The selected replacement trees, native profiles, instructions, skills, hooks, models, credentials and operational state are protected.

## Preconditions

- Both workflow phases and their actual target acceptance have completed.
- The immutable final completion JSON has `schemaVersion: 1`, `status: "completed"`, `passed: true`, and an exact `hostReceipts` array containing the intended receipt's absolute path and SHA256.
- The completion binds the private preservation report and acceptance evidence as `{path, sha256}` objects. Those files must still have the recorded bytes.
- `completion.protectedRoots` lists every actual discovered profile, brain, credential and external linked configuration path. This must be a nonempty array of absolute paths. Default home profile roots, the kit, tool trees and installer state are additionally protected.
- The host receipt is `installed_and_verified`, without blockers; its retirement requests completed successfully. Its hash is captured **after** retirement.
- Every cleanup item is already in that receipt's exact quarantine directory, is a regular file or symlink, still has its recorded identity, and maps back to its original inspected retirement request.
- The original active path is absent, not reused by a later installation, and is not package-owned.
- Fresh read-only host verification succeeds. The helper also checks observable `/proc` executable and memory-map consumers. The broader service/wrapper/project consumer review remains required; a process visibility restriction is not proof that a file has no consumers.

The final cleanup state must be a separate private directory outside the host tool tree and outside the host installer state. The helper uses the host provisioner's operation lock plus a cleanup lock to serialize mutations.

## Commands

The receiving workflow fills these paths and hashes from actual receipts. Keep the command arguments identical between `plan`, `apply` and `restore`:

```bash
/absolute/kit/scripts/python.sh /absolute/kit/scripts/cleanup-retired.py plan \
  --host-receipt /private/host-state/receipts/EXACT_RECEIPT.json \
  --host-receipt-sha256 EXACT_POST_RETIREMENT_SHA256 \
  --completion /private/workflow/completion.json \
  --completion-sha256 EXACT_COMPLETION_SHA256 \
  --host-state /private/host-state \
  --state /private/cleanup-state \
  --mode system
```

Use `apply` after the plan's fresh verification passes. It independently repeats those checks; a stale plan is not sufficient. The ordinary operator starts the command; system mode uses existing noninteractive sudo authority, retaining the operator identity. Explicit user mode uses the operator's managed user installation. Test-only fake prefixes are for the included tests, not installation on a real host.

The helper writes a private transaction directory containing:

- `rollback-files.tar.gz`: a verified archive of the exact retired file/link objects, retaining file bytes, mode, UID/GID and symlink target strings.
- `cleanup-receipt.json`: exact source/completion hashes, inventory, archive SHA256, per-item deletion progress and final status.

Symlinks are archived as symlinks and unlinked as symlinks. Their targets are not followed, read into the archive or deleted. The helper never extracts tar paths generically.

## Recovery and idempotence

The backup is fully verified and its receipt is committed before any deletion. If execution stops after unlinking an item but before logging it, a rerun can recognize the missing item using the committed verified archive and continue. An unexpected changed quarantine object or changed input blocks the operation.

If interruption leaves an archive without a committed receipt, the helper preserves it and blocks. Inspect the transaction rather than deleting its backup or inventing a success receipt.

After successful cleanup, repeated cleanup returns the same completed status after verification. Do **not** rerun `hostctl retire` for that receipt: its individual quarantine files are intentionally absent. Keep the final completion JSON immutable and write cleanup results separately.

For a rollback, call `cleanup-retired.py restore` with the same bound arguments. This restores exact original objects **to their quarantine locations**, without replacing a new occupant. It does not alter active command entrypoints or the current profile. Then invoke `hostctl rollback` with the exact original host receipt. The host provisioner checks the active command identities before restoring the former installation. Keep the kit, completion evidence, host receipt and cleanup state for this procedure.

A restore can be retried when already restored items still match. A changed occupant or corrupt archive blocks and is preserved for inspection. Regular-file restoration stages and verifies the bytes before publishing the destination without replacement.

After a successful restore, the same cleanup transaction cannot purge again. A new cleanup requires a newly qualified workflow and corresponding evidence; avoid alternating delete/restore operations from stale completion claims.

## Builder verification

The separate cleanup suite passed 14 tests with actual temporary executable files and a real replacement command probe. It exercised actual deletion and restoration, symlink preservation without target reading, wrong hashes, incomplete acceptance, quarantine escape, protected profile paths, changed replacements, changed old files, package ownership, a live retired `/bin/sleep` process, recovery after an interrupted unlink, preservation of later occupants and archive corruption.

These are isolated Linux fixture tests. The user's actual native package database, sudo policy, files, internal models and service consumers remain target checks.
