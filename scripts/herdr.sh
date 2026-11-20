#!/usr/bin/env bash
set -euo pipefail
TASK_STATE="${AGENTIC_STATE:-$HOME/.local/share/agentic-stack}"
TASK_BINARY="$TASK_STATE/runtime/bin/herdr"
if [[ ! -x "$TASK_BINARY" ]]; then echo 'Run install.sh install first, or set AGENTIC_STATE to the installation directory.' >&2; exit 1; fi
exec "$TASK_BINARY" "$@"
