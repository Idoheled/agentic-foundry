#!/usr/bin/env bash
# Prefer a selected internal/existing Python, then a suitable host Python.
# Kit bootstrap requires an explicit internal-repository inspection/fallback reason.
set -euo pipefail
TASK_KIT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ -n "${AGENTIC_PYTHON:-}" ]]; then
  if [[ "$AGENTIC_PYTHON" != /* || ! -x "$AGENTIC_PYTHON" ]] || ! "$AGENTIC_PYTHON" -c 'import sys;sys.exit(0 if sys.version_info >= (3,9) else 1)' >/dev/null 2>&1; then
    echo 'AGENTIC_PYTHON must name a verified, executable, absolute Python3.9+ path.' >&2
    exit 2
  fi
  exec "$AGENTIC_PYTHON" "$@"
fi
if command -v python3 >/dev/null && python3 -c 'import sys;sys.exit(0 if sys.version_info >= (3,9) else 1)' >/dev/null 2>&1; then
  exec python3 "$@"
fi
if [[ -z "${AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON:-}" || "${AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON}" == *REPLACE_* ]]; then
  echo 'No suitable Python selected. Inspect internal OS/package repositories first and install/select Python with AGENTIC_PYTHON.' >&2
  echo 'If unavailable or insufficient, set AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON to the factual inspection result to use the portable kit bootstrap. Never replace /usr/bin/python3 blindly.' >&2
  exit 2
fi
TASK_ARCHIVE="$TASK_KIT_ROOT/payload/packages/cpython-3.12.16+20261110-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
TASK_SHA=6a9e62dad033790aef722dbd370e0ce76ce17b73627ba3ae679f537049350b39
TASK_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/agentic-offline-python/3.12.16-20261110"
if [[ ! -f "$TASK_CACHE/.complete" ]]; then
  printf '%s  %s\n' "$TASK_SHA" "$TASK_ARCHIVE" | sha256sum --check --status
  mkdir -p "$(dirname "$TASK_CACHE")"
  TASK_TEMP="$(mktemp -d "$(dirname "$TASK_CACHE")/python-install.XXXXXXXX")"
  trap 'rm -rf -- "$TASK_TEMP"' EXIT
  tar -xzf "$TASK_ARCHIVE" -C "$TASK_TEMP"
  "$TASK_TEMP/python/bin/python3" -c 'import sys,ssl,hashlib,tarfile;assert sys.version_info >= (3,9)'
  touch "$TASK_TEMP/.complete"
  if [[ -e "$TASK_CACHE" ]]; then
    echo "An incomplete portable Python cache exists at $TASK_CACHE; inspect and remove only that generated directory before retrying." >&2
    exit 1
  fi
  mv "$TASK_TEMP" "$TASK_CACHE"
fi
"$TASK_CACHE/python/bin/python3" - "$TASK_CACHE/bootstrap-source-decision.json" <<'PY'
import datetime,json,os,pathlib,sys
p=pathlib.Path(sys.argv[1])
data={"source":"kit","purpose":"controller-bootstrap-only","time":datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "reason":os.environ["AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON"],
      "note":"Final host capability provisioning still follows internal-repository and package-ownership policy."}
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,"w") as stream:json.dump(data,stream,indent=2);stream.write("\n")
os.chmod(p,0o600)
PY
exec "$TASK_CACHE/python/bin/python3" "$@"
