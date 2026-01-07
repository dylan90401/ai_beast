#!/usr/bin/env bash
set -euo pipefail
APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

base="$BASE_DIR/config/features.yml"
localf="$BASE_DIR/config/features.local.yml"
out="$BASE_DIR/config/features.yml"

log(){ echo "[features-merge] $*"; }
[[ -f "$localf" ]] || { log "No local overrides ($localf)."; exit 0; }

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN would merge $localf into $base (override duplicate keys)."
  exit 0
fi

tmp="$BASE_DIR/config/.features.merge.tmp"
# naive merge: remove any keys overridden in local, then append local
cp "$base" "$tmp"
grep -E '^[a-zA-Z0-9_.-]+:' "$localf" | sed -E 's/:.*$//' | while read -r k; do
  [[ -n "$k" ]] || continue
  grep -vE "^${k}:" "$tmp" > "$tmp.2" || true
  mv "$tmp.2" "$tmp"
done
cat "$localf" >> "$tmp"
mv "$tmp" "$out"
log "Merged overrides into $out"
