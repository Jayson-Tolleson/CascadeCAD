#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
fi
echo "Running LFTR Next pre-#7 checkpoint..."
PYTHONPATH="$ROOT" "$ROOT/scripts/check_pre7_checkpoint.py"
echo "LFTR Next pre-#7 checkpoint passed."
