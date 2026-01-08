#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-restore}"; shift || true

APPLY=0
VERBOSE=0
SRC="${1:-}"; shift || true
TARGET=""
RUN_RECONCILE=1
PREBACKUP=1

for arg in "${@:-}"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --verbose) VERBOSE=1 ;;
    --target=*) TARGET="${arg#--target=}" ;;
    --no-reconcile) RUN_RECONCILE=0 ;;
    --no-prebackup) PREBACKUP=0 ;;
  esac
done

log(){ echo "[restore] $*"; }
dbg(){ [[ "$VERBOSE" -eq 1 ]] && echo "[restore][dbg] $*" || true; }
die(){ echo "[restore] ERROR: $*" >&2; exit 1; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

case "$ACTION" in
  restore) ;;
  help|--help|-h)
    cat <<'EOF'
Usage:
  ./bin/beast restore <backup_dir|manifest|archive.tar.gz> [--target=/path] [--apply] [--no-reconcile] [--no-prebackup]
EOF
    exit 0
    ;;
  *) die "Usage: beast restore <backup_dir|manifest|archive.tar.gz> [--apply]" ;;
esac

[[ -n "$SRC" ]] || die "Usage: $0 <backup_dir|manifest|archive.tar.gz> [--target=/path] [--apply]"

TARGET="${TARGET:-$BASE_DIR}"
mkdir -p "$TARGET"

# Determine manifest
MANIFEST=""
if [[ -d "$SRC" ]]; then
  [[ -f "$SRC/backup.manifest.json" ]] || die "No backup.manifest.json found in $SRC"
  MANIFEST="$SRC/backup.manifest.json"
  BACKUP_DIR_PATH="$SRC"
elif [[ -f "$SRC" && "$SRC" == *.json && "$(basename "$SRC")" == "backup.manifest.json" ]]; then
  MANIFEST="$SRC"
  BACKUP_DIR_PATH="$(cd "$(dirname "$SRC")" && pwd)"
elif [[ -f "$SRC" && "$SRC" == *.tar.gz ]]; then
  # legacy single-archive restore
  MANIFEST=""
  BACKUP_DIR_PATH=""
else
  die "Unrecognized restore source: $SRC"
fi

if [[ "$APPLY" -ne 1 ]]; then
  if [[ -n "$MANIFEST" ]]; then
    log "DRYRUN: would restore from manifest: $MANIFEST into $TARGET"
  else
    log "DRYRUN: would restore legacy archive: $SRC into $TARGET"
  fi
  [[ "$RUN_RECONCILE" -eq 1 ]] && log "DRYRUN: would run: $TARGET/bin/beast state apply --apply"
  exit 0
fi

# Pre-backup current target (failsafe rollback)
if [[ "$PREBACKUP" -eq 1 && -d "$TARGET/config" ]]; then
  log "Pre-backup current workspace (failsafe rollback)..."
  (cd "$TARGET" && ./scripts/80_backup.sh backup --profile=min --name="pre_restore_$(date -u +%Y%m%d_%H%M%S)" --apply) || true
fi

# Restore helpers
cat_parts(){
  local dir="$1" pattern="$2"
  python3 - "$dir" "$pattern" <<'PY'
import shutil
import sys
from pathlib import Path

base = Path(sys.argv[1])
pattern = sys.argv[2]
for path in sorted(base.glob(pattern), key=lambda p: p.name):
    with path.open("rb") as handle:
        shutil.copyfileobj(handle, sys.stdout.buffer)
PY
}

extract_stream(){
  local dest="$1"
  mkdir -p "$dest"
  tar -C "$dest" -xzf -
}

extract_parts(){
  local prefix="$1" dest="$2"
  if [[ -f "$BACKUP_DIR_PATH/${prefix}.tar.gz" ]]; then
    log "extract $prefix -> $dest"
    cat "$BACKUP_DIR_PATH/${prefix}.tar.gz" | extract_stream "$dest"
    return 0
  fi
  if ls "$BACKUP_DIR_PATH/${prefix}.tar.gz.part."* >/dev/null 2>&1; then
    log "extract $prefix (chunked) -> $dest"
    cat_parts "$BACKUP_DIR_PATH" "${prefix}.tar.gz.part.*" | extract_stream "$dest"
    return 0
  fi
  log "skip $prefix (no artifact found)"
}

# Legacy restore path
if [[ -z "$MANIFEST" ]]; then
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  tar -C "$tmp" -xzf "$SRC"
  for d in config docker scripts bin docs extensions workflows provenance .cache data downloads; do
    if [[ -e "$tmp/$d" ]]; then
      rm -rf "${TARGET:?}/$d" 2>/dev/null || true
      cp -a "$tmp/$d" "$TARGET/" || true
    fi
  done
  log "legacy restore done."
  [[ "$RUN_RECONCILE" -eq 1 && -x "$TARGET/bin/beast" ]] && (cd "$TARGET" && ./bin/beast state apply --apply) || true
  exit 0
fi

# Manifest-based restore
log "Restoring from: $BACKUP_DIR_PATH"

# 1) core into TARGET
extract_parts "core" "$TARGET"

# 2) load restored paths.env (or existing)
if [[ -f "$TARGET/config/paths.env" ]]; then
  # shellcheck disable=SC1090
  source "$TARGET/config/paths.env"
else
  die "After core restore, missing $TARGET/config/paths.env"
fi

# 3) provenance into DATA_DIR
extract_parts "provenance" "$DATA_DIR"

# 4) full components (models/workflows/data/downloads)
extract_parts "models" "$COMFYUI_MODELS_DIR"
extract_parts "workflows" "$WORKFLOWS_DIR"
# data/downloads restore into their dirs; these may overlap provenance, that's fine
extract_parts "data" "$DATA_DIR"
extract_parts "downloads" "$DOWNLOAD_DIR"

# 5) docker volumes (if present)
if command -v docker >/dev/null 2>&1; then
  # parse manifest to locate any volume:* entries
  export MANIFEST
  python3 - <<PY | while IFS= read -r v; do
import json, pathlib, os
m=json.loads(pathlib.Path(os.environ["MANIFEST"]).read_text())
for c in m.get("components", []):
  n=c.get("name","")
  if n.startswith("volume:"):
    print(n.split(":",1)[1])
PY
    [[ -n "$v" ]] || continue
    log "restoring docker volume: $v"
    docker volume create "$v" >/dev/null 2>&1 || true

    # prefer single archive, else parts
    if [[ -f "$BACKUP_DIR_PATH/volumes/${v}.tar.gz" ]]; then
      cat "$BACKUP_DIR_PATH/volumes/${v}.tar.gz" | docker run --rm -i -v "${v}:/data" alpine:3.20 sh -lc 'cd /data && tar -xzf -'
    elif ls "$BACKUP_DIR_PATH/volumes/${v}.tar.gz.part."* >/dev/null 2>&1; then
      cat_parts "$BACKUP_DIR_PATH/volumes" "${v}.tar.gz.part.*" | docker run --rm -i -v "${v}:/data" alpine:3.20 sh -lc 'cd /data && tar -xzf -'
    else
      log "skip volume $v (no archive found)"
    fi
  done
else
  log "docker not installed; skipping volume restore"
fi

log "restore complete into: $TARGET"

if [[ "$RUN_RECONCILE" -eq 1 && -x "$TARGET/bin/beast" ]]; then
  log "running state reconciler (rebuild services/packs)..."
  (cd "$TARGET" && ./bin/beast state apply --apply) || true
fi

log "done."
