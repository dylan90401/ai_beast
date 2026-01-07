#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"
source "$BASE_DIR/config/paths.env"

out="$BASE_DIR/logs/custom_nodes_audit_$(date +%Y%m%d_%H%M%S).txt"
mkdir -p "$BASE_DIR/logs"

if [[ -d "$COMFYUI_DIR/custom_nodes" ]]; then
  find "$COMFYUI_DIR/custom_nodes" -maxdepth 2 -name ".git" -type d -print | while read -r g; do
    repo="$(dirname "$g")"
    (cd "$repo" && echo "== $repo ==" && git status -sb && git log -1 --oneline) || true
    echo
  done > "$out"
  echo "[nodes-audit] wrote $out"
  "$BASE_DIR/scripts/17_custom_nodes_allowlist_check.sh" || true
else
  echo "[nodes-audit] no custom_nodes"
fi
