#!/usr/bin/env bash
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

msg="[ext:minio] no local install needed; docker service only."
if [[ "$APPLY" -eq 1 ]]; then
  echo "$msg"
else
  echo "[ext:minio] DRYRUN would do nothing."
fi
