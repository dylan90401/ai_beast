#!/usr/bin/env bash
set -euo pipefail

STATE_FILE=""
OUT_DIR=""
FORMAT="both"   # md|dot|both

for arg in "${@:-}"; do
  case "$arg" in
    --state=*) STATE_FILE="${arg#--state=}" ;;
    --out=*) OUT_DIR="${arg#--out=}" ;;
    --format=*) FORMAT="${arg#--format=}" ;;
  esac
done

log(){ echo "[graph] $*"; }
die(){ echo "[graph] ERROR: $*" >&2; exit 1; }
need(){ command -v "$1" >/dev/null 2>&1 || die "Missing '$1'"; }

need python3
need jq

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

if [[ "${1:-}" == "typed" ]]; then
  shift || true
  exec "$BASE_DIR/scripts/97_graph_typed.sh" "${@:-}"
fi

STATE_FILE="${STATE_FILE:-$BASE_DIR/config/state.json}"
packs_cfg="$BASE_DIR/config/packs.json"
assets_cfg="$BASE_DIR/config/asset_packs.json"

[[ -f "$STATE_FILE" ]] || die "State file not found: $STATE_FILE"
[[ -f "$packs_cfg" ]] || die "Missing $packs_cfg"
[[ -f "$assets_cfg" ]] || die "Missing $assets_cfg"

out_dir="${OUT_DIR:-$BASE_DIR/.cache}"
mkdir -p "$out_dir"

dot="$out_dir/resource_graph.dot"
md="$out_dir/resource_graph.md"

python3 - "$STATE_FILE" "$packs_cfg" "$assets_cfg" "$BASE_DIR" "$dot" "$md" <<'PY'
import sys, json, pathlib, re, datetime
state_path, packs_path, assets_path, base_dir, dot_out, md_out = sys.argv[1:]

state=json.loads(pathlib.Path(state_path).read_text(encoding='utf-8'))
packs=json.loads(pathlib.Path(packs_path).read_text(encoding='utf-8'))["packs"]
assets=json.loads(pathlib.Path(assets_path).read_text(encoding='utf-8'))["packs"]

desired_packs=set(state.get("desired",{}).get("packs_enabled",[]) or [])
desired_exts=set(state.get("desired",{}).get("extensions_enabled",[]) or [])
desired_assets=[a.get("pack") for a in (state.get("desired",{}).get("asset_packs",[]) or []) if a.get("pack")]

# pack dep closure + reasons
deps={k:set(v.get("depends",[]) or []) for k,v in packs.items()}
req_by={k:set() for k in packs.keys()}
closure=set()

def dfs(root, cur, stack):
    for d in deps.get(cur,set()):
        closure.add(d)
        req_by.setdefault(d,set()).add(cur)
        dfs(root, d, stack+[d])

for p in list(desired_packs):
    closure.add(p)
    dfs(p,p,[p])

# asset deps → packs/assets (optional)
asset_dep_packs={k:set(v.get("depends_packs",[]) or []) for k,v in assets.items()}
asset_dep_assets={k:set(v.get("depends_assets",[]) or []) for k,v in assets.items()}

asset_closure=set()
def dfs_asset(a, stack):
    for dp in asset_dep_packs.get(a,set()):
        closure.add(dp)
        req_by.setdefault(dp,set()).add(f"asset:{a}")
    for da in asset_dep_assets.get(a,set()):
        if da not in asset_closure:
            asset_closure.add(da)
            dfs_asset(da, stack+[da])

for a in desired_assets:
    asset_closure.add(a)
    dfs_asset(a,[a])

# services: parse base compose + enabled fragments (naive)
def extract_services(yaml_path: pathlib.Path):
    if not yaml_path.exists(): return set()
    lines=yaml_path.read_text(encoding='utf-8', errors='ignore').splitlines()
    services=set()
    in_services=False
    for line in lines:
        if re.match(r'^services\s*:\s*$', line):
            in_services=True; continue
        if in_services:
            if re.match(r'^[A-Za-z0-9_\-]+\s*:\s*$', line) and not line.startswith('  '):
                in_services=False; continue
            m=re.match(r'^\s{2}([A-Za-z0-9_.-]+)\s*:\s*$', line)
            if m: services.add(m.group(1))
    return services

base=pathlib.Path(base_dir)/"docker/compose.yaml"
ops=pathlib.Path(base_dir)/"docker/compose.ops.yaml"
svc=set()
svc |= extract_services(base)
svc |= extract_services(ops)

