#!/usr/bin/env bash
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

msg="[ext:apache_tika] stub installed (placeholder only)."
if [[ "$APPLY" -eq 1 ]]; then
  mkdir -p "$BASE_DIR/extensions/apache_tika/stub"
  echo "$msg" > "$BASE_DIR/extensions/apache_tika/installed.txt"
  echo "$msg"
else
  echo "[ext:apache_tika] DRYRUN would mark stub as installed."
fi
