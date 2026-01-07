#!/usr/bin/env bash
set -euo pipefail

ACTION="gen"
if [[ "${1:-}" != "" && "${1:-}" != --* ]]; then
  ACTION="$1"; shift || true
fi

APPLY=0
WITH_OPS=1
OUT=""
VERBOSE=0
MODE="auto"           # auto|state|legacy
STRICT_STATE=0        # if 1, only state-declared extensions
RENDER=1              # render base/ops from typed services registry
STATE_FILE=""
PROJECT_NAME=""

for arg in "${@:-}"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --no-ops) WITH_OPS=0 ;;
    --out=*) OUT="${arg#--out=}" ;;
    --verbose) VERBOSE=1 ;;
    --mode=*) MODE="${arg#--mode=}" ;;
    --strict-state) STRICT_STATE=1 ;;
    --no-render) RENDER=0 ;;
    --state=*) STATE_FILE="${arg#--state=}" ;;
    --project=*) PROJECT_NAME="${arg#--project=}" ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

# shellcheck disable=SC1091
source "$BASE_DIR/scripts/lib/common.sh"
# shellcheck disable=SC1091
source "$BASE_DIR/scripts/lib/docker_runtime.sh"
# libs
source "$BASE_DIR/scripts/lib/compose_utils.sh"

AI_BEAST_LOG_PREFIX="compose-gen"

dbg(){ [[ "$VERBOSE" -eq 1 ]] && echo "[compose-gen][dbg] $*" || true; }

mkdir -p "$BASE_DIR/.cache" "$BASE_DIR/docker/generated" "$BASE_DIR/extensions"

state_file="${STATE_FILE:-$BASE_DIR/config/state.json}"
packs_file="$BASE_DIR/config/packs.json"
pack_services_file="$BASE_DIR/config/resources/pack_services.json"
services_registry="$BASE_DIR/config/resources/services.json"
ext_root="$BASE_DIR/extensions"

out="${OUT:-$BASE_DIR/docker-compose.yml}"
project="${PROJECT_NAME:-${COMPOSE_PROJECT_NAME:-$(basename "$BASE_DIR")}}"

case "$ACTION" in
  render)
    [[ "$APPLY" -eq 1 ]] || die "compose render requires --apply"
    exec "$BASE_DIR/scripts/24_compose_render.sh" render --apply "${@:-}"
    ;;
  gen|generate) : ;;
  *) die "Unknown action: $ACTION (use: render|gen)" ;;
esac

if [[ "$MODE" == "auto" ]]; then
  [[ -f "$state_file" ]] && MODE="state" || MODE="legacy"
fi

[[ -f "$packs_file" ]] || die "Missing $packs_file"
[[ -f "$pack_services_file" ]] || die "Missing $pack_services_file"
[[ -f "$services_registry" ]] || die "Missing $services_registry"

# Compute desired packs + extensions from state (supports both formats)
desired_json="$(python3 - <<PY
import json, pathlib
p=pathlib.Path("$state_file")
if not p.exists():
    print(json.dumps({"packs_enabled":[], "extensions_enabled":[]}))
else:
    j=json.loads(p.read_text(encoding="utf-8"))
    d=j.get("desired", j)
    print(json.dumps({
      "packs_enabled": d.get("packs_enabled", []) or [],
      "extensions_enabled": d.get("extensions_enabled", []) or [],
    }))
PY
)"

# Pack dependency closure and services union (packs -> services)
desired_services_json="$(python3 - <<PY
import json, pathlib
desired=json.loads('''$desired_json''')
packs_cfg=json.loads(pathlib.Path("$packs_file").read_text(encoding="utf-8")).get("packs", {})
svcmap=json.loads(pathlib.Path("$pack_services_file").read_text(encoding="utf-8")).get("pack_services", {}) or {}

wanted=list(desired.get("packs_enabled",[]) or [])
seen=set(); closure=[]
def dfs(p):
    if p in seen: return
    seen.add(p); closure.append(p)
    for d in (packs_cfg.get(p,{}).get("depends") or []):
        dfs(d)
for p in wanted: dfs(p)

svc=set()
for p in closure:
    for s in (svcmap.get(p,[]) or []):
        svc.add(s)

print(json.dumps(sorted(svc)))
PY
)"

# Extensions: include state + enabled markers (unless strict)
desired_exts_json="$(python3 - <<PY
import json, pathlib
desired=json.loads('''$desired_json''')
root=pathlib.Path("$ext_root")
exts=set(desired.get("extensions_enabled",[]) or [])
strict=int("$STRICT_STATE")
if strict==0:
    for m in root.glob("*/enabled"):
        exts.add(m.parent.name)
    for m in root.glob("*/*/enabled"):
        exts.add(m.parent.name)
print(json.dumps(sorted(exts)))
PY
)"

# Add services referenced by selected extension fragments
desired_services_json="$(python3 - <<PY
import json, pathlib, re
root=pathlib.Path("$ext_root")
exts=set(json.loads('''$desired_exts_json'''))
svc=set(json.loads('''$desired_services_json'''))

def list_services(text):
    out=set(); in_services=False
    for line in text.splitlines():
        if re.match(r'^\s*services:\s*$', line):
            in_services=True; continue
        if in_services:
            if line and not line.startswith(" "):
                in_services=False; continue
            m=re.match(r'^\s{2}([A-Za-z0-9._-]+):\s*$', line)
            if m: out.add(m.group(1))
    return out

for f in sorted(root.glob("*/compose.fragment.yaml")) + sorted(root.glob("*/*/compose.fragment.yaml")):
    if f.parent.name in exts:
        svc |= list_services(f.read_text(errors="ignore"))

