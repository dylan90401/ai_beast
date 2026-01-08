#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-help}"; shift || true

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

log(){ echo "[live] $*"; }
die(){ echo "[live] ERROR: $*" >&2; exit 1; }

run(){
  if [[ "$APPLY" -ne 1 ]]; then
    printf '[live] DRYRUN:'; printf ' %q' "$@"; printf '\n'
  else
    "$@"
  fi
}

apply_all(){
  run "$BASE_DIR/bin/beast" features merge --apply
  run "$BASE_DIR/bin/beast" features sync --apply
  run "$BASE_DIR/bin/beast" compose gen --apply
  run "$BASE_DIR/bin/beast" up
}

case "$ACTION" in
  apply)
    apply_all
    ;;
  enable)
    [[ -n "${1:-}" ]] || die "Usage: live enable <pack> [pack2...] [--apply]"
    packs=()
    for arg in "$@"; do [[ "$arg" == "--apply" ]] && continue; packs+=("$arg"); done
    run "$BASE_DIR/bin/beast" packs enable "${packs[@]}" --apply
    apply_all
    ;;
  disable)
    [[ -n "${1:-}" ]] || die "Usage: live disable <pack> [pack2...] [--apply]"
    packs=()
    for arg in "$@"; do [[ "$arg" == "--apply" ]] && continue; packs+=("$arg"); done
    run "$BASE_DIR/bin/beast" packs disable "${packs[@]}" --apply
    apply_all
    ;;
  restart)
    run "$BASE_DIR/bin/beast" down
    run "$BASE_DIR/bin/beast" up
    ;;
  status)
    echo "== Enabled packs (from config/features.env) =="
    grep -E '^FEATURE_PACKS_' "$BASE_DIR/config/features.env" 2>/dev/null || echo "(none)"
    echo
    echo "== Extensions =="
    "$BASE_DIR/bin/beast" extensions list || true
    echo
    echo "== Docker containers (if running) =="
    if command -v docker >/dev/null 2>&1; then
      docker ps --format 'table {{.Names}}	{{.Status}}	{{.Ports}}' || true
    else
      echo "(docker not installed)"
    fi
    ;;
  *)
    cat <<EOF
Usage:
  ./bin/beast live status
  ./bin/beast live apply --apply
  ./bin/beast live enable <pack> --apply
  ./bin/beast live disable <pack> --apply
  ./bin/beast live restart --apply

What "live apply" means:
- merges/syncs feature flags -> regenerates compose -> applies docker changes.
EOF
    ;;
esac
