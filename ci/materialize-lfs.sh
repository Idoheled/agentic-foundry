#!/usr/bin/env bash
set -euo pipefail
TASK_LFS_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$TASK_LFS_ROOT"

# A same-commit Git checkout can retain pointer files after `git lfs fetch`.
# Explicit checkout reads the local LFS cache; it never downloads missing data.
# Missing or modified files are still subject to the publisher's full verification.
printf '%s\n' 'Materializing cached Git LFS objects into the release working tree'
git lfs checkout
printf '%s\n' 'Cached LFS checkout finished; the publisher will verify every payload byte'
