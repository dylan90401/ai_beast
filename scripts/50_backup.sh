#!/usr/bin/env bash
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"
source "$BASE_DIR/config/paths.env"

ts="$(date +%Y%m%d_%H%M%S)"
out_dir="$BACKUP_DIR/snapshots/$ts"
manifest="$out_dir/manifest.sha256"

run(){
  if [[ "$APPLY" -eq 1 ]]; then
    "$@"
  else
    printf '[backup] DRYRUN:'; printf ' %q' "$@"; printf '\n'
  fi
}

run mkdir -p "$out_dir"
# snapshot minimal config + scripts + docker + extensions + workflows
tar_items=(
  config
  bin
  scripts
  docker
  apps
  extensions
  kryptos_project.yml
  README.md
)
existing_items=()
for item in "${tar_items[@]}"; do
  [[ -e "$BASE_DIR/$item" ]] && existing_items+=("$item")
done
if [[ "${#existing_items[@]}" -gt 0 ]]; then
  run tar -czf "$out_dir/base_dir.tgz" -C "$BASE_DIR" "${existing_items[@]}"
else
  echo "[backup] WARN: nothing to archive from base dir"
fi
# record where heavy roots live
run cp -f "$BASE_DIR/config/paths.env" "$out_dir/paths.env"
if [[ -f "$BASE_DIR/config/ports.env" ]]; then
  run cp -f "$BASE_DIR/config/ports.env" "$out_dir/ports.env"
fi

if [[ "$APPLY" -eq 1 ]]; then
  (cd "$out_dir" && shasum -a 256 base_dir.tgz paths.env ports.env 2>/dev/null | tee "$manifest") || true
  echo "[backup] Wrote $out_dir"
else
  echo "[backup] DRYRUN complete. Re-run with --apply."
fi
