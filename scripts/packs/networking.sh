#!/usr/bin/env bash
set -euo pipefail
APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"
source "$BASE_DIR/config/paths.env"
mkdir -p "$DATA_DIR/networking" "$BASE_DIR/logs"
if [[ "$APPLY" -ne 1 ]]; then
  echo "[pack:networking] DRYRUN would create $DATA_DIR/networking"
  exit 0
fi
echo "Networking pack installed: $(date)" > "$DATA_DIR/networking/README.txt"
