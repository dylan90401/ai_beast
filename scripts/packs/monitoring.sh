#!/usr/bin/env bash
# monitoring.sh — Monitoring and observability pack
# Uptime Kuma + OTEL for production-like monitoring
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

log(){ echo "[pack:monitoring] $*"; }
die(){ echo "[pack:monitoring] ERROR: $*" >&2; exit 1; }

[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env"
# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"

# Extensions to enable
EXTENSIONS="uptime_kuma otel_collector"

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would install monitoring pack"
  log "  Extensions: $EXTENSIONS"
  exit 0
fi

log "Installing monitoring pack..."

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
log "  - Uptime Kuma: port 3001"
log "  - OTel Collector: gRPC=4317, HTTP=4318"
log ""
log "Next: ./bin/beast compose gen --apply && ./bin/beast up"
