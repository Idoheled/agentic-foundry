#!/usr/bin/env bash
# Keep the operator's launch cwd and configured agent environment.
set -euo pipefail
TASK_KIT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
TASK_AGENT="${1:-}"
[[ $# -gt 0 ]] && shift
if [[ "$TASK_AGENT" == omp ]]; then
  exec "$TASK_KIT_ROOT/upgrade.sh" start-omp "$@"
fi
if [[ "$TASK_AGENT" != claude ]]; then
  echo 'Usage: launch-handoff.sh claude [--state ABS] [-- CLAUDE_PROFILE_ARGS...]' >&2
  echo 'After phase 1: launch-handoff.sh omp [--state ABS]' >&2
  exit 2
fi
TASK_STATE="${XDG_STATE_HOME:-$HOME/.local/state}/agentic-stack/upgrade-r4"
if [[ "${1:-}" == --state ]]; then
  [[ $# -ge 2 ]] || { echo '--state requires an absolute path' >&2; exit 2; }
  TASK_STATE="$2"
  shift 2
fi
[[ "$TASK_STATE" == /* ]] || { echo '--state must be absolute' >&2; exit 2; }
[[ "${1:-}" == -- ]] && shift
command -v claude >/dev/null || { echo 'Your existing configured Claude command is unavailable' >&2; exit 2; }
TASK_PROMPT="Perform ONLY phase 1 of the user's two-phase offline upgrade. Your current directory is the operator's preserved launch context: $PWD. The extracted kit is $TASK_KIT_ROOT. Intended private workflow state: $TASK_STATE. Read $TASK_KIT_ROOT/docs/PHASE1_CLAUDE.md and $TASK_KIT_ROOT/docs/TWO_PHASE_UPGRADE.md completely. Inspect existing OMP profile flags, wrappers, environment, project configuration, hooks, skills, brain/instruction files and disconnected routes. Snapshot them before mutation. Prefer adequate existing/internal Artifactory/repository artifacts; use kit fallback only with evidence. Upgrade and qualify OMP only, using upgrade.sh begin/install-omp/record-check/complete-omp. Do not upgrade this running Claude or the remaining stack in phase 1. Declare phase 1 complete only after real internal model, tool, session, skill/hook/brain and preservation checks pass. Generate the private OMP_HANDOFF.md and STOP. The user will manually start the upgraded OMP to perform phase 2. Do not start OMP phase 2 yourself. Do not follow an older full-stack handoff ordering over this phase boundary. The full phase-1 brief follows:

$(cat "$TASK_KIT_ROOT/docs/PHASE1_CLAUDE.md")"
exec claude "$@" --dangerously-skip-permissions -p "$TASK_PROMPT"
