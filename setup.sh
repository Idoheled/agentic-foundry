#!/usr/bin/env bash
# Offline entry point. The controller Python is selected by the existing private-first bootstrap.
set -euo pipefail
TASK_SETUP_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if [[ $# -eq 0 || "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
Usage: ./setup.sh doctor|plan|apply|agent [--config /absolute/site.json] [--state /absolute/private-state]
       ./setup.sh --config /absolute/site.json [--state /absolute/private-state]

doctor  Inspect Linux, architecture, libc, existing commands and candidate profiles; no installation.
plan    Validate factual private-first plans and show exact stages; no installation.
apply   Install and verify requested stages; safe repeat runs verify completed receipts.
agent   Existing machine: launch the original Claude -> OMP two-phase workflow.

--config alone means apply. --only productivity limits plan/apply to productivity tools.
Run as the ordinary operator, with existing sudo access for system installs.
No public-network download or dependency-resolution fallback is provided.

Python bootstrap: select an existing Python >=3.9 via AGENTIC_PYTHON=/absolute/python.
If no suitable Python exists, first inspect internal repositories, then supply a factual
AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON to allow the included Linux x86-64 CPython.
That controller is separate from the eventual native tool installation.
USAGE
  exit 0
fi
# Avoid trying an x86-64 controller on an unsupported architecture when no
# adequate Python is already available. python.sh remains the source-policy gate.
if [[ -z "${AGENTIC_PYTHON:-}" ]] && ! python3 -c 'import sys;raise SystemExit(sys.version_info < (3,9))' >/dev/null 2>&1; then
  case "$(uname -m)" in
    x86_64|amd64) ;;
    *) echo 'BLOCKED: bundled controller Python supports Linux x86-64 only. Supply a qualified native AGENTIC_PYTHON and a separately built target payload.' >&2; exit 2 ;;
  esac
fi
export PYTHONDONTWRITEBYTECODE=1
exec "$TASK_SETUP_ROOT/scripts/python.sh" "$TASK_SETUP_ROOT/scripts/setup.py" "$@"
