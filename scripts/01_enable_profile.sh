#!/usr/bin/env bash
# 01_enable_profile.sh — Enable extensions based on profile (lite/full/prodish)
set -euo pipefail

APPLY=0
PROFILE=""
for arg in "${@:-}"; do
  [[ "$arg" == "--apply" ]] && APPLY=1
  [[ "$arg" == "lite" ]] && PROFILE="lite"
  [[ "$arg" == "full" ]] && PROFILE="full"
  [[ "$arg" == "prodish" ]] && PROFILE="prodish"
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

log(){ echo "[ai-beast:profile] $*"; }
die(){ echo "[ai-beast:profile] ERROR: $*" >&2; exit 1; }

usage() {
  cat <<EOF
Usage: $0 <profile> [--apply]

Profiles:
  lite     Minimal stack (ollama, qdrant, redis)
  full     Standard stack (lite + postgres, n8n, open_webui, searxng)
  prodish  Production-like (full + traefik, otel, uptime_kuma)

Options:
  --apply  Actually enable extensions (default: DRYRUN)

Examples:
  $0 lite              # Preview lite profile
  $0 full --apply      # Enable full profile
EOF
  exit 1
}

[[ -z "$PROFILE" ]] && usage

# Profile definitions
declare -A PROFILES
PROFILES[lite]="qdrant redis"
PROFILES[full]="qdrant redis postgres n8n open_webui searxng minio"
PROFILES[prodish]="qdrant redis postgres n8n open_webui searxng minio traefik otel_collector uptime_kuma"

EXTENSIONS="${PROFILES[$PROFILE]}"

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would enable profile '$PROFILE'"
  log "Extensions: $EXTENSIONS"
  log ""
  log "Run with --apply to actually enable"
  exit 0
fi

log "Enabling profile: $PROFILE"

# Disable all extensions first
for ext_dir in "$BASE_DIR/extensions/"*/; do
  [[ -f "$ext_dir/enabled" ]] && rm "$ext_dir/enabled"
done

# Enable profile extensions
for ext in $EXTENSIONS; do
  ext_dir="$BASE_DIR/extensions/$ext"
  if [[ -d "$ext_dir" ]]; then
    log "  Enabling: $ext"
    touch "$ext_dir/enabled"
  else
    log "  WARN: Extension not found: $ext"
  fi
done

# Update profiles.env
profiles_env="$BASE_DIR/config/profiles.env"
line="export AI_BEAST_PROFILE=\"$PROFILE\""
if [[ -f "$profiles_env" ]]; then
  if grep -Eq '^(export )?AI_BEAST_PROFILE=' "$profiles_env"; then
    sed -i '' -E "s/^(export )?AI_BEAST_PROFILE=.*/$line/" "$profiles_env"
  else
    echo "$line" >> "$profiles_env"
  fi
else
  echo "$line" > "$profiles_env"
fi

log "Profile '$PROFILE' enabled!"
log ""
log "Next steps:"
log "  1. ./bin/beast compose gen --apply"
log "  2. ./bin/beast up"
