#!/usr/bin/env bash
# agent_builders.sh — Low-code agent builder pack
# Enables Langflow, Flowise, and Dify extensions
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

log(){ echo "[pack:agent_builders] $*"; }
die(){ echo "[pack:agent_builders] ERROR: $*" >&2; exit 1; }

[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env"
# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"

# Extensions to enable
EXTENSIONS="langflow flowise dify"

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would install agent_builders pack"
  log "  Extensions to enable: $EXTENSIONS"
  exit 0
fi

log "Installing agent_builders pack..."

# Enable docker extensions
for ext in $EXTENSIONS; do
  ext_dir="$BASE_DIR/extensions/$ext"
  if [[ -d "$ext_dir" ]]; then
    log "Enabling extension: $ext"
    touch "$ext_dir/enabled"
  else
    log "WARN: Extension not found: $ext"
  fi
done

# Update feature flag
features_yml="$BASE_DIR/config/features.yml"
if [[ -f "$features_yml" ]]; then
  if grep -q "^packs.agent_builders:" "$features_yml"; then
    sed -i '' 's/^packs.agent_builders:.*/packs.agent_builders: true/' "$features_yml"
  else
    echo "packs.agent_builders: true" >> "$features_yml"
  fi
fi

log "Pack installed!"
log "Next: ./bin/beast compose gen --apply && ./bin/beast up"
