#!/usr/bin/env bash
set -euo pipefail
APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"
source "$BASE_DIR/config/paths.env"

echo "[ext:example_service] This is a template extension."
if [[ "$APPLY" -eq 1 ]]; then
  mkdir -p "$BASE_DIR/apps/example_service"
  echo "ok" > "$BASE_DIR/apps/example_service/installed.txt"
  echo "[ext:example_service] Installed."
else
  echo "[ext:example_service] DRYRUN would install into $BASE_DIR/apps/example_service"
fi
