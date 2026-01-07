#!/usr/bin/env bash
set -euo pipefail
APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"
source "$BASE_DIR/config/paths.env"

cfgdir="$DATA_DIR/searxng"
if [[ "$APPLY" -ne 1 ]]; then
  echo "[ext:searxng] DRYRUN would create $cfgdir"
  exit 0
fi
mkdir -p "$cfgdir"
# minimal settings file placeholder (SearXNG will generate defaults)
touch "$cfgdir/.keep"
echo "[ext:searxng] ready: $cfgdir"
