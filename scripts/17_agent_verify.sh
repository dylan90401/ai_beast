#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${BASE_DIR:-$(cd "$script_dir/.." && pwd)}"
PY="$BASE_DIR/apps/agent/.venv/bin/python3"
if [[ -x "$PY" ]]; then :; else PY="python3"; fi
exec "$PY" "$BASE_DIR/apps/agent/verifier_strict.py"