print(json.dumps(sorted(svc)))
PY
)"

dbg "mode=$MODE strict_state=$STRICT_STATE desired_services=$(python3 - <<PY
import json; print(", ".join(json.loads('''$desired_services_json''')))
PY
)"

# Render base/ops from typed registry (subset if state mode)
gen_dir="$BASE_DIR/docker/generated"
base_file="$gen_dir/compose.core.yaml"
ops_file="$gen_dir/compose.ops.yaml"

if [[ "$RENDER" -eq 1 ]]; then
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would render compose from registry"
  else
    if [[ "$MODE" == "state" ]]; then
      only="$(python3 - <<PY
import json; print(",".join(json.loads('''$desired_services_json''')))
PY
)"
      "$BASE_DIR/scripts/24_compose_render.sh" render --apply --only-services="$only" >/dev/null
    else
      "$BASE_DIR/scripts/24_compose_render.sh" render --apply >/dev/null
    fi
  fi
fi

[[ -f "$base_file" ]] || die "Missing rendered base: $base_file"
if [[ "$WITH_OPS" -eq 1 ]]; then [[ -f "$ops_file" ]] || die "Missing rendered ops: $ops_file"; fi

# Select fragments
selection_json="$BASE_DIR/.cache/compose.selection.json"

if [[ "$MODE" == "legacy" ]]; then
  mapfile -t frags < <(find "$ext_root" -type f -name "compose.fragment.yaml" -print 2>/dev/null | sort || true)
  # if any enabled markers exist, select only enabled fragments
  if find "$ext_root" -type f -name "enabled" -print -quit 2>/dev/null | grep -q .; then
    tmp=()
    for f in "${frags[@]:-}"; do
      d="$(cd "$(dirname "$f")" && pwd)"
      [[ -f "$d/enabled" ]] && tmp+=("$f")
    done
    frags=("${tmp[@]:-}")
  fi
  selected_frags=("${frags[@]:-}")
  if [[ "$APPLY" -eq 1 ]]; then
    FRAGS_JSON="$(printf '%s\n' "${selected_frags[@]:-}" | python3 - <<'PY'
import sys, json
arr=[l.strip() for l in sys.stdin if l.strip()]
print(json.dumps(arr))
PY
)"
    python3 - <<PY
import json, pathlib
p=pathlib.Path("$selection_json"); p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({"mode":"legacy","selected":json.loads('''$FRAGS_JSON'''), "meta":[]}, indent=2)+"\n", encoding="utf-8")
PY
  fi
else
  selection_payload="$(python3 - <<PY
import json, pathlib, re
root=pathlib.Path("$ext_root")
exts=set(json.loads('''$desired_exts_json'''))
desired=set(json.loads('''$desired_services_json'''))

def list_services(text):
    out=set(); in_services=False
    for line in text.splitlines():
        if re.match(r'^\s*services:\s*$', line):
            in_services=True; continue
        if in_services:
            if line and not line.startswith(" "):
                in_services=False; continue
            m=re.match(r'^\s{2}([A-Za-z0-9._-]+):\s*$', line)
            if m: out.add(m.group(1))
    return out

selected=[]; meta=[]
for f in sorted(root.glob("*/compose.fragment.yaml")) + sorted(root.glob("*/*/compose.fragment.yaml")):
    ex=f.parent.name
    sv=list_services(f.read_text(errors="ignore"))
    by_ext = ex in exts
    hits = sorted(list(sv & desired))
    by_svc = len(hits)>0
    if by_ext or by_svc:
        selected.append(str(f))
        meta.append({"fragment": str(f), "extension": ex, "services": sorted(sv), "selected_by": {"extension": by_ext, "services": hits}})
print(json.dumps({"mode":"state","selected":selected,"meta":meta,"desired_services":sorted(desired),"desired_extensions":sorted(exts)}))
PY
)"
  if [[ "$APPLY" -eq 1 ]]; then
    python3 - <<PY
import json, pathlib
p=pathlib.Path("$selection_json"); p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(json.loads('''$selection_payload'''), indent=2)+"\n", encoding="utf-8")
PY
  fi
  mapfile -t selected_frags < <(python3 - <<PY
import json
j=json.loads('''$selection_payload''')
for s in j.get("selected", []): print(s)
PY
)
fi

args=(-f "$base_file")
if [[ "$WITH_OPS" -eq 1 ]]; then args+=(-f "$ops_file"); fi
for f in "${selected_frags[@]:-}"; do args+=(-f "$f"); done

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would generate $out for project=$project"
  log "DRYRUN: docker compose ${args[*]} config > $out"
  exit 0
fi

# Ensure chosen Docker runtime is reachable before invoking docker compose.
docker_runtime_ensure || die "Docker runtime not reachable"

docker compose "${args[@]}" config > "$out"

python3 - <<PY
import json, pathlib, hashlib, time
out=pathlib.Path("$out")
sel=pathlib.Path("$selection_json")
fp={
  "generated_at": time.time(),
  "project": "$project",
  "compose": str(out.resolve()),
  "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
  "bytes": out.stat().st_size,
  "selection": json.loads(sel.read_text(encoding="utf-8")) if sel.exists() else {},
}
pathlib.Path("$BASE_DIR/.cache/compose.fingerprint.json").write_text(json.dumps(fp, indent=2)+"\n", encoding="utf-8")
print("[compose-gen] wrote", out)
print("[compose-gen] wrote", "$BASE_DIR/.cache/compose.fingerprint.json")
PY
