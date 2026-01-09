#!/usr/bin/env bash
# observability_otel.sh — OpenTelemetry observability pack
# Enables OTel collector for tracing and metrics
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

log(){ echo "[pack:observability_otel] $*"; }
die(){ echo "[pack:observability_otel] ERROR: $*" >&2; exit 1; }

[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env"
# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"

# Extensions to enable
EXTENSIONS="otel_collector"

# pip packages for instrumentation
PIP_PACKAGES="opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-requests opentelemetry-exporter-otlp"

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would install observability_otel pack"
  log "  Extensions: $EXTENSIONS"
  log "  Pip packages: $PIP_PACKAGES"
  exit 0
fi

log "Installing observability_otel pack..."

# Enable extensions
for ext in $EXTENSIONS; do
  ext_dir="$BASE_DIR/extensions/$ext"
  if [[ -d "$ext_dir" ]]; then
    log "Enabling extension: $ext"
    touch "$ext_dir/enabled"
  else
    log "WARN: Extension not found: $ext"
  fi
done

# Install pip packages
if [[ -f "$BASE_DIR/.venv/bin/pip3" ]]; then
  log "Installing pip3 packages..."
  # shellcheck disable=SC2086
  "$BASE_DIR/.venv/bin/pip3" install --quiet $PIP_PACKAGES
elif command -v pip3 >/dev/null 2>&1; then
  log "Installing pip3 packages (system)..."
  # shellcheck disable=SC2086
  pip3 install --quiet --user $PIP_PACKAGES
fi

# Update feature flag
features_yml="$BASE_DIR/config/features.yml"
if [[ -f "$features_yml" ]]; then
  if grep -q "^packs.observability_otel:" "$features_yml"; then
    sed -i '' 's/^packs.observability_otel:.*/packs.observability_otel: true/' "$features_yml"
  else
    echo "packs.observability_otel: true" >> "$features_yml"
  fi
fi

log "Pack installed!"
log "OTel endpoints: gRPC=4317, HTTP=4318"
log "Next: ./bin/beast compose gen --apply && ./bin/beast up"
