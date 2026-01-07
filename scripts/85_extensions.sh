#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-help}"; shift || true

APPLY=0
VERBOSE=0
for arg in "${@:-}"; do
  [[ "$arg" == "--apply" ]] && APPLY=1
  [[ "$arg" == "--verbose" ]] && VERBOSE=1
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

log(){ echo "[ext] $*"; }
die(){ echo "[ext] ERROR: $*" >&2; exit 1; }

ext_root="$BASE_DIR/extensions"
mkdir -p "$ext_root"

list_ext(){
  find "$ext_root" -mindepth 1 -maxdepth 1 -type d -print | sort | while read -r d; do
    name="$(basename "$d")"
    if [[ -f "$d/enabled" ]]; then
      echo "$name\tenabled"
    else
      echo "$name\tdisabled"
    fi
  done
}

enable_ext(){
  local name="$1"
  local dir="$ext_root/$name"
  [[ -d "$dir" ]] || die "Unknown extension '$name' (expected: $dir)"
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would enable $name"
  else
    : > "$dir/enabled"
  fi
  log "enabled: $name"
}

disable_ext(){
  local name="$1"
  local dir="$ext_root/$name"
  [[ -d "$dir" ]] || die "Unknown extension '$name' (expected: $dir)"
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would disable $name"
  else
    rm -f "$dir/enabled" || true
  fi
  log "disabled: $name"
}

install_ext(){
  local name="$1"
  local dir="$ext_root/$name"
  local installer="$dir/install.sh"
  [[ -d "$dir" ]] || die "Unknown extension '$name' (expected: $dir)"
  [[ -f "$installer" ]] || die "Extension '$name' has no install.sh"

  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would run $installer --apply"
    bash "$installer" || true
    return 0
  fi

  log "Running: $installer --apply"
  bash "$installer" --apply
}

case "$ACTION" in
  list) list_ext | expand -t 18 ;;

  enable)
    [[ -n "${1:-}" ]] || die "Usage: extensions enable <name...> [--apply]"
    for a in "$@"; do [[ "$a" == "--apply" ]] && continue; enable_ext "$a"; done
    ;;

  disable)
    [[ -n "${1:-}" ]] || die "Usage: extensions disable <name...> [--apply]"
    for a in "$@"; do [[ "$a" == "--apply" ]] && continue; disable_ext "$a"; done
    ;;

  install)
    [[ -n "${1:-}" ]] || die "Usage: extensions install <name...> [--apply]"
    for a in "$@"; do [[ "$a" == "--apply" ]] && continue; install_ext "$a"; done
    ;;

  *)
    cat <<EOT
Usage:
  ./bin/beast extensions list
  ./bin/beast extensions enable <name...> --apply
  ./bin/beast extensions disable <name...> --apply
  ./bin/beast extensions install <name...> [--apply]

How it works:
- Each extension lives under: extensions/<name>/
- If extensions/<name>/enabled exists, its compose.fragment.yaml is included by compose gen.
- 'install' runs extensions/<name>/install.sh to set up optional local bits.
- Compatibility: if no enabled markers exist anywhere, compose gen includes all fragments (legacy mode).
EOT
    ;;
esac