ext_root=pathlib.Path(base_dir)/"extensions"
sel=pathlib.Path(base_dir)/".cache/compose.selection.json"
if sel.exists():
    try:
        j=json.loads(sel.read_text(encoding="utf-8"))
        frags=[pathlib.Path(p) for p in j.get("selected", [])]
    except Exception:
        frags=[]
else:
    frags=sorted(ext_root.glob("*/compose.fragment.yaml")) + sorted(ext_root.glob("*/*/compose.fragment.yaml"))
    # gating: if any enabled marker exists, include only enabled
    enabled_markers=list(ext_root.glob("*/enabled")) + list(ext_root.glob("*/*/enabled"))
    if enabled_markers:
        frags=[f for f in frags if (f.parent/"enabled").exists()]
for f in frags:
    svc |= extract_services(f)

# Render DOT
now=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
dot_lines=[]
dot_lines.append('digraph AI_BEAST {')
dot_lines.append('  rankdir=LR;')
dot_lines.append(f'  label="AI Beast Resource Graph ({now})"; labelloc=top; fontsize=18;')
dot_lines.append('  node [shape=box];')

def n(s): 
    return re.sub(r'[^A-Za-z0-9_:\-]', '_', s)

# nodes
for p in sorted(closure):
    dot_lines.append(f'  "{n("pack:"+p)}" [label="{p}\n(pack)"];')
for e in sorted(desired_exts):
    dot_lines.append(f'  "{n("ext:"+e)}" [label="{e}\n(extension)"];')
for a in sorted(asset_closure):
    dot_lines.append(f'  "{n("asset:"+a)}" [label="{a}\n(asset_pack)"];')
for s in sorted(svc):
    dot_lines.append(f'  "{n("svc:"+s)}" [label="{s}\n(service)", shape=ellipse];')

# edges packs deps
for p in sorted(closure):
    for d in sorted(deps.get(p,set())):
        if d in closure:
            dot_lines.append(f'  "{n("pack:"+p)}" -> "{n("pack:"+d)}" [label="depends"];')
# desired roots edges
for p in sorted(desired_packs):
    if p in closure:
        dot_lines.append(f'  "state" [label="state.json", shape=diamond];')  # will be duplicated; ok
        dot_lines.append(f'  "state" -> "{n("pack:"+p)}" [label="wants"];')
for e in sorted(desired_exts):
    dot_lines.append(f'  "state" -> "{n("ext:"+e)}" [label="wants"];')
for a in sorted(desired_assets):
    dot_lines.append(f'  "state" -> "{n("asset:"+a)}" [label="wants"];')

# asset deps edges
for a in sorted(asset_closure):
    for dp in sorted(asset_dep_packs.get(a,set())):
        if dp in closure:
            dot_lines.append(f'  "{n("asset:"+a)}" -> "{n("pack:"+dp)}" [label="needs"];')
    for da in sorted(asset_dep_assets.get(a,set())):
        if da in asset_closure:
            dot_lines.append(f'  "{n("asset:"+a)}" -> "{n("asset:"+da)}" [label="needs"];')

dot_lines.append('}')
pathlib.Path(dot_out).write_text("\n".join(dot_lines)+"\n", encoding="utf-8")

# Render MD (reasons)
md=[]
md.append("# AI Beast Resource Graph")
md.append("")
md.append(f"- Generated: {now}")
md.append(f"- Desired state: {state_path}")
md.append("")
md.append("## Packs (desired closure)")
for p in sorted(closure):
    if p in desired_packs:
        md.append(f"- **{p}** (requested)")
    else:
        reasons=sorted(req_by.get(p,set()))
        if reasons:
            md.append(f"- **{p}** (required by: {', '.join(reasons)})")
        else:
            md.append(f"- **{p}** (required)")
md.append("")
md.append("## Extensions (requested)")
if desired_exts:
    for e in sorted(desired_exts):
        md.append(f"- **{e}**")
else:
    md.append("- (none)")
md.append("")
md.append("## Asset packs (requested + closure)")
if asset_closure:
    for a in sorted(asset_closure):
        tag="requested" if a in desired_assets else "dependency"
        md.append(f"- **{a}** ({tag})")
else:
    md.append("- (none)")
md.append("")
md.append("## Services (from compose yaml)")
if svc:
    for s in sorted(svc):
        md.append(f"- `{s}`")
else:
    md.append("- (none detected)")

pathlib.Path(md_out).write_text("\n".join(md)+"\n", encoding="utf-8")
PY

case "$FORMAT" in
  dot) log "Wrote $dot" ;;
  md) log "Wrote $md" ;;
  both|*) log "Wrote $dot and $md" ;;
esac
