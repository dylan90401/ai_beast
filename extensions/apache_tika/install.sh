#!/usr/bin/env bash
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

if [[ "$APPLY" -eq 1 ]]; then
  echo "[ext:apache_tika] no local install needed; docker service only."
else
  echo "[ext:apache_tika] DRYRUN would do nothing."
fi
