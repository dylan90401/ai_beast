#!/usr/bin/env bash
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

# shellcheck disable=SC1091
[[ -f "$BASE_DIR/config/paths.env" ]] && source "$BASE_DIR/config/paths.env" || true

DATA_ROOT="${DATA_DIR:-$BASE_DIR/data}/dify"

if [[ "$APPLY" -eq 1 ]]; then
  mkdir -p "$DATA_ROOT/postgres" "$DATA_ROOT/redis" "$DATA_ROOT/storage"
  echo "[ext:dify] data dirs ready: $DATA_ROOT"
else
  echo "[ext:dify] DRYRUN would create data dirs under: $DATA_ROOT"
fi
