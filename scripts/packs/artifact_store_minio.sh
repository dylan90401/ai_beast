#!/usr/bin/env bash
# artifact_store_minio.sh — S3-compatible artifact store pack
# Enables MinIO for local S3 storage
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

log(){ echo "[pack:artifact_store_minio] $*"; }
die(){ echo "[pack:artifact_store_minio] ERROR: $*" >&2; exit 1; }

[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env"
# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"

# Extensions to enable
EXTENSIONS="minio"

# pip packages for S3 access
PIP_PACKAGES="boto3 minio"

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would install artifact_store_minio pack"
  log "  Extensions: $EXTENSIONS"
  log "  Pip packages: $PIP_PACKAGES"
  exit 0
fi

log "Installing artifact_store_minio pack..."

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
  if grep -q "^packs.artifact_store_minio:" "$features_yml"; then
    sed -i '' 's/^packs.artifact_store_minio:.*/packs.artifact_store_minio: true/' "$features_yml"
  else
    echo "packs.artifact_store_minio: true" >> "$features_yml"
  fi
fi

log "Pack installed!"
log "MinIO API: port 9001, Console: port 9002"
log "Default creds: minioadmin/minioadmin (change in production!)"
log "Next: ./bin/beast compose gen --apply && ./bin/beast up"
