#!/usr/bin/env bash
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

# shellcheck disable=SC1091
[[ -f "$BASE_DIR/config/paths.env" ]] && source "$BASE_DIR/config/paths.env" || true

msg="[ext:dify] stub extension installed (placeholder only)."
if [[ "$APPLY" -eq 1 ]]; then
  mkdir -p "$BASE_DIR/extensions/dify/stub"
  echo "$msg" > "$BASE_DIR/extensions/dify/installed.txt"
  echo "$msg"
else
  echo "[ext:dify] DRYRUN would mark stub as installed."
fi
