#!/usr/bin/env bash
# core_services.sh — Core services pack (qdrant, redis, postgres)
# Foundation services for most deployments
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

log(){ echo "[pack:core_services] $*"; }
die(){ echo "[pack:core_services] ERROR: $*" >&2; exit 1; }

[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env"
# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"

# Extensions to enable
EXTENSIONS="qdrant redis postgres"

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would install core_services pack"
  log "  Extensions: $EXTENSIONS"
  exit 0
fi

log "Installing core_services pack..."

# Enable extensions
for ext in $EXTENSIONS; do
  ext_dir="$BASE_DIR/extensions/$ext"
  if [[ -d "$ext_dir" ]]; then
    log "Enabling extension: $ext"
    if [[ -f "$ext_dir/install.sh" ]]; then
      bash "$ext_dir/install.sh" --apply
    else
      touch "$ext_dir/enabled"
    fi
  else
    log "WARN: Extension not found: $ext"
  fi
done

log "Pack installed!"
log "Services:"
log "  - Qdrant (vector DB): port 6333"
log "  - Redis (cache): port 6379"
log "  - PostgreSQL (relational): port 5432"
log ""
log "Next: ./bin/beast compose gen --apply && ./bin/beast up"
