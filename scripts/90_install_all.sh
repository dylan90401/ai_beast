#!/usr/bin/env bash
set -euo pipefail

APPLY=0
WANT_LAUNCHD=0
for arg in "${@:-}"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --launchd) WANT_LAUNCHD=1 ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"
log(){ echo "[install] $*"; }
run(){ if [[ "$APPLY" -ne 1 ]]; then echo "[install] DRYRUN $*"; else eval "$*"; fi }

log "1) init (paths)"
run ""$BASE_DIR/bin/beast" init --apply"

log "2) bootstrap (brew deps + ollama + comfyui)"
run ""$BASE_DIR/bin/beast" bootstrap --apply"

log "3) comfy postinstall (models dir + workflows)"
run ""$BASE_DIR/bin/beast" comfy postinstall --apply"

log "4) features sync"
run ""$BASE_DIR/bin/beast" features sync --apply"

log "5) compose gen"
run ""$BASE_DIR/bin/beast" compose gen --apply"

log "6) start services"
run ""$BASE_DIR/bin/beast" up"

if [[ "$WANT_LAUNCHD" -eq 1 ]]; then
  log "7) launchd"
  run ""$BASE_DIR/bin/beast" launchd --apply"
fi

log "Done. Next:"
echo "  $BASE_DIR/bin/beast doctor"
echo "  $BASE_DIR/bin/beast urls"
