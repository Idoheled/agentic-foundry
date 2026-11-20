#!/usr/bin/env bash
set -euo pipefail
TASK_KIT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec "$TASK_KIT_ROOT/scripts/python.sh" "$TASK_KIT_ROOT/scripts/install-stack.py" "$@" --only profiles
