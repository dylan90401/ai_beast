#!/usr/bin/env bash
set -euo pipefail

snapshot="${1:-}"
[[ -n "$snapshot" ]] || { echo "Usage: 60_restore.sh <snapshot_dir>"; exit 1; }

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

if [[ "$APPLY" -ne 1 ]]; then
  echo "[restore] DRYRUN: would restore from $snapshot into current BASE_DIR."
  echo "[restore] Re-run with --apply to execute."
  exit 0
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

tarball="$snapshot/base_dir.tgz"
[[ -f "$tarball" ]] || { echo "[restore] ERROR: missing $tarball" >&2; exit 1; }

tar -xzf "$tarball" -C "$BASE_DIR"
echo "[restore] Restored base project into $BASE_DIR"
echo "[restore] Now review config/paths.env then run: ./bin/beast preflight"
