#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export BASE_DIR

# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

parse_common_flags "${@:-}"

TARGET=""
SRC=""
RUN_RECONCILE=1
PREBACKUP=1

for arg in "${@:-}"; do
  case "$arg" in
    --target=*) TARGET="${arg#--target=}" ;;
    --source=*) SRC="${arg#--source=}" ;;
    --no-reconcile) RUN_RECONCILE=0 ;;
    --no-prebackup) PREBACKUP=0 ;;
  esac
done

log_info "==> AI Beast Rollback"
log_info "    BASE_DIR: $BASE_DIR"
log_info "    MODE: $(mode_label)"

confirm_apply "Rollback to a previous backup snapshot" || exit 0

load_beast_config

BACKUP_ROOT="${BACKUP_DIR:-$BASE_DIR/backups}"
TARGET="${TARGET:-$BASE_DIR}"

if [[ -z "$SRC" ]]; then
  if [[ ! -d "$BACKUP_ROOT" ]]; then
    log_error "Backup directory not found: $BACKUP_ROOT"
    exit 1
  fi
  latest_manifest="$(BACKUP_ROOT="$BACKUP_ROOT" python3 - <<'PY'
import os
from pathlib import Path

root = Path(os.environ["BACKUP_ROOT"])
paths = list(root.glob("*/backup.manifest.json"))
if not paths:
    raise SystemExit(0)
latest = max(paths, key=lambda p: p.stat().st_mtime)
print(latest)
PY
)"
  if [[ -z "$latest_manifest" ]]; then
    log_error "No backups found in $BACKUP_ROOT"
    exit 1
  fi
  SRC="$(cd "$(dirname "$latest_manifest")" && pwd)"
fi

log_info "Selected backup: $SRC"
log_info "Target directory: $TARGET"

RESTORE_ARGS=()
[[ "${DRYRUN:-1}" -eq 0 ]] && RESTORE_ARGS+=(--apply)
[[ "$RUN_RECONCILE" -eq 0 ]] && RESTORE_ARGS+=(--no-reconcile)
[[ "$PREBACKUP" -eq 0 ]] && RESTORE_ARGS+=(--no-prebackup)
RESTORE_ARGS+=(--target="$TARGET")

run "$BASE_DIR/scripts/81_restore.sh" "$SRC" "${RESTORE_ARGS[@]}"

log_success "Rollback complete."
