#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-render}"; shift || true

APPLY=0
VERBOSE=0
OUT_DIR=""
ONLY_SERVICES=""

for arg in "${@:-}"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --verbose) VERBOSE=1 ;;
    --out=*) OUT_DIR="${arg#--out=}" ;;
    --only-services=*) ONLY_SERVICES="${arg#--only-services=}" ;;
  esac
done

log(){ echo "[compose-render] $*"; }
dbg(){ [[ "$VERBOSE" -eq 1 ]] && echo "[compose-render][dbg] $*" || true; }
die(){ echo "[compose-render] ERROR: $*" >&2; exit 1; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

reg="$BASE_DIR/config/resources/services.json"
[[ -f "$reg" ]] || die "Missing services registry: $reg"

out_dir="${OUT_DIR:-$BASE_DIR/docker/generated}"
core="$out_dir/compose.core.yaml"
ops="$out_dir/compose.ops.yaml"
meta="$out_dir/compose.render.meta.json"
hashes="$BASE_DIR/.cache/compose.service_hashes.json"

mkdir -p "$out_dir" "$BASE_DIR/.cache"

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would render compose from $reg"
  log "DRYRUN: -> $core"
  log "DRYRUN: -> $ops"
  log "DRYRUN: -> $hashes"
  exit 0
fi

REG_PATH="$reg" OUT_DIR="$out_dir" ONLY_SERVICES="$ONLY_SERVICES" HASHES_PATH="$hashes" META_PATH="$meta" python3 - <<'PY'
import os, json, pathlib, time, hashlib

reg_path = pathlib.Path(os.environ["REG_PATH"])
out_dir  = pathlib.Path(os.environ["OUT_DIR"])
hashes_p = pathlib.Path(os.environ["HASHES_PATH"])
meta_p   = pathlib.Path(os.environ["META_PATH"])
only     = os.environ.get("ONLY_SERVICES","").strip()

reg = json.loads(reg_path.read_text(encoding="utf-8"))
services = reg.get("services", {}) or {}
only_set = set([s.strip() for s in only.split(",") if s.strip()]) if only else None
if only_set is not None:
    services = {k:v for k,v in services.items() if k in only_set}

out_dir.mkdir(parents=True, exist_ok=True)
hashes_p.parent.mkdir(parents=True, exist_ok=True)

def dump_list(lines):
    return "\n".join(lines).rstrip()+"\n"

def svc_block_lines(name, cfg, service_hash=""):
    lines=[]
    lines.append(f"  {name}:")
    prof = cfg.get("profiles") or []
    if prof:
        lines.append(f"    profiles: [{', '.join([json.dumps(p) for p in prof])}]")
    if cfg.get("image"):
        lines.append(f"    image: {cfg['image']}")
    ports = cfg.get("ports") or []
    if ports:
        lines.append("    ports:")
        for p in ports:
            lines.append(f"      - {json.dumps(p)}")
    env = cfg.get("environment")
    if isinstance(env, dict) and env:
        lines.append("    environment:")
        for k,v in env.items():
            lines.append(f"      - {k}={v}")
    elif isinstance(env, list) and env:
        lines.append("    environment:")
        for e in env:
            lines.append(f"      - {e}")
    vols = cfg.get("volumes") or []
    if vols:
        lines.append("    volumes:")
        for v in vols:
            lines.append(f"      - {json.dumps(v)}")
    deps = cfg.get("depends_on") or []
    if deps:
        lines.append("    depends_on:")
        for d in deps:
            lines.append(f"      - {d}")
    if cfg.get("restart"):
        lines.append(f"    restart: {cfg['restart']}")

    tier = cfg.get("tier","core")
    lines.append("    labels:")
    lines.append("      - ai.beast.managed=true")
    lines.append(f"      - ai.beast.tier={tier}")
    if prof:
        lines.append(f"      - ai.beast.profiles={','.join(prof)}")
    if service_hash:
        lines.append(f"      - ai.beast.service_hash={service_hash}")
    return lines

core_lines=["services:"]
ops_lines=["services:"]
svc_hash = {}

for name, cfg in services.items():
    blk = svc_block_lines(name, cfg, service_hash="")
    h = hashlib.sha256("\n".join(blk).encode("utf-8")).hexdigest()
    svc_hash[name]=h
    blk2 = svc_block_lines(name, cfg, service_hash=h)
    tier = cfg.get("tier","core")
    if tier == "ops":
        ops_lines += blk2 + [""]
    else:
        core_lines += blk2 + [""]

core_path = out_dir/"compose.core.yaml"
ops_path  = out_dir/"compose.ops.yaml"
core_path.write_text(dump_list(core_lines), encoding="utf-8")
ops_path.write_text(dump_list(ops_lines), encoding="utf-8")

meta = {
  "generated_at": time.time(),
  "registry": str(reg_path.resolve()),
  "only_services": sorted(list(only_set)) if only_set else None,
  "sha256": {
    "compose.core.yaml": hashlib.sha256(core_path.read_bytes()).hexdigest(),
    "compose.ops.yaml": hashlib.sha256(ops_path.read_bytes()).hexdigest(),
  },
  "service_count": len(services),
}
meta_p.write_text(json.dumps(meta, indent=2)+"\n", encoding="utf-8")
hashes_p.write_text(json.dumps({"generated_at": time.time(), "services": svc_hash}, indent=2)+"\n", encoding="utf-8")

print("[compose-render] wrote", core_path)
print("[compose-render] wrote", ops_path)
print("[compose-render] wrote", hashes_p)
print("[compose-render] wrote", meta_p)
PY
