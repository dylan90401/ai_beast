#!/usr/bin/env bash
set -euo pipefail

# common.sh — shared helpers for AI Beast scripts

log()  { echo "[${AI_BEAST_LOG_PREFIX:-beast}] $*"; }
warn() { echo "[${AI_BEAST_LOG_PREFIX:-beast}][WARN] $*" >&2; }
die()  { echo "[${AI_BEAST_LOG_PREFIX:-beast}][ERROR] $*" >&2; exit 1; }

is_darwin(){ [[ "$(uname -s)" == "Darwin" ]]; }

have_cmd(){ command -v "$1" >/dev/null 2>&1; }

require_cmd(){
  local c="$1"
  have_cmd "$c" || die "Missing required command: $c"
}

# Parse common flags into APPLY/VERBOSE (call in scripts)
parse_common_flags(){
  APPLY=0
  VERBOSE=0
  for arg in "${@:-}"; do
    case "$arg" in
      --apply) APPLY=1 ;;
      --dry-run) APPLY=0 ;;
      --verbose) VERBOSE=1 ;;
    esac
  done
}

run(){
  # shellcheck disable=SC2154
  if [[ "${APPLY:-0}" -eq 1 ]]; then
    log "RUN: $*"
    "$@"
  else
    log "DRYRUN: $*"
  fi
}

# try_run: never exits the script; returns 0/1
try_run(){
  # shellcheck disable=SC2154
  if [[ "${APPLY:-0}" -eq 1 ]]; then
    log "TRY: $*"
    "$@" || { warn "Command failed (continuing): $*"; return 1; }
  else
    log "DRYRUN: $*"
  fi
}

load_env_if_exists(){
  local f="$1"
  [[ -f "$f" ]] && \
    # shellcheck disable=SC1090
    source "$f" || true
}
