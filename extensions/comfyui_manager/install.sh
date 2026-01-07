#!/usr/bin/env bash
set -euo pipefail
APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"
source "$BASE_DIR/config/paths.env"

dest="$COMFYUI_DIR/custom_nodes/ComfyUI-Manager"
repo="https://github.com/Comfy-Org/ComfyUI-Manager.git"

if [[ "$APPLY" -ne 1 ]]; then
  echo "[ext:comfyui_manager] DRYRUN would install to $dest"
  exit 0
fi

mkdir -p "$COMFYUI_DIR/custom_nodes"
if [[ -d "$dest/.git" ]]; then
  (cd "$dest" && git pull --rebase) || true
else
  git clone "$repo" "$dest"
fi
echo "[ext:comfyui_manager] done"
