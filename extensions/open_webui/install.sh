#!/usr/bin/env bash
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

log(){ echo "[ext:open_webui] $*"; }

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would enable open_webui extension"
  exit 0
fi

touch "$script_dir/enabled"

# Ensure port configured
if [[ -f "$BASE_DIR/config/ports.env" ]]; then
  grep -q '^export PORT_WEBUI=' "$BASE_DIR/config/ports.env" || \
    echo 'export PORT_WEBUI="3000"' >> "$BASE_DIR/config/ports.env"
fi

log "Enabled open_webui extension"
log "Access at: http://127.0.0.1:\${PORT_WEBUI:-3000}"
