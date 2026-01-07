#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-backup}"; shift || true

APPLY=0
VERBOSE=0
PROFILE="standard"     # min|standard|full|appliance
CHUNK_SIZE="0"         # e.g. 2g ; 0 = no chunking
OUT_DIR=""
NAME=""
INCLUDE_VOLUMES=0

for arg in "${@:-}"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --verbose) VERBOSE=1 ;;
    --profile=*) PROFILE="${arg#--profile=}" ;;
    --chunk-size=*) CHUNK_SIZE="${arg#--chunk-size=}" ;;
    --out=*) OUT_DIR="${arg#--out=}" ;;
    --name=*) NAME="${arg#--name=}" ;;
    --with-volumes) INCLUDE_VOLUMES=1 ;;
  esac
done

log(){ echo "[backup] $*"; }
dbg(){ [[ "$VERBOSE" -eq 1 ]] && echo "[backup][dbg] $*" || true; }
die(){ echo "[backup] ERROR: $*" >&2; exit 1; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env (run: ./bin/beast init --apply)"
# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"

BACKUP_ROOT="${OUT_DIR:-$BACKUP_DIR}"
mkdir -p "$BACKUP_ROOT"

ts="$(date -u +%Y%m%d_%H%M%S)"
NAME="${NAME:-ai_beast_backup_${PROFILE}_${ts}}"
DEST="$BACKUP_ROOT/$NAME"
MANIFEST="$DEST/backup.manifest.json"
mkdir -p "$DEST"

# profile toggles
WITH_CORE=1
WITH_PROVENANCE=1
WITH_CACHE=0
WITH_WORKFLOWS=0
WITH_MODELS=0
WITH_DATA=0
WITH_DOWNLOADS=0

case "$PROFILE" in
  min)
    WITH_PROVENANCE=0
    ;;
  standard)
    WITH_CACHE=1
    WITH_WORKFLOWS=1
    ;;
  full)
    WITH_CACHE=1
    WITH_WORKFLOWS=1
    WITH_MODELS=1
    WITH_DATA=1
    WITH_DOWNLOADS=1
    ;;
  appliance)
    WITH_CACHE=1
    WITH_WORKFLOWS=1
    WITH_MODELS=1
    WITH_DATA=1
    WITH_DOWNLOADS=1
    INCLUDE_VOLUMES=1
    ;;
  *)
    die "Unknown profile: $PROFILE"
    ;;
esac

components="[]"

add_component(){
  local cname="$1" dprefix="$2" root="$3" parts_json="$4"
  components="$(COMPONENTS="$components" CNAME="$cname" DPREFIX="$dprefix" ROOT="$root" PARTS="$parts_json" python3 - <<'PY'
import json, os
components=json.loads(os.environ["COMPONENTS"])
components.append({
  "name": os.environ["CNAME"],
  "dest_prefix": os.environ["DPREFIX"],
  "root": os.environ["ROOT"],
  "parts": json.loads(os.environ["PARTS"])
})
print(json.dumps(components))
PY
)"
}

hash_parts(){
  python3 - <<'PY'
import json, pathlib, hashlib, os, sys
dest=pathlib.Path(os.environ["DEST"])
files=json.loads(os.environ["FILES"])
out=[]
for f in files:
  p=dest/f
  if not p.exists():
    continue
  out.append({"file": f, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size})
print(json.dumps(out))
PY
}

