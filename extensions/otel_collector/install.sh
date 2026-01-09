#!/usr/bin/env bash
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

msg="[ext:otel_collector] prepared minimal collector config."
if [[ "$APPLY" -eq 1 ]]; then
  mkdir -p "$BASE_DIR/extensions/otel_collector"
  echo "$msg" > "$BASE_DIR/extensions/otel_collector/installed.txt"
  echo "$msg"
else
  echo "[ext:otel_collector] DRYRUN would prepare minimal collector config."
fi
