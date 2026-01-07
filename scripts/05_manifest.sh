#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"
out="$BASE_DIR/config/manifests/manifest_$(date +%Y%m%d_%H%M%S).sha256"
mkdir -p "$(dirname "$out")"
(cd "$BASE_DIR" && find . -type f -not -path "./config/secrets/*" -print0 | xargs -0 shasum -a 256) > "$out"
echo "[manifest] wrote $out"
