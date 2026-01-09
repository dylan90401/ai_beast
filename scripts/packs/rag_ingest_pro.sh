#!/usr/bin/env bash
# rag_ingest_pro.sh — Advanced RAG ingestion pack
# Enables Apache Tika and Unstructured for robust document parsing
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

log(){ echo "[pack:rag_ingest_pro] $*"; }
die(){ echo "[pack:rag_ingest_pro] ERROR: $*" >&2; exit 1; }

[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env"
# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"

# Extensions to enable
EXTENSIONS="apache_tika unstructured_api"

# pip packages
PIP_PACKAGES="unstructured[all-docs] pymupdf pypdf python-docx openpyxl"

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would install rag_ingest_pro pack"
  log "  Extensions: $EXTENSIONS"
  log "  Pip packages: $PIP_PACKAGES"
  exit 0
fi

log "Installing rag_ingest_pro pack..."

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

# Install pip packages in venv
if [[ -f "$BASE_DIR/.venv/bin/pip3" ]]; then
  log "Installing pip3 packages..."
  # shellcheck disable=SC2086
  "$BASE_DIR/.venv/bin/pip3" install --quiet $PIP_PACKAGES
elif command -v pip3 >/dev/null 2>&1; then
  log "Installing pip3 packages (system)..."
  # shellcheck disable=SC2086
  pip3 install --quiet --user $PIP_PACKAGES
fi

# Create ingest directories
mkdir -p "$DATA_DIR/inbox" "$DATA_DIR/processed"

# Update feature flag
features_yml="$BASE_DIR/config/features.yml"
if [[ -f "$features_yml" ]]; then
  if grep -q "^packs.rag_ingest_pro:" "$features_yml"; then
    sed -i '' 's/^packs.rag_ingest_pro:.*/packs.rag_ingest_pro: true/' "$features_yml"
  else
    echo "packs.rag_ingest_pro: true" >> "$features_yml"
  fi
fi

log "Pack installed!"
log "Next: ./bin/beast compose gen --apply && ./bin/beast up"
