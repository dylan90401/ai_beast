#!/usr/bin/env bash
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

if [[ "$APPLY" -eq 1 ]]; then
  echo "[ext:unstructured_api] no local install needed; docker service only."
else
  echo "[ext:unstructured_api] DRYRUN would do nothing."
fi
