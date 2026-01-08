#!/usr/bin/env bash
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

in="$BASE_DIR/config/features.yml"
out="$BASE_DIR/config/features.env"

log(){ echo "[features] $*"; }

[[ -f "$in" ]] || { log "Missing: $in"; exit 1; }

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would generate $out from $in"
  exit 0
fi

tmp="$(mktemp)"
{
  echo "# Generated from config/features.yml on $(date)"
  echo "# shellcheck disable=SC2034"
  while IFS= read -r line; do
    # strip comments
    line="${line%%#*}"
    line="$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    [[ -z "$line" ]] && continue
    [[ "$line" != *:* ]] && continue
    key="${line%%:*}"
    val="${line#*:}"
    key="$(echo "$key" | tr -d '"\047' | sed -e 's/[[:space:]]*$//')"
    val="$(echo "$val" | tr -d '"\047' | sed -e 's/^[[:space:]]*//')"

    # normalize key -> FEATURE_*
    envkey="FEATURE_$(echo "$key" | tr '[:lower:]' '[:upper:]' | sed -E 's/[^A-Z0-9]+/_/g' | sed -E 's/^_+|_+$//g')"

    case "${val,,}" in
      true|yes|1) echo "export ${envkey}=1" ;;
      false|no|0) echo "export ${envkey}=0" ;;
      *) printf 'export %s="%s"\n' "$envkey" "$val" ;;
    esac
  done < "$in"
} > "$tmp"

mkdir -p "$BASE_DIR/config"
mv "$tmp" "$out"
log "Wrote: $out"
