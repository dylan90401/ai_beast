#!/usr/bin/env bash
set -euo pipefail

STATE_FILE=""
OUT_DIR=""
COMPOSE=""
VERBOSE=0

for arg in "${@:-}"; do
  case "$arg" in
    --state=*) STATE_FILE="${arg#--state=}" ;;
    --out=*) OUT_DIR="${arg#--out=}" ;;
    --compose=*) COMPOSE="${arg#--compose=}" ;;
    --verbose) VERBOSE=1 ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

log(){ echo "[graph:typed] $*"; }
die(){ echo "[graph:typed] ERROR: $*" >&2; exit 1; }

[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env (run: ./bin/beast init --apply)"
# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"

STATE_FILE="${STATE_FILE:-$BASE_DIR/config/state.json}"
OUT_DIR="${OUT_DIR:-$BASE_DIR/.cache}"
COMPOSE="${COMPOSE:-$BASE_DIR/docker-compose.yml}"

mkdir -p "$OUT_DIR"

json_out="$OUT_DIR/typed_graph.json"
md_out="$OUT_DIR/typed_graph.md"
dot_out="$OUT_DIR/typed_graph.dot"

STATE_FILE="$STATE_FILE" OUT_DIR="$OUT_DIR" COMPOSE="$COMPOSE" VERBOSE="$VERBOSE" python3 - <<'PY'
import os, json, re, hashlib, datetime, pathlib

BASE_DIR = pathlib.Path(os.environ["BASE_DIR"])
state_path = pathlib.Path(os.environ.get("STATE_FILE", str(BASE_DIR/"config/state.json")))
compose_path = pathlib.Path(os.environ.get("COMPOSE", str(BASE_DIR/"docker-compose.yml")))
out_dir = pathlib.Path(os.environ.get("OUT_DIR", str(BASE_DIR/".cache")))
verbose = int(os.environ.get("VERBOSE", "0"))

packs_cfg = json.loads((BASE_DIR/"config/packs.json").read_text(encoding="utf-8"))
assets_cfg = json.loads((BASE_DIR/"config/asset_packs.json").read_text(encoding="utf-8"))
pack_services_path = BASE_DIR/"config/resources/pack_services.json"
pack_services = {}
if pack_services_path.exists():
    try:
        pack_services = json.loads(pack_services_path.read_text(encoding="utf-8")).get("pack_services", {}) or {}
    except Exception:
        pack_services = {}

def nid(t: str, name: str, source: str="") -> str:
    s = f"{t}:{name}:{source}".encode("utf-8")
    return hashlib.sha256(s).hexdigest()

def add_node(nodes, idx, t, name, meta=None, source=""):
    _id = nid(t, name, source)
    if _id not in idx:
        idx[_id] = {"id": _id, "type": t, "name": name, "meta": meta or {}}
    return _id

def add_edge(edges, a, b, rel, meta=None):
    edges.append({"from": a, "to": b, "rel": rel, "meta": meta or {}})

# Read state
state = {}
if state_path.exists():
    state = json.loads(state_path.read_text(encoding="utf-8"))
desired_packs = set(state.get("packs_enabled", []) or [])
desired_exts = set(state.get("extensions_enabled", []) or [])
desired_assets = set(state.get("asset_packs_enabled", []) or [])

nodes = []
idx = {}
edges = []

state_id = add_node(nodes, idx, "state", "state", meta={"state_file": str(state_path)})

# Packs (all declared packs)
all_packs = packs_cfg.get("packs", {})
for p, pdata in all_packs.items():
    pid = add_node(nodes, idx, "pack", p, meta={"desc": pdata.get("desc",""), "depends": pdata.get("depends",[]) or []})
    if p in desired_packs:
        add_edge(edges, state_id, pid, "wants")
    for dep in (pdata.get("depends") or []):
        depid = add_node(nodes, idx, "pack", dep, meta={"desc": all_packs.get(dep,{}).get("desc",""), "depends": all_packs.get(dep,{}).get("depends",[]) or []})
        add_edge(edges, pid, depid, "needs")


# v17: pack->service edges + service->profile edges (registry)
services_registry_path = BASE_DIR/"config/resources/services.json"
services_registry = {}
if services_registry_path.exists():
    try:
        services_registry = json.loads(services_registry_path.read_text(encoding="utf-8")).get("services", {}) or {}
    except Exception:
        services_registry = {}

for p, pdata in all_packs.items():
    pid = add_node(nodes, idx, "pack", p, meta={"desc": pdata.get("desc",""), "depends": pdata.get("depends",[]) or []})
    for s in (pack_services.get(p, []) or []):
        sid = add_node(nodes, idx, "service", s, meta={"registry": str(services_registry_path) if services_registry_path.exists() else ""})
        add_edge(edges, pid, sid, "provides")

for s, scfg in (services_registry or {}).items():
    sid = add_node(nodes, idx, "service", s, meta={"registry": str(services_registry_path)})
    for prof in (scfg.get("profiles") or []):
        prid = add_node(nodes, idx, "profile", prof, meta={})
        add_edge(edges, sid, prid, "uses_profile")

# Extensions (detected)
ext_root = BASE_DIR/"extensions"
ext_names = set()
if ext_root.exists():
    for p in ext_root.glob("*/compose.fragment.yaml"):
        ext_names.add(p.parent.name)
    for p in ext_root.glob("*/enabled"):
        ext_names.add(p.parent.name)
for e in sorted(ext_names):
    eid = add_node(nodes, idx, "extension", e, meta={"path": str((ext_root/e).resolve())})
    if e in desired_exts:
        add_edge(edges, state_id, eid, "wants")

# Services (from compose + fragments)
svc = set()
def parse_services_from_yaml_text(text: str):
    # naive: find "services:" then capture top-level keys with 2-space indent.
    in_services = False
    for line in text.splitlines():
        if re.match(r'^\s*services:\s*$', line):
            in_services = True
            continue
        if in_services:
            if re.match(r'^\S', line) and not line.startswith(' '):
                # top-level ended
                in_services = False
                continue
            m = re.match(r'^\s{2}([A-Za-z0-9._-]+):\s*$', line)
            if m:
                yield m.group(1)

compose_text = ""
if compose_path.exists():
    compose_text = compose_path.read_text(encoding="utf-8", errors="ignore")
    svc.update(parse_services_from_yaml_text(compose_text))

# parse services from fragments for extension->service edges
for frag in ext_root.glob("*/compose.fragment.yaml"):
    text = frag.read_text(encoding="utf-8", errors="ignore")
    frag_svcs = set(parse_services_from_yaml_text(text))
    for s in frag_svcs:
        sid = add_node(nodes, idx, "service", s, meta={"compose": str(compose_path)})
        eid = add_node(nodes, idx, "extension", frag.parent.name, meta={"path": str((ext_root/frag.parent.name).resolve())})
        add_edge(edges, eid, sid, "provides")
    svc.update(frag_svcs)

# Add compose services nodes
for s in sorted(svc):
    add_node(nodes, idx, "service", s, meta={"compose": str(compose_path)})

# Optional pack->service mapping
for p, svcs in (pack_services or {}).items():
    pid = add_node(nodes, idx, "pack", p, meta={"desc": all_packs.get(p,{}).get("desc",""), "depends": all_packs.get(p,{}).get("depends",[]) or []})
    for s in svcs or []:
        sid = add_node(nodes, idx, "service", s, meta={"compose": str(compose_path)})
        add_edge(edges, pid, sid, "maps_to")

# Asset packs + models + workflows
apacks = (assets_cfg.get("packs") or {})
for a, adata in apacks.items():
    aid = add_node(nodes, idx, "asset_pack", a, meta={"desc": adata.get("desc",""), "depends_packs": adata.get("depends_packs",[]) or [], "depends_assets": adata.get("depends_assets",[]) or []})
    if a in desired_assets:
        add_edge(edges, state_id, aid, "wants")
    for dp in (adata.get("depends_packs") or []):
        pid = add_node(nodes, idx, "pack", dp, meta={"desc": all_packs.get(dp,{}).get("desc",""), "depends": all_packs.get(dp,{}).get("depends",[]) or []})
        add_edge(edges, aid, pid, "needs")
    for da in (adata.get("depends_assets") or []):
        did = add_node(nodes, idx, "asset_pack", da, meta={"desc": apacks.get(da,{}).get("desc","")})
        add_edge(edges, aid, did, "needs")

    for m in (adata.get("models") or []):
        name = m.get("name") or m.get("filename") or "model"
        src = m.get("url","")
        mid = add_node(nodes, idx, "model", name, meta=m, source=src)
        add_edge(edges, aid, mid, "contains")
    for w in (adata.get("workflows") or []):
        name = w.get("name") or w.get("filename") or "workflow"
        src = w.get("url","")
        wid = add_node(nodes, idx, "workflow", name, meta=w, source=src)
        add_edge(edges, aid, wid, "contains")

graph = {
    "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "nodes": list(idx.values()),
    "edges": edges,
}

out_dir.mkdir(parents=True, exist_ok=True)
(json_out := out_dir/"typed_graph.json").write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")

# Dot output
def label(n):
    t=n["type"]; name=n["name"]
    return f'{t}:{name}'
dot = ["digraph G {", '  rankdir=LR;', '  node [shape=box, fontsize=10];']
for n in graph["nodes"]:
    dot.append(f'  "{n["id"]}" [label="{label(n)}"];')
for e in graph["edges"]:
    dot.append(f'  "{e["from"]}" -> "{e["to"]}" [label="{e["rel"]}"];')
dot.append("}")
(out_dir/"typed_graph.dot").write_text("\n".join(dot) + "\n", encoding="utf-8")

# Markdown summary
by_type = {}
for n in graph["nodes"]:
    by_type.setdefault(n["type"], []).append(n)
md = ["# Typed Resource Graph (v13)", "", f"Generated: {graph['generated_at']} UTC", "", "## Nodes"]
for t in ["pack","extension","service","asset_pack","model","workflow"]:
    ns = sorted(by_type.get(t, []), key=lambda x: x["name"].lower())
    md.append(f"### {t} ({len(ns)})")
    if not ns:
        md.append("- (none)")
    else:
        for n in ns[:200]:
            md.append(f"- `{n['name']}`  \n  - id: `{n['id']}`")
    md.append("")
md.append("## Edges (sample)")
for e in graph["edges"][:200]:
    md.append(f"- `{e['rel']}`: `{e['from']}` -> `{e['to']}`")
(out_dir/"typed_graph.md").write_text("\n".join(md) + "\n", encoding="utf-8")
PY

log "Wrote $json_out, $md_out, $dot_out"
