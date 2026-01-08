#!/usr/bin/env bash
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

log(){ echo "[ext:traefik] $*"; }

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would enable traefik extension"
  log "WARNING: Traefik uses ports 80/443 - ensure no conflicts"
  exit 0
fi

touch "$script_dir/enabled"

if [[ -f "$BASE_DIR/config/ports.env" ]]; then
  grep -q '^export PORT_TRAEFIK_HTTP=' "$BASE_DIR/config/ports.env" || \
    echo 'export PORT_TRAEFIK_HTTP="80"' >> "$BASE_DIR/config/ports.env"
  grep -q '^export PORT_TRAEFIK_HTTPS=' "$BASE_DIR/config/ports.env" || \
    echo 'export PORT_TRAEFIK_HTTPS="443"' >> "$BASE_DIR/config/ports.env"
  grep -q '^export PORT_TRAEFIK_DASHBOARD=' "$BASE_DIR/config/ports.env" || \
    echo 'export PORT_TRAEFIK_DASHBOARD="8080"' >> "$BASE_DIR/config/ports.env"
fi

log "Enabled traefik extension"
log "Dashboard at: http://127.0.0.1:\${PORT_TRAEFIK_DASHBOARD:-8080}"
