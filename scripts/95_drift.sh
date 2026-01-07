#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-help}"; shift || true

APPLY=0
VERBOSE=0
REMOVE_ORPHANS=1
COMPOSE_FILE=""
PROJECT=""

for arg in "${@:-}"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --verbose) VERBOSE=1 ;;
    --no-remove-orphans) REMOVE_ORPHANS=0 ;;
    --compose=*) COMPOSE_FILE="${arg#--compose=}" ;;
    --project=*) PROJECT="${arg#--project=}" ;;
  esac
done

log(){ echo "[drift] $*"; }
dbg(){ [[ "$VERBOSE" -eq 1 ]] && echo "[drift][dbg] $*" || true; }
die(){ echo "[drift] ERROR: $*" >&2; exit 1; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

COMPOSE_FILE="${COMPOSE_FILE:-$BASE_DIR/docker-compose.yml}"
PROJECT="${PROJECT:-${COMPOSE_PROJECT_NAME:-$(basename "$BASE_DIR")}}"

graph_json="$BASE_DIR/.cache/typed_graph.json"
service_hashes="$BASE_DIR/.cache/compose.service_hashes.json"

command -v docker >/dev/null 2>&1 || die "docker not found (install Docker Desktop or Colima)."

why_for_service(){
  local svc="$1"
  [[ -f "$graph_json" ]] || return 0
  SVC="$svc" GRAPH="$graph_json" python3 - <<'PY' || true
import os, json, pathlib, collections
svc = os.environ.get("SVC","")
g = pathlib.Path(os.environ.get("GRAPH",""))
graph = json.loads(g.read_text(encoding="utf-8"))
nodes = {n["id"]: n for n in graph.get("nodes", [])}
name_to_id = {(n.get("type"), n.get("name")): n["id"] for n in graph.get("nodes", [])}
state_id = next((n["id"] for n in graph.get("nodes", []) if n.get("type")=="state"), None)
svc_id = name_to_id.get(("service", svc))
if not (state_id and svc_id):
    raise SystemExit(0)
rev=collections.defaultdict(list)
for e in graph.get("edges", []):
    rev[e["to"]].append(e["from"])
q=collections.deque([(svc_id, [svc_id])])
paths=[]
seen=set()
while q:
    cur, path = q.popleft()
    if cur == state_id:
        paths.append(path); continue
    for p in rev.get(cur, []):
        if p in path: continue
        key=(p, tuple(path))
        if key in seen: continue
        seen.add(key)
        q.append((p, [p]+path))
if not paths:
    raise SystemExit(0)
best=min(paths, key=len)
def fmt(nid):
    n=nodes.get(nid,{})
    return f'{n.get("type")}:{n.get("name")}'
print(" -> ".join(fmt(x) for x in best))
PY
}

load_desired_hashes(){
  [[ -f "$service_hashes" ]] || return 0
  python3 - <<PY
import json
j=json.load(open("$service_hashes"))
for k,v in (j.get("services") or {}).items():
    print(f"{k}\t{v}")
PY
}

want_services(){
  awk '
    BEGIN{in_services=0}
    /^[[:space:]]*services:[[:space:]]*$/ {in_services=1; next}
    in_services==1 && match($0, /^  ([A-Za-z0-9_.-]+):[[:space:]]*$/, m) {print m[1]; next}
    in_services==1 && /^[^ ]/ {in_services=0}
  ' "$COMPOSE_FILE" | sort -u
}

running_services(){
  docker ps -a --filter "label=com.docker.compose.project=$PROJECT"     --format '{{.Label "com.docker.compose.service"}}\t{{.ID}}\t{{.Status}}' | sort
}

status(){
  [[ -f "$COMPOSE_FILE" ]] || die "Missing compose file: $COMPOSE_FILE (run: ./bin/beast compose gen --apply --mode=state)"

  declare -A want
  while read -r svc; do [[ -n "$svc" ]] && want["$svc"]=1; done < <(want_services)

  declare -A desired_hash
  while IFS=$'\t' read -r svc h; do desired_hash["$svc"]="$h"; done < <(load_desired_hashes || true)

  declare -A have_id have_status have_hash
  while IFS=$'\t' read -r svc cid st; do
    [[ -n "$svc" ]] || continue
    have_id["$svc"]="$cid"
    have_status["$svc"]="$st"
  done < <(running_services)

  for svc in "${!have_id[@]}"; do
    cid="${have_id[$svc]}"
    h="$(docker inspect -f '{{ index .Config.Labels "ai.beast.service_hash" }}' "$cid" 2>/dev/null || true)"
    [[ -n "$h" ]] && have_hash["$svc"]="$h"
  done

  missing=(); stopped=(); hashdrift=(); extra=()
  for svc in "${!want[@]}"; do
    if [[ -z "${have_id[$svc]:-}" ]]; then missing+=("$svc"); continue; fi
    if echo "${have_status[$svc]}" | grep -qiE 'exited|dead'; then stopped+=("$svc"); fi
    if [[ -n "${desired_hash[$svc]:-}" && -n "${have_hash[$svc]:-}" ]]; then
      [[ "${desired_hash[$svc]}" != "${have_hash[$svc]}" ]] && hashdrift+=("$svc")
    fi
  done
  for svc in "${!have_id[@]}"; do
    [[ -z "${want[$svc]:-}" ]] && extra+=("$svc")
  done

  log "Project: $PROJECT"
  log "Compose:  $COMPOSE_FILE"
  echo

  print_block(){
    local title="$1"; shift
    local -a arr=("$@")
    echo "== $title (${#arr[@]}) =="
    if [[ "${#arr[@]}" -eq 0 ]]; then echo "(none)"; echo; return; fi
    for s in "${arr[@]}"; do
      echo "- $s"
      local why; why="$(why_for_service "$s" || true)"
      [[ -n "$why" ]] && echo "  why: $why"
      if [[ "$title" == "Hash/config drift" ]]; then
        echo "  desired_hash: ${desired_hash[$s]:-}"
        echo "  running_hash: ${have_hash[$s]:-}"
      fi
    done
    echo
  }

  print_block "Missing services" "${missing[@]:-}"
  print_block "Stopped services" "${stopped[@]:-}"
  print_block "Hash/config drift" "${hashdrift[@]:-}"
  print_block "Extra services" "${extra[@]:-}"

  if [[ "${#missing[@]}" -gt 0 || "${#stopped[@]}" -gt 0 || "${#hashdrift[@]}" -gt 0 || "${#extra[@]}" -gt 0 ]]; then
    return 2
  fi
}

apply_fix(){
  [[ "$APPLY" -eq 1 ]] || die "Refusing to apply without --apply"
  [[ -f "$COMPOSE_FILE" ]] || die "Missing compose file: $COMPOSE_FILE"

  set +e; status; rc=$?; set -e
  if [[ "$rc" -eq 0 ]]; then
    log "No drift detected. Nothing to do."
    exit 0
  fi

  # Recompute arrays (same logic as status)
  declare -A want
  while read -r svc; do [[ -n "$svc" ]] && want["$svc"]=1; done < <(want_services)

  declare -A desired_hash
  while IFS=$'\t' read -r svc h; do desired_hash["$svc"]="$h"; done < <(load_desired_hashes || true)

  declare -A have_id have_status have_hash
  while IFS=$'\t' read -r svc cid st; do
    [[ -n "$svc" ]] || continue
    have_id["$svc"]="$cid"
    have_status["$svc"]="$st"
  done < <(running_services)

  for svc in "${!have_id[@]}"; do
    cid="${have_id[$svc]}"
    h="$(docker inspect -f '{{ index .Config.Labels "ai.beast.service_hash" }}' "$cid" 2>/dev/null || true)"
    [[ -n "$h" ]] && have_hash["$svc"]="$h"
  done

  missing=(); stopped=(); hashdrift=(); extra=()
  for svc in "${!want[@]}"; do
    if [[ -z "${have_id[$svc]:-}" ]]; then missing+=("$svc"); continue; fi
    if echo "${have_status[$svc]}" | grep -qiE 'exited|dead'; then stopped+=("$svc"); fi
    if [[ -n "${desired_hash[$svc]:-}" && -n "${have_hash[$svc]:-}" ]]; then
      [[ "${desired_hash[$svc]}" != "${have_hash[$svc]}" ]] && hashdrift+=("$svc")
    fi
  done
  for svc in "${!have_id[@]}"; do
    [[ -z "${want[$svc]:-}" ]] && extra+=("$svc")
  done

  log "Applying surgical reconcile..."
  if [[ "${#missing[@]}" -gt 0 ]]; then
    log "Create missing: ${missing[*]}"
    docker compose -p "$PROJECT" -f "$COMPOSE_FILE" up -d --no-deps "${missing[@]}"
  fi
  if [[ "${#stopped[@]}" -gt 0 ]]; then
    log "Restart stopped: ${stopped[*]}"
    docker compose -p "$PROJECT" -f "$COMPOSE_FILE" up -d --no-deps "${stopped[@]}"
  fi
  if [[ "${#hashdrift[@]}" -gt 0 ]]; then
    log "Recreate drifted: ${hashdrift[*]}"
    docker compose -p "$PROJECT" -f "$COMPOSE_FILE" up -d --no-deps --force-recreate "${hashdrift[@]}"
  fi
  if [[ "$REMOVE_ORPHANS" -eq 1 && "${#extra[@]}" -gt 0 ]]; then
    log "Removing extras: ${extra[*]}"
    docker compose -p "$PROJECT" -f "$COMPOSE_FILE" stop "${extra[@]}" || true
    docker compose -p "$PROJECT" -f "$COMPOSE_FILE" rm -f "${extra[@]}" || true
  fi

  log "Done."
}

case "$ACTION" in
  status) status ;;
  apply) apply_fix ;;
  *)
    cat <<EOF
Usage:
  ./bin/beast drift status [--compose=FILE] [--project=NAME] [--verbose]
  ./bin/beast drift apply  --apply [--compose=FILE] [--project=NAME] [--no-remove-orphans] [--verbose]

Notes:
- Best results when compose was generated via:
    ./bin/beast compose gen --apply --mode=state
- v17 detects hash/config drift for registry-rendered services using label:
    ai.beast.service_hash
EOF
    ;;
esac
