#!/usr/bin/env bash
set -euo pipefail
APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"
source "$BASE_DIR/config/paths.env"
mkdir -p "$DATA_DIR/maps" "$DATA_DIR/maps/osm" "$DATA_DIR/maps/tiles" "$DATA_DIR/maps/notebooks"
if [[ "$APPLY" -ne 1 ]]; then
  echo "[pack:mapping] DRYRUN would create map dirs under $DATA_DIR/maps"
  exit 0
fi
echo "Mapping pack installed: $(date)" > "$DATA_DIR/maps/README.txt"
