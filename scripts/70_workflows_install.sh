#!/usr/bin/env bash
set -euo pipefail
APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"
source "$BASE_DIR/config/paths.env"

src="$BASE_DIR/workflows/templates"
t1="$COMFYUI_DIR/user/default/workflows/ai-beast"
t2="$COMFYUI_DIR/user/workflows/ai-beast"
target="$t1"
[[ -d "$(dirname "$t1")" ]] || target="$t2"

if [[ "$APPLY" -ne 1 ]]; then
  echo "[workflows] DRYRUN would copy $src -> $target"
  exit 0
fi

mkdir -p "$target"
cp -f "$src/"*.json "$target/"
echo "[workflows] installed: $target"
