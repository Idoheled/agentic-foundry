#!/usr/bin/env bash
# Git-checkout entry point: local LFS materialization, then the existing installer.
set -euo pipefail
TASK_FOUNDRY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

if [[ $# -eq 0 || "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
Agentic Foundry Git-checkout deployment

Usage: ./deploy.sh doctor|plan|apply|agent [setup options]
       ./deploy.sh --config /absolute/site.json [--state /absolute/private-state]

Before disconnecting, obtain the repository's LFS bytes with git lfs pull.
This command never downloads: it verifies and materializes the local payload,
then delegates unchanged arguments to setup.sh. doctor and help skip hydration.
Existing machine: ./deploy.sh agent (Claude upgrades OMP, then stops for handoff).
Fresh machine: ./deploy.sh --config /private/site.json --state /private/state.

Use AGENTIC_PYTHON=/qualified/private/python when available. A machine without
Python requires an actual private-source inspection result in
AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON before using the bundled controller.
Payload files are immutable; eligible files may share storage with LFS objects.
USAGE
  exit 0
fi

task_guard_path() {
  local candidate="$1"
  while [[ "$candidate" != / && -n "$candidate" ]]; do
    if [[ -L "$candidate" ]]; then
      printf 'BLOCKED: refusing symlink path: %s\n' "$candidate" >&2
      exit 2
    fi
    candidate="${candidate%/*}"
  done
}

# Break the no-Python materialization cycle using the same pinned archive and
# identity as scripts/python.sh. This stages bytes only, not a native install.
if [[ -z "${AGENTIC_PYTHON:-}" ]] && ! python3 -c 'import sys;raise SystemExit(sys.version_info < (3,9))' >/dev/null 2>&1; then
  case "$(uname -m)" in
    x86_64|amd64) ;;
    *) echo 'BLOCKED: select a qualified native AGENTIC_PYTHON and matching platform payload.' >&2; exit 2 ;;
  esac
  if [[ -z "${AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON:-}" || "${AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON}" == *REPLACE_* ]]; then
    echo 'BLOCKED: no Python3.9+ found. Inspect private repositories and select AGENTIC_PYTHON first.' >&2
    echo 'If unavailable or insufficient, record the real finding in AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON.' >&2
    exit 2
  fi
  TASK_PYTHON_SHA=6a9e62dad033790aef722dbd370e0ce76ce17b73627ba3ae679f537049350b39
  TASK_PYTHON_ARCHIVE="$TASK_FOUNDRY_ROOT/payload/packages/cpython-3.12.16+20261110-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
  TASK_PYTHON_OBJECT="$TASK_FOUNDRY_ROOT/offline/objects/sha256/$TASK_PYTHON_SHA.chunk"
  task_guard_path "$TASK_PYTHON_ARCHIVE"
  if [[ -e "$TASK_PYTHON_ARCHIVE" ]]; then
    printf '%s  %s\n' "$TASK_PYTHON_SHA" "$TASK_PYTHON_ARCHIVE" | sha256sum --check --status || {
      echo 'BLOCKED: preserving an existing differing Python archive.' >&2; exit 2;
    }
  else
    task_guard_path "$TASK_PYTHON_OBJECT"
    [[ -f "$TASK_PYTHON_OBJECT" ]] || { echo 'BLOCKED: missing Python LFS object; obtain git lfs pull before disconnecting.' >&2; exit 2; }
    mkdir -p -- "$(dirname -- "$TASK_PYTHON_ARCHIVE")"
    task_guard_path "$TASK_PYTHON_ARCHIVE"
    TASK_PYTHON_TEMP="$(mktemp "$(dirname -- "$TASK_PYTHON_ARCHIVE")/.foundry-python.XXXXXXXX")"
    trap 'rm -f -- "$TASK_PYTHON_TEMP"' EXIT
    cat -- "$TASK_PYTHON_OBJECT" > "$TASK_PYTHON_TEMP"
    printf '%s  %s\n' "$TASK_PYTHON_SHA" "$TASK_PYTHON_TEMP" | sha256sum --check --status || {
      echo 'BLOCKED: Python object is missing real LFS bytes or differs from its pinned hash.' >&2; exit 2;
    }
    chmod 0644 "$TASK_PYTHON_TEMP"
    ln -- "$TASK_PYTHON_TEMP" "$TASK_PYTHON_ARCHIVE"
    rm -f -- "$TASK_PYTHON_TEMP"
    trap - EXIT
  fi
fi

if [[ "${1:-}" != doctor ]]; then
  "$TASK_FOUNDRY_ROOT/scripts/python.sh" "$TASK_FOUNDRY_ROOT/scripts/refresh-checksums.py" --check --root "$TASK_FOUNDRY_ROOT"
  "$TASK_FOUNDRY_ROOT/scripts/python.sh" "$TASK_FOUNDRY_ROOT/scripts/offline_payload.py" hydrate --root "$TASK_FOUNDRY_ROOT" --link-objects
fi
exec "$TASK_FOUNDRY_ROOT/setup.sh" "$@"
