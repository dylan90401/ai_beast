#!/usr/bin/env bash
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

log(){ echo "[ext:jupyter] $*"; }

# shellcheck disable=SC1090
[[ -f "$BASE_DIR/config/paths.env" ]] && source "$BASE_DIR/config/paths.env"

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would enable jupyter extension"
  log "  - Create enabled marker"
  log "  - Add PORT_JUPYTER to ports.env"
  exit 0
fi

touch "$script_dir/enabled"
log "Enabled jupyter extension"

if [[ -f "$BASE_DIR/config/ports.env" ]]; then
  grep -q '^export PORT_JUPYTER=' "$BASE_DIR/config/ports.env" || \
    echo 'export PORT_JUPYTER="8889"' >> "$BASE_DIR/config/ports.env"
fi

if [[ -n "${DATA_DIR:-}" ]]; then
  mkdir -p "$DATA_DIR/notebooks"
fi

log "Done. Next: ./bin/beast compose gen --apply && ./bin/beast up"
