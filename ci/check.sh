#!/usr/bin/env bash
set -euo pipefail
TASK_CI_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$TASK_CI_ROOT"
export PYTHONDONTWRITEBYTECODE=1
python3 -B -m unittest discover -s tests -v
for TASK_SCRIPT in ./*.sh ./scripts/*.sh ./ci/*.sh; do
  bash -n "$TASK_SCRIPT"
done
python3 - <<'PY'
import ast
from pathlib import Path
for directory in ('scripts', 'build-tools', 'ci'):
    for source in Path(directory).glob('*.py'):
        ast.parse(source.read_text(), filename=str(source))
print('Python syntax and shell syntax checked; no installation or public download performed')
PY
