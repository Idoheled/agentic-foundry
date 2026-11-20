#!/usr/bin/env bash
set -euo pipefail
TASK_KIT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if [[ "${1:-}" == start-claude ]]; then
  shift
  exec "$TASK_KIT_ROOT/launch-handoff.sh" claude "$@"
fi
export PYTHONDONTWRITEBYTECODE=1
exec "$TASK_KIT_ROOT/scripts/python.sh" "$TASK_KIT_ROOT/scripts/upgrade-flow.py" "$@"
