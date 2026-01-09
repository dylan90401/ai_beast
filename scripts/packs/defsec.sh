#!/usr/bin/env bash
set -euo pipefail
APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"
source "$BASE_DIR/config/paths.env"
mkdir -p "$DATA_DIR/defsec" "$BASE_DIR/logs"
if [[ "$APPLY" -ne 1 ]]; then
  echo "[pack:defsec] DRYRUN would create $DATA_DIR/defsec"
  exit 0
fi
echo "DefSec pack installed: $(date)" > "$DATA_DIR/defsec/README.txt"
