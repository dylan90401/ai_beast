#!/usr/bin/env bash
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

log(){ echo "[ext:postgres] $*"; }

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would enable postgres extension"
  exit 0
fi

touch "$script_dir/enabled"

if [[ -f "$BASE_DIR/config/ports.env" ]]; then
  grep -q '^export PORT_POSTGRES=' "$BASE_DIR/config/ports.env" || \
    echo 'export PORT_POSTGRES="5432"' >> "$BASE_DIR/config/ports.env"
fi

log "Enabled postgres extension"
log "Default credentials: aibeast/aibeast_dev (change in production!)"
