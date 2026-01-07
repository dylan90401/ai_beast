#!/usr/bin/env bash
set -euo pipefail

STRICT=0
for arg in "${@:-}"; do [[ "$arg" == "--strict" ]] && STRICT=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"
# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"

allow="$BASE_DIR/config/comfy_nodes_allowlist.txt"
[[ -d "${COMFYUI_DIR:-}/custom_nodes" ]] || { echo "[allowlist] no custom_nodes"; exit 0; }
[[ -f "$allow" ]] || { echo "[allowlist] allowlist missing: $allow"; exit 0; }

bad=0
while IFS= read -r gitdir; do
  repo_dir="$(dirname "$gitdir")"
  url="$(git -C "$repo_dir" remote get-url origin 2>/dev/null || true)"
  if [[ -z "$url" ]]; then
    echo "[allowlist] WARN: no origin remote: $repo_dir"
    continue
  fi
  if ! grep -Fqx "$url" "$allow"; then
    echo "[allowlist] NOT ALLOWLISTED: $url  ($repo_dir)"
    bad=1
  fi
done < <(find "$COMFYUI_DIR/custom_nodes" -maxdepth 2 -type d -name ".git" 2>/dev/null)

if [[ "$STRICT" -eq 1 && "$bad" -eq 1 ]]; then
  echo "[allowlist] STRICT FAILED"
  exit 2
fi
echo "[allowlist] ok"