write_tar_component(){
  local cname="$1" src_dir="$2" out_prefix="$3"
  [[ -d "$src_dir" ]] || { log "skip $cname (missing dir): $src_dir"; add_component "$cname" "$out_prefix" "$src_dir" "[]"; return 0; }

  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would archive $cname from $src_dir -> $out_prefix (chunk=$CHUNK_SIZE)"
    add_component "$cname" "$out_prefix" "$src_dir" "[]"
    return 0
  fi

  if [[ "$CHUNK_SIZE" == "0" || -z "$CHUNK_SIZE" ]]; then
    local out="${out_prefix}.tar.gz"
    log "writing $DEST/$out"
    tar -C "$src_dir" -cf - . | gzip -9 > "$DEST/$out"
    parts_json="$(DEST="$DEST" FILES="$(python3 - <<PY
import json; print(json.dumps(["$out"]))
PY
)" python3 - <<'PY'
import json, pathlib, hashlib, os
dest=pathlib.Path(os.environ["DEST"])
f=dest/json.loads(os.environ["FILES"])[0]
print(json.dumps([{"file": f.name, "sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "bytes": f.stat().st_size}]))
PY
)"
  else
    local outp="${out_prefix}.tar.gz.part."
    log "writing $DEST/${outp}* (chunk=$CHUNK_SIZE)"
    tar -C "$src_dir" -cf - . | gzip -9 | split -b "$CHUNK_SIZE" - "$DEST/${outp}"
    parts_list="$(ls -1 "$DEST/${outp}"* 2>/dev/null | xargs -n1 basename | sort -V)"
    parts_json="$(DEST="$DEST" FILES="$(python3 - <<PY
import json, sys
print(json.dumps(sys.stdin.read().split()))
PY
<<<"$parts_list")" hash_parts)"
  fi

  add_component "$cname" "$out_prefix" "$src_dir" "$parts_json"
}

log "profile=$PROFILE chunk_size=$CHUNK_SIZE volumes=$INCLUDE_VOLUMES"
if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would write backup folder: $DEST"
fi

# Core: workspace essentials (small)
if [[ "$WITH_CORE" -eq 1 ]]; then
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would archive core workspace"
    add_component "core" "core" "$BASE_DIR" "[]"
  else
    core_list=()
    for p in "config" "docker" "extensions" "bin" "docs"; do
      [[ -e "$BASE_DIR/$p" ]] && core_list+=("$p")
    done
    [[ "$WITH_CACHE" -eq 1 && -d "$BASE_DIR/.cache" ]] && core_list+=(".cache")

    if [[ "$CHUNK_SIZE" == "0" || -z "$CHUNK_SIZE" ]]; then
      out="core.tar.gz"
      log "writing $DEST/$out"
      tar -C "$BASE_DIR" -cf - "${core_list[@]}" | gzip -9 > "$DEST/$out"
      parts_json="$(DEST="$DEST" FILES='["core.tar.gz"]' hash_parts)"
    else
      outp="core.tar.gz.part."
      log "writing $DEST/${outp}* (chunk=$CHUNK_SIZE)"
      tar -C "$BASE_DIR" -cf - "${core_list[@]}" | gzip -9 | split -b "$CHUNK_SIZE" - "$DEST/${outp}"
      parts_list="$(ls -1 "$DEST/${outp}"* 2>/dev/null | xargs -n1 basename | sort -V)"
      parts_json="$(DEST="$DEST" FILES="$(python3 - <<PY
import json, sys
print(json.dumps(sys.stdin.read().split()))
PY
<<<"$parts_list")" hash_parts)"
    fi
    add_component "core" "core" "$BASE_DIR" "$parts_json"
  fi
fi

# Provenance/registry: keep separate
if [[ "$WITH_PROVENANCE" -eq 1 ]]; then
  if [[ -d "$DATA_DIR/provenance" || -d "$DATA_DIR/registry" ]]; then
    if [[ "$APPLY" -ne 1 ]]; then
      log "DRYRUN: would archive provenance/registry"
      add_component "provenance" "provenance" "$DATA_DIR" "[]"
    else
      out="provenance.tar.gz"
      log "writing $DEST/$out"
      tar -C "$DATA_DIR" -cf - "provenance" "registry" 2>/dev/null | gzip -9 > "$DEST/$out" || true
      if [[ -f "$DEST/$out" ]]; then
        parts_json="$(DEST="$DEST" FILES='["provenance.tar.gz"]' hash_parts)"
      else
        parts_json="[]"
      fi
      add_component "provenance" "provenance" "$DATA_DIR" "$parts_json"
    fi
  else
    add_component "provenance" "provenance" "$DATA_DIR" "[]"
  fi
fi

# Full/profile externals
[[ "$WITH_MODELS" -eq 1 ]] && write_tar_component "models" "$COMFYUI_MODELS_DIR" "models"
[[ "$WITH_WORKFLOWS" -eq 1 ]] && write_tar_component "workflows" "$WORKFLOWS_DIR" "workflows"
[[ "$WITH_DATA" -eq 1 ]] && write_tar_component "data" "$DATA_DIR" "data"
[[ "$WITH_DOWNLOADS" -eq 1 ]] && write_tar_component "downloads" "$DOWNLOAD_DIR" "downloads"

# Docker volumes (appliance)
if [[ "$INCLUDE_VOLUMES" -eq 1 ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    log "docker not installed; skipping volumes"
    add_component "volumes" "volumes" "docker" "[]"
  else
    mkdir -p "$DEST/volumes"
    project="${COMPOSE_PROJECT_NAME:-$(basename "$BASE_DIR")}"
    vols="$(docker volume ls --filter "label=com.docker.compose.project=$project" -q || true)"
    if [[ -z "$vols" ]]; then
      log "no compose volumes found for project=$project"
      add_component "volumes" "volumes" "$project" "[]"
    else
      for v in $vols; do
        if [[ "$APPLY" -ne 1 ]]; then
          log "DRYRUN: would export docker volume $v"
          add_component "volume:$v" "volumes/$v" "$v" "[]"
          continue
        fi

        if [[ "$CHUNK_SIZE" == "0" || -z "$CHUNK_SIZE" ]]; then
          out="volumes/${v}.tar.gz"
          log "exporting volume $v -> $DEST/$out"
          docker run --rm -v "${v}:/data:ro" -v "$DEST/volumes:/backup" alpine:3.20 sh -lc 'cd /data && tar -cf - . | gzip -9 > "/backup/'"${v}"'.tar.gz"' || true
          if [[ -f "$DEST/$out" ]]; then
            parts_json="$(DEST="$DEST" FILES="$(python3 - <<PY
import json; print(json.dumps(["$out"]))
PY
)" hash_parts)"
          else
            parts_json="[]"
          fi
        else
          outp="volumes/${v}.tar.gz.part."
          log "exporting volume $v chunked -> $DEST/${outp}* (chunk=$CHUNK_SIZE)"
          docker run --rm -v "${v}:/data:ro" alpine:3.20 sh -lc 'cd /data && tar -cf - . | gzip -9' | split -b "$CHUNK_SIZE" - "$DEST/${outp}" || true
          parts_list="$(ls -1 "$DEST/${outp}"* 2>/dev/null | xargs -n1 basename | sort -V)"
          # prefix with volumes/
          parts_json="$(DEST="$DEST" FILES="$(python3 - <<PY
import json, sys
items=sys.stdin.read().split()
items=["volumes/"+i for i in items]
print(json.dumps(items))
PY
<<<"$parts_list")" hash_parts)"
        fi
        add_component "volume:$v" "volumes/$v" "$v" "$parts_json"
      done
    fi
  fi
fi

# Write manifest
if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would write $MANIFEST"
else
  COMPONENTS="$components" PROFILE="$PROFILE" BASE_DIR="$BASE_DIR" COMFYUI_MODELS_DIR="$COMFYUI_MODELS_DIR" WORKFLOWS_DIR="$WORKFLOWS_DIR" DATA_DIR="$DATA_DIR" DOWNLOAD_DIR="$DOWNLOAD_DIR" CACHE_DIR="$CACHE_DIR" MANIFEST="$MANIFEST" python3 - <<'PY'
import json, time, os, pathlib
m={
  "schema": 2,
  "created_at": time.time(),
  "profile": os.environ["PROFILE"],
  "paths": {
    "COMFYUI_MODELS_DIR": os.environ.get("COMFYUI_MODELS_DIR",""),
    "WORKFLOWS_DIR": os.environ.get("WORKFLOWS_DIR",""),
    "DATA_DIR": os.environ.get("DATA_DIR",""),
    "DOWNLOAD_DIR": os.environ.get("DOWNLOAD_DIR",""),
    "CACHE_DIR": os.environ.get("CACHE_DIR",""),
  },
  "components": json.loads(os.environ["COMPONENTS"]),
}
path=pathlib.Path(os.environ["MANIFEST"])
path.write_text(json.dumps(m, indent=2)+"\n", encoding="utf-8")
print("[backup] wrote manifest:", path)
PY
fi

log "backup complete: $DEST"
cat <<EOF
Restore:
  ./bin/beast restore "$DEST" --apply

EOF
