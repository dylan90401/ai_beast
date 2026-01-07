#!/usr/bin/env bash
set -euo pipefail
APPLY=0
TARGET="${1:-}"
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"
source "$BASE_DIR/config/paths.env"

[[ -n "$TARGET" ]] || TARGET="$CACHE_DIR/downloads"

if ! command -v clamscan >/dev/null 2>&1; then
  echo "[model-scan] ClamAV not found. Install: brew install clamav"
  exit 0
fi

if [[ "$APPLY" -ne 1 ]]; then
  echo "[model-scan] DRYRUN would scan: $TARGET"
  exit 0
fi

clamscan -r --bell -i "$TARGET" || true
