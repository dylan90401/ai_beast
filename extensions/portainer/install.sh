#!/usr/bin/env bash
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"
source "$BASE_DIR/config/paths.env"

if [[ "$APPLY" -ne 1 ]]; then
  echo "[ext:portainer] DRYRUN would enable portainer extension"
  exit 0
fi

mkdir -p "$DATA_DIR/portainer"
: > "$script_dir/enabled"
echo "[ext:portainer] ready: $DATA_DIR/portainer"
echo "[ext:portainer] Access at: http://127.0.0.1:\${PORT_PORTAINER:-9000}"
