#!/usr/bin/env bash
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

log(){ echo "[ext:qdrant] $*"; }

# shellcheck disable=SC1090
[[ -f "$BASE_DIR/config/paths.env" ]] && source "$BASE_DIR/config/paths.env"

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would enable qdrant extension"
  log "  - Create enabled marker"
  log "  - Add PORT_QDRANT and PORT_QDRANT_GRPC to ports.env"
  exit 0
fi

# Create enabled marker
touch "$script_dir/enabled"
log "Enabled qdrant extension"

# Ensure ports are configured
if [[ -f "$BASE_DIR/config/ports.env" ]]; then
  grep -q '^export PORT_QDRANT=' "$BASE_DIR/config/ports.env" || \
    echo 'export PORT_QDRANT="6333"' >> "$BASE_DIR/config/ports.env"
  grep -q '^export PORT_QDRANT_GRPC=' "$BASE_DIR/config/ports.env" || \
    echo 'export PORT_QDRANT_GRPC="6334"' >> "$BASE_DIR/config/ports.env"
fi

log "Done. Next: ./bin/beast compose gen --apply && ./bin/beast up"
